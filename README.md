# AI Support Assistant — Proyecto Integrador M1 (AI Engineering, Henry)

"Multitasking Text Utility": recibe una pregunta de un usuario y devuelve
una respuesta estructurada en JSON (`answer`, `confidence`, `actions`) lista
para que un sistema downstream la consuma sin transformaciones adicionales,
junto con métricas de costo, tokens y latencia de cada ejecución.

## Setup

1. Clonar el repo e instalar dependencias:

   ```bash
   git clone <URL_DE_ESTE_REPO>
   cd ai-support-assistant
   python3 -m venv .venv && source .venv/bin/activate   # opcional pero recomendado
   pip install -r requirements.txt
   ```

2. Configurar la API key:

   ```bash
   cp .env.example .env
   # Editar .env y pegar tu OPENAI_API_KEY real
   ```

   El proyecto lee las variables de entorno con `python-dotenv` /
   directamente del entorno (`OPENAI_API_KEY`, `OPENAI_MODEL`). La API key
   **nunca** va hardcodeada en el código ni se commitea (`.env` está en
   `.gitignore`).

## Cómo ejecutar

```bash
# Como argumento de línea de comandos
python src/run_query.py "¿Cómo cambio mi contraseña?"

# O por stdin
echo "¿Cómo cambio mi contraseña?" | python src/run_query.py
```

La salida es el JSON del contrato, impreso por stdout:

```json
{
  "answer": "Podés cambiar tu contraseña desde Configuración > Seguridad > Cambiar contraseña.",
  "confidence": 0.95,
  "actions": []
}
```

## Cómo reproducir las métricas

Cada ejecución de `src/run_query.py` agrega una fila a `metrics/metrics.csv`
con `timestamp, question, model, tokens_prompt, tokens_completion,
total_tokens, latency_ms, estimated_cost_usd, flagged_by_safety,
safety_reason`. No hace falta ningún paso extra: correr el comando de arriba
varias veces con distintas preguntas genera el historial completo.

## Tests

Los tests **no** requieren API key (no llaman a OpenAI): validan el
contrato JSON, el cálculo de costo y el filtro de seguridad con datos
simulados.

```bash
pytest tests/test_core.py -v
```

## Estructura del repo

```
.
├── src/
│   ├── run_query.py    # entrypoint (CLI)
│   ├── llm_client.py   # llamada a la API + métricas + costo
│   ├── schema.py        # contrato de salida JSON + validación
│   └── safety.py        # bonus: filtro de prompts adversariales
├── prompts/
│   └── main_prompt.md   # system prompt + ejemplos few-shot + justificación
├── metrics/
│   └── metrics.csv      # log de métricas por ejecución
├── reports/
│   └── PI_report_en.md  # informe breve (arquitectura, técnica, métricas)
├── tests/
│   └── test_core.py
├── .env.example
├── .gitignore
└── requirements.txt
```

## Decisiones de diseño (resumen — detalle completo en `reports/PI_report_en.md`)

- **Técnica de prompt engineering:** few-shot (ver `prompts/main_prompt.md`
  para la justificación completa de por qué se eligió por sobre
  chain-of-thought o self-consistency).
- **Salida estructurada:** se usa Structured Outputs de OpenAI
  (`response_format=json_schema`) como red de seguridad de formato, y
  además se valida manualmente (`schema.py`) por si el modelo o el SDK
  cambian de comportamiento — nunca se confía ciegamente en que la API
  devuelva siempre JSON válido.
- **Seguridad (bonus):** defensa en capas — un filtro de patrones
  (`safety.py`) detecta intentos de manipulación antes de llamar al modelo
  (ahorra costo y evita exponer el prompt), y el propio system prompt
  incluye instrucciones para que el modelo se niegue a romper su rol.

## Limitaciones conocidas

- El filtro de `safety.py` es una lista de patrones (regex), no un modelo de
  moderación: cubre los vectores de ataque más comunes pero no es exhaustivo.
- Los precios en `PRICING_USD_PER_1M_TOKENS` (`src/llm_client.py`) son un
  snapshot al momento de escribir el proyecto; hay que verificarlos en
  [platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing)
  antes de reportar costos como definitivos.
- `estimated_cost_usd` es una estimación basada en el conteo de tokens que
  devuelve la API, no un monto facturado real.
