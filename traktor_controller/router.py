from __future__ import annotations

import time
from typing import Any

from .common import ControlEvent, log
from .mapping_rules import control_aliases, layer_reasons, profile_matches, state_key
from .unified_actions import ActionDispatcher


class EventRouter:
    def __init__(
        self, config: dict[str, Any], monitor: bool,
        profile: str | None = None, dry_run: bool = False,
    ):
        self.config = config
        self.monitor = monitor
        self.profile = profile or str(config.get("active_profile", "linux-ops"))
        self.dispatcher = ActionDispatcher(config, dry_run=dry_run)
        self.mappings: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        self.last_dispatch: dict[tuple[str, str, str], float] = {}
        self.held: set[tuple[str, str]] = set()

        self.aliases = control_aliases(config)

        for mapping in config.get("mappings", []):
            if not isinstance(mapping, dict) or not bool(mapping.get("enabled", True)):
                continue
            if not self._profile_matches(mapping):
                continue
            key = (str(mapping["device"]), str(mapping["control"]), str(mapping["kind"]))
            self.mappings.setdefault(key, []).append(mapping)

    def _profile_matches(self, mapping: dict[str, Any]) -> bool:
        return profile_matches(mapping, self.profile)

    def _state_key(self, token: str, event: ControlEvent) -> tuple[str, str]:
        return state_key(token, event.device)

    def _conditions_match(self, mapping: dict[str, Any], event: ControlEvent) -> bool:
        return not layer_reasons(mapping, event.device, self.held)

    def _normalize(self, event: Any) -> ControlEvent:
        raw = str(event.control)
        return ControlEvent(
            device=str(event.device),
            control=self.aliases.get(str(event.device), {}).get(raw, raw),
            kind=str(event.kind), value=int(event.value),
            minimum=int(getattr(event, "minimum", 0)),
            maximum=int(getattr(event, "maximum", 1)),
            source=str(getattr(event, "source", "")), raw_control=raw,
        )

    def emit(self, raw_event: Any) -> None:
        event = self._normalize(raw_event)
        held_key = (event.device, event.control)
        if event.kind == "press":
            self.held.add(held_key)
        try:
            if self.monitor:
                log(event.describe())
                return
            key = (event.device, event.control, event.kind)
            mappings = self.mappings.get(key, [])
            if event.kind == "absolute" and mappings:
                now = time.monotonic()
                if now - self.last_dispatch.get(key, 0.0) < 0.04:
                    return
                self.last_dispatch[key] = now
            for mapping in mappings:
                if self._conditions_match(mapping, event):
                    self.dispatcher.dispatch(mapping, event)
        finally:
            if event.kind == "release":
                self.held.discard(held_key)
