# Barrido RU/ZH 2026-10-28 — L1–L10

> Transcripción sin cambios del informe que entregó otro asistente (Kimi). La
> revisión y el estado de verificación de cada afirmación están en
> [`FINDINGS.md`](FINDINGS.md). Las citas no fueron verificadas contra su fuente.

**Fecha:** 2026-10-28 · **Estado:** resultados registrados, interpretación separada de observación
**Método:** búsqueda web con los términos RU/ZH de la agenda de investigación
(`docs/evidence/2026-10-24-research-agenda`), más una segunda ronda fina
para L1, L5, L7 y L10 que quedaron flojas en la primera pasada. Consultas
exactas listadas por línea.

Convención: **[+]** hay respuesta utilizable · **[~]** hay material parcial ·
**[−]** negativo delimitado (resultado registrable).

---

## L1 — Extraer la entidad restringida de prosa imperativa

**Consultas:** `выделение объекта действия правила извлечение`,
`基于规则的信息抽取 依存句法`, `извлечение сущностей правила шаблоны без
машинного обучения`, `祈使句 语义角色标注 信息抽取 规则`

**Qué contenía el corpus.**
- SRL (语义角色标注) y análisis de dependencias están muy desarrollados en
  el ecosistema chino: LTP-Cloud documenta las 15 relaciones de dependencia
  y trata explícitamente el problema de identificar quién hace qué
  ("提出者 是 李克强，而不是 上海…即使它们都是名词，而且距离 更近").
  La extracción de triplas basada en dependencias (SBV/VOB) es enseñada
  como técnica estándar (blog CSDN, HanLP).
- El corpus RU sobre NER sin ML existe y es explícito: metodologías basadas
  en reglas (regex, diccionarios, patrones morfológicos) documentadas en
  Habr y shaip — pero para *entidades nombradas*, no para el objeto de una
  obligación.

**Qué NO contenía.**
- Toda técnica de análisis de dependencias/SRL accesible (HanLP, LTP,
  PaddlePaddle SRL) usa parsers estadísticos (máxima entropía, CRF, BiLSTM,
  BERT). El corpus documenta la evolución: reglas (1990s) → estadístico →
  neuronal → LLM. La ruta determinista quedó en "era pre-statística" sin
  tooling mantenido.
- Nadie trata el imperativo como caso especial; SRL asume predicado dado y
  usa análisis sintáctico previo.

**Interpretación.** **[−] con matices.** La extracción del *objeto* de una
obligación con precisión comparable requiere análisis sintáctico (objeto
directo del verbo normativo) o SRL, y toda implementación disponible pone un
modelo estadístico en el camino. Lo único ML-free del corpus es NER basado
en patrones/diccionarios, que resuelve entidades, no roles. Cierre negativo
registrable **salvo** una vía no explorada por este barrido: parsing
determinista de propósito estrecho (gramática de frases imperativas en
inglés técnico, controlado), que es ingeniería propia, no literatura
existente. El riesgo documentado de ADR-0027 (fabricar conflictos por
normalización a sustantivo genérico) sigue sin contramedida publicada.

---

## L2 — Detectar interacción entre reglas no declaradas

**Consultas:** `обнаружение конфликтов политик межсетевого экрана`,
`防火墙规则冲突 检测`, `shadowing правил`, `策略冲突检测`

**Qué contenía el corpus.**
- El dominio firewall/políticas está maduro **en chino** con taxonomía
  formal y procedimiento de decisión explícito (secrss.com, artículo 实战):
  relaciones entre pares de políticas = exact match / inclusion / superset /
  disjoint / correlated, sobre un árbol de políticas, detectadas por máquina
  de estados campo a campo (protocolo, src, dst, acción). Tipos de
  conflicto: 覆盖冲突 (shadowing — regla muerta), 冗余冲突 (misma acción),
  关联冲突 (correlación, acciones distintas), 泛化冲突 (generalización),
  不相关异常 (condición imposible). Tesis CNKI (SDN, ABAC).
- En RU: modelos formales de colisiones de firewall (CyberLeninka 2015) y
  verificación con Z3 de políticas RBAC y reglas de firewall
  (спелс/bit.spels.ru), incluyendo detección de intersección
  permitir/prohibir.

**Qué NO contenía.**
- Nada pensado para prosa: todo el corpus formaliza políticas ya
  estructuradas (campos con valores). La transferencia exige normalizar una
  obligación en prosa a la tupla (condiciones, acción, decisión), y ese paso
  es exactamente L1 — la línea más débil del barrido.

**Interpretación.** **[+] con dependencia.** La taxonomía pedida existe y es
trasplantable: "sobre qué recae" ↔ campo de condición; "qué obliga" ↔
acción. El criterio de decisión es explícito y determinista (igualdad /
subconjunto / superconjunto / disjunción sobre cada campo + igualdad de
acción). Traslación a `NORMATIVE_CONFLICT`/`CONDITIONAL_CONTRADICTION`:
necesita L1 para el campo "condición" y una decisión de qué cuenta como
"acción" comparable entre skills. Recomendación: registrar la taxonomía
(shadow/redundancy/correlation/generalization/irrelevance) como modelo de
chequeo y marcar el bloqueo en L1.

---

## L3 — Extracción normativa fuera del inglés

**Consultas:** `ключевые слова RFC 2119 перевод ДОЛЖЕН`,
`RFC 2119 中文 必须 应当`

**Qué contenía el corpus.**
- **RU: equivalencia establecida y publicada.** rfc.com.ru mantiene la
  traducción canónica con equivalentes fijos: MUST = «ДОЛЖНО / ТРЕБУЕТСЯ /
  НУЖНО», MUST NOT = «НЕДОПУСТИМО / НЕ ПОЗВОЛЯЕТСЯ», SHOULD = «СЛЕДУЕТ»,
  MAY = «ВОЗМОЖНО / НЕОБЯЗАТЕЛЬНО», con nota de estilo (negrita en lugar de
  mayúsculas). El ecosistema ruso la usa de facto (rus-PSR, mirrors de PHP
  PSR).
- **ZH: equivalentes funcionales informales pero consistentes**
  (必须/应当/可以 en blogs técnicos y traducciones comunitarias), y un
  paralelo institucional fuerte en redacción legal: tres niveles
  應=MUST / 得=MAY / 不得=MUST NOT (blog TW). La comunidad técnica ZH cita
  RFC 2119 en inglés; no hay convención estándar nacional publicada
  equivalente a ГОСТ.

**Qué NO contenía.**
- Trabajo formal que *valide* la equivalencia modal (RU o ZH) para
  extracción de obligaciones; todo es traducción de referencia + uso de
  facto. Nada sobre extracción multilingüe de requisitos.

**Interpretación.** **[+].** Para RU el mapeo léxico directo es adoptable ya
(lista cerrada de 5 niveles × sinónimos, tal como hoy Crucible matchea
inglés). Para ZH, 必须/应当/可以 funciona como candidata pero con riesgo
de falso positivo enorme (必须 es palabra común: "你必须先理解…"). Falta el
corpus no-inglés y no-templado que la agenda ya pide para separar idioma de
plantilla — este barrido no lo resuelve. Alcance de producto: auditar RU es
técnicamente inmediato; ZH requiere el corpus de validación.

---

## L4 — Que un analizador estime su propio recall

**Consultas:** `полнота статического анализатора оценка`,
`静态分析 漏报率 评估`, `мутационное тестирование анализатора`

**Qué contenía el corpus.**
- **ГОСТ Р 71207** (estándar nacional ruso de desarrollo seguro / análisis
  estático): define formalmente cómo reportar FP/FN de analizadores
  estáticos. Claves para L4: (a) *набор квалификационных тестов* = programas
  con errores sembrados **y conocidos**, incluyendo errores no sembrados que
  aparezcan durante el análisis (denominador honesto por construcción);
  (b) fórmulas explícitas FPW/TW y FN/TB; (c) para tipos no críticos,
  muestreo aleatorio con regla de expansión: muestra primaria ≥10, y si
  aparecen errores confirmados, expandir hasta ≥10× los confirmados. Es un
  formalismo publicado para tasa con denominador cuando no se censó todo.
- En ZH, la literatura de ASAT asume benchmark sembrado (Juliet, TCSE) y
  reporta recall sobre él; un artículo (secrss) reconoce la tensión
  漏报/误报 como "eterno juego" de reglas más o menos agresivas.

**Qué NO contenía.**
- Método para estimar el recall **sin** oráculo parcial: todo el corpus
  asume errores sembrados o proyectos con historial conocido. La circularidad
  que la agenda teme (sembrar lo que ya se detecta) no está tratada como
  problema en RU/ZH; el corpus ZH de "alert confirmation" (SWIPER, I_Mem)
  la ignora: entrena y evalúa sobre lo que el analizador ya detectó.

**Interpretación.** **[+].** ГОСТ Р 71207 §10 es directamente adoptable como
marco de reporte: muestra primaria ≥10 + expansión ×10 conserva el
denominador y es exactamente el tipo de estimador que L4 pedía. El
instrumento ciego existente (24/1195 sostiene piso) es compatible: el ГОСТ
daría cómo reportarlo. Queda negativo delimitado: sin oráculo ninguno
(no sembrado, no historial), el corpus no ofrece nada — resultado registrable.

---

## L5 — Redundancia por decisión, no por léxico

**Consultas:** `семантическая эквивалентность правил дублирование
требований`, `需求重复 检测 语义等价`, `requirements engineering duplicate
detection semantic similarity`

**Qué contenía el corpus.**
- Requirements engineering tiene décadas de detección de duplicados, pero
  definidos por similitud de texto: ReSim (PURE dataset) compara Dice /
  Jaccard / Cosine / híbrido WordNet+embeddings — correlación de Pearson
  sobre pares, nunca "misma decisión". Requirement linking matrices por
  similitud semántica (ScienceDirect 2022): enlazar requisitos = σ(Ri,Rj)
  sobre n-gramas y ontología.
- Lo más cercano a "equivalencia por conducta": clones semánticos de código
  (Type-4, PDG + GNN; SCD-PSM con test de razón de verosimilitud sobre
  trazas I/O). Requiere código ejecutable y modelos estadísticos.
- Práctica de deduplicación a escala (resumen emergentmind): pipeline por
  capas exacto → near-exact (Levenshtein) → semántico (embeddings), con
  advertencia explícita de sobre-fusión por encadenamiento.

**Qué NO contenía.**
- Nada que defina redundancia de reglas de prosa por (decisión, alcance,
  verificación). La ontología de requisitos en RU no apareció (0
  resultados). La equivalencia "misma decisión + mismo alcance + mismo
  check" es estructura que el corpus no tiene.

**Interpretación.** **[−] con un dato útil.** La definición por
decisión/alcance/check no existe en el corpus buscado — coherente con
COMPETITIVE_BOUNDARY (es diferenciador). Lo importable: la advertencia de
sobre-fusión por encadenamiento en pipelines por capas — si Crucible agrega
una capa por decisión/alcance sobre el Jaccard actual, debe verificar pares
en el umbral y documentar que la capa nueva *reduce* candidatos del chequeo
léxico, no los reemplaza (los pares renombrados siguen siendo visibles sólo
léxicamente).

---

## L6 — Espacio de pares a escala, con determinismo

**Consultas:** `MinHash детерминированный поиск дубликатов`,
`确定性 局部敏感哈希 SimHash`, `近似重复检测`

**Qué contenía el corpus.**
- MinHash/LSH es la respuesta estándar documentada en ambos idiomas, con
  análisis de error clásico (probabilidad de candidato = 1−(1−s^r)^b;
  USTC notas; blog ZH con el cálculo de falsos negativos ≈1/3000 en su
  ejemplo). El corpus ZH lo repite mucho: "LSH 不是确定性的，而是概率性的"
  (USTC) — la aleatoriedad es reconocida como propiedad, no como defecto.
- **Punto clave:** la aleatoriedad de MinHash en la práctica viene de los
  hash seeds, y fijar el seed es práctica estándar y expuesta en las APIs:
  datasketch (usado por distilabel MinHashDedup) tiene parámetro `seed`
  (default 1) y `num_perm`; Milvus soporta índice MINHASH_LSH con firma
  binaria. Con seed fijado y funciones de hash deterministas (blake2b con
  seed prefijado), la firma es reproducible bit a bit entre procesos; lo
  aleatorio es el *análisis de error*, no la ejecución. Elasticsearch
  documenta el mismo patrón (bucket_count/hash_count fijos).

**Qué NO contenía.**
- Alternativa 100% determinista que escale subcuadráticamente con garantía
  exacta: el corpus no ofrece nada (SimHash también es aleatorizado;
  prefix-filtering/inverted-index Jaccard exacto existe pero no apareció en
  RU/ZH — queda como hueco razonable para buscar en EN).

**Interpretación.** **[+].** La restricción "aleatorizado ⇒ prohibido" se
resuelve más fácil de lo que la agenda suponía: MinHash con seed fijado +
función hash criptográfica determinista + LSH banding determinista da
reproducibilidad bit a bit con coste subcuadrático, y el análisis de error
clásico (curva s-r-b) sigue valiendo porque el error es sobre la *calidad
del estimador*, no sobre la reproducibilidad. Queda verificación pendiente:
medir en el corpus real de Crucible cuántos de los 337 pares conocidos
conserva un LSH bandado a umbral, y confirmar que la firma entra en el
sello de artefactos.

---

## L7 — Abstención como estado de primera clase

**Consultas:** `селективная классификация отказ от предсказания`,
`选择性预测 拒识 置信度校准`, `selective classification abstention
Chow's rule risk-coverage`

**Qué contenía el corpus.**
- Vocabulario formal maduro y nombrado: **selective classification** /
  classification with reject option (Chow 1970), **risk–coverage
  tradeoff**, **Chow loss** (abstención con coste fijo α), **SGR —
  Selection with Guaranteed Risk** (control ajustable de la tasa de error a
  cobertura dada), **conformal prediction** (conjuntos de predicción;
  en binario {0,1} ≡ abstener). Modelo generalizado de Chow con pesos
  (λ,µ,ν) y abstención óptima por post-procesamiento fijo (Selective
  Omniprediction, NeurIPS 2025).
- Sobre el reporte a downstream: métricas explícitas que distinguen
  abstención de acierto: coverage, selection risk, AUC de la curva
  risk–coverage, Effective Reliability, Selective Prediction Recall.
- Sobre el modo de falla concreto de Crucible (abstención leída como
  aprobación): el corpus ZH de 拒答 en producción lo nombra con precisión:
  "拒答只做了「不执行」，没做「去哪」" — toda abstención necesita un
  *salida explícita* (degradar, pedir datos, escalar a humano), con SLA; y
  la advertencia de que subir el threshold en vez de calibrar sólo mueve
  el error.

**Qué NO contenía.**
- Nada sobre abstención en sistemas *deterministas por contrato* — todo el
  corpus asume un predictor probabilístico calibrable detrás. La relación
  risk–coverage presupone una noción de score de confianza continuo, que
  Crucible no tiene (sus chequeos abstienen por precondición, no por
  score). El vocabulario sobra; la mecánica no aplica directamente.

**Interpretación.** **[+].** Vocabulario adoptable ya: "selective
classification", "coverage", "risk-coverage", "reject option". El reporte a
consumidor: los formalismos de conformal (conjunto de predicción explícito)
y la regla operativa ZH (toda abstención lleva salida explícita con SLA)
resuelven exactamente el bug de la página demo ("passed 28" con 7
abstenciones). Propuesta concreta: el artefacto ya reporta abstenciones —
falta el vocabulario en la UI ("coverage: 21/28 checks evaluados; 7
abstuvieron por precondición X") y una salida declarada por chequeo
abstenido.

---

## L8 — Adjudicación a escala sin modelo como autoridad

**Consultas:** `ранжирование предупреждений статического анализатора
ложные срабатывания`, `告警排序 误报 削减 静态分析`

**Qué contenía el corpus.**
- **Esquema de tres vías con denominador conservado** (PVS-Studio / CERT
  SCALe, Habr 2016): clasificar advertencias en e-TP (presunto verdadero,
  va directo a debug), I (intermedio, revisión humana), e-FP (presunto
  falso, ignorado); 20 proyectos, 3147 TP + 11772 FP de archivo; reducción
  ~90% del trabajo manual. Las tasas se reportan sobre *todas* las
  advertencias.
- **Muestreo estratificado con expansión** (ГОСТ Р 71207 §10.6, mismo estándar
  que L4): para tipos no críticos, muestra aleatoria ≥10; si aparecen
  confirmados, expandir ×10. Exactamente "muestra, no censo, con
  denominador honesto".
- En ZH (operaciones de seguridad): tres estados 真实攻击 / 疑似误报 /
  信息不足（未知） como salida de triaje (Aliyun AI 告警降噪) — el tercer
  estado es la abstención de L7 reapareciendo.
- Advertencia metodológica publicada: la replicación Kang/Aw/Lo de los
  "golden features" mostró que aparente >90% de clasificación de FP venía
  de *data leakage* y duplicación train/test — la adjudicación automática
  tiende a sobre-estimar; dataset manual con etiquetas verificadas es el
  remedio citado.

**Qué NO contenía.**
- Un método donde el ranking lo hace un modelo pero la *decisión* queda en
  humanos con el denominador conservado: el corpus mezcla ambos. La
  restricción dura de Crucible (modelo no decide) no aparece como
  requisito en ningún trabajo — pero el esquema e-TP/I/e-FP es compatible:
  el modelo puede *ordenar* y las tres vías preservan el censo para el
  reporte.

**Interpretación.** **[+].** Tres piezas directamente adoptables: (1)
triaje en tres vías (el "I" intermedio es lo que hoy falta entre "hallazgo"
y "descartado"); (2) regla de muestra ГОСТ (≥10, expansión ×10) para el
marco de adjudicación actual con k=10; (3) la advertencia de leakage como
criterio de aceptación: cualquier priorización que Crucible implemente debe
poder demostrar que sus señales no son tautológicas respecto del chequeo
que prioriza.

---

## L9 — Validar que una reparación cambió conducta, no texto

**Consultas:** `A/B тестирование промптов оценка агентов`,
`提示词 A/B 测试 智能体评测`

**Qué contenía el corpus.**
- Práctica ZH madura de A/B de prompts con control de confusión explícito:
  misma tanda de casos, mismo modelo, misma temperatura, múltiples
  muestras, evaluación a ciegas, `judge_score` y `human_preference`
  guardados como campos separados, `failure_tags` por caso (Tencent Cloud
  prompt_test; curso apxml).
- **Advertencia central publicada** (blog Tian Pan 2026): A/B estándar
  fracasa en features LLM — métricas de superficie (CTR, duración) suben
  mientras la calidad semántica cae ("semejante mejora del prompt bajó
  extracción 10% y RAG compliance 13% subiendo instruction-following
  13%"); exige evaluación semántica por segmento de intención y *un cambio a
  la vez*.
- **Control del confounder "el modelo cambia entre corridas":** ADK
  conformance test (Google) — grabar interacciones baseline y *reproducir*
  comparando contra la grabación; detección de regresión de comportamiento
  del agente al cambiar código o modelo. Tres capas de evaluación
  (hello-agents): quick/standard/full con costes distintos.

**Qué NO contenía.**
- Oráculos de propiedad no tautológicos respecto del detector: toda la
  práctica de evaluación mide *tarea cumplida* con juez LLM o humana — la
  pregunta "¿el cambio silenció al detector o corrigió la conducta?" no
  aparece formulada; lo más cercano es evaluar la trayectoria
  (trajectory eval) en vez de sólo la salida.

**Interpretación.** **[~].** El gate L7 gana tres cosas concretas: (1)
protocolo A/B con denominador y campos separados (judge vs humano,
failure_tags) — adoptable ya; (2) conformance replay contra baseline
grabado para cuando el modelo sube de versión — resuelve el control de
confusión documentado; (3) la advertencia de métricas de superficie valida
la sospecha del proyecto y sugiere el criterio: el oráculo del gate debe
medir conducta en tarea **ajena al chequeo reparado** (si reparaste
`NORMATIVE_CONFLICT`, el gate mide ejecución de tareas que no tocan
conflictos), o medir trayectoria. Queda abierto (negativo delimitado):
oráculo de propiedad formal no tautológico no apareció en RU/ZH.

---

## L10 — Calidad de instrucción como objeto medible

**Consultas:** `человеческий фактор стандартные операционные процедуры
качество чек-листа`, `SOP 标准作业程序 设计 人为差错`, `checklist design
principles Gawande aviation`

**Qué contenía el corpus.**
- **FAA/NASA Ames CR-177549** (Human Factors of Flight-Deck Checklists):
  guías de diseño con racional explícito — respuestas deben indicar el
  *estado deseado*, no "chequeado"; filosofía ATA/Boeing: incluir sólo pasos
  cuya omisión tiene impacto adverso directo; mínimas señales para operador
  entrenado; no incluir ítems ya anunciados por sistemas de alerta.
- **Gawande / Checklist Manifesto:** dos tipos (do-confirm vs read-do), 5–9
  ítems, pause points con gatillo definido, prueba de usabilidad ("alguien
  ajeno al diseño lo sigue y completa"). WHO Safe Surgery Checklist: −47%
  muertes, −36% complicaciones en 8 hospitales — criterios que
  sobrevivieron uso real en dominio donde un procedimiento malo mata.
- ZH (aviación CAAC): "六大工具" (SOP, 标准喊话, 交叉检查, 检查单, 飞行简令,
  指令复诵) como conjunto interdependiente, no checklists aislados. Taxonomía
  de error humano: 失误 (error) vs 违规 (violación), factores PIF.

**Qué NO contenía.**
- Criterios *falsables* de calidad de procedimiento en prosa libre: las
  guías son de diseño (cómo escribir), no de auditoría (cómo verificar que
  un procedimiento dado es bueno). La medición publicada es siempre de
  *outcomes* (muertes, incidentes), no de propiedades del texto del
  procedimiento.

**Interpretación.** **[~] (la más útil para la tesis).** Nadie audita la
calidad textual de un procedimiento con chequeos automáticos — el hueco
que COMPETITIVE_BOUNDARY postula se confirma también fuera del mundo
anglófono. Lo importable son criterios de diseño ya validados que pueden
volverse chequeos: (a) "respuesta debe indicar estado deseado, no
'chequeado'" → chequeo de que una verificación en la skill referencia un
estado observável; (b) "sólo pasos cuya omisión tiene impacto directo" →
chequeo de omisión crítica vs relleno; (c) do-confirm/read-do como
*clasificación* de instrucciones; (d) el marco error/violación como tipos
de hallazgo distintos (una regla ambigua induce error; una regla
incompleta invita a violación). Esto da a L10 un puente hacia chequeos
concretos sin salir del contrato.

---

## Síntesis

| Línea | Resultado | Pieza accionable |
|-------|-----------|------------------|
| L1 | [−] | Cierre negativo registrable; vía restante = parser propio de alcance estrecho |
| L2 | [+] | Taxonomía shadow/redundancy/correlation/generalization/irrelevance + máquina de estados campo-a-campo; bloqueada en L1 |
| L3 | [+] | Mapeo RU publicado (rfc.com.ru) adoptable ya; ZH candidata 必须/应当/可以 con corpus de validación pendiente |
| L4 | [+] | ГОСТ Р 71207 §10: sembrado + muestra ≥10/×10 con denominador |
| L5 | [−] | Confirmado hueco; importar advertencia de sobre-fusión por capas |
| L6 | [+] | MinHash de seed fijado + LSH determinista = bit-exacto; análisis de error clásico aplica |
| L7 | [+] | Vocabulario selective classification / risk-coverage / conformal; regla "toda abstención tiene salida explícita" |
| L8 | [+] | Triaje tres vías e-TP/I/e-FP + regla de muestra ГОСТ; criterio anti-leakage |
| L9 | [~] | Protocolo A/B ZH + conformance replay ADK; oráculo no tautológico sigue abierto |
| L10 | [~] | Criterios de diseño FAA/Gawande/CAAC convertibles a chequeos; auditar texto sigue sin precedentes |

## Qué NO investigar (confirmado)

- Nada de L2/L5/L8 requiere modelo en el camino de decisión: las piezas
  adoptables son taxonomías, reglas de muestreo y protocolos — compatibles
  con CLAUDE.md §5.1.
- L6 queda resuelto sin tocar el contrato (el seed fijado no es "meter un
  modelo": es fijar el estado pseudoaleatorio, estándar de la técnica).

## Consultas exactas usadas

Ronda 1: `выделение объекта действия правила извлечение`,
`基于规则的信息抽取 依存句法` · `обнаружение конфликтов политик
межсетевого экрана`, `防火墙规则冲突 检测` · `ключевые слова RFC 2119
перевод ДОЛЖЕН`, `RFC 2119 中文 必须 应当` · `полнота статического
анализатора оценка`, `静态分析 漏报率 评估` · `семантическая
эквивалентность правил дублирование требований`, `需求重复 检测 语义等价`
· `MinHash детерминированный поиск дубликатов`, `确定性 局部敏感哈希
SimHash` · `селективная классификация отказ от предсказания`,
`选择性预测 拒识 置信度校准` · `ранжирование предупреждений
статического анализатора ложные срабатывания`, `告警排序 误报 削减 静态
分析` · `A/B тестирование промптов оценка агентов`, `提示词 A/B 测试
智能体评测` · `человеческий фактор стандартные операционные процедуры
качество чек-листа`, `SOP 标准作业程序 设计 人为差错`.

Ronda 2: `извлечение сущностей правила шаблоны без машинного обучения`,
`祈使句 语义角色标注 信息抽取 规则` · `requirements engineering
duplicate detection semantic similarity`, `требования дублирование
онтология сравнение смысла` (0 resultados) · `selective classification
abstention Chow's rule risk-coverage`, `拒识 三值逻辑 审计 决策 放弃
分类` · `checklist design principles Gawande aviation quality criteria`,
`检查单 设计 原则 紧急程度 人为因素`.
