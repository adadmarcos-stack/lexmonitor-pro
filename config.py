import os

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "10000"))
SECRET_KEY = os.getenv("SECRET_KEY", "troque-no-render")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

LOGIN_APP_EMAIL = os.getenv("LOGIN_APP_EMAIL", "adadjammal@gmail.com").strip().lower()
LOGIN_APP_PASSWORD = os.getenv("LOGIN_APP_PASSWORD", "").strip()

OAB_LOGIN_URL = os.getenv("OAB_LOGIN_URL", "https://recortedigital.oabmg.org.br/").strip()
OAB_NUMERO = os.getenv("OAB_NUMERO", "").strip()
OAB_UF = os.getenv("OAB_UF", "MG").strip()
OAB_CPF = os.getenv("OAB_CPF", "").strip()
OAB_IDENTIDADE = os.getenv("OAB_IDENTIDADE", "").strip()

JUSBRASIL_ENABLED = os.getenv("JUSBRASIL_ENABLED", "false").lower() == "true"
JUSBRASIL_LOGIN_URL = os.getenv("JUSBRASIL_LOGIN_URL", "https://www.jusbrasil.com.br/login?next_url=https%3A%2F%2Fwww.jusbrasil.com.br%2F").strip()
JUSBRASIL_PROCESSOS_URL = os.getenv("JUSBRASIL_PROCESSOS_URL", "https://www.jusbrasil.com.br/acompanhamentos/processos/").strip()
JUSBRASIL_EMAIL = os.getenv("JUSBRASIL_EMAIL", "").strip()
JUSBRASIL_PASSWORD = os.getenv("JUSBRASIL_PASSWORD", "").strip()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "adadjammal@gmail.com").strip() or SMTP_USER

GOOGLE_CALENDAR_ENABLED = os.getenv("GOOGLE_CALENDAR_ENABLED", "false").lower() == "true"
GOOGLE_CALENDAR_ACCESS_TOKEN = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN", "").strip()
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary").strip()

OPENAI_ENABLED = os.getenv("OPENAI_ENABLED", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
