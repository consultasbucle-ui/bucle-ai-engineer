#!/usr/bin/env python3
"""
Entrypoint del proyecto.

Uso:
    python src/run_query.py "¿Cómo cambio mi contraseña?"
    echo "¿Cómo cambio mi contraseña?" | python src/run_query.py

Flujo:
    1. Lee la pregunta del usuario (arg de CLI o stdin).
    2. Capa de seguridad (safety.py): filtra intentos de manipulación
       antes de gastar una llamada a la API.
    3. Si pasa el filtro, llama al modelo (llm_client.py) con el prompt
       few-shot + contrato JSON, y valida la salida (schema.py).
    4. Imprime el JSON resultante por stdout (consumible por otro sistema
       sin transformaciones adicionales, como pide la guía).
    5. Registra la ejecución en metrics/metrics.csv.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import llm_client  # noqa: E402
import safety  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = PROJECT_ROOT / "metrics" / "metrics.csv"
METRICS_FIELDS = [
    "timestamp",
    "question",
    "model",
    "tokens_prompt",
    "tokens_completion",
    "total_tokens",
    "latency_ms",
    "estimated_cost_usd",
    "flagged_by_safety",
    "safety_reason",
]


def _read_question() -> str:
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:]).strip()
    question = sys.stdin.read().strip()
    if not question:
        print("Error: no se recibió ninguna pregunta (ni como argumento ni por stdin).", file=sys.stderr)
        sys.exit(1)
    return question


def _append_metrics_row(row: dict) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = METRICS_PATH.exists() and METRICS_PATH.stat().st_size > 0
    with open(METRICS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=METRICS_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    question = _read_question()
    timestamp = datetime.now(timezone.utc).isoformat()

    decision = safety.check_input(question)

    if decision.flagged:
        result_data = decision.fallback_response
        row = {
            "timestamp": timestamp,
            "question": question,
            "model": "n/a (bloqueado por safety.py antes de llamar al modelo)",
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "total_tokens": 0,
            "latency_ms": 0.0,
            "estimated_cost_usd": 0.0,
            "flagged_by_safety": True,
            "safety_reason": decision.reason,
        }
    else:
        result = llm_client.ask(question)
        result_data = result.data
        row = {
            "timestamp": timestamp,
            "question": question,
            "model": result.model,
            "tokens_prompt": result.tokens_prompt,
            "tokens_completion": result.tokens_completion,
            "total_tokens": result.total_tokens,
            "latency_ms": result.latency_ms,
            "estimated_cost_usd": result.estimated_cost_usd,
            "flagged_by_safety": False,
            "safety_reason": "",
        }

    _append_metrics_row(row)
    print(json.dumps(result_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
