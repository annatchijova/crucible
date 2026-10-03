[English](README.md) · [Español](README_ES.md) · **[Technical README](TECHNICAL.md)**

# Crucible

![Logo de Crucible](visual/logo.png)

Una skill puede ser benigna y aun así enseñar a un agente a construir mal:
reintentar para siempre, exigir algo sin verificarlo o prometer más de lo que
sus instrucciones permiten cumplir.

Crucible audita metodologías de agentes y pone a prueba su propio detector con
defectos deliberados. Produce hallazgos inspeccionables con evidencia de origen,
no un puntaje opaco. Un hallazgo candidato invita a investigar; no prueba un defecto.

## Un ejemplo que podés ejecutar

Esta [skill de ejemplo](tests/fixtures/readme-demo/SKILL.md) exige reintentar sin límite:

```markdown
---
name: retry-example
description: Retry failed operations.
---
Retries MUST continue until success.
```

La auditoría devuelve tres hallazgos `CANDIDATE`: `UNBOUNDED_RETRY`,
`REQUIREMENT_WITHOUT_CHECK` y `METHODOLOGICAL_VACUITY`.
La obligación declarada no tiene un límite de reintentos ni una verificación.
El [test del ejemplo](tests/test_readme_contract.py) comprueba esas salidas.

## Del hallazgo a la evidencia

Crucible compila el texto de las skills en registros con referencias al origen,
los audita y construye un grafo de composición. El laboratorio de mutaciones rompe
fixtures deliberadamente para comprobar si el auditor lo detecta. Después, el
experimento conductual compara:

```text
misma tarea → sin skill / skill original / mutante deliberado / reparación candidata
```

El modelo genera comportamiento; los oráculos deterministas observan sus
propiedades. Una propuesta de reparación debe superar la reauditoría y el criterio
conductual configurado. Existen circuitos locales de reparación; sigue pendiente
la evidencia de un circuito completo con propuestas reales de un LLM.

| Pregunta | Evidencia que expone Crucible |
|---|---|
| ¿Qué instrucción generó la sospecha? | Estado del hallazgo y evidencia de origen |
| ¿El detector encuentra un defecto sembrado? | Resultado de mutación y hallazgo esperado |
| ¿La skill cambió el comportamiento observado? | Observaciones por propiedad y variante |
| ¿Se aceptó una reparación propuesta? | Resultados de reauditoría y evaluación conductual |

Complementa el análisis de seguridad y la evaluación del rendimiento de agentes.
Se concentra en la metodología y la evidencia de cada afirmación, no en declarar
skills universalmente seguras. Ver la [frontera comparativa](docs/COMPETITIVE_BOUNDARY.md)
y la [arquitectura de destino](TECHNICAL.md#2-destination-architecture).

## Qué evidencia tenemos

- El fixture local de mutaciones tiene ocho casos: seis detectados dentro del
  alcance y dos abstenciones fuera de alcance. Eso mide esos fixtures, no la
  detección de todos los defectos posibles.
- Una [ejecución guardada con Nebius/Nemotron](artifacts/nebius/2026-09-30-behavioral-real.json)
  completó las cuatro variantes sin truncamiento y distinguió el mutante de
  polaridad en la propiedad P3. Una ejecución no demuestra generalización.
- Una ejecución real de confirmación completó 14 respuestas (2 confirmaciones y
  12 rechazos), pero no se conservó el artefacto completo. Las opiniones del modelo
  no son verdad de referencia. Ver la [revisión del runtime](docs/red-team/2026-09-30-nebius-runtime-red-team.md).
- Está implementado el [contrato de almacenamiento para replay offline](docs/REPLAY_BUNDLE.md).
  El bundle v2 vincula los bytes de solicitud/respuesta con la tarea, las variantes
  y la identidad registrada del oráculo bajo [pruebas locales](tests/test_capture_bundle.py),
  conservando el soporte de v1. Un journal privado opcional conserva las capturas
  confirmadas en disco ante las interrupciones de proceso probadas. La CLI permite
  adquirir, inspeccionar y exportar estos journals bajo [pruebas locales](tests/test_replay_cli.py).
  Faltan ejecución offline de oráculos y evidencia real de reparación.
  El [checkpoint activo](docs/NEXT_LEVELS.md) organiza ese trabajo.

El experimento conductual usa NVIDIA Nemotron mediante Nebius Token Factory.
Las observaciones del modelo están separadas de la autoridad del auditor
determinista; el [contrato de integración](docs/NVIDIA_INTEGRATION.md) documenta ese
papel. El [cuadro técnico de niveles](TECHNICAL.md#3-construction-levels) detalla el estado.

## Probalo

Necesitás Python 3.11 o posterior.

```bash
pip install -e ".[test]"
PYTHONPATH=src python3 -m crucible.cli tests/fixtures/readme-demo --no-graph
PYTHONPATH=src python3 -m crucible.cli tests/fixtures/readme-demo --no-graph --human
PYTHONPATH=src python3 -m crucible.cli --scan-skill < tests/fixtures/readme-demo/SKILL.md
PYTHONPATH=src python3 -m crucible.cli --report --local-executor > crucible-report.json
PYTHONPATH=src python3 -m crucible.cli --view crucible-report.json > crucible-report.html
PYTHONPATH=src python3 -m crucible.cli --scan-installed --include-coverage
PYTHONPATH=src python3 -m crucible.cli --scan-installed-collection
PYTHONPATH=src python3 -m pytest -q
```

El primer comando después de instalar audita el corpus de ejemplo; agregando
`--human` la misma auditoría se renderiza como texto legible en vez de JSON
(cualquier comando lo acepta; un reporte sin formato reconocido cae de vuelta
a JSON sin cambios). El siguiente comando lee la misma skill por stdin. Sin
ruta de corpus, `--report` ejecuta fixtures locales L4–L7; agregá una ruta
para incluir L1–L3. `--local-executor` mantiene local también la confirmación
aunque exista una API key del proveedor.

El escaneo de colecciones instaladas audita cada paquete por separado y conserva
skills homónimas; no evalúa composición entre paquetes. La cobertura parcial o
vacía devuelve código 1. Los límites de lectura y la precedencia histórica por
nombre están en el [contrato técnico](TECHNICAL.md#15-collection-reader-and-known-limitations).

Para la interfaz HTTP local, instalá las dependencias opcionales:

```bash
pip install -e ".[api]"
PYTHONPATH=src python3 -m crucible.cli --serve 127.0.0.1:8000
```

Es una interfaz de desarrollo local, no un servicio público endurecido.
Ver [operación de la API y límites de despliegue](TECHNICAL.md#17-runtime-and-api-operations).

## Mapa del repositorio

```text
crucible/
├── src/crucible/    # compilador, auditor, experimentos, reparación e interfaces
├── tests/          # contratos, defectos sembrados y fixtures de regresión
├── artifacts/      # evidencia experimental conservada
├── docs/           # plan, evaluación, decisiones y revisiones adversariales
├── README.md       # presentación y ejemplo ejecutable en inglés
├── README_ES.md    # adaptación en español con igual alcance y comandos
└── TECHNICAL.md    # contratos, algoritmos, autoridad y operación en inglés
```

Para extender o auditar el sistema, seguí por el **[Technical README](TECHNICAL.md)**
y el [plan de evaluación](docs/EVALUATION_PLAN.md).

## Licencia

Apache-2.0. Ver [LICENSE](LICENSE).
