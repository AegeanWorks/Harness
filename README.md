# Harness

[![Built with AIKit](https://img.shields.io/badge/built%20with-AIKit-6f42c1)](https://github.com/AegeanWorks/AIKit)

A sandboxed agent harness that turns coding tasks into green test suites with full transcripts and budgets.

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10+ only, no third-party packages.
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
│   │                           r4 injection refusal, r5 delegation, r6 budget death
│   ├── __init__.py
│   ├── check.py
│   ├── r0/
│   ├── r1/
│   ├── r2/
│   ├── r3/
│   ├── r4/
│   ├── r5/
│   └── r6/
├── transcripts/              <- JSONL run logs, replayable from the log alone
│   ├── example.jsonl
│   ├── r0.jsonl
│   ├── r1.jsonl
│   ├── r2.jsonl
│   ├── r3.jsonl
│   ├── r4.jsonl
│   ├── r5.jsonl
│   └── r6.jsonl
├── tests/                    <- escape, transcript, budget-kill, ladder smoke
│   ├── test_escape.py
│   ├── test_transcript.py
│   ├── test_budget_kill.py
│   └── test_ladder.py
└── .aikit/                   <- this project's memory: record, ledger, decisions
```

## Gates

- `python -m pytest tests -q -p no:cacheprovider` stays green.
- `python aikit.py check harness` (from the AIKit folder) stays green.
- `tests/test_escape.py` fails the build if any escape succeeds.
- Every run writes `transcripts/*.jsonl`; replay it with `python -m tools.replay --verify transcripts/example.jsonl --fresh .tmp_replay --starter evals/r3/starter`.

## UI surface (bounded and proof-checked)

- Contract: `.aikit/ui.json`, surface `cli` (`demo.py`, `inventory.py`).
- Fast proof: `python demo.py --scripted --seed 1`; snapshot proof: `python inventory.py`.
- While coding: `python aikit.py ui begin harness --surface cli`, edit only the surface, `python aikit.py ui verify harness`, then `finish` (needs review) or `abort`.

## 📜 License

Free for personal use under the Aegean License 1.1 (AL-1.1); see [LICENSE](LICENSE). Any commercial use needs the Aegean Commercial License 1.0 (ACL-1.0); see [COMMERCIAL.md](COMMERCIAL.md).
