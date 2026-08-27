# Ecosystem research and originality boundary

| Tool | What it already does | MVP relationship |
| --- | --- | --- |
| [OpenRocket](https://openrocket.info/features.html) | Open-source rocket design, stability information, and flight simulation. | Read-only `.ork` artifact input; this prototype does not replace its simulation. |
| [NASA Open MCT](https://nasa.github.io/openmct/about-open-mct/) | Extensible mission-control and telemetry visualization framework. | Future dashboard/export adapter; this prototype contributes student validation context. |
| [NASA NOS3](https://github.com/nasa/nos3) | Software development, integration/test, operations training, and hardware models for space systems. | Future high-fidelity / flight-software target; not copied or embedded. |
| [NASA cFS](https://github.com/nasa/cFS) | Reusable flight-software framework with telemetry and command ecosystem. | Potential integration target through adapters and tests. |
| [RASAero](https://www.rasaero.com/) | Specialist rocket aerodynamic analysis. | Remains an external design-analysis input. |
| [SatNOGS](https://satnogs.org/) | Open ground-station network and observation ecosystem. | Conceptual reference for adapters; not a replacement. |

No code was copied from these projects. The original contribution here is a lightweight, local-first workflow for student teams: import engineering context → simulate telemetry → inject faults → record test evidence → compare with test/flight data → maintain traceable configuration history.
