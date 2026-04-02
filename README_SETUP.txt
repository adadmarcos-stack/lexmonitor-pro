PACOTE FINAL LEXMONITOR

SUBSTITUIR NO GITHUB:
- app.py
- monitor_oab.py
- db.py
- alert.py
- config.py
- requirements.txt
- build.sh
- Procfile
- templates/login.html
- templates/index.html

WEB SERVICE
Build:
pip install -r requirements.txt

Start:
gunicorn app:app

CRON JOB
Build:
pip install -r requirements.txt && python -m playwright install chromium

Command:
python monitor_oab.py

Schedule:
*/10 * * * *

VARIÁVEIS DO WEB SERVICE:
SECRET_KEY=crie_uma_chave
DATABASE_URL=...
LOGIN_APP_EMAIL=adadjammal@gmail.com
LOGIN_APP_PASSWORD=...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
ALERT_EMAIL_TO=...
OAB_LOGIN_URL=https://recortedigital.oabmg.org.br/
OAB_NUMERO=113674
OAB_UF=MG
OAB_CPF=06819623640
OAB_IDENTIDADE=12989116
JUSBRASIL_ENABLED=true
JUSBRASIL_LOGIN_URL=https://www.jusbrasil.com.br/login?next_url=https%3A%2F%2Fwww.jusbrasil.com.br%2F
JUSBRASIL_PROCESSOS_URL=https://www.jusbrasil.com.br/acompanhamentos/processos/
JUSBRASIL_EMAIL=maj.adv@hotmail.com
JUSBRASIL_PASSWORD=(coloque no Render)
GOOGLE_CALENDAR_ENABLED=false
GOOGLE_CALENDAR_ACCESS_TOKEN=
GOOGLE_CALENDAR_ID=primary
OPENAI_ENABLED=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini

VARIÁVEIS DO CRON JOB:
DATABASE_URL=...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
ALERT_EMAIL_TO=...
OAB_LOGIN_URL=https://recortedigital.oabmg.org.br/
OAB_NUMERO=113674
OAB_UF=MG
OAB_CPF=06819623640
OAB_IDENTIDADE=12989116
JUSBRASIL_ENABLED=true
JUSBRASIL_LOGIN_URL=https://www.jusbrasil.com.br/login?next_url=https%3A%2F%2Fwww.jusbrasil.com.br%2F
JUSBRASIL_PROCESSOS_URL=https://www.jusbrasil.com.br/acompanhamentos/processos/
JUSBRASIL_EMAIL=maj.adv@hotmail.com
JUSBRASIL_PASSWORD=(coloque no Render)
GOOGLE_CALENDAR_ENABLED=false
GOOGLE_CALENDAR_ACCESS_TOKEN=
GOOGLE_CALENDAR_ID=primary
OPENAI_ENABLED=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
