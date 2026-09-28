"""Read-only mapping summaries and bounded command execution for the GUI."""
from __future__ import annotations

import subprocess
from typing import Any


def mapping_rows(config: dict[str, Any], query: str = "", state: str = "All") -> list[tuple[str, tuple[str, ...]]]:
    rows = []
    terms = query.casefold().split()
    for index, mapping in enumerate(config.get("mappings", [])):
        if not isinstance(mapping, dict):
            continue
        enabled = "Enabled" if mapping.get("enabled", True) else "Disabled"
        if state != "All" and enabled != state:
            continue
        action = str(mapping.get("action", ""))
        detail = mapping.get("slot") or mapping.get("parameter")
        if detail:
            action += f":{detail}"
        layer = "; ".join(f"{key}: {', '.join(mapping[key])}" for key in ("requires", "unless") if mapping.get(key))
        values = tuple(str(mapping.get(key, "")) for key in ("device", "control", "kind")) + (action, layer, enabled)
        if all(term in " ".join(values).casefold() for term in terms):
            rows.append((str(index), values))
    return rows


def execute_command(command: list[str], timeout: float = 20) -> tuple[int | None, str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return None, f"Timed out after {timeout:g}s. Check the device or service and retry.\n"
    except OSError as error:
        return None, f"Could not run command: {error}\n"
