"""Per-config-entry runtime state and event handling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import math
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.script import Script
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .appliance import (
    ApplianceCycleDetector,
    BinaryActivityDetector,
    CycleEvent,
    CycleThresholds,
    CycleTransition,
)
from .appliance_types import get_appliance_profile
from .const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_TYPE,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_CLIMATE_ENTITY,
    CONF_DOOR_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_EMPTIED_ACTIONS,
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    CONF_MAIL_ARRIVAL_ACTIONS,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
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
    CONF_RUNNING_ENTITY,
    CONF_START_ACTIONS,
    CONF_START_DURATION_SECONDS,
    CONF_START_POWER_W,
    DEFAULT_FINISH_DURATION_SECONDS,
    DEFAULT_FINISH_POWER_W,
    DEFAULT_ALARM_REPEAT_COUNT,
    DEFAULT_ALARM_REPEAT_INTERVAL_SECONDS,
    DEFAULT_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    DEFAULT_DOOR_OPEN_DELAY_SECONDS,
    DEFAULT_PLUG_OFF_REPEAT_COUNT,
    DEFAULT_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
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
_ACTIVITY_SOURCE_KEYS = {
    "power": CONF_POWER_ENTITY,
    "climate": CONF_CLIMATE_ENTITY,
    "running_sensor": CONF_RUNNING_ENTITY,
    "mail_motion": CONF_MAIL_MOTION_ENTITY,
    "mail_slot": CONF_MAIL_SLOT_ENTITY,
    "smart_plug": CONF_PLUG_ENTITY,
}


class ApplianceRuntime:
    """Own one appliance's detector, persistent state, and subscriptions."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.config = config
        self.profile = get_appliance_profile(config.get(CONF_APPLIANCE_TYPE, "washer"))
        self._configured_inputs = {
            item.config_key: config[item.config_key]
            for item in self.profile.sensor_inputs
            if config.get(item.config_key)
        }
        self._unavailable_inputs: set[str] = set()
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
        self.detector = (
            BinaryActivityDetector()
            if "power" not in self.profile.detection_sources
            else ApplianceCycleDetector(thresholds)
        )
        self._mail_sensor_ready = False
        self.mail_slot_open: bool | None = None
        self.energy_kwh = 0.0
        self.door_open: bool | None = None
        self.pending_unload = False
        self.pending_reminder_count = 0
        self.next_pending_reminder: datetime | None = None
        self._pending_generation = 0
        self.door_alarm_active = False
        self.door_alarm_fired_count = 0
        self.next_door_alarm: datetime | None = None
        self._door_alarm_action_running = False
        self._alarm_generation = {"door": 0, "compressor": 0, "plug_off": 0}
        self.compressor_alarm_active = False
        self.compressor_alarm_fired_count = 0
        self.next_compressor_alarm: datetime | None = None
        self._compressor_alarm_action_running = False
        self.plug_off_alarm_active = False
        self.plug_off_alarm_fired_count = 0
        self.next_plug_off_alarm: datetime | None = None
        self._plug_off_alarm_action_running = False
        self._plug_is_off: bool | None = None
        self.max_runtime_fired = False
        self._energy_power_w: float | None = None
        self._energy_updated_at: datetime | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._action_locks: dict[str, asyncio.Lock] = {}
        self._unsubscribe_states: Callable[[], None] | None = None
        self._unsubscribe_timer: Callable[[], None] | None = None
        self._unsubscribe_entity_registry: Callable[[], None] | None = None
        self._is_unloading = False
        self._pending_action_running = False
        self._restoring_detector_state = False
        self._power_available = False
        self._last_valid_power_w: float | None = None
        self._store = Store(hass, _STORE_VERSION, f"{DOMAIN}_{entry.entry_id}")

    async def async_setup(self) -> None:
        """Restore state, subscribe to inputs, and reconcile current states."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._restore(stored)
            self._restoring_detector_state = True
        if (
            "pending_unload" not in self.profile.parameter_groups
            or not self.config.get(CONF_DOOR_ENTITY)
        ):
            self.pending_unload = False
            self.pending_reminder_count = 0
            self.next_pending_reminder = None

        source_key = _ACTIVITY_SOURCE_KEYS[self.profile.detection_sources[0]]
        entity_ids = list(dict.fromkeys(self._configured_inputs.values()))
        self._unsubscribe_states = async_track_state_change_event(
            self.hass, entity_ids, self._async_handle_state_change
        )
        for entity_id in entity_ids:
            self._update_input_availability(
                entity_id, self.hass.states.get(entity_id)
            )

        now = dt_util.utcnow()
        source_entity_id = self.config.get(source_key)
        source_state = (
            self.hass.states.get(source_entity_id) if source_entity_id else None
        )
        if "climate" in self.profile.detection_sources:
            self._apply_climate_state(source_state, now, initialize=True)
        elif "running_sensor" in self.profile.detection_sources:
            self._apply_running_state(source_state, now, initialize=True)
        elif "smart_plug" in self.profile.detection_sources:
            self._apply_running_state(source_state, now, initialize=True)
        elif "mail_motion" in self.profile.detection_sources or "mail_slot" in self.profile.detection_sources:
            self._initialize_mail_sensor(source_state)
        else:
            self._apply_power_state(source_state, now, initialize_energy=True)

        if source_key != CONF_POWER_ENTITY and self.config.get(CONF_POWER_ENTITY):
            self._apply_power_state(
                self.hass.states.get(self.config[CONF_POWER_ENTITY]),
                now,
                initialize_energy=True,
            )

        door_entity = self.config.get(CONF_DOOR_ENTITY)
        if door_entity:
            door_state = self.hass.states.get(door_entity)
            self._apply_door_state(door_state, now)
        plug_entity = self.config.get(CONF_PLUG_ENTITY)
        if plug_entity:
            self._update_plug_off_alarm_state(
                self.hass.states.get(plug_entity), now
            )
            self._schedule_alarm_if_due("plug_off", now)

        self._schedule_deadline()
        self._schedule_save()

    async def async_unload(self) -> None:
        """Cancel listeners and timers, then persist the final runtime state."""
        self._is_unloading = True
        self._integrate_energy_to(dt_util.utcnow())
        if self._unsubscribe_states is not None:
            self._unsubscribe_states()
            self._unsubscribe_states = None
        if self._unsubscribe_timer is not None:
            self._unsubscribe_timer()
            self._unsubscribe_timer = None
        for entity_id in self._configured_inputs.values():
            async_delete_issue(self.hass, DOMAIN, self._input_issue_id(entity_id))
        self._unavailable_inputs.clear()
        await self._store.async_save(self._export_state())

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity to runtime state changes."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def clear_pending_unload(self) -> None:
        """Clear the unload state and cancel all scheduled reminders."""
        was_pending = self.pending_unload
        self._pending_generation += 1
        self.pending_unload = False
        self.pending_reminder_count = 0
        self.next_pending_reminder = None
        self._pending_action_running = False
        if (
            was_pending
            and ("mail_motion" in self.profile.detection_sources or "mail_slot" in self.profile.detection_sources)
        ):
            self._run_actions_in_background(CONF_FINISH_ACTIONS)
        if was_pending and "emptied" in self.profile.action_groups:
            self._run_actions_in_background(CONF_EMPTIED_ACTIONS)
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
    def display_power_w(self) -> float | None:
        """Return the last valid power reading for display during source outages."""
        return self._last_valid_power_w

    @property
    def display_energy_kwh(self) -> float | None:
        """Return the selected energy total or the locally calculated total."""
        entity_id = self.config.get(CONF_ENERGY_ENTITY)
        if not entity_id:
            return self.energy_kwh
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if not isinstance(unit, str) or unit not in EnergyConverter.VALID_UNITS:
            return None
        try:
            value = float(state.state)
            converted = EnergyConverter.convert(value, unit, UnitOfEnergy.KILO_WATT_HOUR)
        except (TypeError, ValueError):
            return None
        return converted if math.isfinite(converted) and converted >= 0 else None

    def reset_local_energy(self) -> None:
        """Reset the locally calculated total without changing an external source."""
        if not self.config.get(CONF_POWER_ENTITY) or self.config.get(CONF_ENERGY_ENTITY):
            return
        self._integrate_energy_to(dt_util.utcnow())
        self.energy_kwh = 0.0
        self._schedule_save()
        self._notify()

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
        if self._is_unloading:
            return
        entity_id = event.data["entity_id"]
        new_state = event.data.get("new_state")
        now = dt_util.utcnow()

        if (
            "climate" in self.profile.detection_sources
            and entity_id == self.config.get(CONF_CLIMATE_ENTITY)
        ):
            self._apply_climate_state(new_state, now)
        elif (
            "running_sensor" in self.profile.detection_sources
            and entity_id == self.config.get(CONF_RUNNING_ENTITY)
        ):
            self._apply_running_state(new_state, now)
        elif (
            "mail_motion" in self.profile.detection_sources
            and entity_id == self.config.get(CONF_MAIL_MOTION_ENTITY)
        ) or (
            "mail_slot" in self.profile.detection_sources
            and entity_id == self.config.get(CONF_MAIL_SLOT_ENTITY)
        ):
            self._apply_mail_sensor_state(new_state, now)
        elif entity_id == self.config.get(CONF_POWER_ENTITY):
            self._apply_power_state(new_state, now)
        elif (
            "smart_plug" in self.profile.detection_sources
            and entity_id == self.config.get(CONF_PLUG_ENTITY)
        ):
            self._apply_running_state(new_state, now)
        elif entity_id == self.config.get(CONF_DOOR_ENTITY):
            self._apply_door_state(new_state, now)
        elif entity_id == self.config.get(CONF_PLUG_ENTITY):
            self._notify()
        elif entity_id == self.config.get(CONF_ENERGY_ENTITY):
            self._notify()
        elif entity_id in self._configured_inputs.values():
            self._notify()

        if entity_id == self.config.get(CONF_PLUG_ENTITY):
            self._update_plug_off_alarm_state(new_state, now)
        self._update_input_availability(entity_id, new_state)

    def _update_plug_off_alarm_state(self, state: Any, now: datetime) -> None:
        if "plug_off_alarm" not in self.profile.parameter_groups:
            self._plug_is_off = None
            self._update_alarm_condition("plug_off", False, now)
            return
        value = state.state if state is not None else None
        if value not in ("on", "off"):
            self._plug_is_off = None
            self._schedule_save()
            self._schedule_deadline()
            return

        self._plug_is_off = value == "off"
        self._update_alarm_condition("plug_off", self._plug_is_off, now)
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    def _input_issue_id(self, entity_id: str) -> str:
        return f"{self.entry.entry_id}_{entity_id}"

    def _update_input_availability(self, entity_id: str, state: Any) -> None:
        if entity_id not in self._configured_inputs.values():
            return
        unavailable = state is None or state.state in ("unknown", "unavailable")
        issue_id = self._input_issue_id(entity_id)
        if unavailable:
            if entity_id in self._unavailable_inputs:
                return
            self._unavailable_inputs.add(entity_id)
            _LOGGER.warning(
                "Configured %s input is unavailable",
                self._input_config_key(entity_id),
            )
            async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="input_unavailable",
                translation_placeholders={"entity_id": entity_id},
            )
            return

        self._unavailable_inputs.discard(entity_id)
        async_delete_issue(self.hass, DOMAIN, issue_id)

    def _input_config_key(self, entity_id: str) -> str:
        return next(
            key
            for key, configured_entity in self._configured_inputs.items()
            if configured_entity == entity_id
        )

    def _apply_running_state(
        self, state: Any, now: datetime, initialize: bool = False
    ) -> None:
        value = state.state if state is not None else None
        self._apply_running_value(value, now, initialize)

    def _apply_climate_state(
        self, state: Any, now: datetime, initialize: bool = False
    ) -> None:
        value = None
        if state is not None and state.state not in ("unknown", "unavailable"):
            value = "off" if state.state == "off" else "on"

        self._apply_running_value(value, now, initialize)

    def _apply_running_value(
        self, value: str | None, now: datetime, initialize: bool = False
    ) -> None:
        if initialize or self._restoring_detector_state:
            events = self.detector.reconcile_state(value, now)
            self._restoring_detector_state = False
        else:
            events = self.detector.observe_state(value, now)
        self._handle_cycle_events(events)
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    def _initialize_mail_sensor(self, state: Any) -> None:
        value = state.state if state is not None else None
        self._mail_sensor_ready = value == "off"
        if "mail_slot" in self.profile.detection_sources:
            self.mail_slot_open = (
                value == "on" if value in ("on", "off") else None
            )

    def _apply_mail_sensor_state(self, state: Any, now: datetime) -> None:
        value = state.state if state is not None else None
        if "mail_slot" in self.profile.detection_sources:
            self.mail_slot_open = (
                value == "on" if value in ("on", "off") else None
            )
        if value == "off":
            self._mail_sensor_ready = True
        elif value == "on":
            if self._mail_sensor_ready:
                self._mail_sensor_ready = False
                self._handle_mail_arrival(now)
        else:
            self._mail_sensor_ready = False
        self._notify()

    def _handle_mail_arrival(self, now: datetime) -> None:
        cycle_already_active = self.pending_unload
        self._pending_generation += 1
        self.pending_unload = True
        self.pending_reminder_count = 0
        self.next_pending_reminder = None
        self._pending_action_running = False
        if not cycle_already_active:
            self._run_actions_in_background(CONF_START_ACTIONS)
        if self.door_open is False and self.config.get(CONF_PENDING_ACTIONS):
            self.next_pending_reminder = now + timedelta(
                seconds=self._pending_delay_seconds
            )
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
        watts = ApplianceCycleDetector.to_watts(value, unit)

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
            self._last_valid_power_w = watts

        if "power" not in self.profile.detection_sources:
            self._schedule_save()
            self._schedule_deadline()
            self._notify()
            return

        if initialize_energy or self._restoring_detector_state:
            events = self.detector.reconcile_power(value, unit, now)
            self._restoring_detector_state = watts is None
        else:
            events = self.detector.observe_power(value, unit, now)
        self._handle_cycle_events(events)
        if (
            "compressor_alarm" in self.profile.parameter_groups
            and watts is not None
        ):
            self._update_alarm_condition(
                "compressor", not self.detector.is_running, now
            )
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    def _apply_door_state(self, state: Any, now: datetime) -> None:
        if state is None or state.state not in ("on", "off"):
            self.door_open = None
        else:
            self.door_open = state.state == "on"
            if "door_alarm" in self.profile.parameter_groups:
                self._update_alarm_condition("door", self.door_open, now)
            if self.door_open and "pending_unload" in self.profile.parameter_groups:
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
                if "pending_unload" in self.profile.parameter_groups and self.config.get(
                    CONF_DOOR_ENTITY
                ):
                    self._pending_generation += 1
                    self.pending_unload = self.door_open is not True
                    self.pending_reminder_count = 0
                    self.next_pending_reminder = None
                    self._pending_action_running = False
                if "cycle_start" in self.profile.action_groups:
                    self._run_actions_in_background(CONF_START_ACTIONS)
            else:
                if "cycle_finish" in self.profile.action_groups:
                    self._run_actions_in_background(CONF_FINISH_ACTIONS)
                if (
                    self.pending_unload
                    and self.door_open is False
                    and self.config.get(CONF_PENDING_ACTIONS)
                ):
                    self.next_pending_reminder = event.occurred_at + timedelta(
                        seconds=self._pending_delay_seconds
                    )
            if "compressor_alarm" in self.profile.parameter_groups:
                self._update_alarm_condition(
                    "compressor",
                    event.transition is CycleTransition.FINISHED,
                    event.occurred_at,
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
        if self._is_unloading:
            return
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
        if self.door_open is not None and self.next_door_alarm is not None:
            deadlines.append(self.next_door_alarm)
        if (
            "compressor_alarm" in self.profile.parameter_groups
            and self._power_available
            and self.next_compressor_alarm is not None
        ):
            deadlines.append(self.next_compressor_alarm)
        if (
            "plug_off_alarm" in self.profile.parameter_groups
            and self._plug_is_off is True
            and self.next_plug_off_alarm is not None
        ):
            deadlines.append(self.next_plug_off_alarm)
        if self._energy_power_w is not None or self.detector.is_running:
            deadlines.append(
                dt_util.utcnow() + _ENERGY_UPDATE_INTERVAL
            )
        if deadlines:
            self._unsubscribe_timer = async_track_point_in_time(
                self.hass, self._async_handle_deadline, min(deadlines)
            )

    async def _async_handle_deadline(self, _: datetime) -> None:
        if self._is_unloading:
            return
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
                pending_generation = self._pending_generation
                self.pending_reminder_count += 1
                self._pending_action_running = True
                self.next_pending_reminder = None
                self.entry.async_create_background_task(
                    self.hass,
                    self._run_pending_reminder(pending_generation),
                    name=f"{DOMAIN} {self.entry.entry_id} pending reminder",
                )
            elif self.door_open is None:
                self.next_pending_reminder = now + timedelta(
                    seconds=self._pending_interval_seconds
                )
            else:
                self.next_pending_reminder = None

        self._schedule_alarm_if_due("door", now)
        self._schedule_alarm_if_due("compressor", now)
        self._schedule_alarm_if_due("plug_off", now)

        self._integrate_energy_to(now)
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    async def _run_pending_reminder(self, generation: int) -> None:
        try:
            await self._run_actions_serialized(
                CONF_PENDING_ACTIONS,
                lambda: (
                    self.pending_unload
                    and self.door_open is False
                    and generation == self._pending_generation
                ),
            )
        finally:
            if generation == self._pending_generation and not self._is_unloading:
                self._pending_action_running = False
                if (
                    self.pending_unload
                    and self.door_open is False
                    and self.pending_reminder_count < self._pending_maximum
                ):
                    self.next_pending_reminder = dt_util.utcnow() + timedelta(
                        seconds=self._pending_interval_seconds
                    )
                else:
                    self.next_pending_reminder = None
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
        if self._is_unloading:
            return
        self.entry.async_create_background_task(
            self.hass,
            self._run_actions_serialized(key),
            name=f"{DOMAIN} {self.entry.entry_id} {key}",
        )

    async def _run_actions_serialized(
        self, key: str, should_run: Callable[[], bool] | None = None
    ) -> None:
        if should_run is not None and not should_run():
            return
        lock = self._action_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if should_run is not None and not should_run():
                return
            await self._run_actions(key)

    async def _run_actions(self, key: str) -> None:
        actions = self.config.get(key)
        if (
            actions is None
            and key == CONF_START_ACTIONS
            and ("mail_motion" in self.profile.detection_sources or "mail_slot" in self.profile.detection_sources)
        ):
            actions = self.config.get(CONF_MAIL_ARRIVAL_ACTIONS, [])
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

    def _update_alarm_condition(
        self, alarm: str, active: bool, now: datetime
    ) -> None:
        action_key = {
            "door": CONF_DOOR_OPEN_ACTIONS,
            "compressor": CONF_COMPRESSOR_INACTIVE_ACTIONS,
            "plug_off": CONF_PLUG_OFF_ACTIONS,
        }[alarm]
        active = active and bool(self.config.get(action_key))
        active_key = f"{alarm}_alarm_active"
        count_key = f"{alarm}_alarm_fired_count"
        deadline_key = f"next_{alarm}_alarm"
        currently_active = getattr(self, active_key)

        if active and not currently_active:
            self._alarm_generation[alarm] += 1
            if alarm == "door":
                delay = int(
                    self.config.get(
                        CONF_DOOR_OPEN_DELAY_SECONDS,
                        DEFAULT_DOOR_OPEN_DELAY_SECONDS,
                    )
                )
            elif alarm == "compressor":
                delay = int(
                    self.config.get(
                        CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
                        DEFAULT_COMPRESSOR_INACTIVE_DELAY_SECONDS,
                    )
                )
            else:
                delay = 0
            setattr(self, active_key, True)
            setattr(self, count_key, 0)
            setattr(self, deadline_key, now + timedelta(seconds=delay))
        elif not active and currently_active:
            self._alarm_generation[alarm] += 1
            setattr(self, active_key, False)
            setattr(self, count_key, 0)
            setattr(self, deadline_key, None)

    def _alarm_is_due(self, alarm: str, now: datetime) -> bool:
        if self._is_unloading:
            return False
        deadline = getattr(self, f"next_{alarm}_alarm")
        if (
            not getattr(self, f"{alarm}_alarm_active")
            or getattr(self, f"_{alarm}_alarm_action_running")
            or deadline is None
            or now < deadline
        ):
            return False
        return (
            alarm != "compressor"
            or "compressor_alarm" in self.profile.parameter_groups
        ) and (
            alarm != "plug_off" or "plug_off_alarm" in self.profile.parameter_groups
        ) and (alarm != "door" or self.door_open is not None) and (
            alarm != "compressor" or self._power_available
        ) and (alarm != "plug_off" or self._plug_is_off is True)

    def _schedule_alarm_if_due(self, alarm: str, now: datetime) -> None:
        if self._is_unloading:
            return
        if not self._alarm_is_due(alarm, now):
            return
        setattr(self, f"_{alarm}_alarm_action_running", True)
        generation = self._alarm_generation[alarm]
        self.entry.async_create_background_task(
            self.hass,
            self._execute_alarm(alarm, now, generation),
            name=f"{DOMAIN} {self.entry.entry_id} {alarm} alarm",
        )

    async def _run_alarm_if_due(self, alarm: str, now: datetime) -> None:
        if not self._alarm_is_due(alarm, now):
            return
        generation = self._alarm_generation[alarm]
        setattr(self, f"_{alarm}_alarm_action_running", True)
        await self._execute_alarm(alarm, now, generation)

    async def _execute_alarm(self, alarm: str, now: datetime, generation: int) -> None:
        active_key = f"{alarm}_alarm_active"
        count_key = f"{alarm}_alarm_fired_count"
        deadline_key = f"next_{alarm}_alarm"
        action_key = {
            "door": CONF_DOOR_OPEN_ACTIONS,
            "compressor": CONF_COMPRESSOR_INACTIVE_ACTIONS,
            "plug_off": CONF_PLUG_OFF_ACTIONS,
        }[alarm]
        try:
            await self._run_actions_serialized(
                action_key,
                lambda: (
                    getattr(self, active_key)
                    and generation == self._alarm_generation[alarm]
                ),
            )
        finally:
            setattr(self, f"_{alarm}_alarm_action_running", False)
        if (
            self._is_unloading
            or not getattr(self, active_key)
            or generation != self._alarm_generation[alarm]
        ):
            return

        fired_count = getattr(self, count_key) + 1
        setattr(self, count_key, fired_count)
        repeat_count_key = (
            CONF_PLUG_OFF_REPEAT_COUNT
            if alarm == "plug_off"
            else CONF_ALARM_REPEAT_COUNT
        )
        repeat_count_default = (
            DEFAULT_PLUG_OFF_REPEAT_COUNT
            if alarm == "plug_off"
            else DEFAULT_ALARM_REPEAT_COUNT
        )
        repeat_count = int(self.config.get(repeat_count_key, repeat_count_default))
        if fired_count < 1 + repeat_count:
            repeat_interval_key = (
                CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS
                if alarm == "plug_off"
                else CONF_ALARM_REPEAT_INTERVAL_SECONDS
            )
            repeat_interval_default = (
                DEFAULT_PLUG_OFF_REPEAT_INTERVAL_SECONDS
                if alarm == "plug_off"
                else DEFAULT_ALARM_REPEAT_INTERVAL_SECONDS
            )
            interval = int(
                self.config.get(
                    repeat_interval_key,
                    repeat_interval_default,
                )
            )
            setattr(
                self,
                deadline_key,
                dt_util.utcnow() + timedelta(seconds=interval),
            )
        else:
            setattr(self, deadline_key, None)
        self._schedule_save()
        self._schedule_deadline()
        self._notify()

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._export_state, _SAVE_DELAY_SECONDS)

    def _export_state(self) -> dict[str, Any]:
        return {
            "detector": self.detector.export_state(),
            "activity_entity": self.config.get(
                _ACTIVITY_SOURCE_KEYS[self.profile.detection_sources[0]]
            ),
            "power_entity": self.config.get(CONF_POWER_ENTITY),
            "last_valid_power_w": self._last_valid_power_w,
            "energy_kwh": self.energy_kwh,
            "door_open": self.door_open,
            "pending_unload": self.pending_unload,
            "pending_reminder_count": self.pending_reminder_count,
            "next_pending_reminder": (
                self.next_pending_reminder.isoformat()
                if self.next_pending_reminder is not None
                else None
            ),
            "door_alarm_active": self.door_alarm_active,
            "door_alarm_fired_count": self.door_alarm_fired_count,
            "next_door_alarm": (
                self.next_door_alarm.isoformat()
                if self.next_door_alarm is not None
                else None
            ),
            "compressor_alarm_active": self.compressor_alarm_active,
            "compressor_alarm_fired_count": self.compressor_alarm_fired_count,
            "next_compressor_alarm": (
                self.next_compressor_alarm.isoformat()
                if self.next_compressor_alarm is not None
                else None
            ),
            "plug_off_alarm_entity": self.config.get(CONF_PLUG_ENTITY),
            "plug_off_alarm_active": self.plug_off_alarm_active,
            "plug_off_alarm_fired_count": self.plug_off_alarm_fired_count,
            "next_plug_off_alarm": (
                self.next_plug_off_alarm.isoformat()
                if self.next_plug_off_alarm is not None
                else None
            ),
            "max_runtime_fired": self.max_runtime_fired,
        }

    def _restore(self, stored: dict[str, Any]) -> None:
        try:
            detector_state = stored.get("detector")
            if isinstance(detector_state, dict):
                current_source = self.config.get(
                    _ACTIVITY_SOURCE_KEYS[self.profile.detection_sources[0]]
                )
                if stored.get("activity_entity", current_source) != current_source:
                    detector_state = {
                        **detector_state,
                        "start_candidate_at": None,
                        "finish_candidate_at": None,
                    }
                self.detector.restore_state(detector_state)
            last_valid_power = stored.get(
                "last_valid_power_w", self.detector.power_w
            )
            if stored.get("power_entity", self.config.get(CONF_POWER_ENTITY)) != self.config.get(
                CONF_POWER_ENTITY
            ):
                last_valid_power = None
            if last_valid_power is not None:
                if isinstance(last_valid_power, bool):
                    raise ValueError("Invalid stored power reading")
                last_valid_power = float(last_valid_power)
                if not math.isfinite(last_valid_power) or last_valid_power < 0:
                    raise ValueError("Invalid stored power reading")
                self._last_valid_power_w = last_valid_power
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
            self.door_alarm_active = bool(stored.get("door_alarm_active", False))
            self.door_alarm_fired_count = max(
                0, int(stored.get("door_alarm_fired_count", 0))
            )
            self.next_door_alarm = self._parse_timestamp(
                stored.get("next_door_alarm")
            )
            self.compressor_alarm_active = bool(
                stored.get("compressor_alarm_active", False)
            )
            self.compressor_alarm_fired_count = max(
                0, int(stored.get("compressor_alarm_fired_count", 0))
            )
            self.next_compressor_alarm = self._parse_timestamp(
                stored.get("next_compressor_alarm")
            )
            if stored.get("plug_off_alarm_entity") == self.config.get(
                CONF_PLUG_ENTITY
            ):
                self.plug_off_alarm_active = bool(
                    stored.get("plug_off_alarm_active", False)
                )
                self.plug_off_alarm_fired_count = max(
                    0, int(stored.get("plug_off_alarm_fired_count", 0))
                )
                self.next_plug_off_alarm = self._parse_timestamp(
                    stored.get("next_plug_off_alarm")
                )
            self.max_runtime_fired = bool(stored.get("max_runtime_fired", False))
        except (TypeError, ValueError, OverflowError):
            _LOGGER.warning("Stored appliance state is invalid; starting fresh")
            self.detector = (
                BinaryActivityDetector()
                if "power" not in self.profile.detection_sources
                else ApplianceCycleDetector(self.detector.thresholds)
            )
            self._last_valid_power_w = None
            self.energy_kwh = 0.0
            self.door_open = None
            self.pending_unload = False
            self.pending_reminder_count = 0
            self.next_pending_reminder = None
            self.max_runtime_fired = False
            self.door_alarm_active = False
            self.door_alarm_fired_count = 0
            self.next_door_alarm = None
            self.compressor_alarm_active = False
            self.compressor_alarm_fired_count = 0
            self.next_compressor_alarm = None
            self.plug_off_alarm_active = False
            self.plug_off_alarm_fired_count = 0
            self.next_plug_off_alarm = None

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Invalid stored alarm timestamp")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Stored alarm timestamp has no timezone")
        return parsed

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()