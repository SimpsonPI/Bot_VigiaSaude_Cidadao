# limpar_vencimentos.py
import io
import re

with io.open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

original_len = len(content)
removidos = []

# 1. Remover a função verificar_vencimentos inteira
padrao_funcao = r"async def verificar_vencimentos\(app\):.*?(?=async def post_init)"
if re.search(padrao_funcao, content, flags=re.DOTALL):
    content = re.sub(padrao_funcao, "", content, flags=re.DOTALL)
    removidos.append("função verificar_vencimentos")

# 2. Remover o job de verificar_vencimentos no post_init
padrao_job_venc = r"\n *\# Vencimentos de assinatura \(6h\).*?\)\n"
if re.search(padrao_job_venc, content, flags=re.DOTALL):
    content = re.sub(padrao_job_venc, "\n", content, flags=re.DOTALL)
    removidos.append("job verificar_vencimentos")

# 3. Remover o job de limpar_pagamentos_pendentes
padrao_job_limpeza = r"\n *\# Limpeza de pagamentos pendentes \(6h\).*?\)\n"
if re.search(padrao_job_limpeza, content, flags=re.DOTALL):
    content = re.sub(padrao_job_limpeza, "\n", content, flags=re.DOTALL)
    removidos.append("job limpar_pagamentos_pendentes")

# 4. Remover o import de limpar_pagamentos_pendentes
if "from handler_tarefas import limpar_pagamentos_pendentes\n" in content:
    content = content.replace("from handler_tarefas import limpar_pagamentos_pendentes\n", "")
    removidos.append("import limpar_pagamentos_pendentes")

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