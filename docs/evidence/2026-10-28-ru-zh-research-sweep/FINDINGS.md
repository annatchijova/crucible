# Barrido RU/ZH 2026-10-28 sobre la agenda L1–L10: registro y revisión

**Fecha:** 2026-10-28
**Responde a:** [`INVESTIGAR-CRUCIBLE.md`](../../../INVESTIGAR-CRUCIBLE.md)
**Procedencia:** el barrido lo hizo otro asistente (Kimi) con búsqueda web. El
informe está transcripto sin cambios en [`SWEEP.md`](SWEEP.md). Esta página es
una revisión posterior hecha sin volver a buscar: contrasta el informe con el
estado del repositorio y marca qué afirmaciones dependen de fuentes que nadie
del proyecto abrió.

**Estado epistémico.** Ninguna cita del informe fue verificada contra su fuente
original. Los números atribuidos a terceros (umbrales del ГОСТ, porcentajes del
blog sobre A/B, resultados de NeurIPS) son **afirmaciones del informe**, no
hechos registrados por el proyecto. Antes de citarlos en una superficie pública
hay que abrir la fuente.

Corrección menor del informe: cita la agenda como
`docs/evidence/2026-10-24-research-agenda`; la agenda está en
`INVESTIGAR-CRUCIBLE.md`, en la raíz.

## Resultado por línea, contrastado con el repositorio

| Línea | Informe | Revisión | Acción |
|---|---|---|---|
| L1 | [−] | Coincide con ADR-0027: toda ruta con SRL o dependencias publicada pone un modelo estadístico en el camino. Negativo registrable. | Ninguna antes de la entrega. ADR-0027 queda vigente. |
| L2 | [+] bloqueada en L1 | La taxonomía (shadowing, redundancia, correlación, generalización) es la de la literatura de firewalls; el corpus ZH la repite. La transferencia exige la tupla (condición, acción), que es L1. | Registrar como modelo de chequeo futuro. No implementable mientras L1 siga cerrado. |
| L3 | [+] | El mapeo RU es una lista cerrada, del mismo tipo que la inglesa. No hay corpus RU no templado para medir falsos positivos, y la nota de método de la agenda sigue abierta. | Fuera de alcance para la entrega. |
| L4 | [+] | El marco de reporte (muestra primaria + expansión, denominador explícito) es compatible con el instrumento ciego existente. Los valores concretos (≥10, ×10, número de sección) **no están verificados**. | Verificar el texto del ГОСТ Р 71207 antes de citarlo. |
| L5 | [−] | Coincide con `COMPETITIVE_BOUNDARY.md`: redundancia por decisión, alcance y verificación no aparece. La advertencia sobre sobre-fusión por encadenamiento aplica a L16, que ya agrupa por componentes conexos. | Ninguna. |
| L6 | [+] | Ver la sección siguiente: el informe resuelve la reproducibilidad pero no la equivalencia de salida. | **Implementado el mismo día** con filtrado por prefijo exacto: [registro](../2026-10-28-prefix-filter-redundancy/FINDINGS.md). |
| L7 | [+] | La propuesta principal (nombrar la abstención en la UI y dejar de decir "passed 28") **ya está implementada** en `d9dca37`, cuatro días antes del barrido. Lo nuevo es el vocabulario (*selective classification*, *coverage*, *reject option*) y la regla de que toda abstención declare una salida. | Opcional: usar "coverage" en la UI. La salida declarada ya existe en parte: cada chequeo abstenido nombra la entrada que requiere. |
| L8 | [+] | El triaje en tres vías (e-TP / I / e-FP) es compatible con el contrato si el modelo sólo ordena. La advertencia sobre *leakage* (replicación de Kang, Aw y Lo) es la pieza más sólida y la más fácil de verificar. | Registrar como criterio de aceptación para cualquier priorización futura. |
| L9 | [~] | La replay contra una línea base grabada coincide con lo que la corrida L16 del 2026-10-24 hizo a mano: mismo cluster, mismo digest, dos veces. Los porcentajes atribuidos al blog **no están verificados**. El oráculo no tautológico sigue abierto. | Ninguna antes de la entrega. |
| L10 | [~] | Es la línea más útil para la tesis y confirma el hueco fuera del ecosistema anglófono: hay guías de diseño de procedimientos, pero no auditoría del texto. Los criterios FAA y Gawande se pueden convertir en chequeos, pero cada uno sería un chequeo nuevo con su propia evidencia. | Puede citarse como contexto, con fuente, y no como validación del producto. |

## L6: reproducible no es lo mismo que equivalente

El informe concluye que MinHash con semilla fija más bandas LSH es reproducible
bit a bit. Es correcto, pero no es la restricción completa. `_check_semantic_redundancy`
emite un hallazgo por cada par con Jaccard ≥ 2/3, calculado con `Fraction`. Un
LSH bandado es reproducible, pero **pierde pares por diseño**: qué hallazgos
aparecen pasaría a depender de `num_perm`, `b` y `r`. El artefacto sellado
seguiría siendo idéntico entre corridas, pero dejaría de ser el mismo artefacto
que hoy, y la tasa de pérdida necesitaría su propio denominador.

El informe deja como "hueco a buscar en EN" la alternativa exacta, que es
conocida: **filtrado por prefijo** para joins de similitud de conjuntos
(familia AllPairs/PPJoin). Con un orden global fijo de tokens, dos conjuntos con
Jaccard ≥ t tienen que compartir al menos un token entre los primeros
`|x| − ⌈t·|x|⌉ + 1` de cada uno. Indexar sólo esos prefijos genera un
superconjunto de los pares calificados, y verificar cada candidato con el
Jaccard exacto actual da **exactamente** los mismos hallazgos. Es determinista
sin semilla y no usa aritmética flotante si el límite se calcula con `Fraction`
o con enteros.

Esto viene del conocimiento de quien escribe esta revisión, no del corpus
barrido. Falta medirlo: cuántos candidatos genera sobre `vantaflow` frente a los
334.153 pares actuales, y confirmar sobre los cinco corpus sellados que los
hallazgos son idénticos byte a byte. **Actualización, mismo día:** implementado y medido. El digest es idéntico en `vantaflow` y `mukul975`, y los pares comparados bajan de 239.086 a 4.131 y de 334.153 a 10.653. Ver el
[registro](../2026-10-28-prefix-filter-redundancy/FINDINGS.md).

## Qué no cambia

- Ninguna línea produjo una técnica que exija meter un modelo en el camino de
  decisión. Las piezas adoptables son taxonomías, reglas de muestreo,
  vocabulario y protocolos.
- No hay afirmación nueva de producto que salga de este barrido. Lo que confirma
  el hueco (L5, L10) lo confirma en el corpus buscado, con la misma salvedad del
  [barrido del 2026-10-04](../2026-10-04-ru-zh-corpus-sweep/FINDINGS.md): "no
  observado en el corpus buscado", no "novedoso".
