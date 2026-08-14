# Vision-only pipeline — Pha 0 baseline snapshot

Captured at: `2026-08-09T22:12:21+07:00`

Git commit at capture: `c8002c3`

## Runtime snapshot

| Field | Captured value |
| --- | --- |
| Flow | sanitize → Qwen Vision → PostgreSQL resolver; no local dish encoder on `/analyze` |
| Vision model | `qwen3.5-plus` |
| Vision key configured | Yes; value intentionally not recorded |
| Vision prompt SHA-256 | `0bcda60e995ee0f5965f8f1304f2cf91e78fa93adf3e2b6e15069da8abbe563e` |
| Vision prompt length | 3.305 characters |
| Baseline golden intake | `data/eval/catalog_name_resolution_golden.jsonl` (15 cases, 3 source families) |
| Golden status | Family labels reviewed by user on 2026-08-10; PostgreSQL nutrition identities still pending; not sealed |
| PostgreSQL/Qdrant local runtime | Not available at capture because Colima is not running |
| API listener on port 8000 | Not observed at capture |

Source code snapshot:

- Upload security and sanitize: `backend/api/upload_utils.py`.
- Vision-only endpoint: `backend/api/analyze.py`.
- Vision prompt/client: `ml/inference/vision.py`.
- Catalog resolver: `backend/services/dishes.py`.
- Alias/identity guard: `backend/services/catalog_aliases.py` and
  `backend/services/catalog_identity.py`.

## Metrics status

| Metric | Status | Reason |
| --- | --- | --- |
| Vision call rate | Pending | Requires request-level baseline run |
| Catalog auto-resolution precision | Pending | Expected PostgreSQL nutrition identities have not been reviewed |
| Catalog coverage | Pending | Same as above |
| Unresolved rate | Pending | Requires resolver output against expected PostgreSQL identities |
| Dangerous mismatch rate | Pending | Requires expected PostgreSQL UUIDs and resolver output |
| Vision p50/p95 latency | Pending | Requires timed live calls to configured provider |
| Cost per request | Pending | Requires provider billing price/source at measurement time |

No metric has been invented or copied from the retired EfficientNet/SigLIP
pipeline. Historical local-recognition reports are not evidence for this
Vision-only baseline.

## Pilot Vision capture after runtime recovery

After the snapshot, Colima and the local PostgreSQL/Qdrant services were started.
PostgreSQL contained 834 `vn_dishes` rows; exact catalog rows `Phở bò chín`,
`Bánh canh thịt heo` and `Há cảo` were present. Qdrant `/healthz` passed.

A raw-name capture called Vision once for every intake image. Raw output is
saved in `data/eval/catalog_name_resolution_phase0_raw_capture.jsonl`.

| Pilot measure | Observed value |
| --- | ---: |
| Planned intake | 15 images |
| Images sent to Vision | 15 |
| Provider success | 15 / 15 |
| Timed-call latency p50 (first six only) | 4.957,4 ms |
| Timed-call latency p95, nearest-rank (first six only) | 5.355,5 ms |
| Raw-name family agreement with user-reviewed label | 6 / 15 (40%) |

On 2026-08-10, the user reviewed all 15 intake images and confirmed that their
source family labels are correct. In this small set, Vision matched all five
Phở bò inputs and one Há cảo chiên variant; it mismatched all five Bánh canh
inputs and four Há cảo inputs. The final nine calls were intentionally not
repeated solely to collect latency, so their latency is recorded as unknown.
This remains a small, non-sealed baseline, not a final Vision accuracy result.

The pilot confidence was `0.92` for all six cases. It must not be interpreted
as a calibrated accuracy measure.

## Completion conditions for the remaining baseline run

1. Start local PostgreSQL/Qdrant and verify the intended catalog snapshot.
2. Resolve expected nutrition item UUIDs from PostgreSQL for every reviewed
   family label.
3. Freeze reviewed cases as a sealed golden version; do not mutate it while
   tuning a later resolver/model.
4. Execute Vision once per golden input, persist raw names, resolver outcome,
   latency and model/prompt/catalog versions.
5. Compute the metrics listed above and save a machine-readable JSON report.

The next phase must not treat this snapshot as a completed performance result.
