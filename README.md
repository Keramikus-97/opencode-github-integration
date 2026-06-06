# OpenCode GitHub Integration

Python library and GitHub Action for automating repository modifications and
issue responses using Anthropic's Claude model.

## Project Structure

```
src/opencode_github/
├── utils/               # Shared utilities (used by every domain module)
│   ├── crypto.py        # HMAC-SHA256 signature helpers
│   ├── env.py           # Environment-variable loading & validation
│   ├── errors.py        # Unified exception hierarchy
│   ├── http.py          # GitHub API HTTP client helpers
│   └── text.py          # Regex extraction & input sanitisation
├── config.py            # Runtime configuration (env → dataclass)
├── comment_parser.py    # Slash-command extraction (/oc, /opencode)
├── github_client.py     # Async GitHub REST API client
└── webhook_handler.py   # Webhook payload validation & event normalisation
```

### Why shared utilities?

Every domain module delegates common patterns to `utils/` instead of
reimplementing them:

| Utility | Used by |
|---------|---------|
| `utils.env` | `config` (env-var loading) |
| `utils.errors` | all modules (consistent exception types) |
| `utils.http` | `github_client` (headers, response parsing, client factory) |
| `utils.crypto` | `webhook_handler` (HMAC verification) |
| `utils.text` | `comment_parser`, `webhook_handler` (regex, sanitisation) |

## Setup

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e '.[dev]'
```

## Lint & Test

```bash
ruff check src/ tests/
pytest -v
```
