# Project skills

Vendored from [anthropics/skills](https://github.com/anthropics/skills) at commit `ca45fc4` (Apache-2.0, see each `LICENSE.txt`). Files are unmodified.

| Skill | Purpose here |
|-------|--------------|
| `webapp-testing` | Python Playwright scripts for testing the dashboard; `scripts/with_server.py` starts the app servers around a test run. |
| `frontend-design` | Design direction for the dashboard and watchlist so they don't look templated. |

Superpowers (obra/superpowers) is enabled as a project plugin in `.claude/settings.json`, not vendored, because its skills call each other's scripts.
The Playwright MCP server is configured in `/.mcp.json`.

To update a vendored skill, copy the folder again from a newer commit of anthropics/skills and update the commit above.
