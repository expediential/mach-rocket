# Testing

Run the dependency-light automated suite:

```bash
python -m unittest discover -s tests -v
```

The tests cover trajectory phases, deterministic seeds, all fault modes, packet validation and alias mapping, OpenRocket XML tolerance, comparison classifications, and secret detection behavior. API behavior is exercised manually through the generated FastAPI OpenAPI page or the built-in client once dependencies are installed.

The included radio-loss test intentionally fails: recovery takes five seconds versus an expected three seconds. It demonstrates that failure evidence remains visible instead of being silently normalized away.
