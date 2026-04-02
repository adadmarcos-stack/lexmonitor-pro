from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re


def consultar_publicacoes():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1400, "height": 2200},
                locale="pt-BR"
            )
            page = context.new_page()

            print("Acessando login...")

            page.goto(
                "https://recortedigital.oabmg.org.br/",
                timeout=120000,
                wait_until="domcontentloaded"
            )

            page.wait_for_timeout(4000)
            page.wait_for_selector("#txbOAB", timeout=30000)
            page.wait_for_selector("#txbCPF", timeout=30000)
            page.wait_for_selector("#txbCI", timeout=30000)
            page.wait_for_selector("#btnEntrar", timeout=30000)

            print("Preenchendo dados...")

            page.fill("#txbOAB", "113674")
            page.fill("#txbCPF", "06819623640")
            page.fill("#txbCI", "12989116")

            try:
                page.select_option("#ddlSiglaUF", "MG")
            except Exception:
                pass

            page.wait_for_timeout(1500)

            print("Clicando entrar...")

            clicou = False

            try:
                page.locator("#btnEntrar").first.click(timeout=15000, force=True)
                clicou = True
            except Exception:
                pass

            if not clicou:
                try:
                    page.locator("input[type='submit']").first.click(timeout=15000, force=True)
                    clicou = True
                except Exception:
                    pass

            if not clicou:
                return {
                    "ok": False,
                    "erro": "Não foi possível clicar no botão Entrar."
                }

            # espera a navegação estabilizar sem usar evaluate
            page.wait_for_timeout(7000)

            print("Indo para histórico...")

            page.goto(
                "https://recortedigital.oabmg.org.br/historico/historicodata.aspx",
                timeout=120000,
                wait_until="domcontentloaded"
            )

            page.wait_for_timeout(6000)

            print("Clicando consultar...")

            clicou_consultar = False

            try:
                page.locator("text=Consultar").first.click(timeout=15000, force=True)
                clicou_consultar = True
            except Exception:
                pass

            if not clicou_consultar:
                try:
                    page.locator("button").filter(has_text="Consultar").first.click(timeout=15000, force=True)
                    clicou_consultar = True
                except Exception:
                    pass

            if not clicou_consultar:
                return {
                    "ok": False,
                    "erro": "Não foi possível clicar em Consultar."
                }

            page.wait_for_timeout(6000)

            print("Clicando visualizar tudo...")

            try:
                if page.locator("text=Visualizar tudo").count() > 0:
                    page.locator("text=Visualizar tudo").first.click(timeout=15000, force=True)
                    page.wait_for_timeout(8000)
            except Exception:
                pass

            try:
                if page.locator("text=Todas").count() > 0:
                    page.locator("text=Todas").first.click(timeout=10000, force=True)
                    page.wait_for_timeout(8000)
            except Exception:
                pass

            print("Forçando carregamento...")

            try:
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(3000)
            except Exception:
                pass

            print("Capturando dados...")

            texto = page.locator("body").inner_text(timeout=30000)
            html = page.content()
            url_final = page.url
            titulo = page.title()

            processos = re.findall(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", texto)
            processos = list(dict.fromkeys(processos))

            datas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", texto)
            datas = list(dict.fromkeys(datas))

            print("Finalizado com sucesso")

            browser.close()

            return {
                "ok": True,
                "titulo": titulo,
                "url_final": url_final,
                "processos_encontrados": processos[:100],
                "datas_encontradas": datas[:100],
                "preview_texto": texto[:12000],
                "preview_html": html[:12000],
            }

    except PlaywrightTimeoutError as e:
        return {
            "ok": False,
            "erro": f"Timeout na automação: {str(e)}"
        }
    except Exception as e:
        return {
            "ok": False,
            "erro": str(e)
        }