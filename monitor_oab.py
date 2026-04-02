import os

print("=== TESTE DE VARIÁVEIS ===")

print("OAB_NUMERO:", os.getenv("OAB_NUMERO"))
print("OAB_UF:", os.getenv("OAB_UF"))
print("OAB_CPF:", os.getenv("OAB_CPF"))
print("OAB_IDENTIDADE:", os.getenv("OAB_IDENTIDADE"))

print("=== FIM TESTE ===")
