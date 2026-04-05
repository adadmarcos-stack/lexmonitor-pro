from flask import Flask, request, render_template, redirect, url_for, session
from config import HOST, PORT, SECRET_KEY, LOGIN_APP_EMAIL, LOGIN_APP_PASSWORD
from db import init_db, fetch_publicacoes

app = Flask(__name__)
app.secret_key = SECRET_KEY
init_db()


# ─── Scheduler automático (roda os monitores a cada 6 horas) ─────────────────
def _run_monitors_background():
    try:
        from monitor_oab import run as run_oab
        print("[Scheduler] Iniciando monitor OAB...")
        run_oab()
        print("[Scheduler] Monitor OAB concluído.")
    except Exception as e:
        print(f"[Scheduler] Erro monitor OAB: {e}")

    try:
        from monitor_drive import run_monitor
        print("[Scheduler] Iniciando monitor Drive...")
        run_monitor()
        print("[Scheduler] Monitor Drive concluído.")
    except Exception as e:
        print(f"[Scheduler] Erro monitor Drive: {e}")


try:
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_monitors_background, "interval", hours=6, id="monitor_job")
    scheduler.start()
    print("[Scheduler] Agendador iniciado — monitores a cada 6 horas.")
except Exception as _sched_err:
    print(f"[Scheduler] APScheduler não disponível: {_sched_err}")
# ─────────────────────────────────────────────────────────────────────────────


def filtrar_publicacoes(publicacoes, busca="", somente_relevantes=False, somente_novas=False):
    busca_norm = (busca or "").upper()
    filtradas = []

    for item in publicacoes:
        if somente_relevantes and not item["relevante"]:
            continue
        if somente_novas and item["enviado_email"]:
            continue

        if busca_norm:
            alvo = " ".join([
                str(item.get("processo", "")),
                str(item.get("data_publicacao", "")),
                str(item.get("texto", "")),
                str(item.get("motivo_filtro", "")),
                str(item.get("parte_autora", "")),
                str(item.get("parte_re", "")),
                str(item.get("tribunal", "")),
                str(item.get("resumo_ia", "")),
                str(item.get("o_que_fazer", "")),
            ]).upper()

            if busca_norm not in alvo:
                continue

        filtradas.append(item)

    return filtradas


def resumo(publicacoes):
    total = len(publicacoes)
    relevantes = sum(1 for p in publicacoes if p["relevante"])
    novas = sum(1 for p in publicacoes if not p["enviado_email"])
    enviadas = sum(1 for p in publicacoes if p["enviado_email"])
    return total, relevantes, novas, enviadas


def logged_in():
    return session.get("logged_in") is True


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if email == LOGIN_APP_EMAIL and password == LOGIN_APP_PASSWORD and LOGIN_APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))

        error = "Credenciais inválidas."

    return render_template("login.html", error=error, login_email=LOGIN_APP_EMAIL)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if not logged_in():
        return redirect(url_for("login"))

    busca = request.args.get("q", "")
    somente_relevantes = request.args.get("relevantes") == "1"
    somente_novas = request.args.get("novas") == "1"

    publicacoes = fetch_publicacoes()
    filtradas = filtrar_publicacoes(publicacoes, busca, somente_relevantes, somente_novas)
    total, relevantes, novas, enviadas = resumo(filtradas)

    return render_template(
        "index.html",
        publicacoes=filtradas,
        busca=busca,
        somente_relevantes=somente_relevantes,
        somente_novas=somente_novas,
        total=total,
        relevantes=relevantes,
        novas=novas,
        enviadas=enviadas,
        login_email=LOGIN_APP_EMAIL,
    )


@app.route("/ping")
def ping():
    return {"status": "ok"}


@app.route("/run-monitors", methods=["POST"])
def run_monitors_manual():
    """Rota para disparar os monitores manualmente (requer login)."""
    if not logged_in():
        return {"error": "não autorizado"}, 401

    import threading
    t = threading.Thread(target=_run_monitors_background, daemon=True)
    t.start()
    return {"status": "Monitores iniciados em background. Aguarde alguns minutos e recarregue a página."}


@app.route("/run-oab", methods=["POST"])
def run_oab_manual():
    """Dispara somente o monitor OAB/Recorte Digital (requer login)."""
    if not logged_in():
        return {"error": "não autorizado"}, 401

    def _run():
        try:
            from monitor_oab import run as run_oab
            run_oab()
        except Exception as e:
            print(f"Erro run_oab manual: {e}")

    import threading
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "Monitor OAB iniciado. Aguarde e recarregue em alguns minutos."}


@app.route("/run-drive", methods=["POST"])
def run_drive_manual():
    """Dispara somente o monitor Google Drive (requer login)."""
    if not logged_in():
        return {"error": "não autorizado"}, 401

    def _run():
        try:
            from monitor_drive import run_monitor
            run_monitor()
        except Exception as e:
            print(f"Erro run_drive manual: {e}")

    import threading
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "Monitor Drive iniciado. Aguarde e recarregue em alguns minutos."}


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
