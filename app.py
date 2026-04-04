from flask import Flask, request, render_template, redirect, url_for, session
from config import HOST, PORT, SECRET_KEY, LOGIN_APP_EMAIL, LOGIN_APP_PASSWORD
from db import init_db, fetch_publicacoes

app = Flask(__name__)
app.secret_key = SECRET_KEY
init_db()


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

        config_email = (LOGIN_APP_EMAIL or "").strip().lower()
        config_password = (LOGIN_APP_PASSWORD or "").strip()

        if email == config_email and password == config_password and config_password:
            session["logged_in"] = True
            return redirect(url_for("index"))

        error = "Credenciais inválidas."

    return render_template("login.html", error=error, login_email=(LOGIN_APP_EMAIL or "").strip().lower())


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
        login_email=(LOGIN_APP_EMAIL or "").strip().lower(),
    )


@app.route("/ping")
def ping():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
