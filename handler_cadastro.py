# handler_cadastro.py
import logging
import os
logger = logging.getLogger(__name__)
import re
from config import is_admin
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database import salvar_regulacao, registrar_consentimento_lgpd, supabase
from utils import (
    DISCLAIMER_TEXTO,
    TECLADO_MENU,
    TECLADO_CANCELAR,
    ETAPA_SUS,
    ETAPA_NOME,
    ETAPA_CELULAR,
    ETAPA_NASCIMENTO,
    ETAPA_REGULACAO,
    ETAPA_CBO,
    ETAPA_PROCEDIMENTO,
    ETAPA_LGPD,
    ETAPA_CONFIRMAR_REUSO,
    ETAPA_ESCOLHER_SUS,
    formatar_data,
    formatar_celular,
    formatar_maiusculo,
    verificar_se_e_menu_e_executar,
)


async def iniciar_cadastro_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o cadastro de uma nova regulação institucional."""
    user_id = update.effective_user.id
    LIMITE_MAX = 10

    # Verifica quantas regulações o usuário já cadastrou
    try:
        res = supabase.table("AlertaSUS_2.0").select("id", count="exact").eq("chat_id", user_id).execute()
        total_regs = res.count if hasattr(res, "count") and res.count is not None else len(res.data or [])
    except Exception as e:
        logger.error(f"Erro ao contar regulações: {e}")

        total_regs = 0

        if total_regs >= LIMITE_MAX and not is_admin(user_id):
            await update.message.reply_text(
                f"📌 <b>Limite de regulações atingido</b>\n\n"
                f"Você já cadastrou <b>{total_regs}/{LIMITE_MAX}</b> regulações — "
                "esse é o máximo permitido pelo sistema.\n\n"
                "💡 <b>Como cadastrar novas regulações?</b>\n"
                "Você pode <b>excluir</b> regulações antigas que já foram finalizadas "
                "e liberar espaço. Use o comando:\n\n"
                "<code>/excluir</code>\n\n"
                "Assim que excluir uma, poderá cadastrar novas normalmente. 😊",
                parse_mode="HTML",
            )
        return ConversationHandler.END

    # Continua o fluxo — verifica SUS ja cadastrados
    context.user_data.clear()
    context.user_data["_em_fluxo_admin"] = "cadastro"

    try:
        res_sus = (
            supabase.table("AlertaSUS_2.0")
            .select("numero_sus, nome_paciente, data_nascimento")
            .eq("chat_id", user_id)
            .order("id", desc=True)
            .execute()
        )
        registros = res_sus.data or []
    except Exception as e:
        logger.error(f"Erro ao buscar SUS: {e}")
        registros = []

    sus_unicos = {}
    for r in registros:
        num = r.get("numero_sus")
        if num and num not in sus_unicos:
            sus_unicos[num] = r
    sus_lista = list(sus_unicos.items())

    if not sus_lista:
        await update.message.reply_text(
            "📝 <b>Iniciando cadastro de nova regulação.</b>\n\n"
            f"Você tem <b>{total_regs}/{LIMITE_MAX}</b> regulações cadastradas.\n\n"
            "Por favor, digite o <b>número do Cartão SUS</b> do paciente (15 dígitos):",
            parse_mode="HTML",
            reply_markup=TECLADO_CANCELAR,
        )
        return ETAPA_SUS

    if len(sus_lista) == 1:
        num, dados = sus_lista[0]
        nome = dados.get("nome_paciente") or "—"
        teclado = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Usar mesmo Cartão do SUS", callback_data=f"usar_sus_{num}")],
                [InlineKeyboardButton("🔄 Cadastrar novo SUS", callback_data="novo_sus")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="iniciar")],
            ]
        )
        await update.message.reply_text(
            "📝 <b>Iniciando cadastro de nova regulação.</b>\n\n"
            f"Você tem <b>{total_regs}/{LIMITE_MAX}</b> regulações cadastradas.\n\n"
            f"💳 Detectei um Cartão do SUS cadastrado:\n"
            f"<code>{num}</code> · {nome}\n\n"
            "Deseja usar o mesmo número de Cartão do SUS?",
            parse_mode="HTML",
            reply_markup=teclado,
        )
    else:
        botoes = []
        for num, dados in sus_lista:
            nome = (dados.get("nome_paciente") or "—")[:22]
            botoes.append([InlineKeyboardButton(f"💳 {num} · {nome}", callback_data=f"usar_sus_{num}")])
        botoes.append([InlineKeyboardButton("➕ Cadastrar novo SUS", callback_data="novo_sus")])
        botoes.append([InlineKeyboardButton("❌ Cancelar", callback_data="iniciar")])
        await update.message.reply_text(
            "📝 <b>Iniciando cadastro de nova regulação.</b>\n\n"
            f"Você tem <b>{total_regs}/{LIMITE_MAX}</b> regulações cadastradas.\n\n"
            "💳 <b>Selecione qual Cartão do SUS deseja usar:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(botoes),
        )

    return ETAPA_ESCOLHER_SUS

from bot_seguranca import safe_callback

@safe_callback
async def callback_escolher_sus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a escolha do SUS no início do cadastro."""
    query = update.callback_query
    data = query.data

    if data == "cancelar":
        await query.edit_message_text("❌ Cadastro cancelado.")
        context.user_data.clear()
        return ConversationHandler.END

    if data == "novo_sus":
        for k in ("sus", "nome", "nascimento"):
            context.user_data.pop(k, None)
        await query.edit_message_text(
            "Ok! Digite o <b>número do Cartão SUS</b> do paciente (15 dígitos):",
            parse_mode="HTML",
        )
        return ETAPA_SUS

    if data.startswith("usar_sus_"):
        num_sus = data.replace("usar_sus_", "")
        try:
            # AQUI ESTAVA O ERRO: A linha do 'res' tinha sido apagada sem querer
            res = (
                supabase.table("AlertaSUS_2.0")
                .select("nome_paciente, data_nascimento")
                .eq("chat_id", update.effective_user.id)
                .eq("numero_sus", num_sus)
                .order("id", desc=True)
                .limit(1)
                .execute()
            )
            dados = res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"Erro ao buscar dados do SUS: {e}")
            dados = {}

        context.user_data["sus"] = num_sus
        context.user_data["nome"] = dados.get("nome_paciente") or ""
        context.user_data["nascimento"] = dados.get("data_nascimento") or ""

        texto_id = (
            f"✅ <b>SUS carregado:</b> <code>{num_sus}</code>\n\n"
            f"👤 <b>Paciente:</b> {dados.get('nome_paciente') or '—'}\n"
            f"📅 <b>Nascimento:</b> {dados.get('data_nascimento') or '—'}\n\n"
            "🆔 <b>Agora digite o ID da Regulação (8 dígitos):</b>"
        )

        # Apaga a mensagem dos botões antiga
        try:
            await query.message.delete()
        except Exception:
            pass

        # Busca o caminho absoluto da imagem
        caminho_imagem = os.path.join(os.path.dirname(__file__), "modelo_comprovante.jpg")

                # Busca o caminho absoluto da imagem
        caminho_imagem = os.path.join(os.path.dirname(__file__), "comprovante_sus.jpg")

        # Envia a foto como nova mensagem
        try:
            with open(caminho_imagem, "rb") as foto:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=foto,
                    caption=texto_id,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Erro ao enviar imagem: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=texto_id + "\n\n(Imagem ilustrativa indisponível no momento)",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Erro ao enviar imagem: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=texto_id + "\n\n(Imagem ilustrativa indisponível no momento)",
                parse_mode="HTML"
            )

        return ETAPA_REGULACAO

    return ConversationHandler.END


async def receber_sus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await verificar_se_e_menu_e_executar(update, context):
        return ConversationHandler.END
    import re as _re

    chat_id = update.effective_chat.id
    texto_bruto = update.message.text.strip()

    # Normaliza: mantém só dígitos (remove espaços, pontos, traços)
    numero_sus = _re.sub(r"\D", "", texto_bruto)

    if not numero_sus:
        await update.message.reply_text(
            "⚠️ Não consegui identificar nenhum dígito.\n\n" "Digite o número do Cartão SUS (apenas números):"
        )
        return ETAPA_SUS

    context.user_data["sus"] = numero_sus

    try:
        resposta = supabase.table("AlertaSUS_2.0").select("*").eq("numero_sus", numero_sus).execute()
        registros = resposta.data

        if registros and len(registros) > 0:
            dados_antigos = registros[0]
            context.user_data["_dados_reuso_pendente"] = {
                "nome": dados_antigos.get("nome_paciente"),
                "celular": dados_antigos.get("celular"),
                "nascimento": dados_antigos.get("data_nascimento"),
                "cbo": dados_antigos.get("cbo"),
                "procedimento": dados_antigos.get("procedimento"),
            }

            nome = dados_antigos.get("nome_paciente") or "Não informado"
            celular = dados_antigos.get("celular") or "Não informado"
            nasc = dados_antigos.get("data_nascimento") or "Não informado"

            print("DEBUG: SUS encontrado! Aguardando confirmação.")

            teclado = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ Usar esses dados", callback_data="reuso_sim")],
                    [InlineKeyboardButton("🔄 Digitar do zero", callback_data="reuso_nao")],
                ]
            )

            await update.message.reply_text(
                f"🔍 <b>Cartão do SUS já cadastrado!</b>\n\n"
                f"Encontramos os seguintes dados:\n"
                f"👤 <b>Nome:</b> {nome}\n"
                f"📱 <b>Celular:</b> {celular}\n"
                f"📅 <b>Nascimento:</b> {nasc}\n\n"
                f"Deseja usar esses dados?",
                parse_mode="HTML",
                reply_markup=teclado,
            )
            return ETAPA_CONFIRMAR_REUSO

    except Exception as e:
        print(f"ERRO no bloco do SUS: {e}")

    print("DEBUG: SUS não encontrado. Indo para ETAPA_NOME.")
    await update.message.reply_text("Qual o nome completo do paciente?")
    return ETAPA_NOME


async def callback_reuso_dados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a escolha do usuário: reusar dados ou digitar do zero."""
    query = update.callback_query
    await query.answer()

    dados = context.user_data.get("_dados_reuso_pendente") or {}

    if query.data == "reuso_sim":
        context.user_data["nome"] = dados.get("nome")
        context.user_data["celular"] = dados.get("celular")
        context.user_data["nascimento"] = dados.get("nascimento")
        context.user_data["cbo"] = dados.get("cbo")
        context.user_data["procedimento"] = dados.get("procedimento")

        await query.edit_message_text(
            "✅ <b>Dados carregados com sucesso!</b>\n\n" "Agora digite apenas o <b>Número da Regulação</b>:",
            parse_mode="HTML",
        )
        return ETAPA_REGULACAO

    else:
        for campo in ("nome", "celular", "nascimento", "cbo", "procedimento"):
            context.user_data[campo] = None
        context.user_data.pop("_dados_reuso_pendente", None)

        await query.edit_message_text(
            "Ok! Vamos começar do zero.\n\n👤 Qual o <b>nome completo do paciente</b>?",
            parse_mode="HTML",
        )
        return ETAPA_NOME


async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await verificar_se_e_menu_e_executar(update, context):
        return ConversationHandler.END
    nome = update.message.text.strip()
    nome = nome.replace("<", "").replace(">", "").replace("&", "&amp;")[:80]
    context.user_data["nome"] = nome
    await update.message.reply_text("Digite o número de <b>celular/WhatsApp</b> (com DDD):", parse_mode="HTML")
    return ETAPA_CELULAR


async def receber_celular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await verificar_se_e_menu_e_executar(update, context):
        return ConversationHandler.END
    celular = formatar_celular(update.message.text.strip())
    context.user_data["celular"] = celular
    await update.message.reply_text(
        "Digite a <b>data de nascimento</b> do paciente (DD/MM/AAAA):",
        parse_mode="HTML",
    )
    return ETAPA_NASCIMENTO


async def receber_nascimento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await verificar_se_e_menu_e_executar(update, context):
        return ConversationHandler.END
    nascimento = formatar_data(update.message.text.strip())
    context.user_data["nascimento"] = nascimento

    texto_id = (
        "✅ <b>Data de nascimento registrada.</b>\n\n"
        "⚠️ <b>PRÓXIMO PASSO: ID da Regulação</b>\n\n"
        "Antes de digitar, tenha em mãos o seu <b>comprovante de agendamento</b> e confira:\n"
        "✅ O ID correto no papel\n"
        "✅ Se os <b>8 dígitos</b> conferem\n\n"
        "🆔 <b>Digite o ID da Regulação:</b>"
    )

    # Envia a foto do comprovante
    try:
        with open("modelo_comprovante.jpg", "rb") as foto:
            await update.message.reply_photo(photo=foto, caption=texto_id, parse_mode="HTML")
    except FileNotFoundError:
        await update.message.reply_text(texto_id, parse_mode="HTML")

    return ETAPA_REGULACAO


async def receber_regulacao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await verificar_se_e_menu_e_executar(update, context):
        return ConversationHandler.END
    num_reg = re.sub(r"\D", "", update.message.text)

    if not num_reg:
        await update.message.reply_text("⚠️ Digite um número de regulação válido (apenas dígitos):")
        return ETAPA_REGULACAO

    # ✅ Validação: ID da regulação tem 8 dígitos
    if len(num_reg) != 8:
        await update.message.reply_text(
            f"⚠️ <b>O ID da regulação deve ter 8 dígitos.</b>\n\n"
            f"Você digitou <b>{len(num_reg)}</b> dígito(s).\n\n"
            "📌 <i>Confira no comprovante de agendamento ou na "
            "unidade básica de saúde.</i>\n\n"
            "Digite novamente:",
            parse_mode="HTML",
        )
        return ETAPA_REGULACAO

    # ✅ Verifica duplicata na conta do usuário
    try:
        chat_id = str(update.effective_user.id)
        res_dup = (
            supabase.table("AlertaSUS_2.0")
            .select("id")
            .eq("numero_reg", num_reg)
            .eq("chat_id", int(chat_id) if chat_id.isdigit() else chat_id)
            .execute()
        )

        if res_dup.data:
            await update.message.reply_text(
                f"⚠️ <b>Você já cadastrou a regulação {num_reg}!</b>\n\n"
                "• Para ver o status: use /verificar_especifico\n"
                "• Para corrigir dados: use /corrigir\n\n"
                "O cadastro foi cancelado.",
                parse_mode="HTML",
            )
            context.user_data.clear()
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Erro ao verificar duplicata no cadastro: {e}")

    # ✅ Salva o número da regulação
    context.user_data["numero_regulacao"] = num_reg

    # ✅ FORA DO TRY/EXCEPT — sempre pede a especialidade no fluxo normal
    await update.message.reply_text(
        "Agora informe a <b>Especialidade</b> da consulta/exame\n"
        "<i>(ex: ULTRASSONOGRAFIA, CARDIOLOGIA, OFTALMOLOGIA)</i>\n\n"
        "Se não souber, digite <code>0</code> para pular.",
        parse_mode="HTML",
    )
    return ETAPA_CBO


async def receber_cbo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await verificar_se_e_menu_e_executar(update, context):
        return ConversationHandler.END

    valor = update.message.text.strip()

    if valor == "0":
        context.user_data["cbo"] = ""
        await update.message.reply_text(
            "⏭️ <b>Especialidade pulada.</b>\n\n"
            "Agora informe a <b>descrição do Procedimento/Exame / Consulta</b>:\n"
            "<i>(ex: ULTRASSONOGRAFIA, CONSULTA CARDIOLOGIA)</i>",
            parse_mode="HTML",
        )
        return ETAPA_PROCEDIMENTO

    cbo = update.message.text.strip()
    cbo = cbo.replace("<", "").replace(">", "").replace("&", "&amp;")[:80]
    cbo = cbo.replace("<", "").replace(">", "").replace("&", "&amp;")[:80]
    context.user_data["cbo"] = formatar_maiusculo(cbo) if cbo != "0" else ""

    await update.message.reply_text(
        f"✅ <b>Especialidade registrada:</b> {formatar_maiusculo(valor)}\n\n"
        "Agora informe a <b>descrição do Procedimento/Exame / Consulta</b>:\n"
        "<i>(ex: EXAME, CONSULTA)</i>",
        parse_mode="HTML",
    )
    return ETAPA_PROCEDIMENTO


async def receber_procedimento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await verificar_se_e_menu_e_executar(update, context):
        return ConversationHandler.END
    proc = update.message.text.strip()
    proc = proc.replace("<", "").replace(">", "").replace("&", "&amp;")[:80]
    context.user_data["procedimento"] = formatar_maiusculo(proc)

    teclado_lgpd = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Aceitar e Finalizar", callback_data="aceitar_lgpd")],
            [InlineKeyboardButton("❌ Cancelar Cadastro", callback_data="cancelar_cadastro")],
        ]
    )

    await update.message.reply_text(
        "🛡️ <b>TERMO DE CONSENTIMENTO LGPD</b>\n\n"
        "Para prosseguir com o monitoramento automático, autorizo o armazenamento dos dados fornecidos exclusivamente para finalidades de consulta pública no sistema FMS Piauí.\n\n"
        f"{DISCLAIMER_TEXTO}\n\nVocê aceita o termo?",
        parse_mode="HTML",
        reply_markup=teclado_lgpd,
    )
    return ETAPA_LGPD


async def finalizar_cadastro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    dados = context.user_data

    if query.data == "cancelar_cadastro":
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Cadastro cancelado pelo usuário.",
            reply_markup=TECLADO_MENU,
        )
        context.user_data.clear()
        context.user_data.pop("_em_fluxo_admin", None)
        return ConversationHandler.END

    dados_salvar = {
        "chat_id": user_id,
        "numero_sus": dados.get("sus"),
        "nome_paciente": dados.get("nome"),
        "celular": dados.get("celular"),
        "data_nascimento": dados.get("nascimento"),
        "numero_reg": dados.get("numero_regulacao"),
        "cbo": dados.get("cbo"),
        "procedimento": dados.get("procedimento"),
    }

    # 🛡️ Prevenção de duplicata: mesmo chat_id + numero_reg
    numero_reg_novo = dados_salvar.get("numero_reg")
    if numero_reg_novo:
        try:
            checagem = (
                supabase.table("AlertaSUS_2.0")
                .select("id")
                .eq("chat_id", user_id)
                .eq("numero_reg", numero_reg_novo)
                .execute()
            )
            if checagem.data:
                # Apaga a mensagem do termo LGPD pra não deixar botão travado
                try:
                    await query.message.delete()
                except Exception:
                    try:
                        await query.edit_message_reply_markup(reply_markup=None)
                    except Exception:
                        pass

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"⚠️ <b>Você já tem a regulação <code>{numero_reg_novo}</code> cadastrada.</b>\n\n"
                        "Não é possível cadastrar a mesma regulação duas vezes.\n\n"
                        "💡 Se precisar alterar algo, use /corrigir.\n"
                        "💡 Se quiser remover, use /excluir."
                    ),
                    parse_mode="HTML",
                    reply_markup=TECLADO_MENU,
                )
                context.user_data.clear()
                context.user_data.pop("_em_fluxo_admin", None)
                return ConversationHandler.END
        except Exception as e:
            print(f"DEBUG duplicata: erro na checagem ({e}) — seguindo com insert")

    print("DEBUG 1: Salvando no Supabase...")
    sucesso = await salvar_regulacao(dados_salvar)
    print(f"DEBUG 2: salvar_regulacao = {sucesso}")

    try:
        registrar_consentimento_lgpd(user_id)
        print("DEBUG 3: LGPD registrado com sucesso.")
    except Exception as e:
        print(f"DEBUG 3 AVISO LGPD: {e}")

    # 1. Apaga a mensagem do Termo LGPD para sumir com os botões travados
    print("DEBUG 4: Apagando mensagem com os botões...")
    try:
        await query.message.delete()
        print("DEBUG 5: Mensagem do termo apagada com sucesso.")
    except Exception as e:
        print(f"DEBUG 5 ERRO ao apagar mensagem: {e}")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    # 2. Envia a mensagem de confirmação no chat
    print("DEBUG 6: Enviando mensagem de sucesso no chat...")
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ <b>Regulação cadastrada com sucesso!</b>\nEla será monitorada automaticamente pelo sistema.",
        parse_mode="HTML",
    )

    # 3. Envia o Menu Principal
    print("DEBUG 7: Enviando menu principal...")
    await context.bot.send_message(chat_id=chat_id, text="O que deseja fazer agora?", reply_markup=TECLADO_MENU)

    # 4. Marketing: oferta pós-1ª regulação
    try:
        from handler import enviar_oferta_primeira_regulacao

        await enviar_oferta_primeira_regulacao(update, context, str(user_id))
    except Exception as e:
        print(f"DEBUG MARKETING: {e}")

    context.user_data.clear()
    print("DEBUG 8: Fluxo finalizado com sucesso!")
    return ConversationHandler.END
