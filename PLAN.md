# Implementation plan

## Architecture decision

Mission Validation Platform is a local-first FastAPI application with a small, dependency-light web client. SQLite stores audit and run records; project artifacts remain immutable on disk. The simulator is deliberately simplified: it produces deterministic, realistic-looking telemetry for software verification, not flight certification or aerodynamic prediction.

## First vertical slice

1. Load the included Falcon-X project and its versioned configuration.
2. Run a deterministic normal or faulted flight simulation.
3. Validate telemetry, inject a selected fault, and record a test verdict.
4. Compare simulated output with included actual-flight telemetry.
5. Present discrepancies, configuration history, security findings, and an exportable HTML report.

## Follow-on seams

- OpenRocket `.ork` extraction is isolated in `backend/app/ork.py`.
- Telemetry producers only depend on the typed packet model.
- A ground-station adapter can consume the `/api/telemetry` response or be added beside it.
- PostgreSQL and authenticated multi-user support are intentionally deferred from this local prototype.

## Evidence-informed product boundary

| Existing tool | Reuse / relationship | What MVP adds |
| --- | --- | --- |
| OpenRocket | Read-only `.ork` design input; it remains the flight-design tool. | Traceable import and validation context. |
| NASA Open MCT | Future dashboard integration through a telemetry adapter. | Student workflow, scenarios, test evidence, comparison. |
| NASA NOS3 / cFS | Future flight-software and hardware-in-the-loop targets. | Lightweight local mission validation without their infrastructure. |

Sources consulted: Open MCT [overview](https://nasa.github.io/openmct/about-open-mct/), [plugins](https://nasa.github.io/openmct/plugins/); [NOS3](https://github.com/nasa/nos3); [cFS](https://github.com/nasa/cFS); [OpenRocket features](https://openrocket.info/features.html).
