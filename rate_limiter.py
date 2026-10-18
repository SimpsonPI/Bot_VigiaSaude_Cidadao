import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

# Dicionário em memória para rastrear as requisições: {user_id: [timestamps]}
_controle_acessos = defaultdict(list)


def rate_limit(max_mensagens: int = 5, janela_segundos: int = 60):
    """
    Decorator de Rate Limiting (Antispam).
    Limita o usuário a um número máximo de interações por janela de tempo.
    """

    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user:
                return await func(update, context, *args, **kwargs)

            user_id = update.effective_user.id
            agora = time.time()

            # Filtra apenas os timestamps dentro da janela de tempo atual (últimos 60 segundos)
            timestamps = _controle_acessos[user_id]
            _controle_acessos[user_id] = [t for t in timestamps if agora - t < janela_segundos]

            # Verifica se o usuário excedeu o limite
            if len(_controle_acessos[user_id]) >= max_mensagens:
                if update.message:
                    await update.message.reply_text(
                        "⚠️ Você está enviando mensagens muito rápido. Aguarde alguns instantes."
                    )
                return

            # Registra o acesso atual e prossegue com a função original
            _controle_acessos[user_id].append(agora)
            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator

    # ═══════════════════════════════════════════════


# CAMADA 2 — ANTI-RAJADA (janela curta por usuário)
# ═══════════════════════════════════════════════
from collections import defaultdict, deque
import time as _time

# {chat_id: deque([(timestamp, tipo), ...])}
_JANELA_CURTA = defaultdict(deque)

# Limites por tipo dentro da janela curta
LIMITES_JANELA_CURTA = {
    "todas": {"max": 2, "janela_seg": 60},
    "especifico": {"max": 3, "janela_seg": 60},
}
# Limite geral (todos os tipos somados) por usuário
LIMITE_JANELA_GERAL = {"max": 5, "janela_seg": 60}


def _limpar_janela(dq: deque, agora: float, janela_seg: int):
    while dq and agora - dq[0][0] > janela_seg:
        dq.popleft()


def pode_verificar_janela_curta(chat_id: str, tipo: str) -> tuple[bool, str]:
    """
    Camada 2 — verifica se o usuário respeitou os limites de janela curta.
    Retorna (pode, motivo). motivo="" se pode; "intervalo:N" se bloqueado.
    """
    if _eh_admin(chat_id):
        return (True, "")

    agora = _time.time()
    dq = _JANELA_CURTA[chat_id]

    # 1) limite geral (todos os tipos somados)
    _limpar_janela(dq, agora, LIMITE_JANELA_GERAL["janela_seg"])
    if len(dq) >= LIMITE_JANELA_GERAL["max"]:
        espera = int(LIMITE_JANELA_GERAL["janela_seg"] - (agora - dq[0][0])) + 1
        return (False, f"intervalo:{espera}")

    # 2) limite por tipo
    cfg = LIMITES_JANELA_CURTA.get(tipo)
    if cfg:
        recentes = [t for t, tp in dq if tp == tipo and agora - t <= cfg["janela_seg"]]
        if len(recentes) >= cfg["max"]:
            espera = int(cfg["janela_seg"] - (agora - recentes[0])) + 1
            return (False, f"intervalo:{espera}")

    return (True, "")

    # ═══════════════════════════════════════════════


# CAMADA 3 — SEMÁFORO GLOBAL + RATE LIMIT GLOBAL
# ═══════════════════════════════════════════════
import asyncio
import logging
from collections import deque

logger = logging.getLogger(__name__)

# Máximo de consultas SIMULTÂNEAS ao portal FMS (todo o bot)
MAX_CONSULTAS_PARALELAS = 3

# Máximo de consultas por minuto (todos os usuários somados)
LIMITE_GLOBAL_MAX = 30
LIMITE_GLOBAL_JANELA_SEG = 60

_semaforo_fms = asyncio.Semaphore(MAX_CONSULTAS_PARALELAS)
_rate_global: deque = deque()  # timestamps das últimas consultas (globais)


async def _aguardar_rate_global():
    """Bloqueia até haver vaga no rate global."""
    agora = time.time()
    while _rate_global and agora - _rate_global[0] > LIMITE_GLOBAL_JANELA_SEG:
        _rate_global.popleft()

    if len(_rate_global) >= LIMITE_GLOBAL_MAX:
        espera = LIMITE_GLOBAL_JANELA_SEG - (agora - _rate_global[0]) + 1
        logger.warning(f"⏳ Rate global FMS atingido. Aguardando {espera:.1f}s...")
        await asyncio.sleep(espera)
        agora = time.time()
        while _rate_global and agora - _rate_global[0] > LIMITE_GLOBAL_JANELA_SEG:
            _rate_global.popleft()

    _rate_global.append(time.time())


async def consultar_com_limite(num_reg: str) -> dict:
    """
    Wrapper que aplica os limites globais ao redor de consultar_status_fms.
    - Rate global (máx 30 consultas/min no bot inteiro)
    - Semáforo (máx 3 consultas em paralelo)
    """
    from scraper import consultar_status_fms  # import tardio evita circular

    await _aguardar_rate_global()
    async with _semaforo_fms:
        return await consultar_status_fms(num_reg)
