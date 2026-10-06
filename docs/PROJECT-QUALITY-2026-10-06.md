# Mapping rehearsal and profile recovery

## Bounded plan

Primary journey: open a profile, find a control, understand its exact action and modifier rules, safely inspect a candidate event, then deliberately monitor or activate the existing runtime.

Evidence: search previously omitted parameters/profile fields; layer strings appeared character-by-character on Linux; the UI had no hardware-free explanation of overlapping/blocked mappings. Reload and close discarded display edits. Linux display saves also forced custom ownership/reset flags to true.

Implement a read-only mapping inspector with full mapping/reference details and routing explanations, using shared pure runtime rules while preserving Linux aliases/profiles and platform-specific release semantics. Protect edited settings with Save / Discard / Cancel; preserve non-editor profile keys and write complete profiles atomically.

Acceptance: preview matches a spy runtime across layered events, invokes no executors/devices/processes, malformed constraints cannot become unconditional mappings, search preserves source indices, profile save/reload/cancel preserves edits and custom data, real Tk interactions pass on target CI.

Fresh upstream baseline: `7e3667bf96d8a82efc4e2f95bd85b2efb746255f`. This includes an existing eight-line engineering/portfolio documentation addition; it is not work from this pass. Prior untracked artifacts are preserved and excluded.

## Delivered

- Find precise parameters and profile fields without losing mapping indices; table has horizontal and vertical scrolling.
- Select a mapping and use **Inspect / try event** or Enter. Readable field labels are the default; **Show JSON** retains exact syntax. Referenced script slots, action definitions and model parameters are inspectable without execution.
- Offline event rehearsal explains eligible, disabled, wrong-kind, profile and modifier results. It uses shared runtime rules, with zero executor or hardware imports in the preview module. It reports all matching mappings in configuration order.
- Display drafts survive cancelled reload/close. Save / Discard / Cancel is explicit; invalid or failed save keeps the console open. Profile replacement is atomic and retains fields outside the editor.
- Linux aliases, named profiles, relative/qualified modifier names and release-before-unhold semantics are preserved. Malformed layer fields are rejected by validation and blocked by runtime/preview; custom color-temperature ownership/reset flags survive Save.

## Evidence

- Final runtime source: `9d9c5543df12cc5528104c987d2aa311a37f6bc8`.
- [Ubuntu / Python 3.13 / Tk 8.6.14 CI](https://github.com/generalgroovy/midilin/actions/runs/37541538312): **passed**. `39` tests, configuration and Python checks passed.
- Local Windows checks: **39 tests passed**, Python compilation, strict UTF-8 decode of tracked source/docs and diff whitespace checks passed.
- A 36-case event matrix compares offline eligibility with the real router's spy action sink. Separate tests cover malformed constraints, complete parameter search, script reference inspection without executors, custom data preservation, atomic replacement failure, cancelled/failed Save and unchanged close.
- Real constructed Tk workflow: **passed** in target CI. Search/empty recovery, layered preview, plain/JSON detail toggle, invalid event recovery, visible inspector layout, save/discard/cancel, invalid draft and process-isolation assertions. [Rendered inspector](evidence/tk-readable-2026-10-06/mapping-inspector.png) and [machine-readable checks](evidence/tk-readable-2026-10-06/report.json) were downloaded from that run; the screenshot was visually reviewed.

## Iteration and remaining limits

Review caught malformed modifier conditions becoming unconstrained during an early extraction; they now fail closed and have runtime/preview regression tests. A first UI screenshot exposed unnecessary JSON syntax as the default view; readable labels now lead and JSON is optional. Existing mocked-constructor tests were kept compatible by tracking drafts after actual widget construction. The first local Windows pytest attempt encountered the pre-existing inaccessible global temporary directory; reruns used fresh isolated directories and passed.

The inspector is a snapshot of the loaded profile, independent of unsaved display fields and any currently running service. Reopen it after Reload. It explains routing only: value transformations, rate limits, action success, acoustic/display response, physical controls and drivers are not simulated. No new profile-switch UI is introduced; existing explicit CLI custom-profile paths remain.

Physical MIDI/controllers, Linux/Sway session integration, startup/services, installed drivers, active mappings, installer execution and human usability acceptance: **NOT_RUN**. Monitor lifecycle and stale-result regressions remain passing; no live lifecycle operations were performed. Existing untracked caches remain outside the commits.

## Reproduce

```sh
python -m unittest discover -s tests -v
# Target CI owns native GUI interaction:
CI=true xvfb-run -a -s "-screen 0 1280x900x24" python tests/tk_workflow.py
```

The Tk workflow requires Pillow for its screenshot and uses temporary profiles plus subprocess guards. It does not require connected devices. Parent review owns main promotion; no repository main branch, portfolio or installer configuration was changed by this agent.
