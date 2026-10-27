from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes


async def comando_privacidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # COLE O SEU LINK LIMPO DO TELEGRAPH AQUI:
    link_telegraph = "https://telegra.ph/DECLARA%C3%87%C3%83O-DE-INDEPEND%C3%8ANCIA-08-13"

    texto = f"Acesse o nosso Termo de Uso e Política de Privacidade no link abaixo:\n\n{link_telegraph}"

    teclado = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💬 Dúvidas / Suporte (FAQ)", callback_data="abrir_faq_suporte")],
        ]
    )

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=texto, reply_markup=teclado, disable_web_page_preview=False
            )
        except Exception:
            pass
    else:
        await update.message.reply_text(text=texto, reply_markup=teclado, disable_web_page_preview=False)
