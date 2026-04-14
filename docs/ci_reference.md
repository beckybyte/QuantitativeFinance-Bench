# CI Reference — Exact Tasks, Environments & Commands

This document details what each CI job does step-by-step: which tasks it
covers, what Docker/Python environment runs inside, and the exact commands
executed.

---

## 1. `ci.yaml` — Structural Validation

**Runner:** `ubuntu-latest` (plain GitHub-hosted, no Docker)  
**Scope:** **every** task under `tasks/*/` on every push and PR

### Step 1 · Validate task structure

Iterates over all `tasks/*/` directories. For each task, checks that all
six required files exist:

```
tasks/<task-id>/task.toml
tasks/<task-id>/instruction.md
tasks/<task-id>/environment/Dockerfile
tasks/<task-id>/tests/test.sh
tasks/<task-id>/tests/test_outputs.py
tasks/<task-id>/solution/solve.sh
```

Shell command (run in workflow):
```bash
for task_dir in tasks/*/; do
  task_id=$(basename "$task_dir")
  for f in task.toml instruction.md environment/Dockerfile \
            tests/test.sh tests/test_outputs.py solution/solve.sh; do
    [ ! -f "$task_dir/$f" ] && echo "FAIL: Missing $task_dir/$f" && status=1
  done
done
```

### Step 2 · Check canary strings

Finds every `.py`, `.sh`, and `Dockerfile` under `tasks/` and verifies
each contains the anti-contamination string:

```
quantitative-finance-bench-canary GUID
```

```bash
canary="quantitative-finance-bench-canary GUID"
for f in $(find tasks -name "*.py" -o -name "*.sh" -o -name "Dockerfile"); do
  grep -q "$canary" "$f" || { echo "FAIL: Missing canary in $f"; status=1; }
done
```

---

## 2. `test-deploy.yml` — Manual Benchmark (Deploy Server)

**Runner:** `ubuntu-latest` (GitHub-hosted) → SSHes into `159.65.5.105`  
**Scope:** only the **changed tasks** in the target PR (detected via git diff)

### Environment — Sandbox Docker Image

All harbor runs execute inside a Docker container built from:

```
docker build -t finance-bench-sandbox:latest \
  -f docker/sandbox.Dockerfile .
```

Base image: **`python:3.11-slim`**

Pre-installed system libraries:
- `build-essential`, `gcc`, `g++` (compilation)
- `TA-Lib 0.6.4` (built from source)

Pre-installed Python packages (`docker/requirements-sandbox.txt`):

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | ≥1.26 | Numerical arrays |
| pandas | ≥2.1 | DataFrames |
| scipy | ≥1.12 | Scientific computing |
| ta-lib | ≥0.6 | Technical analysis |
| backtrader | ≥1.9 | Backtesting |
| yfinance | ≥0.2 | Market data (network disabled at runtime) |
| statsmodels | ≥0.14 | Statistics / econometrics |
| scikit-learn | ≥1.4 | Machine learning |
| matplotlib | ≥3.8 | Plotting |
| seaborn | ≥0.13 | Statistical visualization |
| openpyxl | ≥3.1 | Excel I/O |
| pyarrow | ≥15.0 | Parquet / Arrow |
| tqdm | ≥4.66 | Progress bars |
| requests | ≥2.31 | HTTP (network disabled at runtime) |

> **Network is disabled** inside the sandbox at runtime — tasks must be
> self-contained and operate only on data provided in `/app/data/`.

Each task's own `environment/Dockerfile` extends this base:

```dockerfile
FROM finance-bench-sandbox:latest
COPY data/ /app/data/
# (task-specific additional packages if needed)
```

### Commands run per task

`test_on_server.py` runs the following for each changed task, in order:

#### 1 · Detect changed tasks

```python
git fetch origin main
git fetch upstream main
git diff --name-only upstream/main...HEAD
# → extract tasks/<task-id>/ → [task-id, ...]
```

#### 2 · Build sandbox base image

```bash
docker build -t finance-bench-sandbox:latest \
  -f docker/sandbox.Dockerfile . -q
```

Cached on the deploy server; only rebuilds when the Dockerfile changes.

#### 3 · Structure check

```python
# Checks these files exist under tasks/<task-id>/:
REQUIRED_FILES = [
    "task.toml", "instruction.md", "environment/Dockerfile",
    "tests/test.sh", "tests/test_outputs.py", "solution/solve.sh",
]
```

#### 4 · Canary check

```python
# Every .py, .sh, Dockerfile in the task directory must contain:
CANARY = "finance-bench-canary GUID"
```

#### 5 · Oracle run

```bash
harbor run \
  --path ./tasks \
  --task-name <task-id> \
  --job-name td-<task-id>-<hex6> \
  --agent oracle
```

Runs the reference solution (`solution/solve.sh`) inside the sandbox and
verifies all tests pass. Expected reward = 1.0. If oracle fails, the task
has a broken reference solution.

#### 6 · Finance-Zero run

```bash
harbor run \
  --path ./tasks \
  --task-name <task-id> \
  --job-name td-<task-id>-<hex6> \
  --agent-import-path agents.finance_zero:FinanceZeroAgent \
  --model gemini/gemini-3-flash-preview
```

Zero-shot baseline with no task-specific prompting. If reward = 1.0, the
task is likely too easy.

#### 7 · Claude-Code (Opus) run

```bash
harbor run \
  --path ./tasks \
  --task-name <task-id> \
  --job-name td-<task-id>-<hex6> \
  --agent claude-code \
  --model anthropic/claude-opus-4-6
```

Primary AI benchmark. Uses `CLAUDE_CODE_OAUTH_TOKEN` (OAuth, Max
subscription) injected into the Docker container by harbor.

#### 8 · Claude-Code (Haiku) run

```bash
harbor run \
  --path ./tasks \
  --task-name <task-id> \
  --job-name td-<task-id>-<hex6> \
  --agent claude-code \
  --model anthropic/claude-haiku-4-5-20251001
```

Secondary benchmark — cheaper and faster, useful for comparing difficulty
signal across model tiers.

### How harbor evaluates a run

After each `harbor run`, results are read from the job directory:

```
jobs/td-<task-id>-<hex6>/
  <task-id>__<trial-id>/
    results.json        ← reward (0.0 or 1.0), tests passed/total
    cost.json           ← token usage and USD cost
```

The test harness (`tests/test.sh` + `tests/test_outputs.py`) compares
`/app/output/` against expected values. Reward = 1.0 only if **all** tests
pass.

---

## 3. `eval-on-approve.yml` — Full Evaluation Pipeline

**Runner:** `self-hosted` (own machine with Docker + harbor)  
**Scope:** changed tasks in the PR, detected on merge approval

### Commands

#### Detect changed tasks

```bash
git diff --name-only origin/<base_ref>...HEAD \
  | grep '^tasks/' | cut -d/ -f2 | sort -u
```

#### Build sandbox

```bash
docker build -t finance-bench-sandbox:latest \
  -f docker/sandbox.Dockerfile . -q
```

#### Run evaluations

```bash
python3 .github/scripts/run_eval.py \
  --tasks "<space-separated task ids>" \
  --pr    <pr_number> \
  --commit <sha> \
  --output /tmp/eval_results.json
```

`run_eval.py` calls `harbor run` for each `(task, model)` combination
using the API keys configured as secrets. Results are uploaded to the
leaderboard via `RESULTS_API_URL`.

---

## 4. Summary Table

| Workflow | Scope | Environment | What it checks |
|----------|-------|-------------|----------------|
| `ci.yaml` | All tasks, every commit | ubuntu-latest (no Docker) | File structure, canary strings |
| `test-deploy.yml` | Changed tasks in PR | Docker `python:3.11-slim` + sandbox | Oracle, Finance-Zero, Claude-Code (opus + haiku) |
| `eval-on-approve.yml` | Changed tasks in PR | Self-hosted Docker + sandbox | All configured models → leaderboard |
| `claude-code-review.yml` | PR diff | ubuntu-latest | Code review inline comments |
| `claude.yml` | PR comment threads | ubuntu-latest | Interactive assistant |
