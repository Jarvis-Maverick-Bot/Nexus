# Security Policy

Nexus is an early-stage governance/runtime project. Please report security concerns responsibly.

## Please Do Not Publish Sensitive Details

Do not open public issues containing:

- credentials, tokens, API keys, or secrets;
- private hostnames or network paths;
- non-public governance evidence;
- private operator context;
- exploitable vulnerability details before maintainers have had time to respond.

## Reporting

If you find a vulnerability or sensitive exposure risk, please open a minimal public issue saying that a private security report is needed, or contact the maintainers through the available GitHub profile/contact path.

Include:

- affected file or component;
- high-level impact;
- reproduction steps if safe to share;
- whether any secret or private context may be exposed.

## Scope

Security-sensitive areas include:

- runtime assignment handling;
- credential/config loading;
- message transport adapters;
- evidence generation and redaction;
- human authority and promotion boundaries;
- private-agent invocation boundaries.
