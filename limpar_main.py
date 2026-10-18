# limpar_main.py
import io
import re

with io.open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

original_len = len(content)
removidos = []

# 1. Remover import do handler_pagamento
if "from handler_pagamento import gerar_pagamento_pix" in content:
    content = content.replace("from handler_pagamento import gerar_pagamento_pix\n", "")
    removidos.append("import handler_pagamento")

# 2. Remover bloco de import do pagamento_polling
padrao_pag_polling = r"from pagamento_polling import \([^)]*\)\n"
if re.search(padrao_pag_polling, content, flags=re.DOTALL):
    content = re.sub(padrao_pag_polling, "", content, flags=re.DOTALL)
    removidos.append("import pagamento_polling")

# 3. Remover set_telegram_bot(app.bot)
if "    set_telegram_bot(app.bot)\n" in content:
    content = content.replace("    set_telegram_bot(app.bot)\n", "")
    removidos.append("set_telegram_bot(app.bot)")

# 4. Remover job de polling MP
padrao_polling_job = r"\n *\# Polling do Mercado Pago.*?\n *\)\n"
if re.search(padrao_polling_job, content, flags=re.DOTALL):
    content = re.sub(padrao_polling_job, "\n", content, flags=re.DOTALL)
    removidos.append("job polling MP")

# 5. Remover handler de gerar_pagamento_pix
padrao_handler_pix = r"app\.add_handler\(CallbackQueryHandler\(gerar_pagamento_pix.*?\n *\)\)\n"
if re.search(padrao_handler_pix, content, flags=re.DOTALL):
    content = re.sub(padrao_handler_pix, "", content, flags=re.DOTALL)
    removidos.append("handler gerar_pagamento_pix")

with io.open("main.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Tamanho antes: {original_len} bytes")
print(f"Tamanho depois: {len(content)} bytes")
print(f"Diferença: {original_len - len(content)} bytes")
print()
print("Removidos:")
for item in removidos:
    print(f"  ✅ {item}")
if not removidos:
    print("  (nada encontrado — verificar manualmente)")
