from telegram import Update
from telegram.ext import ContextTypes
from database import supabase
from utils import TECLADO_MENU


async def comando_meus_cadastros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id

    try:
        # Adicionamos 'cbo' e 'procedimento' na busca do banco de dados
        res = (
            supabase.table("VigiaSaude_cidadao")
            .select("numero_reg, nome_paciente, cbo, procedimento")
            .eq("chat_id", chat_id)
            .execute()
        )

        registros = res.data

        if not registros:
            await update.message.reply_text(
                "Você não possui nenhuma regulação cadastrada no momento.\nUse /cadastrar_nova para adicionar.",
                reply_markup=TECLADO_MENU,
            )
            return

        msg = "<b>📋 Suas Regulações Cadastradas:</b>\n\n"
        for i, r in enumerate(registros, 1):
            # Pega os dados, e se estiver vazio, coloca 'Não informado'
            especialidade = r.get("cbo") or "Não informada"
            procedimento = r.get("procedimento") or "Não informado"

            msg += f"{i}. ID: <code>{r.get('numero_reg')}</code>\n"
            msg += f"👤 Paciente: {r.get('nome_paciente')}\n"
            msg += f"🩺 Especialidade: {especialidade}\n"
            msg += f"📋 Procedimento: {procedimento}\n\n"

        msg += "<i>Para atualizar o status, use o botão '🔄 Verificar Todas'.</i>"

        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=TECLADO_MENU)

    except Exception as e:
        await update.message.reply_text("❌ Erro ao buscar seus cadastros.", reply_markup=TECLADO_MENU)
