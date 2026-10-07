# MIDILIN usability iteration — 7 October 2026

## Result

The console now starts with the usable mapping list instead of a large controller diagram. A single next-action button guides saved-profile validation, device detection and input monitoring. Mapping rehearsal remains available without hardware. The full configuration path moved to Display settings, leaving the main strip readable.

Search now explains an empty result and **Clear filters** resets both query and Enabled/Disabled state, returning focus to search. Inspect is enabled only with a selected mapping; the original snapshot rehearsal, full JSON and layer explanations remain available.

**Monitor & runtime** separates read-only inspection from applying mappings to the desktop. A persistent process line stays separate from transient diagnostic feedback. Successful device listing is labeled “Device check complete”, because an exit-zero command can still find no hardware. Diagnostic actions take users to their results; live display sliders retain their tab and focus. Monitor/runtime restoration and save/discard/cancel ownership are unchanged.

The controller diagram now has horizontal and vertical scrollbars at smaller desktop sizes. The minimum window is 860×620; the native CI workflow checks this size and the normal view (up to 1180×760, clamped to the screen), including visible log, actions, recovery and keyboard focus.

## Verification

- Local: **45 behavior tests passed**, Python compilation and `git diff --check` passed.
- Existing real-Tk CI workflow extended with next-action transitions, synthetic empty device results, visible controls at 860×620, filter recovery, mapping-link focus and scrollable diagram, retaining inspector and save/discard/cancel checks.
- Final runtime `f1dea48e78ce93cfdbb6df2ed06e907ca1ec1a55`: [native CI 37602095224](https://github.com/generalgroovy/midilin/actions/runs/37602095224) passed **45 tests**, configuration validation and the real Tk workflow. Shell/SVG checks also passed.
- Accepted screenshots and workflow receipt: [docs/evidence/ux-2026-10-07/f1dea48](docs/evidence/ux-2026-10-07/f1dea48). Linux uses 1180×760 and Windows fits its 1024×768 desktop with a 976×668 client window; both check 860×620. All controls/logs are contained, with zero Tk callback errors.
- Screenshot self-review caught an initially clipped Windows window. Startup now respects screen space. The first screen-sizing follow-up failed mocked-constructor tests; keeping native geometry in UI construction fixed that fixture boundary. Fresh full checks passed.
- Separate reviewer `ux_ko` checked both implementations. It found MIDILIN could replace newer monitor state with a delayed service-command completion. The fix associates service feedback with its command and session generation; positive and negative regression tests pass. The reviewer confirmed the P2 resolution. Root performs final rendered/integration acceptance. No new behavior is introduced by the subsequent evidence/documentation commit.
- No physical controller, driver, desktop action, service activation or human usability acceptance was performed. Tests use synthetic profile data and prohibit subprocess operations.

## Preserved boundaries

The OS-specific command routing, process restoration, runtime lock/service behavior, atomic profile save, unknown configuration fields and existing user/test directories remain intact. This iteration changes the console and its documentation/tests; it does not change installers or mappings.
