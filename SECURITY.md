# Security policy

## Reporting a vulnerability

Report it privately: use **Report a vulnerability** on this repository's Security tab, or reach the
owner through his GitHub profile. Please do not open a public issue for it.

Never post a key, a token, a password or a `.env` file in an issue, a pull request or a report. If
you have found one exposed, say where it is, not what it is.

## Scope

Steward runs on the owner's PC against local Ollama. Security-relevant areas: the approval cards
(no write, commit or push without the owner's click), the confined shell, the file store's refusal
to read `.env` files, and the MCP endpoints, which listen on loopback only.
