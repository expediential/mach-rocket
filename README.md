# Mission Validation Platform

Mission Validation Platform is a local-first prototype for university CanSat and student-rocketry teams. It connects vehicle artifacts, mission configuration, simplified telemetry simulation, fault scenarios, test evidence, real-flight comparison, configuration history, and practical security checks in one understandable workflow.

It is a **software verification and decision-support prototype**. It does not certify flight safety, replace physical testing, or replace OpenRocket, Open MCT, professional flight-dynamics software, CAD, or CFD tools.

## Run locally

The easiest route is Docker:

```bash
docker compose up --build
```

Then open `http://localhost:8000`.

Or use Python 3.12+:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

OpenAPI documentation is available at `http://localhost:8000/docs`.

## Demo story

- Falcon-X is configured for a 1000 m target altitude.
- The synthetic simulation reaches 1000 m; included Flight 003 reaches 967 m.
- A five-second radio interruption fails its three-second recovery expectation.
- Configuration v1.7 records a +80 g mass change and a larger simulation error.
- A malformed packet is detected and rejected before dashboard storage.

Use **Simulate** to run and persist deterministic telemetry with user-controlled parameters, **Test** to execute registered test cases, **Compare** to select persisted simulations and flights, and **Reports** to generate matching HTML and JSON evidence reports. **Flights** replays the selected stored packet stream with a timeline cursor; **Files** previews CSV mappings before confirmation; **Mission** saves new configuration revisions; **Vehicle** renders the normalized model in SVG and WebGL; **Investigations** tracks evidence-linked discrepancy hypotheses and their status. The included `demo/` directory is seeded into SQLite at startup through the same persistence paths as user data.

Create additional projects from Settings and switch active workspaces from the sidebar. Projects can also be duplicated, archived, exported as a ZIP, and imported on another local installation. Reset Demo Data only deletes and recreates the project with id `project-demo-2026`. Imported text artifacts are filename-sanitized, SHA-256 hashed, stored by opaque ID, and downloadable; supported OpenRocket geometry updates the canonical vehicle model. Valid telemetry is stored as a first-class flight with its packets, mapping, validation issues, and computed statistics.

## Architecture and limits

The API holds the application layer and keeps raw telemetry parsing separate from the interface. SQLite is the source of truth for project, vehicle, mission, artifact, flight, packet, simulation, scenario, test, requirement, revision, security, report, and audit records. The client is intentionally a dependency-light modern web interface so the prototype remains easy to run locally; its API boundary supports a later React/Open MCT adapter if desired. See [ARCHITECTURE.md](ARCHITECTURE.md), [SIMULATION.md](SIMULATION.md), and [docs/ECOSYSTEM.md](docs/ECOSYSTEM.md).

## Quality checks

```bash
python -m unittest discover -s tests -v
```

The suite validates simulator behavior, fault injection, telemetry parsing, source-artifact tolerance, comparison classification, and security input checks.
