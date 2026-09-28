from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from .common import BUILTIN_ACTIONS, DEFAULT_CONFIG, load_config
from .router import EventRouter
from .unified_actions import ActionDispatcher


def load_backend() -> Any:
    candidates: list[Path] = []
    if os.environ.get("TRAKTOR_CONTROLLER_BACKEND"):
        candidates.append(Path(os.environ["TRAKTOR_CONTROLLER_BACKEND"]).expanduser())
    candidates.extend([
        Path.home() / ".local/lib/traktor-system-controller/backend.py",
        Path(__file__).resolve().parents[1] / "traktor-system-controller.py",
    ])
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("traktor_hardware_backend", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    raise SystemExit("Traktor hardware backend not found; run install.sh.")


def _mapping_signature(mapping: dict[str, Any]) -> str:
    action = str(mapping.get("action", ""))
    if action == "script_slot":
        return f"script_slot:{mapping.get('slot', '')}"
    if action in {"model_parameter_absolute", "model_parameter_relative"}:
        return f"{action}:{mapping.get('parameter', '')}"
    return action


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(config.get("actions", {}), dict):
        errors.append("actions must be an object")
    mappings = config.get("mappings", [])
    if not isinstance(mappings, list):
        return errors + ["mappings must be an array"]
    known_actions = set(config.get("actions", {})) | BUILTIN_ACTIONS
    signatures: dict[tuple[str, str], int] = {}
    enforce_unique = bool(config.get("layout_rules", {}).get(
        "no_repeated_actions_per_controller", True
    ))
    for index, mapping in enumerate(mappings):
        prefix = f"mappings[{index}]"
        if not isinstance(mapping, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ("device", "control", "kind", "action"):
            if key not in mapping:
                errors.append(f"{prefix} missing {key}")
        if "action" in mapping and str(mapping["action"]) not in known_actions:
            errors.append(f"{prefix} references unknown action {mapping['action']!r}")
        if mapping.get("kind") not in {"press", "release", "relative", "absolute", None}:
            errors.append(f"{prefix} has unsupported kind {mapping.get('kind')!r}")
        if mapping.get("action") == "script_slot" and not mapping.get("slot"):
            errors.append(f"{prefix} script_slot requires slot")
        if mapping.get("action") in {"model_parameter_absolute", "model_parameter_relative"} and not mapping.get("parameter"):
            errors.append(f"{prefix} model action requires parameter")
        if enforce_unique and bool(mapping.get("enabled", True)):
            key = (str(mapping.get("device", "")), _mapping_signature(mapping))
            if key in signatures:
                errors.append(
                    f"{prefix} repeats {_mapping_signature(mapping)!r} on {key[0]} "
                    f"(already mappings[{signatures[key]}])"
                )
            signatures[key] = index
    parameters = config.get("model_controls", {}).get("parameters", {})
    if not isinstance(parameters, dict):
        errors.append("model_controls.parameters must be an object")
    else:
        for name, spec in parameters.items():
            if not isinstance(spec, dict):
                errors.append(f"model parameter {name!r} must be an object")
                continue
            if float(spec.get("max", 1)) <= float(spec.get("min", 0)):
                errors.append(f"model parameter {name!r} max must exceed min")
    return errors


def show_layout(config: dict[str, Any], profile: str | None) -> int:
    selected = profile or str(config.get("active_profile", "linux-ops"))
    router = EventRouter(config, monitor=False, profile=selected, dry_run=True)
    print(f"Active profile: {selected}")
    details = config.get("profiles", {}).get(selected, {})
    if isinstance(details, dict) and details.get("description"):
        print(f"Description: {details['description']}")
    print()
    rows: list[tuple[str, str, str, str, str]] = []
    for (device, control, kind), mappings in router.mappings.items():
        for mapping in mappings:
            modifiers: list[str] = []
            for key in ("requires", "unless"):
                value = mapping.get(key)
                if value:
                    values = value if isinstance(value, list) else [value]
                    modifiers.append(f"{key}=" + ",".join(str(item) for item in values))
            rows.append((device, control, kind, _mapping_signature(mapping), " ".join(modifiers)))
    for device, control, kind, action, modifiers in sorted(rows):
        print(f"{device:3} {control:27} {kind:8} -> {action}" + (f" [{modifiers}]" if modifiers else ""))
    return 0


def show_model_state(config: dict[str, Any]) -> int:
    path = Path(str(config.get("model_controls", {}).get(
        "state_file", "~/.config/traktor-system-controller/model-controls.json"
    ))).expanduser()
    if not path.exists():
        print(f"No model state yet: {path}")
        return 1
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile")
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--show-layout", action="store_true")
    parser.add_argument("--validate-config", action="store_true")
    parser.add_argument("--approve-connected", action="store_true")
    parser.add_argument("--deny-connected", action="store_true")
    parser.add_argument("--forget-device-decisions", action="store_true")
    parser.add_argument("--list-themes", action="store_true")
    parser.add_argument("--set-theme")
    parser.add_argument("--visual-theme")
    parser.add_argument("--model-state", action="store_true")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--set-brightness", type=int, metavar="PERCENT")
    parser.add_argument("--set-temperature", type=int, metavar="KELVIN")
    parser.add_argument("--diagnose-display", action="store_true")
    args = parser.parse_args()

    if args.gui:
        from .gui import main as gui_main
        return gui_main(config_path=args.config)

    config = load_config(args.config)
    errors = validate_config(config)
    if args.validate_config:
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Configuration valid: {args.config}")
        return 0
    if errors:
        raise SystemExit("Invalid configuration:\n- " + "\n- ".join(errors))

    dispatcher = ActionDispatcher(config, dry_run=args.dry_run)
    if args.set_brightness is not None:
        return 0 if dispatcher.set_brightness_percent(args.set_brightness) else 1
    if args.set_temperature is not None:
        return 0 if dispatcher.set_color_temperature_kelvin(args.set_temperature) else 1
    if args.diagnose_display:
        for line in dispatcher.diagnose_displays():
            print(line)
        return 0
    if args.model_state:
        return show_model_state(config)
    if args.show_layout:
        return show_layout(config, args.profile)

    backend = load_backend()
    if args.list_devices or args.list_ports:
        return backend.list_devices()
    if args.list_themes:
        print("\n".join(sorted(backend.THEMES)))
        return 0
    if args.set_theme:
        backend.set_theme(config, args.set_theme)
        print(f"Visual theme set to {args.set_theme}. Restart the service to apply it.")
        return 0
    if args.approve_connected:
        return backend.approve_connected(config, "always")
    if args.deny_connected:
        return backend.approve_connected(config, "never")
    if args.forget_device_decisions:
        return backend.forget_device_decisions(config)

    runtime = backend.ControllerRuntime(
        EventRouter(config, monitor=args.monitor, profile=args.profile, dry_run=args.dry_run),
        config=config, visual_theme=args.visual_theme,
    )
    try:
        runtime.run()
    except KeyboardInterrupt:
        print()
        return 0
    return 0
