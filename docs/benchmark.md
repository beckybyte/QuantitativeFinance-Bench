# Benchmark Runner Guide

## Prerequisites

| Dependency | Install |
|---|---|
| [Harbor](https://github.com/laude-institute/harbor) | `pip install harbor` |
| Docker Desktop | Must be running |
| Python 3.12+ | With `litellm` installed |

```bash
# Load API keys before running
set -a && source .env && set +a

# Verify Docker is running
docker info
```

## Quick Start

```bash
# List all configured models and check which API keys are set
python3 benchmark.py --list-models

# Dry run — see what would be executed
python3 benchmark.py --dry-run

# Run all models (auto-skips completed, targets 3 rounds each)
python3 benchmark.py --workers 8

# Run a specific model
python3 benchmark.py --model gemini-3-flash-preview --workers 4

# Force re-run even if results exist
python3 benchmark.py --model gpt-5.4 --force
```

---

## 1. Anthropic (Claude)

### API Keys

| Key | Purpose | Get it from |
|---|---|---|
| `ANTHROPIC_API_KEY` | Single API calls (finance-zero) | https://console.anthropic.com/settings/keys |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code agentic mode (Max subscription) | See below |

**Getting CLAUDE_CODE_OAUTH_TOKEN (Mac):**
```bash
# Extract from macOS Keychain (requires active Claude Max subscription)
security find-generic-password -s "Claude Code-credentials" -w | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(data['claudeAiOauth']['accessToken'])
"
```

Add to `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-api...
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
```

### Available Models

#### Single API (finance-zero, one LLM call)
| Name | Model ID | Notes |
|---|---|---|
| `claude-haiku-4-5` | claude-haiku-4-5-20251001 | Cheapest Claude |
| `claude-sonnet-4-6` | claude-sonnet-4-6 | |
| `claude-opus-4-6` | claude-opus-4-6 | |
| `claude-opus-4-7` | claude-opus-4-7 | Strongest single-API Claude. Does NOT support temperature param |
| `claude-opus-4-5` | claude-opus-4-5-20251101 | Requires sufficient API credit |

```bash
# Run Claude single API
python3 benchmark.py --model claude-opus-4-7 --workers 1  # workers=1 to avoid rate limit (8k output tokens/min)
python3 benchmark.py --model claude-sonnet-4-6 --workers 4
```

#### Claude Code Agent (agentic, multi-turn, uses Max subscription)
| Name | Model ID | Notes |
|---|---|---|
| `claude-code-sonnet-4-6` | claude-sonnet-4-6 | Best value agentic Claude |
| `claude-code-opus-4-6` | claude-opus-4-6 | Slow (~10-30 min/task), needs 3x timeout |
| `claude-code-opus-4-7` | claude-opus-4-7 | Requires OAuth token support for new model |
| `claude-code-haiku-4-5` | claude-haiku-4-5-20251001 | |

```bash
# Run Claude Code agentic (requires CLAUDE_CODE_OAUTH_TOKEN, NOT ANTHROPIC_API_KEY)
# IMPORTANT: unset ANTHROPIC_API_KEY to avoid conflict
unset ANTHROPIC_API_KEY
export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...

python3 benchmark.py --model claude-code-sonnet-4-6 --workers 4
python3 benchmark.py --model claude-code-opus-4-6 --workers 1  # slow, use 1 worker
```

#### Claude via Harbor + OpenHands (agentic framework)
Not recommended for Claude — Claude Code agent is purpose-built and performs much better.

### Rate Limits
- Opus models: 8,000 output tokens/min. Use `--workers 1` to avoid rate limiting.
- Sonnet/Haiku: Higher limits, `--workers 4` is fine.

### Cost Estimates (per task)
| Mode | Model | ~Cost/task |
|---|---|---|
| Single API | claude-haiku-4-5 | $0.02 |
| Single API | claude-sonnet-4-6 | $0.05 |
| Single API | claude-opus-4-6 | $0.10 |
| Single API | claude-opus-4-7 | $0.10 |
| Agentic | claude-code-sonnet-4-6 | Free (Max subscription) |
| Agentic | claude-code-opus-4-6 | Free (Max subscription) |

---

## 2. OpenAI (GPT)

### API Key

| Key | Purpose | Get it from |
|---|---|---|
| `OPENAI_API_KEY` | All OpenAI models (API + Codex agent) | https://platform.openai.com/api-keys |

Add to `.env`:
```bash
OPENAI_API_KEY=sk-proj-...
```

### Available Models

#### Single API (finance-zero)
| Name | Model ID | Notes |
|---|---|---|
| `gpt-4o` | gpt-4o | |
| `gpt-4.1-nano` | gpt-4.1-nano | |
| `gpt-4.1` | gpt-4.1 | |
| `gpt-5-nano` | gpt-5-nano | temperature forced to 1.0 |
| `gpt-5-mini` | gpt-5-mini | temperature forced to 1.0 |
| `gpt-5` | gpt-5 | temperature forced to 1.0 |
| `gpt-5.4-nano` | gpt-5.4-nano | temperature forced to 1.0 |
| `gpt-5.4-mini` | gpt-5.4-mini | temperature forced to 1.0 |
| `gpt-5.4` | gpt-5.4 | temperature forced to 1.0 |
| `gpt-5.4-pro` | gpt-5.4-pro | temperature forced to 1.0 |

> **Note:** GPT-5 family models only support `temperature=1.0`. This is configured automatically.

```bash
python3 benchmark.py --model gpt-5.4 --workers 8
python3 benchmark.py --model gpt-4.1 --workers 8
```

#### Codex Agent (agentic, OpenAI's CLI agent)
| Name | Model ID | Notes |
|---|---|---|
| `codex-gpt-5.4` | gpt-5.4 | Currently #1 on leaderboard |
| `codex-gpt-5` | gpt-5 | #2 on leaderboard |
| `codex-gpt-4.1` | gpt-4.1 | Weak performance with older model |

```bash
# Codex agent uses the same OPENAI_API_KEY
python3 benchmark.py --model codex-gpt-5.4 --workers 4
```

#### GPT via Harbor + OpenHands (agentic framework)
| Name | Model ID |
|---|---|
| `oh-gpt-4.1` | gpt-4.1 |

```bash
python3 benchmark.py --model oh-gpt-4.1 --workers 1
```

#### GPT via Finance-Agent (simple ReAct, multi-turn)
| Name | Model ID |
|---|---|
| `agent-gpt-4.1` | gpt-4.1 |

```bash
python3 benchmark.py --model agent-gpt-4.1 --workers 4
```

### GPT-OSS (Open-source weights, via OpenRouter)
| Name | Model ID | Notes |
|---|---|---|
| `gpt-oss-120b` | openai/gpt-oss-120b | Requires `OPENROUTER_API_KEY` |
| `gpt-oss-20b` | openai/gpt-oss-20b | Requires `OPENROUTER_API_KEY` |

### Cost Estimates (per task)
| Mode | Model | ~Cost/task |
|---|---|---|
| Single API | gpt-4.1-nano | $0.002 |
| Single API | gpt-4.1 | $0.03 |
| Single API | gpt-5.4 | $0.05 |
| Agentic | codex-gpt-5.4 | ~$0.15-0.50 |

---

## 3. Google (Gemini)

### API Key

| Key | Purpose | Get it from |
|---|---|---|
| `GEMINI_API_KEY` | All Gemini models (API + Gemini CLI agent) | https://aistudio.google.com/apikey (with billing enabled) |

Add to `.env`:
```bash
GEMINI_API_KEY=AIza...
```

> **Important:** Free tier has quota=0 for most models. You need a Google Cloud project with billing enabled.

### Available Models

#### Single API (finance-zero)
| Name | Model ID | Notes |
|---|---|---|
| `gemini-2.5-flash-lite` | gemini-2.5-flash-lite | Cheapest |
| `gemini-2.0-flash` | gemini-2.0-flash | |
| `gemini-2.5-flash` | gemini-2.5-flash | |
| `gemini-2.5-pro` | gemini-2.5-pro | |
| `gemini-3-flash-preview` | gemini-3-flash-preview | Strong performer |
| `gemini-3-pro-preview` | gemini-3-pro-preview | |
| `gemini-3.1-pro` | gemini-3.1-pro-preview | #2 single-API model overall |

> **Note:** `gemini-2.0-flash-lite` has been discontinued by Google (404 as of April 2026).

```bash
python3 benchmark.py --model gemini-3.1-pro --workers 8
python3 benchmark.py --model gemini-3-flash-preview --workers 8
```

#### Gemini CLI Agent (agentic, Google's CLI agent)
| Name | Model ID |
|---|---|
| `gemini-cli-3-pro` | gemini-3-pro-preview |
| `gemini-cli-3-flash` | gemini-3-flash-preview |

```bash
python3 benchmark.py --model gemini-cli-3-pro --workers 4
```

#### Gemini via Harbor + OpenHands (agentic framework)
| Name | Model ID |
|---|---|
| `oh-gemini-3-flash` | gemini-3-flash-preview |

```bash
python3 benchmark.py --model oh-gemini-3-flash --workers 1
```

#### Gemini via Finance-Agent (simple ReAct, multi-turn)
| Name | Model ID |
|---|---|
| `agent-gemini-3-flash` | gemini-3-flash-preview |

```bash
python3 benchmark.py --model agent-gemini-3-flash --workers 4
```

### Cost Estimates (per task)
| Mode | Model | ~Cost/task |
|---|---|---|
| Single API | gemini-2.5-flash-lite | $0.001 |
| Single API | gemini-2.0-flash | $0.003 |
| Single API | gemini-3-flash-preview | $0.01 |
| Single API | gemini-3.1-pro | $0.04 |
| Agentic | gemini-cli-3-pro | ~$0.10-0.30 |

---

## 4. OpenRouter (Open-Source & Third-Party Models)

### API Key

| Key | Purpose | Get it from |
|---|---|---|
| `OPENROUTER_API_KEY` | All OpenRouter models | https://openrouter.ai/keys |

Add to `.env`:
```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

OpenRouter is a unified gateway to many models. Pay-as-you-go, prices vary by model.

### Available Models

#### Single API (finance-zero)

**DeepSeek**
| Name | Model ID | Notes |
|---|---|---|
| `deepseek-v3` | deepseek/deepseek-chat-v3-0324 | |
| `deepseek-r1` | deepseek/deepseek-r1 | Reasoning model |

**Meta Llama**
| Name | Model ID |
|---|---|
| `llama-4-maverick` | meta-llama/llama-4-maverick |
| `llama-4-scout` | meta-llama/llama-4-scout |

**Qwen (Alibaba)**
| Name | Model ID |
|---|---|
| `qwen-3-235b` | qwen/qwen3-235b-a22b |
| `qwen-2.5-coder-32b` | qwen/qwen-2.5-coder-32b-instruct |
| `qwen-3-coder-next` | qwen/qwen3-coder-next |

**Kimi / Moonshot**
| Name | Model ID |
|---|---|
| `kimi-k2` | moonshotai/kimi-k2-0905 |
| `kimi-k2-thinking` | moonshotai/kimi-k2-thinking |
| `kimi-k2.5` | moonshotai/kimi-k2.5 |

**GLM / Z.AI (Zhipu)**
| Name | Model ID |
|---|---|
| `glm-4.7` | z-ai/glm-4.7 |
| `glm-5.1` | z-ai/glm-5.1 |

**MiniMax**
| Name | Model ID |
|---|---|
| `minimax-m2.7` | minimax/minimax-m2.7 |
| `minimax-m2.5` | minimax/minimax-m2.5 |

**Mistral**
| Name | Model ID |
|---|---|
| `mistral-large` | mistralai/mistral-large-2411 |

**OpenAI OSS (via OpenRouter)**
| Name | Model ID |
|---|---|
| `gpt-oss-120b` | openai/gpt-oss-120b |
| `gpt-oss-20b` | openai/gpt-oss-20b |

```bash
python3 benchmark.py --model deepseek-r1 --workers 8
python3 benchmark.py --model qwen-3-235b --workers 8
python3 benchmark.py --model kimi-k2.5 --workers 4
```

#### OpenRouter via Finance-Agent (simple ReAct, multi-turn)
| Name | Model ID |
|---|---|
| `agent-deepseek-v3` | deepseek/deepseek-chat-v3-0324 |
| `agent-deepseek-r1` | deepseek/deepseek-r1 |
| `agent-llama-4-maverick` | meta-llama/llama-4-maverick |
| `agent-qwen-3-235b` | qwen/qwen3-235b-a22b |

```bash
python3 benchmark.py --model agent-deepseek-v3 --workers 1
```

#### OpenRouter via Harbor + OpenHands (agentic framework)
| Name | Model ID |
|---|---|
| `oh-deepseek-v3` | deepseek/deepseek-chat-v3-0324 |
| `oh-deepseek-r1` | deepseek/deepseek-r1 |
| `oh-qwen-3-235b` | qwen/qwen3-235b-a22b |

```bash
python3 benchmark.py --model oh-deepseek-v3 --workers 1
```

### Cost Estimates (per task, single API)
| Model | ~Cost/task |
|---|---|
| deepseek-v3 | $0.003 |
| deepseek-r1 | $0.01 |
| qwen-3-235b | ~free (OpenRouter free tier) |
| llama-4-maverick | ~free |
| kimi-k2.5 | ~free |
| glm-4.7 | ~free |
| mistral-large | ~free |

---

## Agent Types Explained

| Agent | Description | How it works | When to use |
|---|---|---|---|
| **finance-zero** | Single API call baseline | One LLM call, extract code, execute once | Cheapest. Calibrate task difficulty |
| **finance-agent** | Simple multi-turn ReAct | Code → Execute → Observe → Fix (5 turns max) | Moderate cost. Any litellm model |
| **claude-code** | Claude Code CLI | Full dev environment (file browsing, terminal, debugging) | Best for Claude models. Uses Max subscription |
| **codex** | OpenAI Codex CLI | Similar to claude-code but for OpenAI | Best for GPT models |
| **gemini-cli** | Google Gemini CLI | Similar to claude-code but for Gemini | Best for Gemini models |
| **openhands** | OpenHands framework | Full agent with planner, tools, file editing | Heavy, expensive. Any model via litellm |

---

## CLI Options

| Flag | Default | Description |
|---|---|---|
| `--model NAME` | all | Run only this model (by short name) |
| `--task NAME` | all | Run only this task |
| `--tag TAG` | `bench` | Tag for this run |
| `--rounds N` | 3 | Target valid rounds per (model, task) |
| `--workers N` | 4 | Number of concurrent harbor processes |
| `--temperature F` | 0.0 | LLM temperature (overridden per-model when needed) |
| `--max-tokens N` | 8192 | Max output tokens |
| `--dry-run` | off | Show plan without executing |
| `--force` | off | Ignore existing results, re-run everything |
| `--list-models` | off | List all configured models and exit |

## Smart Features

- **All-zero detection**: Runs where every task scores 0 are automatically invalidated (auth/config failures)
- **Cross-tag round counting**: Counts valid rounds across ALL result files, not just the current tag
- **Auto-skip**: Models missing their API key are skipped with a clear message
- **Per-task Docker locks**: Prevents concurrent image build conflicts
- **Prebuild**: Docker images are built sequentially before concurrent evaluation starts

## Dashboard

```bash
python3 dashboard.py
# Open http://localhost:5050
```

Pages:
- **Overview**: Stats + leaderboard bar chart + table with progress bars
- **Leaderboard**: Tabbed view — All / Agentic / Single API with head-to-head comparison
- **Heatmap**: Interactive task x model matrix
- **Models**: Per-model detail with tokens, cost, avg time
- **Tasks**: Difficulty ranking (hardest first)
- **Logs**: All run files with valid/error/invalid counts
- **Jobs**: Harbor job browser (legacy)
- **Export PNG**: Button on every page to download as image

## Output Files

Results are saved to `results/run_<id>.json`. Each file contains metadata and per-task results including reward, cost, tokens, elapsed time, subtests, and errors.

Harbor job directories are in `jobs/<run_id>__<model>__<task>/` with agent logs, pytest output, and verifier results.

## Adding a New Model

Edit the `MODELS` list in `benchmark.py`:

```python
{"name": "my-model",
 "model": "provider/model-id",
 "agent_path": "agents.finance_zero:FinanceZeroAgent",  # or "agent": "claude-code"
 "env_key": "MY_API_KEY"},
```

For models that don't support temperature=0:
```python
{"name": "my-model", ..., "temperature": 1.0},   # force temperature=1
{"name": "my-model", ..., "temperature": -1},     # omit temperature entirely
```
