# OpenCode GitHub Integration

Python helpers and a GitHub Actions workflow for triggering [OpenCode](https://github.com/anomalyco/opencode) from issue and PR comments.

## Quick start

1. Add the `ANTHROPIC_API_KEY` secret to your repository (Settings → Secrets and variables → Actions).
2. Copy `.github/workflows/opencode.yml` into your repo.
3. Comment `/oc <instruction>` or `/opencode <instruction>` on any issue or PR.

Only repository **owners**, **members**, and **collaborators** can trigger the bot.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `GITHUB_TOKEN` | *(auto-provided)* | GitHub token for API calls |
| `OPENCODE_MODEL` | `anthropic/claude-sonnet-4-20250514` | Model identifier |
| `GITHUB_API_URL` | `https://api.github.com` | GitHub API base URL (for GHES) |
| `OPENCODE_COMMANDS` | `/oc,/opencode` | Comma-separated trigger prefixes |
| `OPENCODE_TIMEOUT` | `30` | HTTP request timeout in seconds (1–300) |

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
