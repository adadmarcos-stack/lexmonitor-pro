from flask import Flask, request, render_template
from config import HOST, PORT
from db import init_db, get_conn
import threading
import time

from monitor_oab import executar_monitor

app = Flask(__name__)
init_db()


# 🔥 LOOP AUTOMÁTICO
def loop_monitor():
    while True:
        try:
            print("Rodando monitor automático...")
            executar_monitor()
        except Exception as e:
            print(f"Erro no monitor: {e}")

        time.sleep(600)  # 10 minutos


# 🚀 INICIA THREAD AUTOMÁTICA
thread = threading.Thread(target=loop_monitor, daemon=True)
thread.start()


def carregar_publicacoes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, processo, data_publicacao, texto, relevante, motivo_filtro, enviado_email, criado_em
    FROM publicacoes
    ORDER BY id DESC
    """)
    itens = []
    for row in cur.fetchall():
        itens.append({
            "id": row["id"],
            "processo": row["processo"] or "",
            "data_publicacao": row["data_publicacao"] or "",
            "texto": row["texto"] or "",
            "relevante": bool(row["relevante"]),
            "motivo": row["motivo_filtro"] or "",
            "enviado_email": bool(row["enviado_email"]),
            "criado_em": row["criado_em"] or "",
        })
    conn.close()
    return itens


def filtrar_publicacoes(publicacoes, busca="", somente_relevantes=False, somente_novas=False):
    busca_norm = (busca or "").upper()
    filtradas = []
    for item in publicacoes:
        if somente_relevantes and not item["relevante"]:
            continue
        if somente_novas and item["enviado_email"]:
            continue
        if busca_norm:
            alvo = f"{item['processo']} {item['data_publicacao']} {item['texto']} {item['motivo']}".upper()
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


@app.route("/")
def index():
    busca = request.args.get("q", "")
    somente_relevantes = request.args.get("relevantes") == "1"
    somente_novas = request.args.get("novas") == "1"
    publicacoes = carregar_publicacoes()
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
    )


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
