"""
Contrato de salida del asistente.

Toda respuesta del modelo debe cumplir este esquema. Definir el "contrato"
antes de pedirle nada al modelo (y validarlo siempre) es una de las buenas
prácticas pedidas en la guía del proyecto: "Trabaja con la idea de contrato"
y "Valida la salida antes de confiar en ella".
"""

from __future__ import annotations

# JSON Schema en formato compatible con OpenAI Structured Outputs
# (response_format={"type": "json_schema", "json_schema": {...}})
RESPONSE_JSON_SCHEMA = {
    "name": "support_assistant_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "Respuesta concisa y directa a la pregunta del usuario.",
            },
            "confidence": {
                "type": "number",
                "description": "Estimación de confianza del modelo en su respuesta, entre 0.0 y 1.0.",
            },
            "actions": {
                "type": "array",
                "description": "Acciones recomendadas para el sistema downstream (puede ser una lista vacía).",
                "items": {"type": "string"},
            },
        },
        "required": ["answer", "confidence", "actions"],
        "additionalProperties": False,
    },
}

REQUIRED_FIELDS = ("answer", "confidence", "actions")


class SchemaValidationError(ValueError):
    """Se lanza cuando la salida del modelo no respeta el contrato JSON."""


def validate_response(data: dict) -> None:
    """
    Valida que `data` cumpla el contrato de salida.

    Lanza SchemaValidationError con un mensaje claro si algo no cumple.
    No devuelve nada si todo está bien (falla rápido y ruidoso, en vez de
    dejar pasar datos mal formados silenciosamente).
    """
    if not isinstance(data, dict):
        raise SchemaValidationError(f"La salida debe ser un objeto JSON, se recibió: {type(data)}")

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise SchemaValidationError(f"Faltan campos obligatorios en la salida: {missing}")

    if not isinstance(data["answer"], str) or not data["answer"].strip():
        raise SchemaValidationError("El campo 'answer' debe ser un string no vacío.")

    confidence = data["confidence"]
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise SchemaValidationError("El campo 'confidence' debe ser numérico.")
    if not (0.0 <= float(confidence) <= 1.0):
        raise SchemaValidationError(f"El campo 'confidence' debe estar entre 0 y 1, se recibió: {confidence}")

    actions = data["actions"]
    if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
        raise SchemaValidationError("El campo 'actions' debe ser una lista de strings.")
