# Threat model

## Scope

This prototype runs on one local machine. It treats imported telemetry and artifacts as untrusted data.

## Controls

- CSV parsing validates field type, phase, and bounded physical ranges; invalid rows are reported and not accepted.
- Upload payload sizes are bounded by API models; client-side file selection does not execute files.
- Artifact parsing uses a non-mutating, tolerant XML extractor and does not run external tools.
- Potential secrets are scanned as text. Findings are advisory; the scanner is not a substitute for Gitleaks or a code review.
- Synthetic telemetry integrity uses an explicitly development-only HMAC demonstration key. Real deployments must obtain secrets through a secret manager and rotate them.
- SQLite audit entries record actor (local-user), action, result, time, and concise detail.

## Out of scope

No authentication, multi-user authorization, encrypted remote transport, hardware command uplink, or production key management is implemented. These are required before any networked or operational use.
