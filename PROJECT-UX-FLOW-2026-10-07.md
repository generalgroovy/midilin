# MIDILIN input-to-mapping explanation — 7 October 2026

## Observed friction

The monitor prints incoming event data and flashes the controller diagram on a different tab. To understand a received control, users had to remember its device/control name, switch tabs, search and reopen the offline inspector. This was especially unhelpful when input arrived but a layer, disabled mapping or missing mapping explained why an action was unavailable.

Baseline `2b1f1d5f7221776c94b1425e1c134d80b2cc630c` matched origin/main. Candidate branch: `codex/ux-flow-2026-10-07`. No applicable AGENTS.md was present. The baseline checkout was clean.

## Result

- Monitor & runtime now keeps a compact **Last received** summary with device, control, event kind and value. **Inspect last input** remains disabled until a supported event arrives from the current console child.
- The action opens the existing offline inspector with the received device/control/event and the corresponding mapping selected. All routing candidates remain visible, including disabled, different-kind and layer-blocked mappings. Linux aliases and profile rules continue through the existing pure routing rules.
- An unmapped input opens a clear explanation and the editable rehearsal instead of leaving users without a next step. The header explains that held controls were not captured and must be entered for the rehearsal.
- The inspector uses a loaded-profile snapshot, exposes complete mapping/reference details and Show JSON, and never replays the event or invokes desktop actions. A later received event does not change an open snapshot.
- Old-child output is rejected before updating the summary. Starting a new console process clears the prior input; stopping retains the honestly labeled historical Last received input for inspection. Service/runtime restoration, detection, profile save/reload and active control remain unchanged.

## Validation

Local `python -m unittest discover -s tests -v`: **48 tests passed**. Three added regressions cover current/stale/unrecognized events, stopped input retention, explicit offline-inspector arguments without subprocess activity or profile writes, clearing on new process and no-op before input. Python compilation and diff checks passed.

Final runtime `4f0f6aa728f40c77e123d836c8f8c52932500b78` passed [native CI 37614874167](https://github.com/generalgroovy/midilin/actions/runs/37614874167), including all 48 tests, configuration validation and the target-platform Tk workflow. The native journey feeds synthetic events through the actual output handler, invokes the real button, checks mapped/layered and unmapped routing and rejects stale output. All subprocess execution remains prohibited in that workflow, which reported zero Tk callback errors.

The owner inspected the three complete final screenshots at [docs/evidence/ux-flow-2026-10-07/4f0f6aa](docs/evidence/ux-flow-2026-10-07/4f0f6aa): 860×620 monitor, 790×640 inspector and its 580×480 minimum. The received-input summary, explicit inspector action, Show JSON and Try event fit; long details and results retain their scroll areas. The native workflow checks widget containment and Show JSON activation at the minimum size. Receipt and screenshots are also in shared `ux-flow-2026-10-07/evidence/midilin-ci-final/`.

Independent reviewer `flow_a` passed the final paired source, independently running the original full 48/60 suites and three focused cases per final runtime. The reviewer found that a fixed-width new header could crowd Show JSON at 580px. The correction reserves the checkbox width and wraps the header to the remaining space; expanded native CI verifies both platforms at 580×480. No outstanding source findings remain. Shared review: `ux-flow-2026-10-07/reviews/midi-review.md`.

## Release boundary

Root separately inspected the final Linux and Windows narrow monitor windows and minimum-size inspectors, accepted the visible controls/results/header and clear offline-action boundaries, and authorized normal main promotion. The source release consists of the reviewed runtime above plus evidence-only documentation. Source URL: <https://github.com/generalgroovy/midilin>. The shared machine release receipt records the exact final main SHA and source verification; no hosted deployment is applicable.

No physical MIDI, active desktop mapping, service activation, driver change, audible result or installer execution has been performed. Source and native-widget acceptance cannot establish those separate device outcomes.
