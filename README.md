# AI Company Framework

An autonomous AI company framework powered by multi-agent orchestration. Agents operate as async workers that respond to events from Linear, GitHub, and Slack — converting ideas into shipped code with minimal human intervention.

## Architecture

```
Webhook Events (Linear/GitHub/Slack)
        │
        ▼
┌─────────────────┐
│  FastAPI Server  │  ← receives webhooks, pushes to event bus
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Orchestrator   │  ← manages agent lifecycle, routes events
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌───────────┐
│  PM    │ │ Developer │  ← autonomous agents with tool access
└────────┘ └───────────┘
```

## Agents

| Agent | Role |
|-------|------|
| **Product Manager** | Converts ideas and feedback into structured Linear epics and tickets |
| **Developer** | Picks up assigned tickets, writes code via Claude Code CLI, opens PRs |

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
python -m src.orchestrator
```

## Configuration

- `config/agents.yaml` — Agent definitions, polling intervals, tool permissions
- `config/workflows.yaml` — State machine transitions for ticket lifecycle

## Environment Variables

| Variable | Description |
|----------|-------------|
| `LINEAR_API_KEY` | Linear API key |
| `GITHUB_TOKEN` | GitHub personal access token |
| `SLACK_BOT_TOKEN` | Slack bot OAuth token |
| `WEBHOOK_SECRET` | Shared secret for webhook signature verification |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |

## License

MIT
