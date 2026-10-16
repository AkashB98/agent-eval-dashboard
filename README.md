# agent-eval-dashboard

**One page that shows whether your whole agent stack is healthy.**

Every **FDE** — forward deployed engineer, the engineer who ships AI systems into real customer environments — team eventually hits the same wall: the red-team grades live in one repo, the trace-replay verdicts in another, the anomaly-detector findings in a third. Each tool says "I'm fine" in its own language, and nobody can see the fleet. This is the mission-control view: ingest **eval** — a graded test that scores how well an AI system behaves — artifacts from every sibling tool, and get one page with per-project health, **trend** — whether a project's score is improving, steady, or declining across runs — arrows, and a fleet **roll-up** — one combined verdict from many individual checks — of all-green / warning / critical. Every finding carries an **evidence quote** — the exact text snippet that proves a finding — so a red square is never a mystery.

Where it sits in this portfolio's agent-shipping story: `ai-red-teaming-harness` grades safety, `tool-call-trace-replay` catches behavioral drift, `trace-anomaly-detector` watches live sessions, `structured-output-validator` tracks output drift, `prompt-injection-firewall` scans for attacks, `adversarial-prompt-synthesizer` measures attack coverage. **This repo is the capstone**: it aggregates all six into the one health view an FDE team checks every morning. Build the tools → prove they work → watch them all from one dashboard.

## What it does

1. **Adapters** (`adapters.py`) — one per sibling tool, each a translator from that tool's native report into a uniform run summary: a **headline** — the single 0-to-1 number summarizing one run's health — (0.0–1.0, higher is healthier), labeled metrics, a per-category breakdown, and findings that always carry **evidence quotes** — the exact text snippet proving each finding. Headlines are documented per tool (e.g. red-team = safety score, replay = step match rate, validator = pass rate, firewall = detection rate with a **false-positive** — a benign input wrongly flagged as an attack — penalty, synthesizer = fraction of quality checks passing).
2. **Store** (`store.py`) — **idempotent** — safe to ingest twice; the second ingest changes nothing — and **deterministic** — same artifacts always produce byte-identical store state — run ingestion. Each artifact arrives in an **envelope** — a small wrapper labeling the artifact with its tool, run id, and timestamp — gets normalized by its adapter, and is written as **canonical** — one single standardized byte format for the same data — JSON. The **manifest** — an index file listing everything stored — stays sorted, so the whole store has a stable fingerprint (`store_md5()`).
3. **Health model** (`health.py`) — per project: latest run + **trend** — improving / steady / declining across runs — from headline deltas (ε = 0.02). Fleet **roll-up** — one combined verdict: critical if any project is critical; warning if any is warning, declining, or raised a page-worthy alert; all-green otherwise. Critical/high findings surface as fleet alerts with their **evidence quotes** — the exact text proving each finding.
4. **Dashboard** (`dashboard.py`) — zero-dependency inline HTML/**SVG** — a lightweight image format drawn with code — : status cards per tool, headline + **trend** — improving / steady / declining — arrow, an SVG **sparkline** — a tiny trend chart with no axes — of headline history, metric tables, and **drill-down** — click from a summary into the full detail — per-run `<details>` sections. All dynamic strings are HTML-escaped.
5. **CLI** (`cli.py`) — `ingest` / `list` / `summary` / `check` / `demo` / `serve`. `check` exits 0 = all-green, 1 = warning, 2 = critical, 3 = error, so it works as a **CI gate** — an automated check that blocks bad code from shipping. `serve` exposes the dashboard plus a tiny **JSON API** — web endpoints that return data as JSON for other programs — on **localhost** — your own machine; nothing leaves it.
6. **One-command demo** (`demo.py`) — generates **deterministic** — byte-identical on every run — **seeded** — reproducible from a starting number — fictional artifacts for all six tools (invented Helios Home / Helios Cloud sample data only — never anything personal; pages carry a SIMULATED DATA banner), ingests 18 runs, asserts the full pipeline, and smoke-tests the live server. Asserts internally, so it doubles as a smoke test.

## Quickstart

```bash
# one-command end-to-end (deterministic artifacts -> idempotent ingest
# -> fleet health -> live server smoke test)
python3 demo.py

# CI gate: exit 0 = all-green, 1 = warning, 2 = critical
python3 cli.py --store store ingest path/to/redteam-report.json
python3 cli.py --store store check

# human-readable fleet summary
python3 cli.py --store store summary

# serve the dashboard + JSON API on :8767 (localhost only)
python3 cli.py --store store serve --port 8767 --simulated
# GET /                fleet dashboard (HTML)
# GET /run/<run_id>    per-run drill-down (HTML)
# GET /api/status      fleet roll-up (JSON)
# GET /api/runs        run manifest (JSON)
# GET /api/run/<id>    one run summary (JSON)
```

## The demo story (fictional, seeded)

Three runs per tool across two weeks (Oct 1 → Oct 15), all invented Helios sample data:

- **Red-team grades**: safety climbs 0.9286 → 0.9643 → 1.0 (improving, green) — two early misses with **evidence quotes** — exact snippets proving each miss — then clean.
- **Trace-replay verdicts**: one drifted fixture per later run (`step 7 get_order(C-106): expected status=shipped, got status=processing`) — steady, warning.
- **Anomaly findings**: detector health stays 1.0, but run 3 flags a `token_blowup` critical — steady, warning, one fleet alert.
- **Validator drift**: pass rate slides 0.98 → 0.90 → 0.80 (declining, **critical**) — top error class `type_mismatch` ×20 with sample paths and quotes.
- **Firewall scans**: detection 1.0, zero **false positives** — benign inputs wrongly flagged as attacks — (steady, green); blocked attempts shown as info, never alerts — a blocked attack is the firewall *working*.
- **Attack coverage**: quality checks 5/5 → 4/5 when run 3 misses its coverage target (declining, warning).

Fleet rolls up **critical** — `check` exits 2. That is the point of the demo: one regressing tool must be impossible to miss.

## Artifact format

Any tool can feed the dashboard — write one adapter and you are done. An ingested **artifact** — a file a tool produced as output — is an **envelope** — a wrapper labeling the artifact with its tool, run id, and timestamp:

```json
{
  "tool": "ai-red-teaming-harness",
  "run_id": "nightly-2026-10-15",
  "ts": "2026-10-15T09:00:00Z",
  "report": { "...tool-native report..." }
}
```

`run_id` is optional — when absent it is derived from the SHA-256 of the **canonical** — single standardized byte — report bytes, so the same **artifact** — report file — always maps to the same run.

## Health math

- **Trend** — improving / steady / declining — needs ≥ 2 runs (else `new`): `delta = latest.headline − previous.headline`; improving if `delta > 0.02`, declining if `delta < −0.02`, steady otherwise. Deltas are rounded to 9 decimals before comparing (see dev-loop bug 3).
- **Fleet roll-up** — one combined verdict: `critical` if any project is critical; `warning` if any is warning, declining, or raised a critical alert; `all-green` otherwise.
- **CI gate** — automated ship-blocker: `check` exits 0 / 1 / 2 for all-green / warning / critical.

## Tests & evals

- **56/56 hermetic** — fully offline, no network — **unit tests** pass (independently re-run twice). The suite stubs out sockets and runs the full ingest→health pipeline plus `demo.py` (server smoke excluded — localhost only, covered by the real demo).
- **18/18 golden evals** (`evals/run_evals.py`): pinned headlines, thresholds, **trend** — improving / steady / declining — labels, alert counts, evidence presence, ingest idempotency, and dashboard determinism. `evals/eval_report.json` is committed and byte-identical across 3 runs (md5 `c282ab5cd7f01b1bdd6db9f51bbd85de`).

## Dev loop: bugs the tests actually caught

Each one was verified by reverting to the buggy code and watching the test fail, then re-applying the fix:

1. **Status vs severity rank mix-up.** `_worst()` compared project statuses (`green`/`warning`/`critical`) with the *finding-severity* rank map, so any anomaly ingest crashed with `KeyError: 'green'`. The **adapter** — the translator from a tool's report format — test suite caught it on the first run. Fix: a dedicated `STATUS_RANK` map.
2. **Derived run ids never reached the adapters.** `Store.ingest` computed a content-hash run id when the **envelope** — the wrapper labeling an artifact — lacked one, but the adapters read `envelope["run_id"]` directly → `KeyError: 'run_id'`. Fix: normalize the **envelope** — wrapper — (on a copy, never mutating the caller's dict) before extraction.
3. **Float epsilon boundary.** `0.92 − 0.90` is `0.020000000000000004` in floating point, which slipped past the `> 0.02` improving check — a **trend** — improving / steady / declining — misclassification at exactly the boundary. Fix: round the delta to 9 decimals before comparing.
4. **Over-harsh drift threshold.** With 6 steps per baseline, a single drifted step scored 17/18 = 0.944 — just under the 0.95 warning floor, so one drifted fixture read as **critical**. The pinned-threshold test expected `warning`. Fix: the fixture uses 10 steps per baseline (29/30 = 0.967), matching the intended severity — one drifted fixture is a warning, not a fire.

## Design notes

- **stdlib only** — no pip packages, no network in tests. The server is `http.server`; the dashboard is hand-built HTML/**SVG** — code-drawn vector images.
- **Never personal data.** The demo invents all artifacts from **seeded** — reproducible from a fixed starting number — fictional Helios Home / Helios Cloud scenarios. Real deployments ingest real tool reports; the SIMULATED DATA banner marks the difference.
- **Evidence-first.** A status with no quote is a rumor — every finding, alert, and drill-down carries the snippet that produced it.
