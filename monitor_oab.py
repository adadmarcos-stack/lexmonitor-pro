import os
import asyncio
import subprocess
from playwright.async_api import async_playwright

# 🔥 FORÇA INSTALAÇÃO DO BROWSER EM TEMPO DE EXECUÇÃO
subprocess.run(["playwright", "install"], check=True)

OAB_NUMERO = os.getenv("OAB_NUMERO")
OAB_UF = os.getenv("OAB_UF")
OAB_CPF = os.getenv("OAB_CPF")
OAB_IDENTIDADE = os.getenv("OAB_IDENTIDADE")

async def buscar_publicacoes():
    print("🚀 Iniciando monitor da OAB...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌐 Acessando site...")
        await page.goto("https://recortedigital.oabmg.org.br")

        await page.wait_for_timeout(3000)

        print("🔐 Preenchendo dados...")
        await page.fill('input[name="numeroOAB"]', OAB_NUMERO)
        await page.fill('input[name="ufOAB"]', OAB_UF)
        await page.fill('input[name="cpf"]', OAB_CPF)
        await page.fill('input[name="identidade"]', OAB_IDENTIDADE)

        print("📡 Buscando publicações...")
        await page.click('button[type="submit"]')

        await page.wait_for_timeout(5000)

        content = await page.content()

        if "Nenhuma publicação encontrada" in content:
            print("⚠️ Nenhuma publicação encontrada.")
        else:
            print("✅ POSSÍVEL PUBLICAÇÃO ENCONTRADA!")
            print(content[:1000])

        await browser.close()

asyncio.run(buscar_publicacoes())
