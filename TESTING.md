# Testing

Run the dependency-light automated suite:

```bash
python -m unittest discover -s tests -v
```

The tests cover trajectory phases, deterministic seeds, all fault modes, packet validation and alias mapping, OpenRocket XML tolerance, comparison classifications, and secret detection behavior. HTTP-level integration tests exercise project creation, simulation persistence, CSV preview/confirmation, dataset comparison, report generation, test creation/execution, security findings, and audit records using FastAPI's test client.

The included radio-loss test intentionally fails: recovery takes five seconds versus an expected three seconds. It demonstrates that failure evidence remains visible instead of being silently normalized away.
