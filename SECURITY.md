# Security Policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon/security/advisories/new)
for this repository. Include what you found, how to reproduce it, and the impact you see.

You can expect an acknowledgement within a few days. This is a small project run by one maintainer, so please allow
reasonable time for a fix.

## Supported versions

Only the latest commit on `main` is supported.

## Things worth knowing

- **Decision support only.** TariffTrail's output must not be relied on as legal advice, and its filing tool is
  simulated: `file_entry` writes to a local file and never contacts customs authorities.
- **We put no authentication in front of the Strands Decider server.** It binds to `127.0.0.1` in our deployment;
  do not expose it to a network. The reference host in [`infra/`](infra) has no inbound ports and is driven only
  through AWS Systems Manager.
- **Credentials:** the code reads AWS credentials from the standard provider chain. Nothing in this repository should
  contain a key, token or account secret; `.env` is git-ignored. If you find one, report it using the process above.
- **The demo UI** accepts free-text product descriptions and forwards them to Decider and to Amazon Bedrock. Run live
  mode only on a trusted network.
