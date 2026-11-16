# OpenCode GitHub Integration

A Python library and GitHub Action that triggers AI-powered code operations from issue and PR comments using slash commands (`/oc`, `/opencode`).

## Table of Contents

- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Library API](#library-api)
- [Development](#development)
- [Running Tests](#running-tests)
- [Linting](#linting)
- [Further Documentation](#further-documentation)
- [Contributing](#contributing)
- [License](#license)

## How It Works

1. A user posts a comment containing `/oc <instructions>` or `/opencode <instructions>` on an issue or pull request.
2. The GitHub Actions workflow detects the trigger phrase and runs the [OpenCode action](https://github.com/anomalyco/opencode).
3. The action forwards the comment to Anthropic's Claude model, which performs the requested code operation (bug fix, refactor, explanation, etc.).
4. Results are posted back as a comment on the same issue or PR.

```text
User comment:  /oc fix the typo in README
                 ↓
GitHub Action:  opencode.yml triggers
                 ↓
Anthropic API:  Claude processes the request
                 ↓
GitHub:         Bot posts the result
```

## Quick Start

### 1. Add the workflow to your repository

Copy `.github/workflows/opencode.yml` into your repo (or reference it in an existing workflow file):

```yaml
name: opencode

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  opencode:
    if: |
      contains(github.event.comment.body, '/oc') ||
      contains(github.event.comment.body, '/opencode')
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: write
      pull-requests: write
      issues: write
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 1
          persist-credentials: false

      - uses: anomalyco/opencode/github@latest
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          model: anthropic/claude-sonnet-4-20250514
          use_github_token: true
```

### 2. Add repository secrets

In your repository **Settings > Secrets and variables > Actions**, add:

| Secret               | Description                            |
|:---------------------|:---------------------------------------|
| `ANTHROPIC_API_KEY`  | API key from [Anthropic Console](https://console.anthropic.com/) |

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

### 3. Trigger a command

Comment on any issue or PR:

```text
/oc refactor the login handler to use async/await
```

## Project Structure

```
opencode-github-integration/
├── .github/workflows/
│   └── opencode.yml              # GitHub Actions workflow
├── src/opencode_github/
│   ├── __init__.py               # Public API re-exports
│   ├── comment_parser.py         # Slash-command extraction from markdown
│   ├── config.py                 # Environment-based configuration
│   ├── gamified_learning.py      # Gamified critical-analysis module
│   ├── github_client.py          # Async GitHub REST API client (httpx)
│   └── webhook_handler.py        # Webhook payload validation & parsing
├── tests/                        # pytest test suite (asyncio)
├── docs/
│   └── overrides.md              # Linguist override documentation
├── pyproject.toml                # Build config, dependencies, tool settings
└── poetry.lock                   # Locked dependency versions
```

## Configuration

All runtime configuration is read from environment variables via `Config.from_env()`:

| Variable            | Required | Default                             | Description                        |
|:--------------------|:---------|:------------------------------------|:-----------------------------------|
| `GITHUB_TOKEN`      | Yes      | —                                   | GitHub PAT or installation token   |
| `ANTHROPIC_API_KEY` | Yes      | —                                   | Anthropic API key                  |
| `OPENCODE_MODEL`    | No       | `anthropic/claude-sonnet-4-20250514`     | Model identifier                   |
| `GITHUB_API_URL`    | No       | `https://api.github.com`            | API base URL (for GHES)            |
| `OPENCODE_COMMANDS` | No       | `/oc,/opencode`                     | Comma-separated trigger prefixes   |
| `OPENCODE_TIMEOUT`  | No       | `30`                                | HTTP request timeout (seconds)     |

## Library API

The `opencode_github` package exposes several modules that can be used independently:

### Comment Parser

```python
from opencode_github import extract_commands, is_command_comment, split_arguments

commands = extract_commands(comment_body, ["/oc", "/opencode"])
# → [ParsedCommand(trigger="/oc", arguments="fix the bug", raw_body=...)]

split_arguments('fix bug --verbose "hello world"')
# → ["fix", "bug", "--verbose", "hello world"]
```

### GitHub Client

```python
from opencode_github import GitHubClient

async with GitHubClient(token="ghp_...") as client:
    pr = await client.get_pull_request("owner", "repo", 42)
    comments = await client.list_issue_comments("owner", "repo", 42)
    await client.create_issue_comment("owner", "repo", 42, "Done!")
    await client.add_reaction("owner", "repo", comment_id=1001, reaction="+1")
```

### Webhook Handler

```python
from opencode_github import WebhookEvent, EventType
from opencode_github.webhook_handler import verify_signature, parse_raw

# Verify payload authenticity
valid = verify_signature(raw_body, signature_header, webhook_secret)

# Parse in one step
event = parse_raw(event_header="issue_comment", body=raw_body)
```

### Gamified Learning

A module for building gamified critical-analysis exercises around technical documentation:

```python
from opencode_github import LearnerProfile, LearningChallenge
from opencode_github.gamified_learning import create_challenge, complete_challenge, score_analysis

challenge = create_challenge("ch-1", "Analyze API Docs", source_text="...")
profile = LearnerProfile(user_id="user-1")
result = score_analysis(assumptions, source_text)
profile, events = complete_challenge(profile, challenge, result)
# events → ["level_up:2", "badge:first_analysis"]
```

## Development

### Requirements

- Python 3.10+
- [pip](https://pip.pypa.io/) (or any PEP 517 compatible installer)

### Install dependencies

```bash
pip install -e ".[dev]"
```

This installs the package in editable mode along with all development dependencies (`pytest`, `ruff`, `pytest-asyncio`, etc.).

## Running Tests

```bash
pytest
```

Run with coverage reporting:

```bash
pytest --cov=src --cov-report=term-missing
```

The test suite uses `pytest-asyncio` for async tests and `respx` for mocking `httpx` requests. Coverage must remain at or above **80%** (enforced via `pyproject.toml`).

## Linting

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

Ruff is configured in `pyproject.toml` with `line-length = 100` and rules `E`, `F`, `I`, `W`.

## Further Documentation

- [Overrides documentation](docs/overrides.md) — Linguist `.gitattributes` overrides for language classification.
- [Anthropic API reference](https://docs.anthropic.com/) — Claude model documentation.
- [GitHub Webhooks](https://docs.github.com/en/webhooks) — Event payload schemas.
- [OpenCode Action](https://github.com/anomalyco/opencode) — The upstream GitHub Action.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request. When contributing:

1. Install dev dependencies: `pip install -e ".[dev]"`
2. Run `ruff check` and `pytest` before submitting.
3. Follow the existing code style (type hints, `dataclass`-based models, async where applicable).

## License

This project does not yet specify a license. Please contact the maintainers for usage terms.

---

_Originally written and maintained by contributors and [Devin](https://app.devin.ai), with updates from the core team._
