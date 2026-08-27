# Current-state audit

Audit performed against the repository before the hardening pass. The prototype had a coherent visual shell, but most demo records were produced by Python constants rather than persisted project data.

| Feature | Current implementation | Problem | What needs to become real | Priority |
| --- | --- | --- | --- | --- |
| Project/dashboard | `dashboard()` returns a literal Falcon-X dictionary | Current project and health are not stored or recalculated | Seed and retrieve project/mission/configuration from SQLite; calculate health | P1 |
| Vehicle | `/api/vehicle` returns fixed metadata; CSS rocket is decorative | No normalized geometry, labels, CG/CP, or artifact-driven rendering | Persist vehicle components and render one model in SVG + WebGL | P1 |
| Simulation | Simulator is deterministic and genuinely computes packets | Inputs are partly fixed and runs only store a summary | Accept all parameters and persist complete packets/run metadata | P1 |
| Fault injection | Named single fault is implemented | No event list or multi-event scenarios; result is not a reusable scenario record | Persist scenario events and apply generalized events | P2 |
| Telemetry import | CSV validates aliases and reports errors | Parsed packets are discarded after the response | Persist flight, packet rows, hashes, mapping, and stats | P1 |
| Replay | Flight rows are returned as fixed records; Play only changes text | No time cursor or telemetry playback | Select a stored flight and animate its actual packets | P1 |
| Compare | Always compares generated simulation to a fixed helper flight | User cannot select datasets; no time alignment | Compare selected persisted runs/flights with aligned metrics | P1 |
| MissionTest | `/api/tests/run` returns a literal 30/26/3/1 summary | No registered test execution or result storage | Store test cases, execute parser/simulation fixtures, persist runs | P1 |
| Configuration history | `/api/config/history` returns fixed revisions | Changes cannot be made or diffed | Persist config JSON and create revisions from edits | P2 |
| Reports | Generates an HTML file but from fixed dashboard/test/comparison inputs | Report does not reflect current project state | Build report from persisted selected/current data and store metadata | P2 |
| Security | Text scanner is real; demo findings are fixed and HMAC key is hard-coded | Findings are not project records; secret key violates configuration rule | Use environment key, persist findings, mask evidence | P2 |
| Requirements | Demo JSON exists but no API/UI/storage | Traceability is not queryable | Add requirement/evidence records and a view | P3 |
| Artifact import | OpenRocket parser is tolerant but not wired to uploads | No SHA-256, component model, or version comparison | Store bytes/hash and normalize supported artifacts | P2 |
| API | FastAPI routes exist | Several endpoints are demo-only and there is no project lifecycle | Add CRUD-style project/import/run endpoints and integration tests | P1 |
| UI navigation | All pages render | Some buttons claim replay/3D/compare/test-builder behavior that is not implemented | Remove or implement claims; connect controls to real state | P1 |

## Highest-risk findings

1. The database only stored audit events and run summaries; it was not the source of truth.
2. The flight, test, configuration, security, health, and dashboard values were hard-coded.
3. Imported telemetry was not reusable by replay, compare, or reports.
4. Replay, vehicle visualization, project creation, test creation, and configuration editing were absent.

The remediation below keeps the local-first FastAPI/SQLite architecture and replaces demo constants with seeded rows that use the same normal application paths as user-created data.
