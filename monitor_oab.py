import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from db import get_conn


LOGIN_URL = os.getenv("OAB_LOGIN_URL", "https://recortedigital.oabmg.org.br/").strip()
OAB_NUMERO = os.getenv("OAB_NUMERO", "").strip()
OAB_UF = os.getenv("OAB_UF", "MG").strip()
OAB_CPF = re.sub(r"\D", "", os.getenv("OAB_CPF", ""))
OAB_IDENTIDADE = re.sub(r"\D", "", os.getenv("OAB_IDENTIDADE", ""))


def publicacao_existe(processo, texto):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id
        FROM publicacoes
        WHERE COALESCE(processo, '') = COALESCE(%s, '')
          AND texto = %s
        LIMIT 1;
        """,
        (processo, texto),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def inserir_publicacao(processo, data_publicacao, texto, relevante=False, motivo_filtro="", enviado_email=False):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO publicacoes (
            processo,
            data_publicacao,
            texto,
            relevante,
            motivo_filtro,
            enviado_email
        )
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (
            processo,
            data_publicacao,
            texto,
            relevante,
            motivo_filtro,
            enviado_email,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def analisar_relevancia(texto):
    texto_lower = (texto or "").lower()

    palavras_chave = [
        "intimação",
        "prazo",
        "manifestação",
        "sentença",
        "decisão",
        "audiência",
        "urgente",
        "cumprimento",
        "citação",
        "embargos",
        "apelação",
        "contestação",
        "liminar",
        "despacho",
    ]

    for palavra in palavras_chave:
        if palavra in texto_lower:
            return True, f"Contém a palavra-chave: {palavra}"

    return False, ""


def limpar_texto(texto):
    if not texto:
        return ""
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{2,}", "\n", texto)
    return texto.strip()


def extrair_data(texto):
    if not texto:
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    padroes = [
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto)
        if m:
            return m.group(0)

    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def extrair_processo(texto):
    if not texto:
        return ""

    padroes = [
        r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b",
        r"\b\d{20}\b",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto)
        if m:
            return m.group(0)

    return ""


def tentar_preencher_login(page):
    inputs = page.locator("input")
    total_inputs = inputs.count()

    if total_inputs < 3:
        raise RuntimeError("Não encontrei campos suficientes na tela de login.")

    try:
        inputs.nth(0).fill(OAB_NUMERO)
    except Exception:
        page.locator("input").first.fill(OAB_NUMERO)

    try:
        selects = page.locator("select")
        if selects.count() > 0:
            try:
                selects.nth(0).select_option(label=OAB_UF)
            except Exception:
                try:
                    selects.nth(0).select_option(value=OAB_UF)
                except Exception:
                    pass
    except Exception:
        pass

    try:
        inputs.nth(1).fill(OAB_CPF)
    except Exception:
        pass

    try:
        inputs.nth(2).fill(OAB_IDENTIDADE)
    except Exception:
        pass

    botao = page.get_by_role("button", name=re.compile(r"entrar", re.I))
    if botao.count() == 0:
        botao = page.locator("button, input[type='submit']").filter(has_text=re.compile(r"entrar", re.I))

    if botao.count() > 0:
        botao.first.click()
    else:
        raise RuntimeError("Não encontrei o botão Entrar.")


def extrair_blocos_da_pagina(page):
    seletores = [
        "table tbody tr",
        ".publicacao",
        ".resultado",
        ".resultado-item",
        ".item-resultado",
        ".card",
        ".list-group-item",
        ".panel",
        ".row",
    ]

    blocos = []

    for seletor in seletores:
        loc = page.locator(seletor)
        try:
            qtd = loc.count()
        except Exception:
            qtd = 0

        if qtd and qtd > 0:
            for i in range(qtd):
                try:
                    txt = limpar_texto(loc.nth(i).inner_text(timeout=2000))
                    if len(txt) >= 20:
                        blocos.append(txt)
                except Exception:
                    continue

        if len(blocos) >= 3:
            break

    if not blocos:
        corpo = limpar_texto(page.locator("body").inner_text(timeout=5000))
        partes = [p.strip() for p in re.split(r"\n{2,}", corpo) if p.strip()]
        for parte in partes:
            if len(parte) >= 30:
                blocos.append(parte)

    return blocos


def filtrar_blocos_relevantes(brutos):
    saida = []
    vistos = set()

    for txt in brutos:
        processo = extrair_processo(txt)
        data_publicacao = extrair_data(txt)

        if not processo and "intima" not in txt.lower() and "despacho" not in txt.lower() and "senten" not in txt.lower():
            continue

        chave = (processo, txt[:300])
        if chave in vistos:
            continue

        vistos.add(chave)
        saida.append(
            {
                "processo": processo,
                "data_publicacao": data_publicacao,
                "texto": txt,
            }
        )

    return saida


def capturar_publicacoes():
    if not OAB_NUMERO or not OAB_CPF or not OAB_IDENTIDADE:
        raise RuntimeError("Variáveis OAB_NUMERO, OAB_CPF e OAB_IDENTIDADE não configuradas.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            tentar_preencher_login(page)

            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeoutError:
                pass

            page.wait_for_timeout(3000)

            blocos = extrair_blocos_da_pagina(page)
            publicacoes = filtrar_blocos_relevantes(blocos)

            return publicacoes

        finally:
            browser.close()


def executar_monitor():
    print("Iniciando monitor real da OAB...")

    try:
        publicacoes = capturar_publicacoes()
    except Exception as e:
        print(f"Erro ao capturar publicações: {e}")
        return

    if not publicacoes:
        print("Nenhuma publicação encontrada.")
        return

    for item in publicacoes:
        processo = item["processo"]
        data_publicacao = item["data_publicacao"]
        texto = item["texto"]

        if publicacao_existe(processo, texto):
            print(f"Já existe: {processo or 'sem processo'}")
            continue

        relevante, motivo = analisar_relevancia(texto)

        inserir_publicacao(
            processo=processo,
            data_publicacao=data_publicacao,
            texto=texto,
            relevante=relevante,
            motivo_filtro=motivo,
            enviado_email=False,
        )

        print(f"Inserido: {processo or 'sem processo'} | relevante={relevante}")


if __name__ == "__main__":
    executar_monitor()
