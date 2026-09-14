"""
Cliente delgado sobre la API de OpenAI: arma el prompt, hace la llamada,
mide latencia/tokens/costo y devuelve una respuesta ya validada contra el
contrato JSON definido en schema.py.

Decisión de diseño (documentada, como pide la guía): además de aplicar
few-shot prompting (ver prompts/main_prompt.md) usamos Structured Outputs
de OpenAI (response_format=json_schema) como segunda red de seguridad para
la salida estructurada. El few-shot resuelve la CALIDAD del contenido
(cómo redactar answer/actions y cómo calibrar confidence); Structured
Outputs resuelve el FORMATO (que siempre sea JSON parseable). Ninguna de
las dos técnicas reemplaza a la otra, y aun así validamos manualmente con
schema.py por si el modelo/SDK cambia de comportamiento.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

from schema import RESPONSE_JSON_SCHEMA, validate_response

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Precios de referencia (USD por 1M de tokens). Son los publicados por
# OpenAI para gpt-4o-mini al momento de escribir este proyecto.
# OJO: los precios cambian -> antes de reportar costos reales, verificar
# en https://platform.openai.com/docs/pricing y actualizar estas constantes.
PRICING_USD_PER_1M_TOKENS = {
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@dataclass
class QueryResult:
    data: dict
    raw_content: str
    model: str
    tokens_prompt: int
    tokens_completion: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    flagged_by_safety: bool = False
    safety_reason: str = ""


def _load_prompt_template() -> str:
    path = PROMPTS_DIR / "main_prompt.md"
    return path.read_text(encoding="utf-8")


def _estimate_cost(model: str, tokens_prompt: int, tokens_completion: int) -> float:
    pricing = PRICING_USD_PER_1M_TOKENS.get(model)
    if pricing is None:
        # Modelo sin precio conocido en este proyecto: no inventamos un número,
        # devolvemos 0.0 y dejamos constancia en vez de reportar un costo falso.
        return 0.0
    cost = (tokens_prompt / 1_000_000) * pricing["input"] + (tokens_completion / 1_000_000) * pricing["output"]
    return round(cost, 8)


def ask(user_question: str, model: str | None = None, client: OpenAI | None = None) -> QueryResult:
    """
    Envía `user_question` al modelo aplicando el prompt few-shot y el
    contrato JSON, y devuelve un QueryResult con la respuesta ya validada
    y las métricas de la ejecución.
    """
    model = model or DEFAULT_MODEL
    client = client or OpenAI()  # usa OPENAI_API_KEY del entorno

    template = _load_prompt_template()
    # Todo lo que está ANTES del marcador se envía al modelo (instrucciones +
    # ejemplos few-shot incluidos). Lo que está después es documentación para
    # humanos (por qué elegimos esta técnica) y no se envía como prompt.
    system_prompt = template.split("<!-- END_SYSTEM_PROMPT -->")[0].strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": RESPONSE_JSON_SCHEMA},
        temperature=0.2,  # baja temperatura: queremos respuestas consistentes/reproducibles, no creativas
    )
    latency_ms = (time.perf_counter() - start) * 1000

    raw_content = response.choices[0].message.content
    data = json.loads(raw_content)
    validate_response(data)  # falla ruidoso si, pese a Structured Outputs, algo no cierra

    usage = response.usage
    tokens_prompt = usage.prompt_tokens
    tokens_completion = usage.completion_tokens
    total_tokens = usage.total_tokens

    return QueryResult(
        data=data,
        raw_content=raw_content,
        model=model,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        total_tokens=total_tokens,
        latency_ms=round(latency_ms, 2),
        estimated_cost_usd=_estimate_cost(model, tokens_prompt, tokens_completion),
    )
