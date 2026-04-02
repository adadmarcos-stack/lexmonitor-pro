import json
from pathlib import Path
from app.services.oabmg_service import consultar_publicacoes
from app.services.alert import enviar_alerta_email


BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_HISTORICO = BASE_DIR / "data" / "publicacoes_salvas.json"


def garantir_pasta_data():
    ARQUIVO_HISTORICO.parent.mkdir(parents=True, exist_ok=True)


def carregar_historico():
    garantir_pasta_data()

    if not ARQUIVO_HISTORICO.exists():
        return []

    try:
        with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, list):
                return dados
            return []
    except Exception:
        return []


def salvar_historico(publicacoes):
    garantir_pasta_data()

    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(publicacoes, f, ensure_ascii=False, indent=2)


def montar_chave_publicacao(pub):
    processo = str(pub.get("processo", "")).strip()
    data_disponibilizacao = str(pub.get("data_disponibilizacao", "")).strip()
    data_publicacao = str(pub.get("data_publicacao", "")).strip()
    pagina = str(pub.get("pagina", "")).strip()
    vara = str(pub.get("vara", "")).strip()

    return f"{processo}|{data_disponibilizacao}|{data_publicacao}|{pagina}|{vara}"


def extrair_publicacoes_do_texto(texto):
    import re

    blocos = re.split(r"\n\s*(?=\d+\.\s*\nData de disponibilização:)", texto)
    publicacoes = []

    for bloco in blocos:
        bloco = bloco.strip()

        if not bloco or not re.match(r"^\d+\.", bloco):
            continue

        processo = re.search(r"Número do processo:\s*([0-9\.\-]+)", bloco)
        data_disp = re.search(r"Data de disponibilização:\s*([0-9/]+)", bloco)
        data_pub = re.search(r"Data de publicação:\s*([0-9/]+)", bloco)
        jornal = re.search(r"Jornal:\s*(.+?)(?=Tribunal:|$)", bloco, re.S)
        tribunal = re.search(
            r"Tribunal:\s*(.+?)(?=Caderno:|Vara:|Título:|Número do processo:|Página:|Intimação|Expediente|$)",
            bloco,
            re.S,
        )
        caderno = re.search(
            r"Caderno:\s*(.+?)(?=Vara:|Título:|Número do processo:|Página:|Intimação|Expediente|$)",
            bloco,
            re.S,
        )
        vara = re.search(
            r"Vara:\s*(.+?)(?=Título:|Número do processo:|Página:|Intimação|Expediente|$)",
            bloco,
            re.S,
        )
        titulo = re.search(
            r"Título:\s*(.+?)(?=Número do processo:|Página:|Intimação|Expediente|$)",
            bloco,
            re.S,
        )
        pagina = re.search(r"Página:\s*([0-9]+)", bloco)

        texto_publicacao = ""
        if "Intimação" in bloco:
            texto_publicacao = bloco.split("Intimação", 1)[1].strip()
        elif "Expediente" in bloco:
            texto_publicacao = bloco.split("Expediente", 1)[1].strip()

        publicacoes.append(
            {
                "processo": processo.group(1).strip() if processo else "",
                "data_disponibilizacao": data_disp.group(1).strip() if data_disp else "",
                "data_publicacao": data_pub.group(1).strip() if data_pub else "",
                "jornal": " ".join(jornal.group(1).split()) if jornal else "",
                "tribunal": " ".join(tribunal.group(1).split()) if tribunal else "",
                "caderno": " ".join(caderno.group(1).split()) if caderno else "",
                "vara": " ".join(vara.group(1).split()) if vara else "",
                "titulo": " ".join(titulo.group(1).split()) if titulo else "",
                "pagina": pagina.group(1).strip() if pagina else "",
                "texto": texto_publicacao[:3000],
            }
        )

    return publicacoes


def montar_mensagem_email(novas_publicacoes):
    linhas = []
    linhas.append("Novas publicações encontradas:")
    linhas.append("")

    for i, pub in enumerate(novas_publicacoes, start=1):
        linhas.append(f"{i}. Processo: {pub.get('processo', '')}")
        linhas.append(f"Data disponibilização: {pub.get('data_disponibilizacao', '')}")
        linhas.append(f"Data publicação: {pub.get('data_publicacao', '')}")
        linhas.append(f"Vara: {pub.get('vara', '')}")
        linhas.append(f"Tribunal: {pub.get('tribunal', '')}")
        linhas.append(f"Página: {pub.get('pagina', '')}")
        linhas.append(f"Texto: {pub.get('texto', '')[:500]}")
        linhas.append("-" * 60)

    return "\n".join(linhas)


def monitorar_publicacoes_oab():
    dados = consultar_publicacoes()

    if not dados.get("ok"):
        return {
            "ok": False,
            "erro": dados.get("erro", "Erro ao consultar publicações.")
        }

    texto = dados.get("preview_texto", "")
    publicacoes_atuais = extrair_publicacoes_do_texto(texto)

    historico = carregar_historico()
    chaves_historico = {montar_chave_publicacao(pub) for pub in historico}

    novas_publicacoes = [
        pub for pub in publicacoes_atuais
        if montar_chave_publicacao(pub) not in chaves_historico
    ]

    email_enviado = False

    if novas_publicacoes:
        assunto = f"Alerta OAB: {len(novas_publicacoes)} nova(s) publicação(ões)"
        mensagem = montar_mensagem_email(novas_publicacoes)
        email_enviado = enviar_alerta_email(assunto, mensagem)

    salvar_historico(publicacoes_atuais)

    return {
        "ok": True,
        "total_atual": len(publicacoes_atuais),
        "total_historico_anterior": len(historico),
        "total_novas": len(novas_publicacoes),
        "email_enviado": email_enviado,
        "novas_publicacoes": novas_publicacoes,
        "arquivo_historico": str(ARQUIVO_HISTORICO)
    }