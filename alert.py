import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ALERT_EMAIL_TO,
)

from db import (
    buscar_publicacoes_pendentes_alerta,
    marcar_email_enviado,
    marcar_evento_calendario,
)


def enviar_email_alerta(destinatario, assunto, corpo):
    if not SMTP_USER or not SMTP_PASSWORD or not destinatario:
        print("E-mail não configurado; alerta ignorado.")
        return False

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = destinatario
    msg["Subject"] = assunto

    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


def montar_corpo_email(item):
    processo = item.get("processo") or "Sem número"
    tribunal = item.get("tribunal") or "—"
    fonte = item.get("fonte") or "—"
    data_publicacao = item.get("data_publicacao") or "—"
    parte_autora = item.get("parte_autora") or "—"
    parte_re = item.get("parte_re") or "—"
    resumo_ia = item.get("resumo_ia") or item.get("texto") or "—"
    o_que_fazer = item.get("o_que_fazer") or "Analisar a publicação."
    prazo = item.get("prazo") or "Não identificado"
    urgencia = item.get("urgencia") or "baixa"

    return f"""🚨 Nova publicação processual

Processo: {processo}
Tribunal: {tribunal}
Fonte: {fonte}
Data: {data_publicacao}

Parte autora: {parte_autora}
Parte ré: {parte_re}

Resumo:
{resumo_ia}

O que fazer:
{o_que_fazer}

Prazo:
{prazo}

Urgência:
{urgencia.upper()}
"""


def process_alerts():
    pendentes = buscar_publicacoes_pendentes_alerta()

    if not pendentes:
        print("Nenhuma publicação pendente.")
        return

    for item in pendentes:
        processo = item.get("processo") or "Sem número"
        urgencia = (item.get("urgencia") or "baixa").upper()

        assunto = f"[LexMonitor] {processo} | {urgencia}"

        corpo = montar_corpo_email(item)

        enviado = enviar_email_alerta(
            ALERT_EMAIL_TO,
            assunto,
            corpo
        )

        if enviado:
            marcar_email_enviado(item["id"])
            marcar_evento_calendario(item["id"])
            print(f"Enviado: {item['id']}")
        else:
            print(f"Erro envio: {item['id']}")
