# Harness

[![Built with AIKit](https://img.shields.io/badge/built%20with-AIKit-6f42c1)](https://github.com/AegeanWorks/AIKit)

A sandboxed agent harness that turns coding tasks into green test suites with full transcripts and budgets.

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10+ only, no third-party packages.
- **One-click start** (from `projects/harness`):
  ```bash
  python start.py --check     # gates: python, loopback, pytest, providers
  python start.py             # serves the board UI, auto-opens the browser
  ```
  Double-click `start.cmd` on Windows. First run shows Setup (`/`):
  provider picker, key SET/MISSING dots (env only, never values),
  task box, Run. Restart is one click.
- **Providers** (config entry, not code change): `providers.json` holds two
  OpenAI-compatible entries (`openai-compat` + `local-compat`). A new one
  costs one JSON object; keys live in env (`OPENAI_API_KEY`, …). Swap
  mid-task via `/settings`; the run survives through `wait` + fallback.
- **Canonical Regression Shield Gate**:
  ```bash
  python -m pytest tests -q -p no:cacheprovider
  ```
- **Agent smoke** (run from `projects/harness`):
  ```bash
  python -m evals.check all
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status harness` |
| Phase 4: every gate | `python aikit.py check harness` |
| Repair memory and map, then check | `python aikit.py fix harness` |
| Resume an interrupted task | `python aikit.py resume harness` |

## 📦 What's Inside

```text
harness/
├── .gitignore
├── COMMERCIAL.md
├── LICENSE
├── LICENSES/
├── REUSE.toml
├── README.md
├── demo.py                   <- AI-compat scripted drive: WORLD-DELTA lines (ADR-315)
├── inventory.py              <- AI-compat inventory: kind|name|locator lines (ADR-315)
├── start.py                    <- one-click: --check, serve board UI (ADR-007)
├── start.cmd                   <- Windows one-click wrapper (ADR-007)
├── ui_server.py                <- board UI: /, /run, /runs, /tools, /settings (ADR-007)
├── providers.json              <- two OpenAI-compat entries, no secrets (ADR-007)
├── config.example.json         <- local-only template; real config.local.json ignored
├── providers/                  <- registry + LLM policy with fallback (ADR-007)
│   ├── __init__.py
│   ├── providers.py
│   └── policy.py
├── harness/                  <- agent loop, budget, transcript, kill switch
│   ├── __init__.py
│   ├── loop.py
│   ├── budget.py
│   ├── transcript.py
│   └── kill.py
├── sandbox/                  <- filesystem jail + network shim
│   ├── __init__.py
│   └── jail.py
├── tools/                    <- read/edit/exec/test/web/delegate/replay
│   ├── __init__.py
│   ├── io.py
│   ├── runner.py
│   ├── web.py
│   ├── delegate.py
│   └── replay.py
├── evals/                    <- r0 read-only, r1 fix, r2 rename, r3 debug,
│   │                           r4 injection refusal, r5 delegation, r6 budget death,
│   │                           r7 hallucinated-tool refusal, r8 failover, r9 warmup
│   ├── __init__.py
│   ├── check.py
│   ├── r0/
│   ├── r1/
│   ├── r2/
│   ├── r3/
│   ├── r4/
│   ├── r5/
│   ├── r6/
│   ├── r7/
│   ├── r8/
│   └── r9/
├── transcripts/              <- JSONL run logs, replayable from the log alone
│   ├── example.jsonl
│   ├── r0.jsonl
│   ├── r1.jsonl
│   ├── r2.jsonl
│   ├── r3.jsonl
│   ├── r4.jsonl
│   ├── r5.jsonl
│   ├── r6.jsonl
│   ├── r7.jsonl
│   ├── r8.jsonl
│   └── r9.jsonl
├── tests/                    <- escape, transcript, budget-kill, ladder smoke
│   ├── test_escape.py
│   ├── test_transcript.py
│   ├── test_budget_kill.py
│   ├── test_ladder.py
│   ├── test_start.py
│   ├── test_providers.py
│   └── test_ui_pages.py
├── shots/                    <- board screenshots S1-S5 before/after (ADR-007)
└── .aikit/                   <- this project's memory: record, ledger, decisions
```

## Gates

- `python -m pytest tests -q -p no:cacheprovider` stays green.
- `python aikit.py check harness` (from the AIKit folder) stays green.
- `tests/test_escape.py` fails the build if any escape succeeds.
- Every run writes `transcripts/*.jsonl`; replay it with `python -m tools.replay --verify transcripts/example.jsonl --fresh .tmp_replay --starter evals/r3/starter`.

## UI surface (bounded and proof-checked)

- Contract: `.aikit/ui.json`, surfaces `cli` (`demo.py`, `inventory.py`)
  and `board` (`start.py`, `ui_server.py`).
- Fast proof: `python demo.py --scripted --seed 1`; snapshot proof: `python inventory.py`.
- Board smoke: `python ui_server.py --smoke --port 8765 --seed 1 --fixture r3`
  (all five routes 200, POST /stop + /clear + /replay verified, fixture-masked). Shots live in `shots/`.
- While coding: `python aikit.py ui begin harness --surface board`, edit only the surface, `python aikit.py ui verify harness`, then `finish` (needs review) or `abort`.

## 📜 License

Free for personal use under the Aegean License 1.1 (AL-1.1); see [LICENSE](LICENSE). Any commercial use needs the Aegean Commercial License 1.0 (ACL-1.0); see [COMMERCIAL.md](COMMERCIAL.md).
