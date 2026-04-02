import hashlib
import json
import smtplib
import tempfile
import urllib.parse
import urllib.request
import re
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO,
    GOOGLE_CALENDAR_ENABLED, GOOGLE_CALENDAR_ACCESS_TOKEN, GOOGLE_CALENDAR_ID,
)
from db import buscar_publicacoes_pendentes_alerta, marcar_email_enviado, marcar_evento_calendario

def detect_deadline_date(text):
    m = re.search(r"prazo de\s+(\d{1,2})\s+dias?", (text or "").lower())
    if m:
        due = datetime.now() + timedelta(days=int(m.group(1)))
        return due.replace(hour=9, minute=0, second=0, microsecond=0)
    return None

def create_ics_file(title, description, when_dt):
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dtstart = when_dt.strftime("%Y%m%dT%H%M%S")
    dtend = (when_dt + timedelta(minutes=30)).strftime("%Y%m%dT%H%M%S")
    content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//LexMonitor//PT-BR//EN
BEGIN:VEVENT
UID:{hashlib.md5((title + dtstart).encode()).hexdigest()}@lexmonitor
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{title}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR
"""
    temp = Path(tempfile.gettempdir()) / f"lexmonitor_{hashlib.md5(title.encode()).hexdigest()}.ics"
    temp.write_text(content, encoding="utf-8")
    return temp

def try_create_google_calendar_event(title, description, when_dt):
    if not GOOGLE_CALENDAR_ENABLED or not GOOGLE_CALENDAR_ACCESS_TOKEN:
        return False
    payload = {
        "summary": title,
        "description": description,
        "start": {"dateTime": when_dt.isoformat()},
        "end": {"dateTime": (when_dt + timedelta(minutes=30)).isoformat()},
    }
    req = urllib.request.Request(
        f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(GOOGLE_CALENDAR_ID)}/events",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {GOOGLE_CALENDAR_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        return True
    except Exception as e:
        print(f"Google Calendar não criou evento: {e}")
        return False

def send_email_alert(subject, body, ics_path=None):
    if not SMTP_USER or not SMTP_PASSWORD or not ALERT_EMAIL_TO:
        print("E-mail não configurado; alerta ignorado.")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL_TO
    msg.set_content(body)
    if ics_path and Path(ics_path).exists():
        msg.add_attachment(Path(ics_path).read_bytes(), maintype="text", subtype="calendar", filename=Path(ics_path).name)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    return True

def process_alerts():
    pendentes = buscar_publicacoes_pendentes_alerta()
    for item in pendentes:
        title = f"[LexMonitor] Nova publicação relevante - {item['processo'] or 'sem processo'}"
        body = (
            f"Fonte: {item['fonte']}\n"
            f"Processo: {item['processo']}\n"
            f"Data: {item['data_publicacao']}\n"
            f"Motivo: {item['motivo_filtro']}\n\n"
            f"Texto:\n{item['texto'][:5000]}"
        )
        ics_path = None
        due = detect_deadline_date(item["texto"])
        if due:
            ics_path = create_ics_file(
                title=f"Prazo - {item['processo'] or 'publicação'}",
                description=item["texto"][:2000],
                when_dt=due,
            )
            try_create_google_calendar_event(
                title=f"Prazo - {item['processo'] or 'publicação'}",
                description=item["texto"][:2000],
                when_dt=due,
            )
            marcar_evento_calendario(item["id"])
        if send_email_alert(title, body, ics_path):
            marcar_email_enviado(item["id"])
