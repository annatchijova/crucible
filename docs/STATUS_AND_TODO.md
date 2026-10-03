# Crucible Skills — Estado y Pendientes

**Fecha original:** 2026-09-24 (actualizado 2026-10-02, ver notas abajo)
**Base:** main @ 1fe6361
**Tests:** 411 pasan originalmente — **655 pasan al 2026-10-01** (R3, R4, y L15 se agregaron después de esta fecha; ver TECHNICAL.md para el estado nivel por nivel actualizado, esta tabla quedó vieja)

---

## Lo que está hecho

13 niveles coherentes completos, todos con tests falsificables, determinismo
verificado cross-process, y sellado SHA-256:

| Nivel | Qué hace | Estado |
|-------|----------|--------|
| L1 | Compilador de corpus a Skill IR versionada | Completo |
| L2 | Auditor determinista con 29 checks | Completo |
| L2.5 | Capa de confirmación LLM (5 tipos de finding) | Completo (mock) |
| L3 | Grafo de composición tipado | Completo |
| L4 | Laboratorio de mutaciones (8 clases) | Completo |
| L5 | Harness diferencial conductual | Completo (local) |
| L6 | Workflow de Bob (proponer + re-auditar) | Completo (rule-based) |
| L7 | Loop cerrado de reparación | Completo (local) |
| L8 | CI + viewer HTML + reporte compuesto | Completo |
| L9 | Extracción style-agnostic | Completo |
| L10 | Taxonomía de 8 checks de ingeniería | Completo |
| L11 | API pública + demo UI + 3 modos de scan | Completo |
| L12 | Confirmación Nemotron para 19 tipos | Completo (mock) |
| L13 | Validación corpus-agnóstico (10 skills, 7 fuentes) | Completo |
| L14 | Real-runtime boundary (L5) | Completo — agregado después de esta fecha, ver TECHNICAL.md |
| R2/R3 | Replay bundle (acquisition/export + offline oracle replay) | Completo — agregado 2026-10-01, ver docs/REPLAY_BUNDLE.md |
| R4 | Private repair evidence capture | Una corrida live del fixture aceptada; accuracy y estabilidad aún sin evaluar — ver docs/REPAIR_EVIDENCE.md |
| L15 | Recomendación determinística + narrador LLM + reporte final MD/HTML/PDF | Completo y corrido en vivo contra Nebius 2026-10-01 (incluyendo los 3 formatos de salida) — ver docs/red-team/2026-10-01-l15-recommendation-narrator-review.md y docs/evidence/2026-10-01-l15-render-live-run/ |
| L16 | Workflow de consolidación de skills (cluster → LLM propone fusión → gate determinista) | Completo (local, sin NEBIUS_API_KEY corrido real) — ver docs/decisions/0020-l16-consolidation-scope.md |

Red team L11 completado: 5 hallazgos encontrados y arreglados (RT-01 a RT-05),
1 hipótesis falsificada (RT-06), invariantes verificados (RT-07).

Actualización 2026-10-03: se agregó el check `COMMAND_ORACLE_WITHOUT_ARTIFACT`
(L2, check 29), a partir de un insight de investigación externa (artículo de
Habr sobre diseño de skills: "toda instrucción no verificable por máquina
tarde o temprano se viola sin que te enteres"). Detecta un check con
`oracle_kind` "command" que solo tiene un verbo de verificación, sin nombrar
un comando, script o bloque de código concreto. Medido contra el corpus
diverso (L13, 10 skills): la primera versión tenía 3/7 falsos positivos
(casos "Run the server:\n```bash\n...\n```" donde el comando real está en un
bloque cercado en la línea siguiente, invisible al extractor); corregido
agregando lookahead de bloque cercado, quedando 0/4 falsos positivos
medidos. Rompió ~20 tests en 7 archivos que usaban el idiom "Verify X" sin
backtick como relleno de "check válido" en sus fixtures; todos corregidos
haciendo esos checks concretos (con `` `scripts/...` ``) en vez de debilitar
el check nuevo.

Actualización 2026-10-03 (2): se agregó L16, el workflow de consolidación
de skills (`consolidation.py`), a pedido del usuario: cuando varios skills
son redundantes entre sí (no solo un par), un LLM propone UN skill
fusionado que los reemplaza, con el mismo principio arquitectónico de
siempre (el LLM propone, lo determinista decide). Agrupa pares
`SEMANTIC_REDUNDANCY` ya CONFIRMADOS (L2.5) en clusters vía componentes
conexas; si algún skill fuera del cluster lo referencia por nombre,
rechaza la fusión entera (decisión del usuario: no reescribir referencias
externas en este incremento); verifica cobertura (cada regla/check
original debe tener contenido equivalente en la fusión, Jaccard ≥ 1/2,
umbral propio y distinto del 2/3 que ya usa el detector de duplicados); y
NO tiene gate conductual (L5 no generaliza a contenido arbitrario, así que
cada reporte lo dice explícitamente en vez de omitirlo). 8 tests nuevos,
suite completa en verde. Detalle completo en
docs/decisions/0020-l16-consolidation-scope.md.

Actualización 2026-10-03 (3): se agregó el modo batch (`run_consolidation_batch`,
CLI `--consolidate-all`) — procesa todos los clusters de una sola corrida en
vez de uno por vez. Los clusters se calculan una sola vez al principio (son
componentes conexas disjuntas), pero cada fusión corre contra una auditoría
recién recalculada del corpus (los `finding_id` de la confirmación quedan
viejos en cuanto una fusión anterior cambia el corpus). Un cluster
rechazado/bloqueado queda sin fusionar y NO frena al resto — es un lote de
intentos independientes, no una transacción. De paso encontré y arreglé un
bug real: el mismo patrón que rompió `--cluster-index` (default `0`
confundido con "flag seteado" en el chequeo de exclusión mutua de replay)
había que revisarlo también para `--consolidate-all`; resultó inofensivo
porque es `store_true` con default `False`, pero valía la pena confirmarlo
en vez de asumirlo. 4 tests nuevos, 738 tests totales, todo en verde.

Actualización 2026-10-03 (4): se implementó la auto-reescritura de
referencias externas que ADR-0020 había dejado afuera por riesgo. Resultó
que el riesgo real solo aplica a la mitad del problema: una referencia
"## Composes with"/"## Delegates to" tiene como valor del bullet
exactamente el nombre del skill (así es como el auditor la resuelve), así
que reescribirla es un replace de línea preciso, sin ambigüedad — eso ya
se auto-reescribe por default. Una referencia en prosa libre dentro del
campo `description:` del YAML sigue bloqueando la fusión entera, porque
reescribirla significaría re-serializar un escalar YAML, no un match de
línea — un problema distinto y más difícil, no resuelto en este
incremento. Un cluster con una mezcla de ambos tipos sigue bloqueando
(una reescritura parcial que deja una referencia rota no es un resultado
aceptable). 4 tests nuevos (uno reemplaza al que afirmaba el bloqueo
incondicional viejo), 740 tests totales, todo en verde. Detalle en el
addendum 2 de docs/decisions/0020-l16-consolidation-scope.md.

Actualización 2026-10-03 (5): primera corrida real de L16 contra Nemotron
(la key de `~/Downloads/token_nvidia.txt` seguía vigente en `.env`, la
misma de la corrida L1-L7 del 2026-10-01). 3 escenarios reales: fusión de
2 skills (ACCEPTED, 4.9s), fusión de 3 skills + reescritura de referencia
externa real (ACCEPTED, la referencia quedó resuelta sin
`BROKEN_REFERENCE`), y un caso diseñado para medir el umbral de cobertura
con contenido genuinamente distinto entre los dos skills — Nemotron
conservó los dos checks distintos, 0 gaps. No se encontró ningún caso real
donde el modelo dropeara contenido en esta sesión, así que el umbral 1/2
sigue siendo "no obviamente mal calibrado para este tipo de entrada", no
"medido contra una falla real". Evidencia completa (JSON crudo + qué
establece y qué no) en docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md.

Actualización 2026-10-03 (6): corrida real del modo batch
(`run_consolidation_batch` y, aparte, el CLI `--consolidate-all` posta —
confirmación real + consolidación real, no solo la API de Python).
Corpus de 5 skills con 2 clusters independientes (retry, format) + una
referencia externa. `find_redundancy_clusters` separó bien los dos
clusters (no los mezcló en uno); el batch corrió las dos fusiones reales
secuencialmente (7.0s total), ambas ACCEPTED, la referencia externa quedó
reescrita apuntando al nombre nuevo. Hallazgo aparte, real y útil:
`MockConfirmExecutor` (heurística de solapamiento de líneas, 80%) y el
check real `SEMANTIC_REDUNDANCY` (Jaccard de tokens, 2/3) NO siempre
coinciden — mis fixtures cercanas pasaban cómodo el umbral real pero
fallaban el del mock por las líneas de nombre/heading distintas. Quedó
documentado para no confundir un `NO_CLUSTERS` de calibración del mock
con que el detector real no encontró nada. Detalle y JSON en los runs 4 y
5 de docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md.

---

## Lo que falta — por prioridad

### P0 — Bloqueador de submission al hackathon

**1. NEBIUS_API_KEY — ejecución real con Nemotron — RESUELTO 2026-10-01**

La key estaba generada desde el 24/09 (`~/Downloads/token_nvidia.txt`) pero
nunca se había seteado como `NEBIUS_API_KEY`, por eso nunca "aparecía". Ya
está en `.env` (gitignored) y se corrieron los tres comandos reales:

- `crucible --behave` → `nebius_blocked: false`, 4 variantes `COMPLETED`
- `crucible tests/fixtures/readme-demo --confirm` → 2/2 `CONFIRMED`
- `crucible --report` → `nebius_blocked: false`, pipeline L1-L7 sellado completo

Modelo real usado: `nvidia/nemotron-3-super-120b-a12b` vía
`nebius-token-factory`. Evidencia completa (JSON crudo + digests + qué
establece y qué no) en `docs/NEBIUS_LIVE_RUN_EVIDENCE.md`. No se re-corrió
`--bob`/`--repair-loop`/`--repair-evidence` contra la API real en esta
sesión — queda pendiente si se quiere esa cobertura también documentada.

Componentes afectados (estado original al 2026-10-01):
- L5 behavioral differential (NebiusExecutor) — probado
- L2.5/L12 confirmation layer (NebiusConfirmExecutor) — probado
- L6 Bob LLM proposer (LLMProposer) — NO probado en esta sesión
- L7 repair loop (NebiusExecutor + LLMProposer) — NO probado en esta sesión

Actualización 2026-10-02: se capturaron dos corridas de L7 con el fixture
sintético integrado. La primera fue `REJECTED / NO_PROPOSAL` por truncamiento
al límite de 1.000 tokens; la segunda, tras elevar el límite a 3.000, fue
`ACCEPTED` por reauditoría determinista y replay conductual. Ambas capturas
privadas y sus digests están descritos en `docs/REPAIR_EVIDENCE.md`. Esto cubre
el camino L7 contra el proveedor en una tarea sintética; no mide precisión,
generalización ni estabilidad. Los tres comandos de arriba y la afirmación
“no se re-corrió” mantienen su alcance histórico del 2026-10-01.

**2. Video de demo (≤3 minutos)**

Requisito del hackathon. No existe. Debe mostrar el flujo end-to-end:
audit → mutation → behavioral differential → repair → replay.

**3. Demo URL o test build**

Requisito del hackathon. Opciones:
- Deployar la API (Dockerfile existe, expone `0.0.0.0:8000`)
- O proveer instrucciones deterministas para correr el demo localmente

### P1 — Calidad de submission

**4. Corpus externo — selección y licenciamiento**

El evaluation plan define 4 corpus (autor, mutantes, OSS, NVIDIA). Solo el
corpus del autor (88-103 skills) y el diverse corpus (10 skills, 7 fuentes)
están implementados. Falta:
- Corpus OSS independiente (false-positive pressure real) — **corrido
  2026-10-02**: github.com/mukul975/Anthropic-Cybersecurity-Skills (818
  skills reales). Encontró y cerró 3 bugs reales del compilador (frontmatter
  YAML real vía PyYAML + reparo dirigido de dos puntos sin comillas, ver
  commit de compiler.py); 818/818 compilan, 552 findings reales. Dos
  hallazgos concretos de calibración documentados en
  `docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md`:
  SEMANTIC_REDUNDANCY bien calibrado (confirmado por inducción, no
  subdetecta), DESCRIPTION_BODY_GAP con un patrón real de falso positivo en
  skills estilo workflow/procedural sin vocabulario RFC-2119. Todavía sin
  licenciar explícitamente para uso como demo pública.
- Corpus NVIDIA verified skills (interoperabilidad)
- Documentar licencias de cada corpus

**5. Política de CI gate**

El CI corre tests y genera el reporte, pero no bloquea merges. Falta definir:
- ¿Qué pasa = merge bloqueado?
- ¿Findings CANDIDATE bloquean? ¿Solo CONFIRMED?
- ¿Mutation kill rate mínimo?

**6. Feedback sobre tools/models — RESUELTO 2026-10-03**

Requisito del hackathon. Documento completo en `docs/FEEDBACK.md`,
consolidando los hallazgos reales de todas las sesiones con key real
(2026-09-30 a 2026-10-03): los 4 hallazgos del red team del 2026-09-30
sobre Nemotron (`content: null`, truncamiento con presupuestos de tokens
bajos, contexto pasivo no es causal — el hallazgo más importante — y
tipografía real rompiendo oráculos lexicales), latencia observada en L16
(~5s por propuesta), nada de errores de autenticación ni rate limits
observados en ninguna sesión (el código de reintento en 429 existe pero
nunca se disparó), y la diferencia real entre el executor local y
Nemotron real (el hallazgo de contexto pasivo solo pudo encontrarse
contra el modelo real; el mock de confirmación y el detector real de
redundancia no siempre coinciden en el mismo par). Actualizada también
la fila correspondiente de `docs/NVIDIA_INTEGRATION.md` (PLANNED → DONE).

**7. Pre-existing project disclosure**

Requisito del hackathon si el proyecto existía antes del periodo de submission.
Hay que escribir qué se hizo durante el hackathon vs. qué preexistía.

### P2 — Mejoras técnicas conocidas

**8. Mutation survivors — RESUELTO 2026-09-25 (esta nota quedó vieja)**

Esta entrada decía que `EXCEPTION_REMOVAL` y `EDGE_REMOVAL` sobrevivían.
Verificado contra el código real el 2026-10-03 (`run_mutation_lab()`):
las 8 mutaciones de L4 dan `kill_rate: "6/6"`, 0 SURVIVED — ya se habían
cerrado en el commit `539b5d9c` (2026-09-25, "kill both mutation
survivors, add CI gates, project disclosure"), antes de la última
actualización de esta tabla. `EXCEPTION_REMOVAL` lo cerró el check
`OVERGENERALIZATION` (usa las condiciones de excepción que la IR ya
extraía, pero que ningún check consumía); `EDGE_REMOVAL` lo cerró
conectar la spec de la mutación con la propiedad `ISOLATED_SKILL` que el
grafo (L3) ya emitía. No hizo falta ningún cambio nuevo — la nota de
abajo ("ambos son cambios no triviales") describía un estado que ya no
era cierto.

**9. TUI pulida — RESUELTO 2026-10-03 (alcance acotado, sin TUI interactiva)**

Preguntado directamente: TUI interactiva real (textual/rich, dependencia
nueva) vs. salida legible sin agregar dependencias — se eligió lo
segundo, consistente con que el proyecto es deliberadamente
stdlib-only en todo lo demás. Nuevo flag `--human`: un solo helper
(`_emit`) reemplaza los ~17 `print(json.dumps(...))` del CLI, y un
dispatcher (`human_output.py`) detecta el tipo de reporte (audit,
mutation, behavioral, graph, confirmation, bob/repair-loop/
consolidation, consolidation batch) y lo renderiza como texto legible
con color ANSI (solo si hay terminal real — `isatty()` — nunca al
redirigir o hacer pipe). Cualquier forma no reconocida cae a JSON sin
cambios: `--human` nunca es un downgrade. De yapa, muestra en vivo las
activation traces del punto 10. El viewer HTML read-only sigue como
está — esto no lo reemplaza, es presentación de CLI. 13 tests nuevos.
Detalle en docs/decisions/0022-human-readable-cli-output.md. Una TUI
interactiva de verdad queda fuera de alcance, explícitamente.

**10. Runtime activation traces — RESUELTO 2026-10-03**

Cada observación de propiedad en L5 ahora trae un trace de activación
real en `evidence`: qué palabra clave matcheó en el output real del
modelo (y en qué fragmento), o la lista completa de palabras buscadas y
no encontradas — ya no una frase estática idéntica sin importar el
resultado. `evidence` se mantiene como `str` (no se cambió a dict ni se
agregó un campo nuevo) porque el validador del bundle sellado de replay
(`replay.py`, R2/R3) exige exactamente `{property_id, status, evidence}`
con `evidence` como texto — ensanchar ese contrato para que entre un
campo nuevo hubiera sido debilitar una validación deliberadamente
estricta, así que la traza más rica se renderiza como un string
descriptivo en vez de como un campo separado. El viewer HTML también
muestra esta evidencia como tooltip. Es un trace léxico determinista, no
una prueba de qué "razonó" el modelo — documentado así explícitamente.
4 tests nuevos. Detalle en docs/decisions/0021-l5-activation-traces.md.

**11. Model/provider integration — estabilidad cross-version — NO VERIFICABLE con el acceso actual (2026-10-03)**

Preguntado directamente: el único acceso real disponible vía Nebius
Token Factory es `nvidia/nemotron-3-super-120b-a12b` — no hay una
segunda versión/tag de Nemotron para comparar. Medir estabilidad
cross-version requiere correr el mismo experimento L5 (mismo task, mismo
fixture) contra al menos dos versiones reales del modelo y comparar
observaciones; con una sola versión disponible, cualquier intento de
"medir" esto sería simulación, no evidencia. Se deja documentado como
limitación honesta y no verificable con el acceso actual, no como
pendiente de implementación — no hay código que escribir acá hasta que
exista una segunda versión real contra la que comparar. Ya está
declarado así en `docs/NVIDIA_INTEGRATION.md` ("We have not verified
that every planned behavioral task is stable across model versions").

### P3 — Deferido explícitamente (no bloquea submission)

**12. Firmas y supply-chain**

El competitive boundary dice que CRUCIBLE consume evidencia de SkillSpector/
SkillEvaluator como input vecino, pero no integra firmas ni validación de
supply chain. Eso es_FULL OVERLAP con NVIDIA — no es diferenciador.

**13. Polished TUI y viewer**

El viewer es funcional pero minimal. No es blocking.

**14. Corpus plan completo**

Los 4 corpus del evaluation plan están todos en PLANNED excepto el del autor.
El diverse corpus (L13) es un sustituto parcial del corpus OSS.

---

## Resumen ejecutivo

```
P0 (bloquea submission):  NEBIUS_API_KEY, video, demo URL
P1 (calidad):              corpus externo, CI gate, disclosure (feedback RESUELTO 2026-10-03)
P2 (mejoras técnicas):     TODOS RESUELTOS O NO VERIFICABLES — mutation survivors RESUELTO 2026-09-25, TUI/traces RESUELTOS 2026-10-03 (alcance acotado), cross-version NO VERIFICABLE con el acceso actual
P3 (deferido):             firmas, viewer pulido, corpus completo
```

El proyecto tiene 13 niveles completos con 411 tests, red team hecho y
arreglado, y arquitectura determinista con LLM fuera del path de decisión.
El bloqueador principal es conseguir la API key y ejecutar el pipeline
completo con Nemotron real — sin eso, no hay submission válida.
