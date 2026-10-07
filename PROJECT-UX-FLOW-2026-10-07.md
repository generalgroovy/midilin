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

Local `python -m unittest discover -s tests -v`: **48 tests passed**. Three added regressions cover current/stale/unrecognized events, stopped input retention, explicit offline-inspector arguments without subprocess activity or profile writes, clearing on new process and no-op before input. Python compilation and diff checks are part of the candidate gate.

The existing target-platform Tk CI workflow now feeds synthetic events through the actual output handler, invokes the real button, checks mapped/layered and unmapped routing, rejects stale output and records the narrow monitor and input-inspector screenshots. All subprocess execution remains prohibited in that native workflow. Initial native CI and independent review are pending at this freeze.

## Release boundary

Candidate only until independent source review and root's rendered acceptance pass. Intended source URL: <https://github.com/generalgroovy/midilin>. No physical MIDI, active desktop mapping, service activation, driver change, audible result or installer execution has been performed. Source and native-widget acceptance cannot establish those separate device outcomes.
