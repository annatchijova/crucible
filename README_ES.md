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

Lo corrés en un minuto, o mirás primero la salida verificada de cada comando:
**[docs/DEMO.md](docs/DEMO.md)** tiene un camino local que no necesita
credenciales y otro en contenedor para un test build.

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

Crucible complementa el análisis de seguridad y la evaluación del rendimiento de
agentes. Se concentra en la metodología y la evidencia de cada afirmación, no en
declarar skills universalmente seguras. Los `checks` extraídos son candidatos
estructurales, no cobertura vinculada a reglas: un paso de flujo puede ocultar un
hallazgo candidato por falta de verificación. Ver la [revisión red team](docs/red-team/2026-10-07-check-heading-adjudication.md),
la [frontera comparativa](docs/COMPETITIVE_BOUNDARY.md) y la
[arquitectura de destino](TECHNICAL.md#2-destination-architecture).

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
- Un experimento acotado con el modelo se puede reproducir offline sin volver a
  contactar al proveedor. El [contrato de bundle de replay](docs/REPLAY_BUNDLE.md)
  vincula los bytes de solicitud y respuesta con la tarea, las variantes de skill
  y la identidad registrada del oráculo, bajo [pruebas del bundle](tests/test_capture_bundle.py)
  y [pruebas de contrato de la CLI](tests/test_replay_cli.py). Una corrida L7
  privada capturada completó reparación, reauditoría y replay conductual sobre el
  fixture integrado. El [checkpoint activo](docs/NEXT_LEVELS.md) separa esa
  demostración de la evaluación held-out y de estar listo para release.
- La ruta de consolidación corrió sobre skills que no escribió el autor. En
  una rebanada de cuatro skills de un corpus externo sellado, con NVIDIA
  Nemotron real en cada paso de modelo, el modelo confirmó dos candidatos de
  redundancia, propuso una fusión para cada uno, y el gate determinista
  **aceptó una y rechazó la otra**. Investigar ese rechazo encontró defectos en
  el gate mismo, no en la fusión: un hallazgo de nivel corpus que se re-ancla a
  un skill no tocado tras la fusión se leía como defecto nuevo. Ese y tres
  defectos relacionados, en los que el veredicto dependía del nombre de un skill
  ajeno, ya están corregidos, junto con un camino en el que una fusión cuyo
  texto declaraba otro nombre pasaba la cobertura sin chequear nada. Repitiendo la prueba sobre los mismos skills reales y sin
  modelo, el cluster rechazado ahora se acepta
  ([correcciones del gate](docs/evidence/2026-10-28-l16-gate-fixes/FINDINGS.md)). Una corrida controlada mostró
  que el modelo es no determinista a temperatura 0 mientras el veredicto del
  gate se mantuvo idéntico, que es la afirmación central de la arquitectura
  puesta a prueba directamente. Fusionar un grupo mayor está implementado pero
  no ejercitado sobre entrada real: con todas las similitudes léxicas medidas,
  ninguna familia real de skills fusionables pasa de cinco
  ([medición de familias](docs/evidence/2026-10-28-n-to-1-families/FINDINGS.md)).
  Ver la [corrida de consolidación en vivo](docs/evidence/2026-10-24-l16-live-real-corpus/FINDINGS.md).
- El chequeo de redundancia ya no compara todos los pares. El filtrado por
  prefijo exacto da el mismo digest de auditoría en `vantaflow` y `mukul975`
  comparando 4.131 y 10.653 pares en lugar de 239.086 y 334.153
  ([medición](docs/evidence/2026-10-28-prefix-filter-redundancy/FINDINGS.md)).
- El informe narrado (grupos para fusionar, contradicciones con su riesgo,
  reescrituras sugeridas y verificadas por el gate, resumen ejecutivo) se
  corrió una vez con el modelo en vivo, sobre una porción de cuatro skills
  del corpus held-out `TerminalSkills`. Dos de las cuatro candidatas
  confirmadas a MODIFY (`auth-system-setup`, `aws-rds`) recibieron una
  reescritura real de NVIDIA Nemotron que el gate aceptó tras reauditar la
  porción; las otras dos (`adonisjs`, `batch-processor`) recibieron
  `NO_PROPOSAL`, una decisión del modelo, no un fallo del circuito. 13
  llamadas al modelo, 114 s
  ([evidencia](docs/evidence/2026-10-28-live-report/RUN.md)). Cuatro skills
  de 1057 no establece calidad de narración ni precisión de reparación en
  general, y ningún código del gate o del proposer cambió a partir del
  resultado de esta corrida, así que el estatus held-out del corpus para una
  evaluación independiente sigue vigente para las otras 1053 skills.
- Cuatro corpus externos independientes están congelados por commit y digest de
  manifiesto, dos reservados como held-out. Auditar los cinco (2806 skills) dio
  un resultado negativo que conviene decir sin rodeos: el grafo de composición da
  86 aristas en el corpus del autor y **cero** en cada corpus escrito por
  terceros, porque una arista exige que un autor nombre otra skill. Seis de ocho
  chequeos con precondición se abstienen en los cinco corpus, y el artefacto de
  auditoría ahora reporta esas abstenciones en vez de devolver un resultado vacío
  que se lee como limpio. Las mediciones completas están en la
  [replicación en cinco corpus](docs/evidence/2026-10-23-heldout-replication/FINDINGS.md).

El experimento conductual usa NVIDIA Nemotron mediante Nebius Token Factory.
Las observaciones del modelo están separadas de la autoridad del auditor
determinista; el [contrato de integración](docs/NVIDIA_INTEGRATION.md) documenta ese
papel. El [cuadro técnico de niveles](TECHNICAL.md#3-construction-levels) detalla el estado.

## Capturas

Un reporte narrado con modelo real sobre un slice de 4 skills de un corpus
held-out — resumen, recomendación por skill, y el intento de reescritura
`llm-nebius`, todo atado a hallazgos que el auditor determinista ya había
sellado:

![Resumen del reporte narrado](visual/screenshot-narrated-report.png)
![Detalle por skill del reporte narrado](visual/screenshot-narrated-detail.png)

El mismo motor escaneando las skills instaladas de esta misma autora — 101
escaneadas, 108 hallazgos, 14 clases de defecto, y cobertura `PARTIAL`
reportada honestamente en vez de tratar en silencio las 198 skills
salteadas como si estuvieran limpias:

![Escaneo de skills instaladas](visual/screenshot-installed-scan.png)

Más capturas de esta sesión están en [`visual/`](visual/).

## Probalo

Necesitás Python 3.11 o posterior.

```bash
pip install -e ".[test]"

# el ejemplo de arriba, como texto legible
PYTHONPATH=src python3 -m crucible.cli tests/fixtures/readme-demo --no-graph --human

# el detector puesto a prueba contra ocho defectos sembrados
PYTHONPATH=src python3 -m crucible.cli --mutate

# tus propias skills instaladas, con cobertura explícita
PYTHONPATH=src python3 -m crucible.cli --scan-installed --include-coverage

PYTHONPATH=src python3 -m pytest -q
```

Sacá `--human` para el artefacto JSON sellado. Todos los demás modos y flags,
con su salida verificada, están en
[docs/DEMO.md](docs/DEMO.md#cli-modes-and-flags).

Para un informe escrito sobre una skill, un directorio o tus skills instaladas:
grupos de duplicados para fusionar, contradicciones con su riesgo, texto de
reglas repetido, qué no se analizó y una recomendación narrada por skill.
`--with-consolidation` además le pide al modelo que proponga una skill fusionada
por grupo, `--with-repairs` le pide una reescritura para las skills a
modificar (hasta `--repair-limit`, 10 por defecto), y el gate determinista
acepta o rechaza cada propuesta re-auditando el texto.

```bash
# necesita NEBIUS_API_KEY; --mock-narrate corre la misma ruta con sustitutos deterministas
PYTHONPATH=src python3 -m crucible.cli path/to/skills --narrate --with-consolidation --with-repairs --render-format html --out report.html
PYTHONPATH=src python3 -m crucible.cli path/to/SKILL.md --narrate --render-format markdown
PYTHONPATH=src python3 -m crucible.cli --scan-installed --narrate --render-format pdf --out report.pdf
```

El modelo redacta la prosa y propone fusiones. No decide ninguna
recomendación, y cada hallazgo que cita se verifica contra la auditoría sellada.

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
├── TECHNICAL.md    # contratos, algoritmos, autoridad y operación en inglés
└── INVESTIGAR-CRUCIBLE.md  # preguntas abiertas, con términos de búsqueda RU/ZH
```

Para extender o auditar el sistema, seguí por el **[Technical README](TECHNICAL.md)**
y el [plan de evaluación](docs/EVALUATION_PLAN.md).

## Licencia

Apache-2.0. Ver [LICENSE](LICENSE).
