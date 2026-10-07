# MIDILIN usability iteration — 7 October 2026

## Result

The console now starts with the usable mapping list instead of a large controller diagram. A single next-action button guides saved-profile validation, device detection and input monitoring. Mapping rehearsal remains available without hardware. The full configuration path moved to Display settings, leaving the main strip readable.

Search now explains an empty result and **Clear filters** resets both query and Enabled/Disabled state, returning focus to search. Inspect is enabled only with a selected mapping; the original snapshot rehearsal, full JSON and layer explanations remain available.

**Monitor & runtime** separates read-only inspection from applying mappings to the desktop. A persistent process line stays separate from transient diagnostic feedback. Successful device listing is labeled “Device check complete”, because an exit-zero command can still find no hardware. Diagnostic actions take users to their results; live display sliders retain their tab and focus. Monitor/runtime restoration and save/discard/cancel ownership are unchanged.

The controller diagram now has horizontal and vertical scrollbars at smaller desktop sizes. The minimum window is 860×620; the native CI workflow checks this size and the normal 1180×760 view, including visible log, actions, recovery and keyboard focus.

## Verification

- Local: **43 behavior tests passed**, Python compilation and `git diff --check` passed.
- Existing real-Tk CI workflow extended with next-action transitions, synthetic empty device results, visible controls at 860×620, filter recovery, mapping-link focus and scrollable diagram, retaining inspector and save/discard/cancel checks.
- Native CI and independent review: pending candidate run/review. Screenshots and run URL will be recorded once available.
- No physical controller, driver, desktop action, service activation or human usability acceptance was performed. Tests use synthetic profile data and prohibit subprocess operations.

## Preserved boundaries

The OS-specific command routing, process restoration, runtime lock/service behavior, atomic profile save, unknown configuration fields and existing user/test directories remain intact. This iteration changes the console and its documentation/tests; it does not change installers or mappings.
