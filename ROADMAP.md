# Original eight-feature roadmap and current evidence

The owner supplied the following original feature titles in task 004F. These product features are
separate from engineering task IDs such as 004A–004F. The titles do not include detailed original
acceptance criteria, so the status below is scoped to the documented prototype and tested behavior,
not a claim that every possible interpretation of the hackathon roadmap is complete.

| Original feature | Prototype status | Implementation and tests | Remaining scope/limitations |
| --- | --- | --- | --- |
| 1. Document ingestion | COMPLETE for supported prototype formats | `services/evidence.py`, case routes; `test_cases.py`, browser uploads | CSV/labeled text PDF only; no arbitrary layouts/OCR |
| 2. Financial-data normalization | COMPLETE for documented schema | `extraction/`; `test_extraction.py` | Supported currencies, Decimal precision/rounding rules, explicit missing/ambiguous fields |
| 3. Cross-document verification | COMPLETE for documented deterministic rules | `verification/`, `services/verification.py`; invoice/PO API/unit/browser tests | Conservative matching, per-invoice comparisons; no cumulative PO utilization |
| 4. Duplicate-financing detection | PARTIAL: potential recorded-dataset conflicts implemented | `claims/engine.py`, claim routes; `test_claims.py`, browser conflict journey | Recorded assertions do not independently establish actual financing; no external registry coverage |
| 5. Discrepancy/anomaly detection | COMPLETE for documented deterministic checks | Extraction validation, verification and claim conflicts; mismatch/failure tests | No general statistical/predictive anomaly model |
| 6. Evidence-provenance graph | PARTIAL: traceable relationships implemented | Document/extraction/provenance IDs, finding observations, claim/investigation links; provenance tests/UI | No dedicated graph exploration/visualization API or graph UI |
| 7. Meta-powered AI investigation | PARTIAL: adapter and grounded orchestration implemented | `investigations/`, persisted snapshots, strict validation; offline provider tests | Successful live Meta inference remains unvalidated because billing is restricted; mock results are test-only |
| 8. Evidence-based risk scoring and decisions | COMPLETE for minimum categorical human-review support | `risk/`, read-only risk service/API and case UI; `test_risk.py`, complete-demo/browser tests | Categorical evidence indicators only; no numerical predictive score or automatic financing decision; no persisted risk-assessment history |

Feature 8 reuses existing findings and exposes explicit uncertainty. No low-risk/creditworthiness,
fraud, legal ownership or approval/rejection conclusion is inferred. Every assessment requires human
review. [RISK.md](apps/api/RISK.md) specifies rules, source references, freshness and replay behavior.

The minimum categorical Feature 8 work is implemented in task 004F. The broader roadmap remains
partial for Features 4, 6 and 7 under the limits above. The owner must confirm whether graph exploration
or independently substantiated financing were intended acceptance criteria rather than additional
scope. Do not add external registries or speculative risk predictions merely to change these labels.
Live Meta validation requires billing resolution and separate explicit authorization; it must not be
run during restricted/offline tasks. License and dependency-release decisions remain separate from
feature implementation.
