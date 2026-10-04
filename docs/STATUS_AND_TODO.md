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

Actualización 2026-10-03 (7): el usuario pidió frenar el ritmo — quedan
27 días, la prioridad es que el escaneo de 1 skill / 1 repo / instalados
funcione bien de verdad, no sumar features. Corrí `--scan-installed`
contra la colección real de ~100 skills del usuario (no un fixture
sintético) y encontré 2 bugs reales de extracción, preexistentes (no
introducidos esta sesión): (1) `_VERIFICATION_STARTER` no distinguía una
oración nueva de una línea de **continuación** envuelta a mano — un
fragmento de oración que arranca con "does"/"confirm"/etc. se extraía
como check falso; (2) `_CODE_FENCE` no reconocía bloques \`\`\` con
indentación (anidados en una lista), dejando pasar YAML embebido como
prosa. Medido, no asumido: `COMMAND_ORACLE_WITHOUT_ARTIFACT` bajó de 58 a
35 findings (-40%) sobre la misma colección real, y `REQUIREMENT_WITHOUT_CHECK`
subió de 16 a 24 — los fragmentos basura estaban tapando skills que de
verdad no tienen checks. 4 tests nuevos (fixtures sintéticos, no texto
real del usuario). Al revisar los 35 que quedaron encontré un tercer
problema, más grande, **sin arreglar todavía**: varios checks/rules con
bullet explícito que envuelven en 2+ líneas físicas pierden el resto del
texto (el extractor solo lee la primera línea) — afecta no solo checks
sino también rules y relations, mismo patrón en los tres. Queda como
pendiente nuevo (ver abajo), no cerrado. Detalle completo en
docs/decisions/0023-verification-starter-continuation-lines.md.

Actualización 2026-10-04: el usuario pidió avanzar el gate de "evaluación
independiente" (`docs/NEXT_LEVELS.md`) en vez de seguir por días del
calendario — y notó que `mukul975` ya no sirve como held-out: se usó para
calibrar el compilador/auditor durante la sesión del 10-03, así que es dev
data, no evidencia independiente. Buscamos y clonamos 3 repos reales nunca
tocados antes (`microsoft/skills`, `machina-sports/sports-skills`,
`TerminalSkills/skills`; dominios deliberadamente distintos entre sí y de
mukul975) y simulamos un usuario instalándolos (HOME apuntado a un
directorio aislado, sin tocar la colección real) con
`--scan-installed-collection`. Encontramos que el cap de 500 entries aborta
todo el scan sin devolver ningún parcial — confirmado intencional por su
propio test, no un bug. 488 skills analizados (el resto de TerminalSkills,
1055 en total, muestreado con semilla fija bajo el cap). Adjudicamos a mano
la clase `NON_DETERMINISTIC_INSTRUCTION` (39 findings) contra el criterio ya
establecido en la adjudicación de mukul975: encontramos un mecanismo nuevo
(100% de 35/39 era la misma oración plantilla "Pick sync OR async... Choose
one mode per module" — una instrucción ANTI-no-determinismo, no una
instancia de él) y lo arreglamos en el auditor (se sacó "one" de la
alternación `pick/choose`, queda solo "any"; 1 test nuevo, 770 tests en
verde, mutation gate 6/6 intacto). Los 4 findings restantes también
resultaron falsos positivos, todos ya cubiertos por mecanismos documentados
previamente (randomness criptográfica requerida, texto descriptivo de un
riesgo de terceros). Resultado agregado: **0 verdaderos positivos para
`NON_DETERMINISTIC_INSTRUCTION` en 4 corpus independientes** hasta la
fecha (autor, mukul975, y estos 3 nuevos combinados) — señal fuerte de que
el diseño léxico del check puede ser estructuralmente incapaz de distinguir
"se le instruye al agente actuar sin método fijo" de "el texto contiene la
palabra random/arbitrary/pick/choose por otra razón". Rediseñar el check
es una decisión de Anna, no un default del implementador — queda planteada,
no resuelta.

Segunda clase adjudicada en la misma corrida: `IRREVERSIBLE_WITHOUT_REVIEW`
(54 findings). A diferencia de `NON_DETERMINISTIC_INSTRUCTION`, este check
nunca excluía reglas con modalidad MUST_NOT/SHOULD_NOT/NEVER ("Never delete
underperforming videos" se marcaba como la acción irreversible peligrosa
que la propia regla prohíbe). Arreglado reusando el guard ya existente
(`_NEGATIVE_MODALITIES`) para reglas, y el detector léxico del compilador
(`_NORMATIVE_STARTERS`) para procedural steps (que no tienen campo
`modality`). Medido: 54 → 47 (-7, exactamente los casos de prohibición). Los
47 restantes son una mezcla más riesgosa de tocar a ciegas: sentidos
metafóricos de "drop/remove" (query projection, fallback, declive de una
métrica, metáfora de ventas), una regla de autorización de PocketBase mal
interpretada como instrucción, el mismo patrón de plantilla repetida de la
clase anterior ("never" a mitad de oración, no al inicio, el guard
deliberadamente no llega ahí), y un hueco real: el check no tiene noción de
que código en git es recuperable. Quedan documentados, no parcheados —
cambiar esos patrones a ciegas arriesga falsos negativos reales en un check
de seguridad. 2 tests nuevos, 772 tests en verde, mutation gate 6/6 intacto.

Tercera clase adjudicada en la misma corrida: `COMMAND_ORACLE_WITHOUT_ARTIFACT`
(106 findings) — mucho más heterogénea que las dos anteriores, al menos 5
mecanismos distintos leyendo las 106 una por una: (1) líneas de introducción
a una lista ("Check these rules:", "Verify:") contadas como check vago
extra, encima de los checks reales de la lista que ya se extraen por
separado — 8/106, arreglado reusando `_EXPLICIT_LIST_MARKER` del compilador;
(2) herramienta/URL nombrada en texto plano (Grok Debugger, VoiceOver, GROQ,
Nikto...) — ~15, ya es una limitación documentada en el propio docstring del
check, no un bug oculto; (3) texto que no es un check en absoluto (nota de
arquitectura, advertencia de seguridad, la propia descripción del skill)
que arrancó con un verbo-trigger por casualidad — ~15-18, requeriría tocar
qué cuenta como "check" en la extracción, superficie mucho más grande y
riesgosa; (4) instrucciones de confirmación humana, no verificables por
máquina — ~3-4, pregunta de producto (¿cuenta un humano confirmando como
bound válido?), no mía para decidir; (5) el resto (~60-65) parece
genuinamente vago sin artefacto nombrado — el check funcionando como se
espera. Solo se arregló (1), el mecanismo limpio y de bajo riesgo: medido
106 → 99 (7 de los 8 esperados; el octavo introduce una tabla markdown, no
una lista, caso correctamente fuera de alcance). 2 tests nuevos, 774 tests
en verde, mutation gate 6/6 intacto. Los otros 4 mecanismos quedan
documentados sin tocar — necesitan criterio de producto o un cambio mucho
más grande, no un regex ciego.

Cuarta clase: `REQUIREMENT_WITHOUT_CHECK` (120) — a diferencia de las tres
anteriores, resistió bien la lectura: muestra de 10 skills (espn-api,
adonisjs, cors, azure-storage-blob-rust, fail2ban...), todas con reglas
normativas reales ("NEVER use Access-Control-Allow-Origin: * with
credentials: true") y cero verificación en todo el cuerpo — skills tipo
documentación/referencia que sí carecen genuinamente de mecanismo de
verificación. Pero una (`polymarket`) reveló un bug real un nivel más abajo,
en el compilador: dentro de una sección "### Live Odds Check" (reconocida
como sección de Checks), el extractor solo capturaba bullets, nunca listas
numeradas — 3 checks reales con comandos concretos se perdían enteros, no
solo mal clasificados. Arreglado (`_EXPLICIT_LIST_MARKER` en vez de
`_BULLET` en `_extract_checks`). Medido: 120 → 118. 1 test nuevo.

Este mismo fix destapó un SEGUNDO problema, real pero preexistente y sin
arreglar: el filtro de título de sección ("check"/"verification"/
"validation" como substring) es demasiado laxo — "### Example 3:
Fact-checking and verification" y "### Example 2: ...system health checks"
son walkthroughs de ejemplo cuyo título solo *menciona* esas palabras, no
secciones de checks reales. Antes eran invisibles (contenido numerado, el
bug de arriba los tapaba); ahora se extraen sus pasos de ejemplo como
checks falsos, y en el caso de `web-research` eso alcanza a sacarlo de la
lista de `REQUIREMENT_WITHOUT_CHECK` sobre la base de checks que no son
reales — podría estar tapando un caso genuino. Angostar el filtro de título
de "contiene la palabra" a "el heading ES de checks" es un cambio más
grande y arriesgado que cualquiera de los anteriores en este archivo
(riesgo de falso negativo en un `## Checks and Verification` real) — queda
documentado, no resuelto. 775 tests en verde, mutation gate 6/6 intacto.

**Nota: sesión paralela detectada.** Mientras se hacía este trabajo, otra
sesión de Claude Code corría en paralelo sobre el mismo checkout (otra de
las ventanas abiertas), haciendo la misma adjudicación held-out de forma
independiente. Encontró y arregló el mismo problema de título de sección
laxo que esta sesión había dejado documentado sin cerrar
(`_EXAMPLE_HEADING`, commit `b6cd2ad`). Por compartir el mismo directorio
de trabajo, ese commit terminó incluyendo también un fix mío que todavía
no había comiteado (la extracción de trigger, ver abajo) — ambos cambios
son correctos e independientemente testeados, pero la atribución en el
historial de git quedó mezclada entre las dos sesiones. Avisado a Anna.

Quinta clase: `MISSING_FAILURE_MODE` (41) — el vocabulario del check se
perdía 4 formas comunes de nombrar una falla sin decir literalmente
"fail"/"error": "invalid" (un `catch` real devolviendo "Invalid
signature", 400, marcado como que no tiene ningún manejo de fallas) y
"crash"/"denied"/"rejected" (ssh: "fix permission denied and host key
errors", literal en la descripción del propio skill). Agregadas las 4
palabras, confirmadas una por una contra el texto real antes de tocar
nada. Medido en dos pasos: 41 → 37 → 33. 2 tests nuevos.

Sexta clase: `SCOPE_TRIGGER_MISMATCH` (15) — `windsurf-rules` reveló un
bug real en la extracción del trigger: el regex corta en el primer punto
literal, incluso dentro de un nombre de archivo. La descripción real
dice "Use when a user asks to set up `.windsurfrules` or
`.windsurf/rules`, write global..." pero el trigger capturado quedaba en
"a user asks to set up" — el punto de ".windsurfrules" cortaba todo lo
demás, dejando 4 tokens genéricos sin ningún vocabulario real del
dominio. Arreglado: el límite ahora exige que el punto esté seguido de
espacio o fin de string, no cualquier punto. Medido: 15 → 13 (verificado
que los 13 restantes no muestran el mismo síntoma). Este fix quedó
mezclado en el commit `b6cd2ad` de la otra sesión por el motivo de
arriba.

El resto de las clases de finding sobre este mismo corpus
(`METHODOLOGICAL_VACUITY` 20, y 8 clases más) quedó sin adjudicar — el
gate de evaluación independiente sigue abierto. Entre las dos sesiones se
cerraron 6 clases de quince. Detalle completo, manifiesto de muestreo y
digests en docs/evidence/2026-10-04-held-out-corpora-adjudication/FINDINGS.md
y docs/evidence/2026-10-04-held-out-corpora-my-classes/FINDINGS.md.

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

**4b. Multi-line bullet/rule wrapping — RESUELTO 2026-10-03 (mismo día, a pedido del usuario)**

Encontrado y arreglado el mismo día (ver actualización (7) arriba y el
addendum de docs/decisions/0023-verification-starter-continuation-lines.md).
Dos helpers de join compartidos (`_join_marked_continuation` para
bullets/números explícitos — junta hasta línea en blanco/heading/code
fence/próximo marcador; `_join_unmarked_sentence` para oraciones sin
marcador — junta solo hasta el primer límite de oración real, para no
fusionar varias oraciones de una sola línea cada una) conectados en
`_extract_rules`, `_extract_checks` (las dos vías), y
`_extract_procedural_steps`. `_extract_relations` quedó sin tocar a
propósito (son nombres de skill cortos, no prosa). Medido de nuevo
contra la misma colección real: `COMMAND_ORACLE_WITHOUT_ARTIFACT` bajó
más, de 35 a 31 — las preguntas con bullet que envolvían el "?" a una
segunda línea ahora se reclasifican bien como "question". Los 757 tests
preexistentes pasaron sin tocar ninguno; 4 tests nuevos. Suite completa
en 765 tests, todo verde.

**5. Política de CI gate**

Verificado el 2026-10-03 (no asumido): `.github/workflows/ci.yml` ya
tiene 3 jobs reales (test suite, red-team de seguridad, gate de
mutation kill rate que falla si no es 6/6) — corren en cada push/PR. Pero
`gh api repos/annatchijova/crucible/branches/main/protection` devuelve
`404 Branch not protected`: `main` no tiene ninguna regla de protección,
así que un job en rojo no impide mergear. Falta definir (decisión del
usuario, no algo que se pueda inferir del código):
- ¿Se activa branch protection exigiendo estos 3 checks?
- ¿Findings CANDIDATE bloquean? ¿Solo CONFIRMED?
- ¿Mutation kill rate mínimo (ya hay un job que exige 6/6, falta activarlo como requisito)?

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

**7. Pre-existing project disclosure — RESUELTO 2026-10-03 (reescrito, estaba desactualizado)**

`docs/PRE_EXISTING_PROJECT_DISCLOSURE.md` ya existía pero decía "38
commits en 2 días" (2026-09-23/24) — mismo patrón de doc vieja que las
otras entradas de esta tabla. Verificado contra el estado real: **92
commits en 7 días** (hasta 2026-09-23 a 10-03). Reescrito con la
cronología completa día por día y una sección "What is NOT complete"
corregida (varias cosas que decía "pendiente" ya se hicieron — ejecución
real contra Nebius, corpus externo real de 818 skills — y encontré algo
nuevo al verificar en vez de asumir: `gh api .../branches/main/protection`
devuelve `404 Branch not protected` — confirma empíricamente que el CI
(punto 5 de esta lista) corre pero no bloquea nada, no es solo una
sospecha).

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
