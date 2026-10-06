"""Pure routing rules shared by the runtime and the offline inspector.

This module deliberately has no action, device or subprocess imports.
"""
from __future__ import annotations

from typing import Any

SUPPORTS_PROFILES = True

from .common import X1_DEFAULT_ALIASES


def control_aliases(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    aliases = {"x1": dict(X1_DEFAULT_ALIASES), "f1": {}}
    configured = config.get("control_aliases", {})
    if not isinstance(configured, dict):
        return aliases
    for device, values in configured.items():
        if isinstance(values, dict):
            aliases.setdefault(str(device), {}).update({str(k): str(v) for k, v in values.items()})
    return aliases


def profile_matches(mapping: dict[str, Any], profile: str) -> bool:
    value = mapping.get("profile", mapping.get("profiles"))
    if value is None:
        return True
    return value == profile if isinstance(value, str) else isinstance(value, list) and profile in {str(v) for v in value}


def tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError("Layer conditions must be a name or a list of non-empty names.")
    return value


def state_key(token: str, device: str) -> tuple[str, str]:
    token = token.strip()
    for separator in (".", ":"):
        if separator in token:
            left, right = token.split(separator, 1)
            return left, right
    return device, token


def layer_reasons(mapping: dict[str, Any], device: str, held: set[tuple[str, str]]) -> list[str]:
    try:
        required, excluded = tokens(mapping.get("requires", [])), tokens(mapping.get("unless", []))
    except ValueError as error:
        return ["Invalid layer condition: " + str(error)]
    missing = [v for v in required if state_key(v, device) not in held]
    blocked = [v for v in excluded if state_key(v, device) in held]
    return (["Hold " + ", ".join(missing)] if missing else []) + (["Release " + ", ".join(blocked)] if blocked else [])


def preview_event(config: dict[str, Any], device: str, control: str, kind: str,
                  held_text: str = "", profile: str = "") -> dict[str, Any]:
    if kind not in {"press", "release", "relative", "absolute"}:
        raise ValueError("Choose press, release, relative or absolute.")
    if not device.strip() or not control.strip():
        raise ValueError("Choose a device and control.")
    device, control = device.strip(), control.strip()
    control = control_aliases(config).get(device, {}).get(control, control)
    profile = profile.strip() or str(config.get("active_profile", "linux-ops"))
    held = {state_key(v, device) for v in held_text.replace(",", " ").split()}
    # Linux release mappings observe the held control before it is removed.
    if kind == "press":
        held.add((device, control))
    decisions = []
    for index, mapping in enumerate(config.get("mappings", [])):
        if not isinstance(mapping, dict) or (mapping.get("device"), mapping.get("control")) != (device, control):
            continue
        reasons = []
        if not mapping.get("enabled", True):
            reasons.append("Disabled")
        if not profile_matches(mapping, profile):
            reasons.append("Different profile")
        if mapping.get("kind") != kind:
            reasons.append("Needs " + str(mapping.get("kind", "event kind")))
        reasons.extend(layer_reasons(mapping, device, held))
        decisions.append((index, mapping, reasons))
    return {"control": control, "profile": profile, "decisions": decisions}
