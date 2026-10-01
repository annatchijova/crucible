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

## Principio de construcción

El destino es un sistema completo de verificación de metodología. El tiempo decide hasta qué nivel coherente llegamos; no convierte los niveles no alcanzados en prototipos descartables. Cada nivel debe ser útil, compatible con el siguiente y conservar los invariantes anteriores.

## Licencia

Apache-2.0. Ver [`LICENSE`](LICENSE).
