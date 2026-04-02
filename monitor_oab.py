import os
import time
import subprocess
from playwright.sync_api import sync_playwright

def instalar_playwright():
    print("== Instalando Chromium do Playwright ==")

    # Instala browsers + dependências necessárias
    subprocess.run("python -m playwright install chromium", shell=True, check=True)
    subprocess.run("python -m playwright install-deps", shell=True)

def executar_monitor():
    print("== Iniciando monitor da OAB ==")

    numero = os.getenv("OAB_NUMERO")
    uf = os.getenv("OAB_UF")
    cpf = os.getenv("OAB_CPF")
    identidade = os.getenv("OAB_IDENTIDADE")

    print("== TESTE DE VARIÁVEIS ==")
    print(f"OAB_NUMERO: {numero}")
    print(f"OAB_UF: {uf}")
    print(f"OAB_CPF: {cpf}")
    print(f"OAB_IDENTIDADE: {identidade}")
    print("== FIM TESTE ==")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = browser.new_page()

        print("== Acessando site da OAB ==")
        page.goto("https://recortedigital.oabmg.org.br/")

        time.sleep(10)

        print("== Finalizado acesso ==")

        browser.close()


if __name__ == "__main__":
    instalar_playwright()
    executar_monitor()
