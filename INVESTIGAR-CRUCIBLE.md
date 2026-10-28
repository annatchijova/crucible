# Qué investigar para mejorar Crucible

**Fecha:** 2026-10-24 · **Estado:** agenda de investigación, no resultados

**Resultados:** el primer barrido sobre L1–L10 está registrado, con su
revisión, en [`docs/evidence/2026-10-28-ru-zh-research-sweep`](docs/evidence/2026-10-28-ru-zh-research-sweep/FINDINGS.md).

Este documento es una lista de preguntas abiertas con los términos para
buscarlas. Las preguntas están en español; los términos de búsqueda están en
ruso y en chino, porque la literatura de ingeniería de esos dos ecosistemas
cubre varios de estos problemas con más profundidad práctica que la discusión
en inglés sobre agentes, que tiende a quedarse en prompts.

**Cada línea está anclada a un defecto medido**, con su registro de evidencia
enlazado. Ninguna afirma que la respuesta exista: afirma dónde sería razonable
buscarla y qué haría falta para cerrarla, incluso negativamente. Un
"no se encontró nada en el corpus buscado" es un resultado registrable, como
ya lo fue en el [barrido RU/ZH del 2026-10-04](docs/evidence/2026-10-04-ru-zh-corpus-sweep/FINDINGS.md).

**No vuelvas a barrer lo ya barrido.** Ese documento ya cerró: pinning de
dependencias, variables de entorno como entrada no confiable, el panorama
competitivo (tres ejes ocupados: auditoría de uso, escaneo de seguridad en
instalación, registries con gobernanza; y un cuarto confirmado vacío:
auditoría de calidad metodológica con estados epistémicos y mutación del
propio verificador). Si una búsqueda te devuelve eso, ya está registrado.

---

## L1 — Extraer la entidad restringida de prosa imperativa, sin NLP probabilístico

**Pregunta.** ¿Existe una técnica determinista y explicable para identificar
*sobre qué* recae una obligación escrita en imperativo («Never commit secrets
to the repository» → `secrets`), con precisión suficiente como para comparar
dos reglas entre sí?

**Por qué.** `subject` se extrae en 27 de 2806 skills reales. Sólo la ruta de
modales RFC-2119 lo asigna; las rutas de arranque negativo e imperativo
escriben `""` por construcción. Eso deja mudos a `NORMATIVE_CONFLICT` y
`CONDITIONAL_CONTRADICTION`, los dos chequeos más cercanos al diferenciador
declarado. Ver [ADR-0027](docs/decisions/0027-defer-imperative-subject-extraction.md).

**Qué respuesta sirve.** Una que trate el resultado como *candidato con
procedencia*, no como hecho, y que falle de forma visible. El riesgo
documentado no es omitir un conflicto: es **fabricarlo**, emparejando dos
reglas no relacionadas que normalizan al mismo sustantivo genérico.

**Qué la cierra en negativo.** Que toda técnica encontrada requiera un modelo
estadístico en el camino de decisión. Eso la descarta por contrato
(`CLAUDE.md` §5.1) y el resultado se registra como tal.

**RU:** `семантическая разметка ролей`, `выделение объекта действия`,
`синтаксический разбор зависимостей`, `выделение именных групп`,
`поверхностный синтаксический анализ`, `извлечение сущностей без ML`,
`правила на основе шаблонов извлечение`

**ZH:** `语义角色标注`, `谓词论元结构`, `依存句法分析`, `名词短语提取`,
`浅层句法分析`, `基于规则的信息抽取`, `祈使句 分析`

---

## L2 — Detectar interacción entre reglas que no se declaran entre sí

**Pregunta.** ¿Cómo detectan otros dominios conflictos entre conjuntos de
reglas escritos por autores independientes, **sin** que los autores declaren
una relación?

**Por qué.** Es el hallazgo más fuerte de la sesión: el grafo de composición
da 86 aristas en el corpus del autor y **cero** en los cuatro corpus
independientes, porque toda arista exige que un autor nombre otra skill. La
capa mide convención de autoría, no metodología. Ver
[composición muda](docs/evidence/2026-10-23-composition-silent-on-external-corpus/FINDINGS.md).

**Dónde está la literatura.** Éste es el dominio con más trabajo previo de
toda la lista, y casi nada está escrito pensando en agentes: análisis de
conflictos entre reglas de firewall, anomalías en políticas de control de
acceso, consistencia de políticas XACML, verificación de políticas SELinux.
Son décadas de trabajo sobre exactamente el problema de "dos reglas
independientes que se contradicen bajo ciertas condiciones".

**Qué respuesta sirve.** Una taxonomía de tipos de conflicto (sombra,
generalización, correlación, redundancia) que se pueda trasladar a
obligaciones en prosa, con su criterio de decisión explícito.

**RU:** `обнаружение конфликтов политик`, `конфликты правил межсетевого
экрана`, `аномалии правил фаервола`, `анализ политик управления доступом`,
`непротиворечивость политик безопасности`, `верификация политик`,
`shadowing правил`

**ZH:** `策略冲突检测`, `防火墙规则冲突`, `规则异常检测`, `访问控制策略分析`,
`策略一致性验证`, `规则冗余 检测`, `策略 shadowing`

---

## L3 — Extracción normativa fuera del inglés

**Pregunta.** ¿Qué equivalentes funcionales de `MUST` / `SHOULD` / `MAY`
existen en otros idiomas para texto normativo técnico, y hay trabajo sobre
extraer obligaciones de requisitos multilingües?

**Por qué.** Los encabezados más frecuentes de `vantaflow` son franceses
(`bonnes pratiques 2026` en 420 skills, `garde-fous et anti-patterns` en 199)
mientras toda la extracción por encabezado matchea palabras inglesas. Es una
explicación del bajo rendimiento que **no tiene nada que ver con modalidad**,
y amplía la ley: la extracción está calibrada no sólo a las convenciones del
autor sino a las inglesas. Ver [replicación en cinco corpus](docs/evidence/2026-10-23-heldout-replication/FINDINGS.md).

**Qué respuesta sirve.** Saber si RFC-2119 tiene convenciones establecidas en
ruso y chino para documentos técnicos, y si alguien formalizó la equivalencia.
Esto es doblemente útil: resuelve un defecto y además dice si Crucible puede
auditar corpus no anglófonos, que es una pregunta de alcance de producto.

**Nota de método.** En ese corpus idioma y plantilla co-ocurren y no quedaron
separados. Hace falta un corpus no inglés y **no** templado para separarlos.

**RU:** `ключевые слова RFC 2119 перевод`, `ДОЛЖЕН СЛЕДУЕТ МОЖЕТ стандарт`,
`нормативные требования формулировка ГОСТ`, `извлечение требований из текста`,
`многоязычное извлечение информации`, `модальность требований`

**ZH:** `RFC 2119 中文`, `必须 应当 可以 规范用语`, `规范性引用 术语`,
`需求抽取 中文`, `跨语言 信息抽取`, `国家标准 助动词 用法`

---

## L4 — Que un analizador estime su propio recall

**Pregunta.** ¿Cómo estiman los analizadores estáticos cuánto **no** detectan,
sin tener un oráculo de verdad externo?

**Por qué.** Crucible no emite nada para el 54% de un corpus held-out de 1057
skills. El silencio es su salida más frecuente y la menos examinada. Ya
existe el [instrumento ciego de falsos negativos](docs/evidence/2026-10-23-false-negative-frame/FINDINGS.md),
pero es de descubrimiento, no estimador: 24 skills de 1195 sostienen un piso,
no una tasa.

**Qué respuesta sirve.** Métodos de construcción de benchmark con defectos
sembrados que no sean circulares (sembrar lo que ya sabés detectar no mide
nada), y cualquier formalismo para reportar recall con denominador honesto
cuando el universo de defectos no está enumerado.

**RU:** `полнота статического анализатора`, `пропуски статического анализа`,
`оценка качества анализатора`, `мутационное тестирование`,
`внедрение дефектов`, `эталонный набор дефектов`, `ложноотрицательные
срабатывания`

**ZH:** `静态分析 漏报率`, `缺陷检测 召回率`, `变异测试`, `缺陷注入`,
`基准数据集 构建`, `静态分析器 评估`, `漏报 评估方法`

---

## L5 — Redundancia definida por decisión, no por léxico

**Pregunta.** ¿Hay trabajo que defina "dos reglas son redundantes" por la
decisión que cambian, su alcance de activación y su verificación, en vez de
por similitud superficial de texto?

**Por qué.** Éste es un caso donde el chequeo salió **mejor** de lo que creí:
los 337 hallazgos de `SEMANTIC_REDUNDANCY` en `vantaflow` son verdaderos
positivos — el corpus publica cada skill dos veces, con nombre pelado y con
prefijo de categoría. Ver [el seguimiento](docs/evidence/2026-10-23-redundancy-evidence-denominator/FINDINGS.md).
Pero sigue siendo Jaccard léxico, y `COMPETITIVE_BOUNDARY.md` exige
explícitamente definir redundancia por decisión/alcance/check en vez de por
etiquetas de similitud.

**Dato a favor de no tirar lo léxico.** Esos pares tienen nombres declarados
*distintos*, así que el chequeo de colisión de nombres los deja pasar: la
republicación renombrada es invisible a un chequeo de nombres y visible a uno
léxico. Lo que se busque tiene que convivir con eso, no reemplazarlo.

**RU:** `семантическая эквивалентность правил`, `нормализация требований`,
`дублирование требований обнаружение`, `сравнение смысла правил`,
`онтология требований`

**ZH:** `需求重复 检测`, `语义等价 判定`, `规则归一化`, `需求 冲突与冗余`,
`本体 需求建模`

---

## L6 — El espacio de pares, a escala y sin perder determinismo

**Pregunta.** ¿Qué técnicas permiten comparar todos los pares de un corpus
grande sin coste cuadrático, **conservando** reproducibilidad bit a bit?

**Por qué.** `_check_semantic_redundancy` compara los 334.153 pares de un
corpus de 818 skills. Hoy es asequible porque cada comparación es un Jaccard
sobre conjuntos precomputados, pero el auditor ya escala de forma superlineal
(~2,85x por duplicación) y supera al compilador entre 400 y 818 skills. Ver
[el registro de costo](docs/evidence/2026-10-23-cost-scaling/FINDINGS.md).

**La restricción que hace la pregunta interesante.** MinHash y LSH son la
respuesta estándar y son *aleatorizados*. Crucible sella artefactos y exige
reproducibilidad bit a bit entre procesos. Lo que sirve es la variante con
semilla fijada y su análisis de error, o una alternativa determinista.

**RU:** `поиск почти дубликатов`, `локально-чувствительное хеширование`,
`минхеш`, `симхеш`, `дедупликация текстов масштаб`,
`детерминированное хеширование`

**ZH:** `近似重复检测`, `局部敏感哈希`, `MinHash`, `SimHash`, `海量文本去重`,
`确定性 哈希`

---

## L7 — La abstención como estado de primera clase

**Pregunta.** ¿Cómo tratan otros sistemas de decisión el "no puedo responder
esto" como salida legítima, distinta de "no encontré nada"?

**Por qué.** Es la invariante central del producto y la implementamos
nosotros, no la tomamos de ningún lado. Hoy seis de ocho chequeos con
precondición se abstienen en los cinco corpus medidos, y el artefacto ahora
lo reporta. Ver [ADR-0025](docs/decisions/0025-report-unmet-check-preconditions.md).
Valdría saber si existe vocabulario formal para esto que podamos adoptar en
vez de inventar.

**Qué respuesta sirve.** Terminología establecida y, sobre todo, cómo se
**reporta** una abstención a un consumidor downstream sin que la lea como
aprobación. Ése es el modo de falla concreto: la página demo decía "passed
all 28 checks" sobre un resultado donde siete se habían abstenido.

**RU:** `классификация с отказом`, `селективная классификация`,
`отказ от предсказания`, `калибровка уверенности`, `трёхзначная логика
решений`, `неопределённость в системах поддержки принятия решений`

**ZH:** `拒识`, `选择性预测`, `带拒绝选项的分类`, `置信度校准`,
`三值逻辑`, `不确定性 表达`

---

## L8 — Adjudicación a escala sin convertir al modelo en autoridad

**Pregunta.** ¿Cómo se revisan miles de advertencias de analizador sin que el
costo humano lo haga inviable, y sin que un modelo termine decidiendo?

**Por qué.** El [marco de adjudicación](docs/evidence/2026-10-23-adjudication-frame/FINDINGS.md)
selecciona 192 hallazgos de 1015 con k=10, y las dos clases dominantes siguen
siendo muestra, no censo, con cualquier k que probé. Y la restricción dura:
el modelo no puede decidir, por contrato.

**Qué respuesta sirve.** Priorización y muestreo estratificado que *conserve*
el denominador — no que lo esconda. Cualquier cosa que reporte una tasa sin
decir sobre cuántos, no sirve.

**RU:** `приоритизация предупреждений анализатора`, `ранжирование
предупреждений`, `триаж дефектов`, `сокращение ложных срабатываний`,
`стратифицированная выборка оценка`, `разметка с участием человека`

**ZH:** `告警排序`, `警报优先级`, `缺陷 三元组 分流`, `误报 削减`,
`分层抽样 评估`, `人工标注 成本`

---

## L9 — Validar que una reparación cambió la conducta, no sólo el texto

**Pregunta.** ¿Cómo se mide que un cambio en una instrucción cambió de verdad
el comportamiento de un agente, y no sólo silenció al detector?

**Por qué.** Es el gate L7 y hoy descansa en **una** tarea sintética y una
sesión de modelo. El riesgo está nombrado desde el inicio del proyecto: una
reparación que silencia al detector no necesariamente corrige la conducta.

**Qué respuesta sirve.** Diseño de oráculos de propiedad que no sean
tautológicos respecto del detector, y control de confusión cuando el modelo
cambia entre corridas.

**RU:** `оценка агентов на основе LLM`, `воспроизводимость экспериментов с
языковыми моделями`, `A/B тестирование промптов`, `метрики качества
инструкций`, `регрессия поведения модели`

**ZH:** `智能体 评测`, `大模型 可复现性`, `提示词 A/B 测试`,
`行为回归 检测`, `评测 oracle 设计`

---

## L10 — Calidad de instrucción como objeto medible

**Pregunta.** ¿Alguien mide la calidad de una *metodología* escrita —
procedimiento, runbook, checklist, política interna — de forma falsable, fuera
del mundo de los agentes?

**Por qué.** Es la tesis del producto, y el barrido anterior la encontró
vacía dentro del ecosistema de agentes. Pero el objeto "instrucción escrita
que gente sigue y a veces es mala" es mucho más viejo que los LLM: hay
literatura en factores humanos, seguridad operacional, aviación y medicina
sobre calidad de procedimientos y checklists.

**Qué respuesta sirve.** Criterios de calidad de procedimiento que ya hayan
sobrevivido a uso real en dominios donde un procedimiento malo mata gente. Es
la fuente más plausible de criterios que no inventamos nosotros.

**RU:** `качество инструкций`, `разработка регламентов`, `человеческий
фактор процедуры`, `чек-лист проектирование`, `анализ ошибок персонала`,
`стандартные операционные процедуры качество`

**ZH:** `作业指导书 质量`, `标准作业程序 SOP 设计`, `检查表 设计`,
`人因工程 程序`, `操作规程 评估`, `人为差错 分析`

---

## Qué NO investigar

Para proteger el alcance, y porque ya está decidido o registrado:

- **Otro escáner de seguridad.** Eje ocupado y registrado; `COMPETITIVE_BOUNDARY.md`
  lo marca como solapamiento total.
- **Un score escalar de calidad de skill.** Rechazado explícitamente: oculta
  falsos positivos por clase.
- **Registries, firmas, distribución.** Eje ocupado, fuera del límite actual.
- **Meter un modelo en el camino de decisión** para cualquiera de las líneas
  de arriba. Si la única respuesta a una pregunta lo exige, la respuesta es
  registrar el resultado negativo, no cambiar el contrato.

## Cómo registrar lo que encuentres

Mismo formato que el barrido anterior: pregunta, qué contenía el corpus, qué
**no** contenía, queries exactas usadas, y la interpretación separada de la
observación. Un negativo bien delimitado vale tanto como un hallazgo, y es más
frecuente.
