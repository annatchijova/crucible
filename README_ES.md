# Crucible

**Ingeniería de verificación para metodologías de agentes de IA — construido sobre Nebius AI Cloud con NVIDIA Nemotron.**

[English](README.md) · **Español** · [Technical README](TECHNICAL.md)

![Logo de Crucible](visual/logo.png)

> **Estado: en progreso — primero el contrato arquitectónico y de evaluación.**

Las skills de agentes son metodología ejecutable: cambian qué detecta, prioriza, verifica y hace un agente de coding. Ya existen herramientas para validar su forma, buscar comportamiento malicioso y medir si un agente rinde mejor con ellas. Falta una pregunta más difícil:

> **¿La metodología es coherente, verificable, componible y realmente vale la pena agregarla al corpus?**

Crucible busca responderla con evidencia estructurada, no con un puntaje opaco.

## Construido con

| Herramienta | Rol |
|---|---|
| **Nebius AI Cloud** | Ejecución del modelo para el harness diferencial conductual (L5) y la confirmación semántica (L2.5) |
| **Nebius Token Factory** | Autenticación y gestión de tokens para inferencia |
| **NVIDIA Nemotron** (`nvidia/nemotron-3-super-120b-a12b`) | Genera el comportamiento observado por oráculos deterministas y confirma findings de auditoría |

El modelo es **causal para el experimento**, no un narrador. Genera el comportamiento que observan los oráculos deterministas; el LLM nunca decide findings, sellos ni veredictos.

## Por qué existe ahora

Las Agent Skills se están convirtiendo en infraestructura. NVIDIA ya está construyendo infraestructura seria alrededor de ellas: SkillSpector cubre riesgos de seguridad y supply chain; SkillEvaluator cubre validación, overlap semántico, datasets sintéticos y evaluación live de agentes; y el catálogo NVIDIA agrega Skill Cards, firmas, benchmarks y gates de publicación. Queremos esos controles. CRUCIBLE no existe porque sean insuficientes o irrelevantes, sino porque no agotan la pregunta metodológica.

> **Una skill no necesita ser maliciosa para ser una mala metodología. Puede ser perfectamente benigna y aun así enseñar a un agente a construir mal.**

Ejemplo:

```text
Skill A: reintentar operaciones fallidas hasta tener éxito.
Skill B: las acciones irreversibles deben ser acotadas y revisables.

Ninguna es necesariamente maliciosa por separado.
La composición falla cuando el objetivo del retry es irreversible y no idempotente.
```

CRUCIBLE intenta hacer ese tipo de afirmación inspeccionable, condicional y falsable. Es una capa complementaria de verificación metodológica, no un reemplazo de un security scanner ni de un evaluator conductual. Ver la [frontera competitiva](docs/COMPETITIVE_BOUNDARY.md).

## La idea en un ejemplo

Dos skills pueden parecer razonables por separado y producir una composición incorrecta:

```text
Skill A: reintentar operaciones críticas hasta que tengan éxito.
Skill B: las operaciones irreversibles deben tener efectos acotados y revisables.

Plausibles por separado → composición insegura cuando el retry duplica un efecto irreversible.
```

Crucible extrae reglas declaradas, scopes, triggers, checks, referencias y aristas de composición; después audita contradicciones, verificaciones ausentes, redundancia, provenance rota y resistencia a mutaciones.

## Estado del documento

Esta versión es una adaptación de trabajo en español. La especificación pública y el roadmap canónico están en inglés; el plan operativo en español se mantiene local e ignorado por Git para poder iterarlo durante el hackathon.

Ver el detalle completo en el [Technical README](TECHNICAL.md) y el mapa de construcción en [ROADMAP.md](docs/ROADMAP.md).

## Estado de implementación

Ya existen 14 niveles coherentes. L1 transforma un corpus real en una Skill IR versionada, con source spans y digest SHA-256 determinista; L2 implementa 28 checks de metodología e ingeniería; L3 modela composición tipada; L4 prueba el auditor con 8 mutaciones (6/6 KILLED en alcance, 2 ABSTAINED fuera de alcance); L5–L7 cubren diferencial conductual, reparación y replay; L8 integra CI, reportes sellados y viewer HTML; L9–L13 agregan extracción style-agnostic, taxonomía de defectos de ingeniería, API pública, confirmación Nemotron y validación corpus-agnóstica; L14 verifica la frontera real de Nebius, la activación causal y la completitud de respuestas.

La capa de confirmación L2.5 toma todos los CANDIDATEs del audit L2 y pregunta a un executor (Nemotron vía Nebius, o mock determinista) si cada uno es un defecto real o un falso positivo. La confirmación es un artifact separado (`crucible-confirmation/v1`) con su propio digest SHA-256; el audit L2 nunca se modifica. Si `NEBIUS_API_KEY` no está configurada, la ejecución se reporta como BLOCKED, no simulada.

## Ejecución y cobertura actual

```bash
pip install -e ".[test]"
PYTHONPATH=src python3 -m pytest -q
# Una skill desde stdin
PYTHONPATH=src python3 -m crucible.cli --scan-skill < SKILL.md
# Un repositorio local: auditoría conjunta y grafo
PYTHONPATH=src python3 -m crucible.cli ruta/al/repositorio
# Instaladas con prioridad histórica por nombre y cobertura explícita
PYTHONPATH=src python3 -m crucible.cli --scan-installed --include-coverage
# Paquetes anidados y homónimos auditados independientemente
PYTHONPATH=src python3 -m crucible.cli --scan-installed-collection
# Reporte local y visualización
PYTHONPATH=src python3 -m crucible.cli --report --local-executor > report.json
PYTHONPATH=src python3 -m crucible.cli --view report.json > report.html
```

La colección busca en los directorios estándar configurados de Claude, Devin y
`~/.codex/skills`. Conserva rutas de origen y errores por paquete en un reporte
sellado; no evalúa composición entre paquetes. Cobertura parcial o vacía devuelve
código de salida 1. Las rutas personalizadas y cachés externas de plugins todavía
no se descubren automáticamente.

El modo antiguo `--scan-installed` conserva la prioridad por nombre y copia
temporalmente solo los `SKILL.md`, manteniendo rutas anidadas y verificando la
identidad de origen. Las identidades de raíz y directorios registradas al listar
se conservan al abrir los paquetes seleccionados; los reemplazos detectados
abortan. Admite hasta 500 archivos de skills, 20 MB acumulados y
1 MB por archivo; no copia adjuntos ajenos al análisis. La enumeración inicial y
el descubrimiento de paquetes comparten un presupuesto de origen de 100.000
entradas y 10.000 directorios entre todas las raíces. Las entradas se cuentan
antes de ordenar, incluidos archivos ajenos y candidatos duplicados; las raíces
vacías también consumen presupuesto de directorios.

Límites de la colección: 500 entradas de reporte, 100.000 entradas descubiertas
(incluidos archivos ajenos), 10.000 directorios admitidos, 1 MB por skill y
20 MB acumulados de entrada, compartidos entre raíces. En plataformas POSIX compatibles, el modo
colección fija descriptores de directorio y rechaza symlinks en cada componente
de la ruta. Lee sin bloquearse en FIFO y con límite de bytes; rechaza cambios
observados de tamaño o timestamps. El compilador de repositorios ahora comparte
esta lectura acotada (1 MB por archivo), conservando rutas de origen relativas.
Todavía resuelve la raíz antes de descubrir archivos: admite aliases symlink de
esa raíz. El descubrimiento del repositorio enumera descriptores de directorio
fijados, abiertos sin seguir symlinks. Registra dispositivo/inode de la raíz,
directorios descubiertos y archivos de skills; los contrasta con los descriptores
antes de enumerar o leer y aborta ante reemplazos detectados. No es una instantánea:
la reutilización de inodes y los cambios de contenido sobre el mismo inode entre
descubrimiento y apertura quedan fuera de esa comprobación.
La colección instalada también enumera descriptores fijados y verifica las
identidades registradas antes de leer. Los symlinks y puntos de entrada inválidos
se reportan como errores; los errores por directorio conservan cobertura parcial
y vecinos válidos. El reporte se ordena por ruta de origen.
El compilador de repositorios
limita la entrada acumulada a 20 MB, los directorios a 10.000 (incluida la raíz)
y las entradas descubiertas a 100.000 (incluidos archivos ajenos a las skills).
Los errores de enumeración abortan la compilación; estos presupuestos rigen
incluso sin límite explícito de cantidad de skills. No representa una instantánea
del filesystem.

Hay un diferencial conductual real guardado, con el mutante distinguible del
original y la reparación. Otra ejecución real de confirmación devolvió 2 apoyos
y 12 rechazos, sin truncación; su artefacto completo no se guardó. Esas opiniones
del modelo no son etiquetas verdaderas. Falta evidencia real del loop de reparación
con proponente LLM. Ver [próximos niveles](docs/NEXT_LEVELS.md).

## Principio de construcción

El destino es un sistema completo de verificación de metodología. El tiempo decide hasta qué nivel coherente llegamos; no convierte los niveles no alcanzados en prototipos descartables. Cada nivel debe ser útil, compatible con el siguiente y conservar los invariantes anteriores.

## Licencia

Apache-2.0. Ver [`LICENSE`](LICENSE).
