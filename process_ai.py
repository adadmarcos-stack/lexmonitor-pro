import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from dateutil import parser as date_parser

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _get_config_value(name: str, default=None):
    try:
        import config  # type: ignore

        return getattr(config, name, default)
    except Exception:
        return default


def _get_openai_client() -> Optional[Any]:
    api_key = _get_config_value("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    return OpenAI(api_key=api_key)


def _clean_text(text: str, max_len: int = 12000) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_len]


def _extract_process_number(text: str) -> Optional[str]:
    patterns = [
        r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b",
        r"\b\d{20}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _extract_possible_deadline(text: str) -> Optional[str]:
    """
    Heurística simples:
    - encontra menções como 'prazo de 5 dias'
    - calcula a partir de hoje
    """
    text_lower = (text or "").lower()

    match = re.search(r"prazo de (\d{1,3}) dias", text_lower)
    if match:
        days = int(match.group(1))
        return (datetime.utcnow() + timedelta(days=days)).date().isoformat()

    return None


def _rule_based_analysis(text: str, title: str = "", source: str = "unknown") -> Dict[str, Any]:
    joined = f"{title}\n{text}".strip()
    clean = _clean_text(joined, max_len=4000)
    lower = clean.lower()

    process_number = _extract_process_number(clean)
    deadline_date = _extract_possible_deadline(clean)

    important_terms = [
        "intimação",
        "prazo",
        "manifestação",
        "audiência",
        "decisão",
        "sentença",
        "despacho",
        "urgente",
        "penhora",
        "bloqueio",
        "contestação",
        "recurso",
        "edital",
        "publicação",
    ]

    score = 0
    for term in important_terms:
        if term in lower:
            score += 1

    if any(term in lower for term in ["urgente", "prazo", "intimação", "penhora", "bloqueio"]):
        risk = "alto"
    elif score >= 2:
        risk = "médio"
    else:
        risk = "baixo"

    is_relevant = 1 if score >= 1 or process_number else 0

    summary = clean[:500].strip()
    if len(clean) > 500:
        summary += "..."

    if "audiência" in lower:
        action = "Verificar data e preparar atuação para audiência."
    elif "prazo" in lower or "intimação" in lower:
        action = "Revisar imediatamente o teor da publicação e conferir prazo processual."
    elif "sentença" in lower or "decisão" in lower:
        action = "Ler o inteiro teor e avaliar providência recursal ou cumprimento."
    else:
        action = "Revisar o documento e classificar a providência necessária."

    tags = []
    for term in important_terms:
        if term in lower:
            tags.append(term)

    return {
        "source": source,
        "process_number": process_number,
        "deadline_date": deadline_date,
        "risk_level": risk,
        "ai_summary": summary,
        "ai_action": action,
        "ai_tags": ", ".join(sorted(set(tags))),
        "is_relevant": is_relevant,
    }


def _openai_analysis(text: str, title: str = "", source: str = "unknown") -> Dict[str, Any]:
    client = _get_openai_client()
    if client is None:
        return _rule_based_analysis(text=text, title=title, source=source)

    clean_text = _clean_text(text)
    clean_title = _clean_text(title, max_len=500)

    prompt = f"""
Você é um assistente jurídico que analisa publicações e documentos.
Responda APENAS em JSON válido, sem markdown.

Campos obrigatórios:
- process_number: string|null
- deadline_date: string|null (formato YYYY-MM-DD, se houver)
- risk_level: "alto" | "médio" | "baixo"
- ai_summary: string
- ai_action: string
- ai_tags: string (tags separadas por vírgula)
- is_relevant: 0 ou 1

Título:
{clean_title}

Conteúdo:
{clean_text}
""".strip()

    response = client.responses.create(
        model=_get_config_value("OPENAI_MODEL", "gpt-4.1-mini"),
        input=prompt,
    )

    raw = response.output_text.strip()

    try:
        data = json.loads(raw)
    except Exception:
        return _rule_based_analysis(text=text, title=title, source=source)

    result = {
        "source": source,
        "process_number": data.get("process_number"),
        "deadline_date": data.get("deadline_date"),
        "risk_level": data.get("risk_level", "médio"),
        "ai_summary": data.get("ai_summary", ""),
        "ai_action": data.get("ai_action", ""),
        "ai_tags": data.get("ai_tags", ""),
        "is_relevant": int(data.get("is_relevant", 1)),
    }
    return result


def analyze_text(text: str, title: str = "", source: str = "unknown") -> Dict[str, Any]:
    return _openai_analysis(text=text, title=title, source=source)


def process_publication(publication: Dict[str, Any]) -> Dict[str, Any]:
    title = publication.get("title", "") or ""
    content = publication.get("content", "") or ""
    source = publication.get("source", "unknown") or "unknown"

    analysis = analyze_text(text=content, title=title, source=source)

    merged = dict(publication)
    merged.update(analysis)
    return merged


def parse_date_safe(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        return dt.date().isoformat()
    except Exception:
        return None
