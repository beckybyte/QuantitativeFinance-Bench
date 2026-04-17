# Benchmark Runner

`benchmark.py` runs all tasks across multiple models with concurrent execution,
saves structured results, and prints a summary table.

## Prerequisites

| Dependency | Install |
|---|---|
| [Harbor](https://github.com/laude-institute/harbor) | `pip install harbor` |
| Docker | Must be running |
| Sandbox image | `docker build -t finance-bench-sandbox:latest -f docker/sandbox.Dockerfile .` |

## API Keys

Create a `.env` file in the project root (git-ignored):

```bash
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
```

Load before running:

```bash
set -a && source .env && set +a
```

## Supported Models

| Name | Provider | Agent | API Key |
|---|---|---|---|
| `gemini-2.5-flash-lite` | Google | Finance-Zero | `GEMINI_API_KEY` |
| `gemini-2.0-flash-lite` | Google | Finance-Zero | `GEMINI_API_KEY` |
| `gemini-2.0-flash` | Google | Finance-Zero | `GEMINI_API_KEY` |
| `gemini-2.5-flash` | Google | Finance-Zero | `GEMINI_API_KEY` |
| `gemini-2.5-pro` | Google | Finance-Zero | `GEMINI_API_KEY` |
| `claude-haiku-4-5` | Anthropic | claude-code | `ANTHROPIC_API_KEY` |
| `claude-sonnet-4-6` | Anthropic | claude-code | `ANTHROPIC_API_KEY` |
| `claude-opus-4-6` | Anthropic | claude-code | `ANTHROPIC_API_KEY` |

To add a model, edit the `MODELS` list in `benchmark.py`.

## Usage

```bash
# Run all models on all tasks (4 concurrent workers)
python3 benchmark.py

# Run a specific model
python3 benchmark.py --model gemini-2.0-flash

# Run a specific task
python3 benchmark.py --task data-cleaning

# Tag this run for identification
python3 benchmark.py --tag round1

# Multiple rounds
python3 benchmark.py --tag round1 --rounds 3

# More concurrent workers
python3 benchmark.py --workers 8

# Dry run — preview what would execute
python3 benchmark.py --dry-run

# Combine flags
python3 benchmark.py --model gemini-2.5-flash --tag round1 --rounds 5 --workers 8
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--model NAME` | all | Run only this model (by short name) |
| `--task NAME` | all | Run only this task |
| `--tag TAG` | `""` | Tag for this run (e.g. `v1`, `round1`) |
| `--rounds N` | 1 | Number of rounds to run |
| `--workers N` | 4 | Number of concurrent harbor processes |
| `--dry-run` | off | Show plan without executing |

## Skip Logic

When a `--tag` is provided, the runner checks `results/` for existing results
with the same tag. Task/model combos that already have a valid result (no error,
has a reward) are skipped automatically.

This means you can safely re-run the same command after a crash or interruption
and it will pick up where it left off.

With `--rounds N`, each round gets a tag suffix (`round1_r1`, `round1_r2`, etc.)
so rounds are tracked independently.

## Output

### Console

Progress is printed in real time:

```
[  1/ 15]  gemini-2.0-flash × data-cleaning              reward=1.0       (11/11)  cost=$0.0002  time=20s
[  2/ 15]  gemini-2.0-flash × hull-white-swaption         reward=0.0       (3/12)   cost=$0.0020  time=18s
```

A summary table is printed at the end:

```
Task                            gemini-2.0-flash
-------------------------------------------------
data-cleaning                              11/11
hull-white-swaption                         3/12
momentum-backtest                          26/26
...
-------------------------------------------------
MEAN                                       0.133
```

Sub-test counts (`passed/total`) are shown when available.
With `--rounds > 1`, a cross-round average summary is printed at the end.

### Files

Each run saves a JSON file to `results/`:

```
results/
  run_20260309_221055_a1b2c3.json
  run_20260309_223000_d4e5f6.json
```

Each file contains:

```json
{
  "meta": {
    "run_id": "20260309_221055_a1b2c3",
    "tag": "round1",
    "round": 1,
    "started_at": "...",
    "finished_at": "...",
    "wall_time_sec": 120.5,
    "tasks": ["data-cleaning", "..."],
    "models": ["gemini-2.0-flash"],
    "workers": 4
  },
  "results": [
    {
      "task": "data-cleaning",
      "model": "gemini-2.0-flash",
      "reward": 1.0,
      "tests_total": 11,
      "tests_passed": 11,
      "subtests": [
        {"name": "test_output_files_exist", "status": "passed"},
        {"name": "test_clean_csv_columns", "status": "passed"}
      ],
      "cost_usd": 0.0002,
      "n_input_tokens": 406,
      "n_output_tokens": 516,
      "elapsed_sec": 20.3,
      "error": null
    }
  ]
}
```

### Harbor Job Directories

Raw harbor output (agent trajectories, pytest logs, artifacts) is in `jobs/`:

```
jobs/<run_id>__<model>__<task>/
  <task>__<trial_id>/
    verifier/
      reward.txt          # 1 or 0
      test-stdout.txt     # full pytest output
      ctrf.json           # per-test pass/fail
    agent/
      ...                 # agent logs and trajectories
```

## Cost Estimates (per task, Finance-Zero single-call)

| Model | ~Cost/task | 15 tasks |
|---|---|---|
| gemini-2.5-flash-lite | $0.0005 | $0.007 |
| gemini-2.0-flash-lite | $0.0010 | $0.014 |
| gemini-2.0-flash | $0.0013 | $0.019 |
| gemini-2.5-flash | $0.0019 | $0.029 |
| gemini-2.5-pro | $0.030 | $0.45 |

Claude models using `claude-code` agent cost significantly more due to
multi-turn agentic execution (~10-20x more tokens per task).

## Recommended Workflow

```bash
# 1. Verify tasks are correct (free)
harbor run --path ./tasks --agent oracle

# 2. Run cheap models first
python3 benchmark.py --model gemini-2.5-flash-lite --tag v1
python3 benchmark.py --model gemini-2.0-flash --tag v1

# 3. Run expensive models
python3 benchmark.py --model gemini-2.5-pro --tag v1

# 4. Multiple rounds for statistical significance
python3 benchmark.py --model gemini-2.0-flash --tag v1 --rounds 3
```
