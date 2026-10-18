# handler_autorizacao.py
"""Comandos admin para gerenciar acesso do Cidadão."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS, ADMIN_CHAT_ID, is_admin
from autorizacao import autorizar, desautorizar, listar_autorizados

logger = logging.getLogger(__name__)


def _eh_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or user_id == ADMIN_CHAT_ID


async def comando_autorizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _eh_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Acesso negado.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Uso:</b> <code>/autorizar &lt;chat_id&gt; [nome]</code>",
            parse_mode="HTML",
        )
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ O chat_id precisa ser um número.")
        return

    nome = " ".join(context.args[1:]).strip() if len(context.args) > 1 else None

    if autorizar(chat_id, nome, update.effective_user.id):
        await update.message.reply_text(
            f"✅ <b>Autorizado!</b>\n\n"
            f"• ID: <code>{chat_id}</code>\n"
            f"• Nome: {nome or '—'}\n\n"
            f"<i>O usuário já pode usar o bot.</i>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text("❌ Erro ao autorizar. Verifique o log.")


async def comando_desautorizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _eh_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Acesso negado.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Uso:</b> <code>/desautorizar &lt;chat_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ O chat_id precisa ser um número.")
        return

    if desautorizar(chat_id):
        await update.message.reply_text(
            f"🚫 <b>Desautorizado:</b> <code>{chat_id}</code>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text("❌ Erro ao desautorizar.")


async def comando_listar_autorizados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _eh_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Acesso negado.")
        return

    lista = listar_autorizados()
    if not lista:
        await update.message.reply_text("ℹ️ Nenhum usuário autorizado.")
        return

    linhas = [f"👥 <b>Autorizados ({len(lista)})</b>\n"]
    for u in lista[:30]:
        nome = u.get("nome") or "—"
        linhas.append(f"• <code>{u['chat_id']}</code> · {nome}")

    if len(lista) > 30:
        linhas.append(f"\n<i>... e mais {len(lista) - 30}</i>")

    await update.message.reply_text("\n".join(linhas), parse_mode="HTML")
