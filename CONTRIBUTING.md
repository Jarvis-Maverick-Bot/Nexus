# Contributing

Thanks for your interest in Nexus.

Nexus is an early-stage project. Contributions that improve clarity, tests, public examples, safety documentation, and issue hygiene are especially welcome.

## Good First Contributions

- Improve README wording or examples.
- Add tests for small governance/runtime units.
- Clarify setup steps.
- Improve public-safe documentation of authority gates, lifecycle events, or evidence records.
- Triage issues and propose clearer labels.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m pytest
```

On Windows, activate the virtual environment with the equivalent PowerShell or Command Prompt activation command.

## Contribution Rules

- Do not include credentials, tokens, private hostnames, private operator context, or non-public evidence.
- Do not claim production readiness, final PASS, grant approval, or external adoption unless it is public and verifiable.
- Keep examples synthetic unless a maintainer explicitly marks them public-safe.
- Prefer small pull requests with clear scope.
- Include test evidence when changing runtime or governance behavior.

## Pull Requests

A good pull request includes:

- what changed;
- why it matters;
- how it was tested;
- any safety or governance impact;
- screenshots or diagrams when changing public docs.
