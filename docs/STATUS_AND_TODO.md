# Crucible Skills — Estado y Pendientes

**Fecha original:** 2026-09-24 (actualizado 2026-10-01, ver nota abajo)
**Base:** main @ 1fe6361
**Tests:** 411 pasan originalmente — **655 pasan al 2026-10-01** (R3, R4, y L15 se agregaron después de esta fecha; ver TECHNICAL.md para el estado nivel por nivel actualizado, esta tabla quedó vieja)

---

## Lo que está hecho

13 niveles coherentes completos, todos con tests falsificables, determinismo
verificado cross-process, y sellado SHA-256:

| Nivel | Qué hace | Estado |
|-------|----------|--------|
| L1 | Compilador de corpus a Skill IR versionada | Completo |
| L2 | Auditor determinista con 28 checks | Completo |
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
| R4 | Private repair evidence capture | Core implementado, corrida en vivo pendiente — ver docs/REPAIR_EVIDENCE.md |
| L15 | Recomendación determinística + narrador LLM | Core implementado y corrido en vivo contra Nebius 2026-10-01; faltan MD/PDF/HTML del reporte final — ver docs/red-team/2026-10-01-l15-recommendation-narrator-review.md |

Red team L11 completado: 5 hallazgos encontrados y arreglados (RT-01 a RT-05),
1 hipótesis falsificada (RT-06), invariantes verificados (RT-07).

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

Componentes afectados (ya probados contra Nebius real salvo lo anotado
arriba):
- L5 behavioral differential (NebiusExecutor) — probado
- L2.5/L12 confirmation layer (NebiusConfirmExecutor) — probado
- L6 Bob LLM proposer (LLMProposer) — NO probado en esta sesión
- L7 repair loop (NebiusExecutor + LLMProposer) — NO probado en esta sesión

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
- Corpus OSS independiente (false-positive pressure real)
- Corpus NVIDIA verified skills (interoperabilidad)
- Documentar licencias de cada corpus

**5. Política de CI gate**

El CI corre tests y genera el reporte, pero no bloquea merges. Falta definir:
- ¿Qué pasa = merge bloqueado?
- ¿Findings CANDIDATE bloquean? ¿Solo CONFIRMED?
- ¿Mutation kill rate mínimo?

**6. Feedback sobre tools/models**

Requisito del hackathon. No existe. Notas operativas honestas sobre:
- Nemotron en la práctica (latencia, estabilidad, calidad)
- Token Factory API (errores, rate limits)
- Diferencia entre local executor y Nemotron real

**7. Pre-existing project disclosure**

Requisito del hackathon si el proyecto existía antes del periodo de submission.
Hay que escribir qué se hizo durante el hackathon vs. qué preexistía.

### P2 — Mejoras técnicas conocidas

**8. Mutation survivors — cerrar los 2 que sobrevivieron**

L4 tiene 2 mutaciones que sobreviven (SURVIVED):
- `EXCEPTION_REMOVAL`: la IR no extrae excepciones (INSUFFICIENT_REPRESENTATION)
- `EDGE_REMOVAL`: el auditor detecta edges rotos pero no faltantes
  (INSUFFICIENT_DETECTOR)

Cerrarlos requiere extender la IR (extraer excepciones) o agregar un check
de edges faltantes. Ambos son cambios no triviales al compiler y al auditor.

**9. TUI pulida**

El viewer HTML existe y es read-only, pero no hay TUI interactiva. El CLI
es funcional pero produce JSON crudo. Un TUI mejoraría la demo.

**10. Runtime activation traces**

No hay traces de qué skill se activó en qué momento durante el behavioral
differential. El reporte dice qué variante corrió pero no cómo el modelo
interpretó la skill.

**11. Model/provider integration — estabilidad cross-version**

No se verificó que las observaciones conductuales sean estables across
versiones del modelo. El plan lo lista como limitación conocida.

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
P1 (calidad):              corpus externo, CI gate, feedback, disclosure
P2 (mejoras técnicas):     mutation survivors, TUI, traces, cross-version
P3 (deferido):             firmas, viewer pulido, corpus completo
```

El proyecto tiene 13 niveles completos con 411 tests, red team hecho y
arreglado, y arquitectura determinista con LLM fuera del path de decisión.
El bloqueador principal es conseguir la API key y ejecutar el pipeline
completo con Nemotron real — sin eso, no hay submission válida.
