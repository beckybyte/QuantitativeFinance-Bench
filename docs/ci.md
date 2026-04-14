# CI/CD Pipeline

QuantitativeFinance-Bench uses five GitHub Actions workflows that form a
layered review pipeline — from instant structural checks to full
multi-model benchmark runs.

---

## Overview

```
PR opened / updated
    │
    ├─► ci.yaml                  (every push & PR)
    │     Structure + canary checks
    │
    ├─► claude-code-review.yml   (every PR, non-draft)
    │     Inline code review by Claude
    │
    ├─► claude.yml               (comments & review threads)
    │     Interactive Claude assistant
    │
    ├─► eval-on-approve.yml      (on PR approval, self-hosted)
    │     Full multi-model evaluation
    │
    └─► test-deploy.yml          (manual: /test-deploy comment)
          Oracle + Finance-Zero + Claude-Code benchmarks
          on the deploy server
```

---

## Workflow Details

### 1. `ci.yaml` — Structural Validation

**Trigger:** every `push` and every `pull_request` targeting `main`  
**Runner:** `ubuntu-latest`

Two fast checks that run on every commit:

| Step | What it checks |
|------|---------------|
| Validate task structure | Every `tasks/*/` directory has all required files: `task.toml`, `instruction.md`, `environment/Dockerfile`, `tests/test.sh`, `tests/test_outputs.py`, `solution/solve.sh` |
| Check canary strings | Every `.py`, `.sh`, and `Dockerfile` under `tasks/` contains the string `quantitative-finance-bench-canary GUID` |

The canary string prevents benchmark data from being silently stripped or
used in training corpora.

---

### 2. `claude-code-review.yml` — Automated Code Review

**Trigger:** PR opened, pushed to, or marked ready-for-review (non-draft only)  
**Runner:** `ubuntu-latest`

Uses `anthropics/claude-code-action@v1` to post **inline comments** on
specific issues (bugs, security, performance). If the code looks good,
it does nothing. It never posts a summary comment.

The action is given read-only tools:
- `gh pr diff` — reads the diff
- `gh pr view` — reads PR metadata
- `create_inline_comment` — posts inline review comments

Authentication uses `CLAUDE_CODE_OAUTH_TOKEN` (stored as a repo secret).

---

### 3. `claude.yml` — Interactive Claude Assistant

**Triggers:**
- `issue_comment` (PR comments containing `@claude` or similar)
- `pull_request_review_comment`
- PR opened/assigned
- PR review submitted

**Runner:** `ubuntu-latest`

Allows contributors and reviewers to interact with Claude in PR threads —
ask questions, request explanations, or get help with the task spec.

---

### 4. `eval-on-approve.yml` — Full Evaluation Pipeline

**Trigger:** PR review submitted with state `approved`  
**Runner:** `self-hosted` (requires a machine with Docker + harbor installed)

This is the **heavyweight** pipeline. It runs when a maintainer approves
a PR and evaluates the new task against multiple models.

```
PR approved
    │
    ▼
Detect changed tasks
  git diff origin/<base_ref>...HEAD
    │
    ▼
For each changed task, for each configured model:
  harbor run --agent <model> --task-name <task>
    │
    ▼
Post results table to PR comment
  ✅ / ❌ per (task, model) cell
```

**Required secrets:**

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | Claude models |
| `GEMINI_API_KEY` | Gemini models |
| `DASHSCOPE_API_KEY` | Qwen models |
| `MISTRAL_API_KEY` | Mistral models |
| `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID` | MiniMax models |
| `RESULTS_API_URL` / `RESULTS_API_TOKEN` | Upload results to leaderboard |

> **Note:** This workflow uses a `self-hosted` runner. The runner machine
> must have Docker, harbor, and all required API keys configured.
> It differs from `test-deploy.yml` in that it connects via GitHub Actions
> runner protocol (not SSH), and runs a broader set of models for the
> official leaderboard.

---

### 5. `test-deploy.yml` — Manual Benchmark (Deploy Server)

**Trigger:** PR comment containing `/test-deploy` (maintainers only)  
**Runner:** `ubuntu-latest` → SSHes into `159.65.5.105`

A lightweight, on-demand pipeline designed for **task authors and reviewers**
to quickly validate a new task before formal approval. See
[`test_deploy.md`](test_deploy.md) for the full setup guide and lessons
learned.

**Agents run:**

| Agent | Model | Purpose |
|-------|-------|---------|
| oracle | — | Reference solution must score reward = 1 |
| finance-zero | gemini-3-flash-preview | Zero-shot baseline (reward = 1 → task too easy) |
| claude-code | claude-opus-4-6 | Primary benchmark |
| claude-code | claude-haiku-4-5-20251001 | Secondary benchmark |

**Access control:** Only comments from repo `OWNER`, `MEMBER`, or
`COLLABORATOR` trigger the run. Others are ignored.

**Required secrets** (set in both `beckybyte` fork and `QF-Bench`):

| Secret | Value |
|--------|-------|
| `DEPLOY_SSH_KEY` | Private key to SSH into the deploy server |
| `DEPLOY_USER` | `root` |
| `DEPLOY_HOST` | `159.65.5.105` |
| `DEPLOY_REPO_PATH` | `/root/ke/QuantitativeFinance-Bench` |

---

## Pipeline Decision Tree

```
New task PR submitted
    │
    ├─ ci.yaml passes?
    │       NO  → fix structure / add canary strings
    │       YES ↓
    │
    ├─ claude-code-review leaves issues?
    │       YES → address inline comments
    │       OK  ↓
    │
    ├─ /test-deploy comment → oracle passes? canary ok?
    │       NO  → fix task (reference solution or files)
    │       YES → check claude-code reward
    │             reward = 0 → task is hard (good)
    │             reward = 1 via finance-zero → task may be too easy
    │
    └─ Maintainer approves
            │
            └─ eval-on-approve.yml → full multi-model results
               → merged to main + leaderboard updated
```

---

## Adding a New Workflow

When extending the pipeline, keep in mind:

- **Canary string** — any new `.py`, `.sh`, or `Dockerfile` in `tasks/`
  must contain `quantitative-finance-bench-canary GUID <uuid>`.
- **Concurrency** — use `concurrency.group` with `cancel-in-progress: true`
  to avoid duplicate runs from webhook retries.
- **Non-interactive SSH** — environment variables for tools (harbor, API
  keys) must be in `/etc/environment` on the server, not `.bashrc`.
- **origin vs upstream** — the server repo has two remotes. Task PRs
  target `upstream` (QF-Bench), so always diff against
  `upstream/<base_ref>`, not `origin/<base_ref>`.
