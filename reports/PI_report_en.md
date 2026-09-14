# Informe Breve — Proyecto Integrador M1: AI Support Assistant

## 1. Arquitectura

El sistema es un servicio de línea de comandos (`src/run_query.py`) con tres
componentes desacoplados:

```
pregunta del usuario
        │
        ▼
 safety.check_input()  ──(si detecta manipulación)──► fallback JSON + log
        │ (si pasa el filtro)
        ▼
 llm_client.ask()  ──► OpenAI API (gpt-4o-mini, Structured Outputs)
        │
        ▼
 schema.validate_response()  ──► valida el contrato antes de confiar en la salida
        │
        ▼
 JSON por stdout + fila nueva en metrics/metrics.csv
```

Cada módulo tiene una sola responsabilidad: `schema.py` define y valida el
contrato de salida, `llm_client.py` habla con la API y calcula métricas,
`safety.py` es la capa de defensa, y `run_query.py` orquesta el flujo y
persiste las métricas. Esto permite testear `schema.py` y `safety.py` sin
necesidad de una API key (ver `tests/test_core.py`).

## 2. Técnica de prompting usada y por qué

**Few-shot prompting**, documentado en detalle en
`prompts/main_prompt.md` (sección "Notas de diseño"). En resumen: el
problema no requiere razonamiento multi-paso (donde chain-of-thought
aportaría más), sino calibrar criterio — cuándo escalar a un humano, cómo
de segura debe sonar una respuesta. Tres ejemplos few-shot que cubren los
casos límite (alta confianza / escalamiento / consulta ambigua) comunican
ese criterio mejor que reglas abstractas. Se complementa con **Structured
Outputs** de la API (JSON Schema) como segunda capa que garantiza el
formato, independientemente de si el contenido generado es el ideal.

## 3. Resumen de métricas y resultados de muestra

> **Nota para quien evalúa:** la tabla de abajo se completa con la primera
> fila real de `metrics/metrics.csv` al correr el proyecto con una API key
> válida (`python src/run_query.py "..."`). Antes de entregar, reemplazar
> estos valores de ejemplo por resultados reales de al menos una ejecución
> exitosa y, si se implementó el bonus, una ejecución bloqueada por
> `safety.py`.

| Pregunta | Modelo | tokens_prompt | tokens_completion | total_tokens | latency_ms | estimated_cost_usd |
|---|---|---|---|---|---|---|
| "¿Cómo cambio mi contraseña?" *(ejemplo ilustrativo, completar con corrida real)* | gpt-4o-mini | ~250 | ~40 | ~290 | ~900 | ~0.00006 |

Interpretación esperada: para consultas cortas de soporte, el costo por
consulta con `gpt-4o-mini` debería ser sub-centavo de dólar, con la mayoría
del tokens_prompt explicado por el system prompt (instrucciones + few-shot),
no por la pregunta del usuario en sí — algo a tener en cuenta si se quisiera
optimizar costo más adelante (por ejemplo, cacheando el prompt del sistema).

## 4. Desafíos

- **Confiar en el formato de salida del modelo:** aunque Structured Outputs
  reduce mucho el riesgo, decidimos no confiar ciegamente y mantener
  `schema.validate_response()` como última línea de defensa — un modelo o
  versión de API distinta podría no respetar el `response_format`.
- **Calibrar `confidence` de forma consistente:** sin ejemplos, el modelo
  tiende a responder siempre con confianza alta. Los ejemplos few-shot
  fueron elegidos específicamente para mostrar el rango completo (alta,
  media/baja, y el caso "no entendí nada").
- **Evitar que el filtro de seguridad genere falsos positivos:** una lista
  de patrones muy agresiva bloquearía preguntas legítimas de soporte. Se
  ajustaron los patrones para apuntar a frases características de intentos
  de manipulación ("ignorá las instrucciones anteriores", "actuá como si
  fueras...") y no a lenguaje de soporte normal.

## 5. Posibles mejoras

- Sumar un paso de moderación con el endpoint de moderación de OpenAI como
  segunda señal además del filtro por patrones de `safety.py`.
- Cachear el system prompt (prompt caching) para bajar costo y latencia en
  ejecuciones repetidas, dado que es la parte más grande del `tokens_prompt`.
- Persistir las métricas en una base de datos liviana (SQLite) en vez de
  CSV si el volumen de consultas creciera, para poder consultarlas mejor.
- Agregar reintentos con backoff ante errores transitorios de la API.
