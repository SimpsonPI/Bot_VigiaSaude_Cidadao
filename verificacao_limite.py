# verificacao_limite.py
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Limites diários
LIMITE_VERIFICAR_TODAS = 3
LIMITE_VERIFICAR_ESPECIFICO = 10

# Intervalo mínimo entre 2 consultas do mesmo usuário (segundos)
INTERVALO_MINIMO = 60

# Admin isento de limites
ADMIN_ID = 5242040324


def _hoje_brasilia() -> str:
    """Retorna a data de hoje no fuso de Brasília (UTC-3)."""
    agora_brasilia = datetime.now(timezone.utc) - timedelta(hours=3)
    return agora_brasilia.strftime("%Y-%m-%d")


def _eh_admin(chat_id: str) -> bool:
    try:
        return int(chat_id) == ADMIN_ID
    except (ValueError, TypeError):
        return False


def _nome_coluna(tipo: str) -> str:
    """
    Mapeia o tipo para o nome correto da coluna no banco.
    - "todas"      → "verificacoes_todas"
    - "especifico" → "verificacoes_especificas"  ← CORRIGIDO
    """
    if tipo == "todas":
        return "verificacoes_todas"
    if tipo == "especifico":
        return "verificacoes_especificas"
    raise ValueError(f"Tipo inválido: {tipo}")


def pode_verificar(chat_id: str, tipo: str) -> tuple[bool, str, int]:
    from database import supabase

    if _eh_admin(chat_id):
        return (True, "", 999)

    # Camada 2 — anti-rajada (só para usuários comuns)
    pode_jc, motivo_jc = pode_verificar_janela_curta(chat_id, tipo)
    if not pode_jc:
        return (False, motivo_jc, 0)

    hoje = _hoje_brasilia()

    # Camada 2 — anti-rajada em memória (antes de bater no banco)
    pode_jc, motivo_jc = pode_verificar_janela_curta(chat_id, tipo)
    if not pode_jc:
        return (False, motivo_jc, 0)

    hoje = _hoje_brasilia()

    limite = LIMITE_VERIFICAR_TODAS if tipo == "todas" else LIMITE_VERIFICAR_ESPECIFICO
    coluna = _nome_coluna(tipo)

    try:
        res = supabase.table("verificacoes_usuarios").select(
            f"{coluna}, ultima_verificacao"
        ).eq("chat_id", str(chat_id)).eq("data", hoje).execute()

        usadas = 0
        ultima = None

        if res.data:
            reg = res.data[0]
            usadas = reg.get(coluna, 0)
            ultima_str = reg.get("ultima_verificacao")
            if ultima_str:
                try:
                    ultima = datetime.fromisoformat(str(ultima_str).replace("Z", "+00:00"))
                except Exception:
                    ultima = None

        if ultima:
            agora = datetime.now(timezone.utc)
            diff = (agora - ultima).total_seconds()
            if diff < INTERVALO_MINIMO:
                espera = int(INTERVALO_MINIMO - diff)
                return (False, f"intervalo:{espera}", 0)

        restantes = max(0, limite - usadas)
        if restantes <= 0:
            return (False, "limite_diario", 0)

        return (True, "", restantes)

    except Exception as e:
        logger.error(f"Erro ao verificar limite: {e}")
        return (True, "", limite)


def registrar_verificacao(chat_id: str, tipo: str):
    """Incrementa o contador de verificações do usuário."""
    registrar_janela_curta(chat_id, tipo)
    from database import supabase
    # ... resto igual ...
    hoje = _hoje_brasilia()
    agora = datetime.now(timezone.utc).isoformat()

    coluna = _nome_coluna(tipo)   # ← CORRIGIDO

    try:
        res = supabase.table("verificacoes_usuarios").select(
            f"id, {coluna}"
        ).eq("chat_id", str(chat_id)).eq("data", hoje).execute()

        if res.data:
            atual = res.data[0].get(coluna, 0)
            supabase.table("verificacoes_usuarios").update({
                coluna: atual + 1,
                "ultima_verificacao": agora,
                "updated_at": agora,
            }).eq("id", res.data[0]["id"]).execute()
        else:
            dados = {
                "chat_id": str(chat_id),
                "data": hoje,
                "verificacoes_todas": 0,
                "verificacoes_especificas": 0,
                "ultima_verificacao": agora,
            }
            dados[coluna] = 1
            supabase.table("verificacoes_usuarios").insert(dados).execute()

    except Exception as e:
        logger.error(f"Erro ao registrar verificação: {e}")

def restantes_reais(chat_id: str, tipo: str) -> int:
    """
    Retorna quantas verificações ainda restam, IGNORANDO o intervalo.
    Use para CONTADORES (menus, avisos).
    """
    from database import supabase

    if _eh_admin(chat_id):
        return 999

    hoje = _hoje_brasilia()
    limite = LIMITE_VERIFICAR_TODAS if tipo == "todas" else LIMITE_VERIFICAR_ESPECIFICO
    coluna = _nome_coluna(tipo)

    try:
        res = supabase.table("verificacoes_usuarios").select(coluna).eq(
            "chat_id", str(chat_id)
        ).eq("data", hoje).execute()

        usadas = 0
        if res.data:
            usadas = res.data[0].get(coluna, 0)

        return max(0, limite - usadas)
    except Exception as e:
        logger.error(f"Erro ao contar restantes: {e}")
        return limite

# ═══════════════════════════════════════════════
# CAMADA 2 — ANTI-RAJADA (janela curta por usuário)
# ═══════════════════════════════════════════════
from collections import defaultdict, deque
import time as _time

_JANELA_CURTA = defaultdict(deque)

LIMITES_JANELA_CURTA = {
    "todas":      {"max": 2, "janela_seg": 60},
    "especifico": {"max": 3, "janela_seg": 60},
}
LIMITE_JANELA_GERAL = {"max": 5, "janela_seg": 60}


def _limpar_janela(dq: deque, agora: float, janela_seg: int):
    while dq and agora - dq[0][0] > janela_seg:
        dq.popleft()


def pode_verificar_janela_curta(chat_id: str, tipo: str) -> tuple[bool, str]:
    if _eh_admin(chat_id):
        return (True, "")

    agora = _time.time()
    dq = _JANELA_CURTA[chat_id]

    _limpar_janela(dq, agora, LIMITE_JANELA_GERAL["janela_seg"])
    if len(dq) >= LIMITE_JANELA_GERAL["max"]:
        espera = int(LIMITE_JANELA_GERAL["janela_seg"] - (agora - dq[0][0])) + 1
        return (False, f"intervalo:{espera}")

    cfg = LIMITES_JANELA_CURTA.get(tipo)
    if cfg:
        recentes = [t for t, tp in dq if tp == tipo and agora - t <= cfg["janela_seg"]]
        if len(recentes) >= cfg["max"]:
            espera = int(cfg["janela_seg"] - (agora - recentes[0])) + 1
            return (False, f"intervalo:{espera}")

    return (True, "")


def registrar_janela_curta(chat_id: str, tipo: str):
    if _eh_admin(chat_id):
        return
    _JANELA_CURTA[chat_id].append((_time.time(), tipo))