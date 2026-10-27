"""Per-config-entry runtime state and event handling."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import math
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.script import Script
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .appliance import (
    ApplianceCycleDetector,
    CycleEvent,
    CycleThresholds,
    CycleTransition,
)
from .const import (
    CONF_DOOR_ENTITY,
    CONF_FINISH_ACTIONS,
    CONF_FINISH_DURATION_SECONDS,
    CONF_FINISH_POWER_W,
    CONF_MAX_RUNTIME_ACTIONS,
    CONF_MAX_RUNTIME_SECONDS,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_PLUG_ENTITY,
    CONF_POWER_ENTITY,
    CONF_START_ACTIONS,
    CONF_START_DURATION_SECONDS,
    CONF_START_POWER_W,
    DEFAULT_FINISH_DURATION_SECONDS,
    DEFAULT_FINISH_POWER_W,
    DEFAULT_PENDING_DELAY_SECONDS,
    DEFAULT_PENDING_INTERVAL_SECONDS,
    DEFAULT_PENDING_REPEATS,
    DEFAULT_START_DURATION_SECONDS,
    DEFAULT_START_POWER_W,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_STORE_VERSION = 1
_SAVE_DELAY_SECONDS = 1
_ENERGY_UPDATE_INTERVAL = timedelta(minutes=1)


class ApplianceRuntime:
    """Own one appliance's detector, persistent state, and subscriptions."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.config = config
        thresholds = CycleThresholds(
            start_power_w=float(config.get(CONF_START_POWER_W, DEFAULT_START_POWER_W)),
            start_duration=timedelta(
                seconds=float(
                    config.get(
                        CONF_START_DURATION_SECONDS,
                        DEFAULT_START_DURATION_SECONDS,
                    )
                )
            ),
            finish_power_w=float(
                config.get(CONF_FINISH_POWER_W, DEFAULT_FINISH_POWER_W)
            ),
            finish_duration=timedelta(
                seconds=float(
                    config.get(
                        CONF_FINISH_DURATION_SECONDS,
                        DEFAULT_FINISH_DURATION_SECONDS,
                    )
                )
            ),
        )
        self.detector = ApplianceCycleDetector(thresholds)
        self.energy_kwh = 0.0
        self.door_open: bool | None = None
        self.pending_unload = False
        self.pending_reminder_count = 0
        self.next_pending_reminder: datetime | None = None
        self.max_runtime_fired = False
        self._energy_power_w: float | None = None
        self._energy_updated_at: datetime | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._unsubscribe_states: Callable[[], None] | None = None
        self._unsubscribe_timer: Callable[[], None] | None = None
        self._pending_action_running = False
        self._restoring_detector_state = False
        self._power_available = False
        self._store = Store(hass, _STORE_VERSION, f"{DOMAIN}_{entry.entry_id}")

    async def async_setup(self) -> None:
        """Restore state, subscribe to inputs, and reconcile current states."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._restore(stored)
            self._restoring_detector_state = True
        if not self.config.get(CONF_DOOR_ENTITY):
            self.pending_unload = False
            self.pending_reminder_count = 0
            self.next_pending_reminder = None

        entity_ids = [self.config[CONF_POWER_ENTITY]]
        for key in (CONF_DOOR_ENTITY, CONF_PLUG_ENTITY):
            entity_id = self.config.get(key)
            if entity_id:
                entity_ids.append(entity_id)
        self._unsubscribe_states = async_track_state_change_event(
            self.hass, entity_ids, self._async_handle_state_change
        )

        now = dt_util.utcnow()
        power_state = self.hass.states.get(self.config[CONF_POWER_ENTITY])
        self._apply_power_state(power_state, now, initialize_energy=True)

        door_entity = self.config.get(CONF_DOOR_ENTITY)
        if door_entity:
            door_state = self.hass.states.get(door_entity)
            self._apply_door_state(door_state, now)

        self._schedule_deadline()
        self._schedule_save()

    async def async_unload(self) -> None:
        """Cancel listeners and timers, then persist the final runtime state."""
        self._integrate_energy_to(dt_util.utcnow())
        if self._unsubscribe_states is not None:
            self._unsubscribe_states()
            self._unsubscribe_states = None
        if self._unsubscribe_timer is not None:
            self._unsubscribe_timer()
            self._unsubscribe_timer = None
        await self._store.async_save(self._export_state())

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity to runtime state changes."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def clear_pending_unload(self) -> None:
        """Clear the unload state and cancel all scheduled reminders."""
        self.pending_unload = False
        self.pending_reminder_count = 0
        self.next_pending_reminder = None
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    @property
    def max_runtime(self) -> timedelta | None:
        """Return the configured maximum runtime, if enabled."""
        seconds = self.config.get(CONF_MAX_RUNTIME_SECONDS)
        if seconds in (None, ""):
            return None
        return timedelta(seconds=float(seconds))

    @property
    def power_available(self) -> bool:
        """Return whether the selected power sensor currently has a valid reading."""
        return self._power_available

    @property
    def remaining_seconds(self) -> float | None:
        """Estimate remaining time from the most recently completed cycle."""
        if not self.detector.is_running or self.detector.last_cycle_duration is None:
            return None
        assert self.detector.cycle_started_at is not None
        elapsed = dt_util.utcnow() - self.detector.cycle_started_at
        return max(
            (self.detector.last_cycle_duration - elapsed).total_seconds(), 0.0
        )

    async def _async_handle_state_change(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data.get("new_state")
        now = dt_util.utcnow()

        if entity_id == self.config[CONF_POWER_ENTITY]:
            self._apply_power_state(new_state, now)
        elif entity_id == self.config.get(CONF_DOOR_ENTITY):
            self._apply_door_state(new_state, now)
        elif entity_id == self.config.get(CONF_PLUG_ENTITY):
            if new_state is not None and new_state.state == "off":
                event_result = self.detector.finish_by_switch(now)
                if event_result is not None:
                    self._handle_cycle_events([event_result])
                self._schedule_save()
                self._schedule_deadline()
            self._notify()

    def _apply_power_state(
        self, state: Any, now: datetime, initialize_energy: bool = False
    ) -> None:
        value = state.state if state is not None else None
        unit = (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if state is not None
            else None
        )
        watts = self.detector.to_watts(value, unit)

        if initialize_energy:
            self._energy_power_w = None
            self._energy_updated_at = None
        self._integrate_energy_to(now)
        if watts is None:
            self._power_available = False
            self._energy_power_w = None
            self._energy_updated_at = None
        else:
            self._power_available = True
            self._energy_power_w = watts
            self._energy_updated_at = now

        if initialize_energy or self._restoring_detector_state:
            events = self.detector.reconcile_power(value, unit, now)
            self._restoring_detector_state = watts is None
        else:
            events = self.detector.observe_power(value, unit, now)
        self._handle_cycle_events(events)
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    def _apply_door_state(self, state: Any, now: datetime) -> None:
        if state is None or state.state not in ("on", "off"):
            self.door_open = None
        else:
            self.door_open = state.state == "on"
            if self.door_open:
                self.clear_pending_unload()
            elif (
                self.pending_unload
                and not self.detector.is_running
                and self.config.get(CONF_PENDING_ACTIONS)
                and self.next_pending_reminder is None
            ):
                self.next_pending_reminder = now + timedelta(
                    seconds=self._pending_delay_seconds
                )
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    def _handle_cycle_events(self, events: list[CycleEvent]) -> None:
        for event in events:
            if event.transition is CycleTransition.STARTED:
                self.max_runtime_fired = False
                if self.config.get(CONF_DOOR_ENTITY):
                    self.pending_unload = self.door_open is not True
                    self.pending_reminder_count = 0
                    self.next_pending_reminder = None
                self._run_actions_in_background(CONF_START_ACTIONS)
            else:
                self._run_actions_in_background(CONF_FINISH_ACTIONS)
                if (
                    self.pending_unload
                    and self.door_open is False
                    and self.config.get(CONF_PENDING_ACTIONS)
                ):
                    self.next_pending_reminder = event.occurred_at + timedelta(
                        seconds=self._pending_delay_seconds
                    )
        self._schedule_save()
        self._schedule_deadline()

    @property
    def _pending_delay_seconds(self) -> int:
        return int(
            self.config.get(
                CONF_PENDING_DELAY_SECONDS, DEFAULT_PENDING_DELAY_SECONDS
            )
        )

    @property
    def _pending_interval_seconds(self) -> int:
        return int(
            self.config.get(
                CONF_PENDING_INTERVAL_SECONDS, DEFAULT_PENDING_INTERVAL_SECONDS
            )
        )

    @property
    def _pending_maximum(self) -> int:
        return 1 + int(self.config.get(CONF_PENDING_REPEATS, DEFAULT_PENDING_REPEATS))

    def _schedule_deadline(self) -> None:
        if self._unsubscribe_timer is not None:
            self._unsubscribe_timer()
            self._unsubscribe_timer = None

        deadlines: list[datetime] = []
        detector_deadline = (
            self.detector.next_deadline if self._power_available else None
        )
        if detector_deadline is not None:
            deadlines.append(detector_deadline)
        if self.detector.is_running and not self.max_runtime_fired:
            max_runtime = self.max_runtime
            if max_runtime is not None and self.detector.cycle_started_at is not None:
                deadlines.append(self.detector.cycle_started_at + max_runtime)
        if self.next_pending_reminder is not None:
            deadlines.append(self.next_pending_reminder)
        if self.detector.power_w is not None or self.detector.is_running:
            deadlines.append(
                dt_util.utcnow() + _ENERGY_UPDATE_INTERVAL
            )
        if deadlines:
            self._unsubscribe_timer = async_track_point_in_time(
                self.hass, self._async_handle_deadline, min(deadlines)
            )

    async def _async_handle_deadline(self, _: datetime) -> None:
        self._unsubscribe_timer = None
        now = dt_util.utcnow()
        if self.detector.next_deadline is not None and self._power_available:
            power_state = self.hass.states.get(self.config[CONF_POWER_ENTITY])
            power = self.detector.to_watts(
                power_state.state if power_state else None,
                power_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                if power_state
                else None,
            )
            if power is None:
                self.detector.observe_power(None, None, now)
            else:
                self._handle_cycle_events(self.detector.advance_time(now))

        if (
            self.detector.is_running
            and not self.max_runtime_fired
            and self.max_runtime is not None
            and self.detector.cycle_started_at is not None
            and now >= self.detector.cycle_started_at + self.max_runtime
        ):
            self.max_runtime_fired = True
            self._run_actions_in_background(CONF_MAX_RUNTIME_ACTIONS)

        if (
            self.pending_unload
            and self.next_pending_reminder is not None
            and now >= self.next_pending_reminder
        ):
            if not self.config.get(CONF_PENDING_ACTIONS):
                self.next_pending_reminder = None
            elif self.door_open is False and not self._pending_action_running:
                self.pending_reminder_count += 1
                self._pending_action_running = True
                await self._run_actions(CONF_PENDING_ACTIONS)
                self._pending_action_running = False
                if self.pending_unload and self.pending_reminder_count < self._pending_maximum:
                    self.next_pending_reminder = now + timedelta(
                        seconds=self._pending_interval_seconds
                    )
                else:
                    self.next_pending_reminder = None
            elif self.door_open is None:
                self.next_pending_reminder = now + timedelta(
                    seconds=self._pending_interval_seconds
                )
            else:
                self.next_pending_reminder = None

        self._integrate_energy_to(now)
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    def _integrate_energy_to(self, now: datetime) -> None:
        if self._energy_power_w is None or self._energy_updated_at is None:
            return
        elapsed_seconds = max((now - self._energy_updated_at).total_seconds(), 0.0)
        self.energy_kwh += self._energy_power_w * elapsed_seconds / 3_600_000
        self._energy_updated_at = now

    def _run_actions_in_background(self, key: str) -> None:
        self.entry.async_create_background_task(
            self.hass,
            self._run_actions(key),
            name=f"{DOMAIN} {self.entry.entry_id} {key}",
        )

    async def _run_actions(self, key: str) -> None:
        actions = self.config.get(key, [])
        if not isinstance(actions, list):
            return
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            try:
                await Script(
                    self.hass,
                    [action],
                    f"{DOMAIN} {key} {index + 1}",
                    DOMAIN,
                    logger=_LOGGER,
                ).async_run()
            except Exception:
                _LOGGER.error("Configured %s action %s failed", key, index + 1)

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._export_state, _SAVE_DELAY_SECONDS)

    def _export_state(self) -> dict[str, Any]:
        return {
            "detector": self.detector.export_state(),
            "energy_kwh": self.energy_kwh,
            "door_open": self.door_open,
            "pending_unload": self.pending_unload,
            "pending_reminder_count": self.pending_reminder_count,
            "next_pending_reminder": (
                self.next_pending_reminder.isoformat()
                if self.next_pending_reminder is not None
                else None
            ),
            "max_runtime_fired": self.max_runtime_fired,
        }

    def _restore(self, stored: dict[str, Any]) -> None:
        try:
            detector_state = stored.get("detector")
            if isinstance(detector_state, dict):
                self.detector.restore_state(detector_state)
            energy = float(stored.get("energy_kwh", 0))
            if not math.isfinite(energy) or energy < 0:
                raise ValueError("Invalid stored energy")
            self.energy_kwh = energy
            door_open = stored.get("door_open")
            self.door_open = door_open if isinstance(door_open, bool) else None
            self.pending_unload = bool(stored.get("pending_unload", False))
            self.pending_reminder_count = max(
                0, int(stored.get("pending_reminder_count", 0))
            )
            next_reminder = stored.get("next_pending_reminder")
            if next_reminder is not None:
                if not isinstance(next_reminder, str):
                    raise ValueError("Invalid stored reminder timestamp")
                self.next_pending_reminder = datetime.fromisoformat(next_reminder)
                if self.next_pending_reminder.tzinfo is None:
                    raise ValueError("Stored reminder timestamp has no timezone")
            self.max_runtime_fired = bool(stored.get("max_runtime_fired", False))
        except (TypeError, ValueError, OverflowError):
            _LOGGER.warning("Stored appliance state is invalid; starting fresh")
            self.detector = ApplianceCycleDetector(self.detector.thresholds)
            self.energy_kwh = 0.0
            self.door_open = None
            self.pending_unload = False
            self.pending_reminder_count = 0
            self.next_pending_reminder = None
            self.max_runtime_fired = False

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()