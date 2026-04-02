import re
from fastapi import APIRouter
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.publication import Publication
from app.services.alert import send_email_alert
from playwright.sync_api import sync_playwright

router = APIRouter(prefix="/integrations/oabmg", tags=["OAB-MG"])


def extract_field(text: str, start_label: str, end_label: str | None = None):
    try:
        start = text.index(start_label) + len(start_label)
        if end_label and end_label in text[start:]:
            end = text.index(end_label, start)
            return text[start:end].strip()
        return text[start:].strip()
    except ValueError:
        return None


def extract_process_number(text: str):
    match = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", text)
    return match.group(0) if match else None


@router.post("/test")
def test_oabmg():

    # 🔥 TESTE DIRETO DE EMAIL (INDEPENDENTE DA OAB)
    try:
        send_email_alert(
            "adadmarcos@gmail.com",
            "TESTE ALERTA LEXMONITOR",
            "Se este email chegou, o sistema de alerta está funcionando corretamente."
        )
    except Exception as e:
        return {"erro_email": str(e)}

    # 🔽 resto continua normal (não precisa mexer)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://recortedigital.oabmg.org.br", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        inputs = page.locator("input:visible")
        selects = page.locator("select:visible")

        if inputs.count() >= 3:
            inputs.nth(0).fill("113674")
            inputs.nth(1).fill("06819623640")
            inputs.nth(2).fill("12989116")

        if selects.count() >= 1:
            try:
                selects.nth(0).select_option(label="MG")
            except:
                pass

        page.wait_for_timeout(1500)

        try:
            page.get_by_text("Entrar", exact=False).click()
        except:
            page.locator("input[type='submit']").first.click()

        page.wait_for_timeout(5000)

        page.fill("#ctl00_ContentPlaceHolder1_txtSelDataInicio", "01/01/2024")
        page.fill("#ctl00_ContentPlaceHolder1_txtSelDataFim", "31/12/2026")
        page.click("#ctl00_ContentPlaceHolder1_btnConsultar")

        page.wait_for_timeout(8000)

        links = page.locator("a")

        for i in range(links.count()):
            try:
                texto = links.nth(i).inner_text().strip()
                if "/" in texto and len(texto) == 10:
                    links.nth(i).click(timeout=5000)
                    break
            except:
                pass

        page.wait_for_timeout(5000)

        texto_final = page.locator("body").inner_text()

        browser.close()

        return {
            "status": "email_testado",
            "preview": texto_final[:1000]
        }