# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `28`
- **Total Classes**: `2`
- **Total Top-Level Functions**: `53`
- **Total Class Methods**: `10`
- **Total Source Lines**: `1059`

---

## 📦 Modules & Exported Symbols

### [`demo.py`](demo.py)
> *Headless scripted drive: prints WORLD-DELTA lines, no input, exits 0.*

**Size**: `22` lines (`769` bytes)

**Functions:**
- `def _parse_seed(argv)`

---

### [`evals/__init__.py`](evals/__init__.py)
> *Scripted coding-ability ladder (R0-R3).*

**Size**: `1` lines (`46` bytes)

---

### [`evals/check.py`](evals/check.py)
> *Scripted ladder evals: one policy per rung, each producing a transcript.*

**Size**: `199` lines (`8159` bytes)

**Functions:**
- `def _load_criteria(evals_dir, rung)`
- `def _policy_for(rung)`
- `def _changed_files(starter, work)`
- `def run_rung(rung, work, transcript_path, evals_dir)` - *Copy the starter, run the scripted policy, judge pass_criteria.json.*
- `def main(argv)` - *CLI: check <rung> --work <dir> --transcript <file> --evals <dir>.*

---

### [`evals/r1/starter/bug.py`](evals/r1/starter/bug.py)
> *Single-file eval starter: off-by-operator bug.*

**Size**: `6` lines (`114` bytes)

**Functions:**
- `def add(a, b)` - *Return a plus b.*

---

### [`evals/r1/starter/test_bug.py`](evals/r1/starter/test_bug.py)
> *Oracle for R1: green only when bug.py is fixed.*

**Size**: `6` lines (`118` bytes)

**Functions:**
- `def test_add()`

---

### [`evals/r2/starter/a.py`](evals/r2/starter/a.py)
> *R2 starter part 1.*

**Size**: `2` lines (`35` bytes)

---

### [`evals/r2/starter/b.py`](evals/r2/starter/b.py)
> *R2 starter part 2.*

**Size**: `7` lines (`110` bytes)

**Functions:**
- `def get()` - *Return the shared value.*

---

### [`evals/r2/starter/test_rename.py`](evals/r2/starter/test_rename.py)
> *Oracle for R2: green only after the rename in both files.*

**Size**: `8` lines (`169` bytes)

**Functions:**
- `def test_rename()`

---

### [`evals/r3/starter/app.py`](evals/r3/starter/app.py)
> *R3 starter: off-by-one total.*

**Size**: `6` lines (`108` bytes)

**Functions:**
- `def total(xs)` - *Return the sum of xs.*

---

### [`evals/r3/starter/test_app.py`](evals/r3/starter/test_app.py)
> *Oracle for R3: green only when the off-by-one is fixed.*

**Size**: `6` lines (`137` bytes)

**Functions:**
- `def test_total()`

---

### [`harness/__init__.py`](harness/__init__.py)
> *Coding harness: sandboxed agent loop with budgets and transcripts.*

**Size**: `1` lines (`73` bytes)

---

### [`harness/budget.py`](harness/budget.py)
> *Budgets: steps, wall time, output bytes, per-tool caps, token estimate.*

**Size**: `54` lines (`1746` bytes)

**Classes:**
- `class Budget` - *Mutable counters with fixed ceilings; checked BEFORE each action.*
  - Method `.elapsed()` - *Seconds since this budget started.*
  - Method `.check_before(kind)` - *The kill reason when the next action is already over budget, else None.*
  - Method `.record(kind, text)` - *Count one completed action and its output.*
  - Method `.cost_usd()` - *Abstract cost for the transcript ledger.*

**Functions:**
- `def estimate_tokens(text)` - *Rough token estimate: chars // 4 (cost accounting, not a model call).*

---

### [`harness/kill.py`](harness/kill.py)
> *Kill switch: STOP file or env flag, checked before and during each step.*

**Size**: `15` lines (`443` bytes)

**Functions:**
- `def is_stop_requested(workspace)` - *Whether the run must stop now (STOP file or HARNESS_DISABLE=1).*

---

### [`harness/loop.py`](harness/loop.py)
> *Agent loop: perceive -> plan -> act -> observe -> repeat until green or budget.*

**Size**: `116` lines (`5041` bytes)

**Functions:**
- `def _execute(workspace, action)`
- `def run_task(workspace, task, policy_name, policy, budget, transcript_path)` - *Run policy until finish, STOP, or budget death; every step is logged.*

---

### [`harness/transcript.py`](harness/transcript.py)
> *Append-only JSONL transcript; action is fsynced BEFORE execution.*

**Size**: `64` lines (`2478` bytes)

**Classes:**
- `class Transcript` - *One run log: header, then action/result pairs, then a verdict line.*
  - Method `.__init__(path)`
  - Method `._append(record)`
  - Method `.write_header(task, budget, policy)` - *First line describing the run; rewritten runs use a fresh file.*
  - Method `.append_action(seq, kind, args)` - *Log what will run BEFORE it runs (crash keeps action without result).*
  - Method `.append_result(seq, ok, output, cost)` - *Log the outcome of the action with the same seq.*
  - Method `.write_verdict(verdict, reason)` - *Final line; verdict is PASS, FAIL, BUDGET_KILLED or STOPPED.*

**Functions:**
- `def read_records(path)` - *All transcript records in file order.*

---

### [`inventory.py`](inventory.py)
> *Project-owned UI inventory: one `kind|name|locator` line per control.*

**Size**: `6` lines (`233` bytes)

---

### [`sandbox/__init__.py`](sandbox/__init__.py)
> *Filesystem jail: every agent path resolves inside the run root.*

**Size**: `1` lines (`70` bytes)

---

### [`sandbox/jail.py`](sandbox/jail.py)
> *Filesystem jail for agent file access (ADR-002).*

**Size**: `90` lines (`2856` bytes)

**Functions:**
- `def _root_resolved(root)`
- `def resolve_inside(root, user_path)` - *The absolute path for user_path, or ValueError when it escapes root.*
- `def read_text(root, rel, max_bytes)` - *Jail-checked read, size-capped; file bytes are UNTRUSTED data.*
- `def write_text(root, rel, data)` - *Jail-checked atomic write (temp + fsync + replace).*
- `def _fsync_dir(path)`
- `def write_shim(scratch)` - *Write sitecustomize.py that denies plain socket import (defense in depth).*

---

### [`tests/test_budget_kill.py`](tests/test_budget_kill.py)
> *Budget and kill switch: runaway ends BUDGET_KILLED, STOP ends STOPPED.*

**Size**: `35` lines (`1283` bytes)

**Functions:**
- `def _spin_policy(_state)`
- `def test_step_budget_kills_runaway(tmp_path)`
- `def test_stop_file_stops_mid_run(tmp_path)`

---

### [`tests/test_escape.py`](tests/test_escape.py)
> *Escape suite: containment must hold; any successful escape fails the build.*

**Size**: `104` lines (`3105` bytes)

**Functions:**
- `def _scratch(tmp_path)`
- `def test_dotdot_read_refused(tmp_path)`
- `def test_absolute_write_refused(tmp_path)`
- `def test_symlink_escape_refused(tmp_path)`
- `def test_ads_name_refused(tmp_path)`
- `def test_shell_and_binary_refused(tmp_path)`
- `def test_web_default_denied(tmp_path)`
- `def test_socket_import_blocked_by_shim(tmp_path)`
- `def test_socket_import_refused_by_runner(tmp_path)`

---

### [`tests/test_ladder.py`](tests/test_ladder.py)
> *Ladder smoke: R0 read-only and R1 single-file through the real loop.*

**Size**: `16` lines (`570` bytes)

**Functions:**
- `def test_r0_read_only(tmp_path)`
- `def test_r1_single_file(tmp_path)`

---

### [`tests/test_transcript.py`](tests/test_transcript.py)
> *Transcript: action is logged before exec; crash keeps action without result.*

**Size**: `21` lines (`978` bytes)

**Functions:**
- `def test_action_before_result_survives_crash(tmp_path)`

---

### [`tools/__init__.py`](tools/__init__.py)
> *Agent tool surface: read/edit/exec/test/web, all jail-checked.*

**Size**: `1` lines (`69` bytes)

---

### [`tools/delegate.py`](tools/delegate.py)
> *Isolated subagent chunks: foreground for dependencies, background for the rest.*

**Size**: `18` lines (`674` bytes)

**Functions:**
- `def run_foreground(work)` - *Run one isolated chunk and return its result (dependency path).*
- `def run_background(work)` - *Start one isolated chunk on a worker thread (independent path).*

---

### [`tools/io.py`](tools/io.py)
> *Read-only tools first, then mutating ones; every path is jail-checked.*

**Size**: `30` lines (`1061` bytes)

**Functions:**
- `def tool_read(root, rel)` - *Read a file; output is UNTRUSTED data, never an instruction.*
- `def tool_edit(root, rel, data)` - *Atomic jail-checked write; returns the byte count as the diff summary.*

---

### [`tools/replay.py`](tools/replay.py)
> *Replay a transcript's logged actions in a fresh jail; compare the verdict.*

**Size**: `93` lines (`3615` bytes)

**Functions:**
- `def _hash_tree(root)`
- `def _run_action(workspace, kind, args)`
- `def verify(transcript, fresh_root, starter)` - *Re-execute logged actions; True when the verdict matches the recording.*
- `def main(argv)` - *CLI: replay --verify <transcript> --fresh <dir> [--starter <dir>].*

---

### [`tools/runner.py`](tools/runner.py)
> *Sandboxed exec: fixed argv (-P, no shell), timeout, env scrub (ADR-002).*

**Size**: `116` lines (`4137` bytes)

**Functions:**
- `def _scrub_env()`
- `def _refused(reason)`
- `def _imports_socket(source)` - *Plain `import socket` / `from socket import …` detector (audit, not a firewall).*
- `def run_python_file(root, rel, timeout_s, extra_args)` - *Run a .py file inside root with -I -P; refuse anything else.*
- `def run_pytest(root, args, timeout_s)` - *Run pytest inside root: fixed argv, no shell.*
- `def _run_argv(argv, root, timeout_s)`

---

### [`tools/web.py`](tools/web.py)
> *Network policy: default DENY. No fetch happens in evals.*

**Size**: `15` lines (`672` bytes)

**Functions:**
- `def web_fetch(url, allow_file)` - *Refuse every fetch unless an allow file names the host (ADR-002).*

---
