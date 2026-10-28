"""Component tests for the Home Assistant runtime."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.issue_registry import async_get as async_get_issue_registry
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations

from custom_components.appliance_cycle_monitor.const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_TYPE,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_CLIMATE_ENTITY,
    CONF_DOOR_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_MAIL_ARRIVAL_ACTIONS,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_MAX_RUNTIME_ACTIONS,
    CONF_MAX_RUNTIME_SECONDS,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_PLUG_ENTITY,
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    CONF_POWER_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_START_ACTIONS,
    DOMAIN,
)
from custom_components.appliance_cycle_monitor import (
    _async_reload_entry,
    async_remove_entry,
    async_unload_entry,
)
from custom_components.appliance_cycle_monitor import runtime as runtime_module
from custom_components.appliance_cycle_monitor.appliance import ApplianceCycleDetector
from custom_components.appliance_cycle_monitor.runtime import ApplianceRuntime
from custom_components.appliance_cycle_monitor.binary_sensor import ApplianceBinarySensor
from custom_components.appliance_cycle_monitor.sensor import ApplianceSensor
from custom_components.appliance_cycle_monitor.button import (
    ClearPendingButton,
    async_setup_entry as setup_button_entry,
)
from custom_components.appliance_cycle_monitor.switch import (
    AppliancePlugSwitch,
    async_setup_entry as setup_switch_entry,
)


@pytest.fixture
def config() -> dict[str, str]:
    return {
        CONF_POWER_ENTITY: "sensor.washer_power",
        CONF_DOOR_ENTITY: "binary_sensor.washer_door",
        CONF_PLUG_ENTITY: "switch.washer_plug",
        "name": "Washer",
        "appliance_type": "washer",
    }


async def _async_fire_deadline(runtime: ApplianceRuntime, when: datetime) -> None:
    if runtime._unsubscribe_timer is not None:
        runtime._unsubscribe_timer()
        runtime._unsubscribe_timer = None
    await runtime._async_handle_deadline(when)


@pytest.mark.asyncio
async def test_power_updates_and_switch_off_are_event_driven(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()

    assert not runtime.detector.is_running
    assert runtime.detector.last_cycle_duration == timedelta(seconds=1)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_door_open_clears_pending_reminders(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    runtime.pending_unload = True
    runtime.pending_reminder_count = 2
    runtime.next_pending_reminder = current_time[0] + timedelta(minutes=1)

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()

    assert runtime.door_open is True
    assert runtime.pending_unload is False
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_runtime_state_restores_after_unload(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    runtime.energy_kwh = 0.125
    runtime.pending_unload = True
    runtime.pending_reminder_count = 1
    runtime.next_pending_reminder = current_time[0] + timedelta(minutes=15)
    await runtime.async_unload()

    restored = ApplianceRuntime(hass, entry, config)
    await restored.async_setup()

    assert restored.detector.is_running
    assert restored.energy_kwh == 0.125
    assert restored.pending_unload is True
    assert restored.pending_reminder_count == 1
    assert restored.next_pending_reminder == current_time[0] + timedelta(minutes=15)
    await restored.async_unload()


@pytest.mark.asyncio
async def test_energy_integrates_power_over_elapsed_time(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "100", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    current_time[0] += timedelta(hours=1)
    await _async_fire_deadline(runtime, current_time[0])

    assert runtime.energy_kwh == pytest.approx(0.1)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_max_runtime_actions_fire_once(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config[CONF_MAX_RUNTIME_SECONDS] = 60
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    triggered: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", triggered.append)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running
    triggered.clear()

    current_time[0] += timedelta(seconds=59)
    await _async_fire_deadline(runtime, current_time[0])
    assert CONF_MAX_RUNTIME_ACTIONS not in triggered

    current_time[0] += timedelta(seconds=1)
    await _async_fire_deadline(runtime, current_time[0])
    await _async_fire_deadline(runtime, current_time[0] + timedelta(seconds=1))

    assert triggered == [CONF_MAX_RUNTIME_ACTIONS]
    assert runtime.detector.is_running
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_pending_reminders_use_initial_delay_then_repeat_interval(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config.update(
        {
            CONF_PENDING_ACTIONS: [{"service": "test.noop"}],
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 1,
        }
    )
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    reminders: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", lambda _key: None)

    async def record_actions(key: str) -> None:
        reminders.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_actions)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    current_time[0] += timedelta(seconds=5)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0.5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(minutes=1)
    await _async_fire_deadline(runtime, current_time[0])
    first_reminder_at = current_time[0] + timedelta(seconds=120)

    current_time[0] = first_reminder_at - timedelta(seconds=1)
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == []
    current_time[0] = first_reminder_at
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == [CONF_PENDING_ACTIONS]

    current_time[0] += timedelta(seconds=299)
    await _async_fire_deadline(runtime, current_time[0])
    assert len(reminders) == 1
    current_time[0] += timedelta(seconds=1)
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == [CONF_PENDING_ACTIONS, CONF_PENDING_ACTIONS]
    assert runtime.next_pending_reminder is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_overdue_restored_reminder_runs_once_then_resumes_interval(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config.update(
        {
            CONF_PENDING_ACTIONS: [{"service": "test.noop"}],
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 2,
        }
    )
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save(
        {
            "pending_unload": True,
            "pending_reminder_count": 0,
            "next_pending_reminder": (
                current_time[0] - timedelta(minutes=10)
            ).isoformat(),
        }
    )
    runtime = ApplianceRuntime(hass, entry, config)
    reminders = []

    async def record_actions(key: str) -> None:
        reminders.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_actions)
    await runtime.async_setup()

    await _async_fire_deadline(runtime, current_time[0])
    await _async_fire_deadline(runtime, current_time[0])

    assert reminders == [CONF_PENDING_ACTIONS]
    assert runtime.pending_reminder_count == 1
    assert runtime.next_pending_reminder == current_time[0] + timedelta(seconds=300)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_unavailable_power_does_not_finish_a_cycle(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    current_time[0] += timedelta(seconds=5)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0.5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=10)
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()
    current_time[0] += timedelta(minutes=2)
    await _async_fire_deadline(runtime, current_time[0])

    assert runtime.detector.is_running
    assert runtime.detector.last_cycle_duration is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_remaining_estimate_decreases_during_power_outage(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.detector.cycle_started_at = current_time[0] - timedelta(minutes=2)
    runtime.detector.last_cycle_duration = timedelta(minutes=5)

    assert runtime.remaining_seconds == 180

    await runtime.async_unload()


@pytest.mark.asyncio
async def test_action_failure_does_not_stop_later_actions(
    hass, config, monkeypatch
):
    config[CONF_START_ACTIONS] = [
        {"action": "test.fail"},
        {"action": "test.succeed"},
    ]
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    executed: list[str] = []

    class FakeScript:
        def __init__(self, hass, sequence, name, domain, **kwargs):
            self.action = sequence[0]["action"]

        async def async_run(self):
            executed.append(self.action)
            if self.action == "test.fail":
                raise RuntimeError("simulated failure")

    monkeypatch.setattr(runtime_module, "Script", FakeScript)

    await runtime._run_actions(CONF_START_ACTIONS)

    assert executed == ["test.fail", "test.succeed"]


@pytest.mark.asyncio
async def test_removing_entry_deletes_its_persistent_state(hass, config):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save({"sentinel": True})

    await async_remove_entry(hass, entry)

    assert await store.async_load() is None


@pytest.mark.asyncio
async def test_config_entry_reload_and_unload_failure(hass, config, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    calls = []

    async def record_reload(_config_entries, entry_id):
        calls.append(("reload", entry_id))

    async def refuse_unload(_config_entries, _entry, _platforms):
        calls.append(("unload",))
        return False

    config_entries_type = type(hass.config_entries)
    monkeypatch.setattr(config_entries_type, "async_reload", record_reload)
    monkeypatch.setattr(
        config_entries_type, "async_unload_platforms", refuse_unload
    )

    await _async_reload_entry(hass, entry)
    assert not await async_unload_entry(hass, entry)
    assert calls == [("reload", entry.entry_id), ("unload",)]


@pytest.mark.asyncio
async def test_removing_door_sensor_clears_restored_pending_state(hass, config):
    config.pop(CONF_DOOR_ENTITY)
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save(
        {
            "pending_unload": True,
            "pending_reminder_count": 2,
            "next_pending_reminder": (
                datetime.now(timezone.utc) + timedelta(minutes=1)
            ).isoformat(),
        }
    )

    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    assert not runtime.pending_unload
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_power_entity_is_available_before_first_valid_reading(hass, config):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    power = ApplianceSensor(
        runtime,
        entry,
        "power",
        lambda: runtime.display_power_w,
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    )

    assert power.available
    assert power.native_value is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_power_entity_keeps_last_reading_when_input_is_unavailable(
    hass, config
):
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    power = ApplianceSensor(
        runtime,
        entry,
        "power",
        lambda: runtime.display_power_w,
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    )

    assert power.available
    assert power.native_value == 0

    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()

    assert not runtime.power_available
    assert runtime.detector.power_w is None
    assert power.available
    assert power.native_value == 0

    restored_runtime = ApplianceRuntime(hass, entry, config)
    restored_runtime._restore(runtime._export_state())
    assert restored_runtime.display_power_w == 0

    hass.states.async_set(
        config[CONF_POWER_ENTITY], "11", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    assert runtime.power_available
    assert power.native_value == 11
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_power_entity_restores_last_reading_after_reload_during_outage(
    hass, config, enable_custom_integrations
):
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "42", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    power_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_power"
    )
    assert hass.states.get(power_entity_id).state == "42.0"

    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(power_entity_id).state == "42.0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)

    power_state = hass.states.get(power_entity_id)
    assert power_state.state == "42.0"
    assert power_state.state not in ("unknown", "unavailable")
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_config_entry_loads_power_only_entities_and_unloads(
    hass, enable_custom_integrations
):
    config = {
        CONF_POWER_ENTITY: "sensor.washer_power",
        "name": "Washer",
        "appliance_type": "washer",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entry_entities = [
        entity
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    ]
    unique_ids = {entity.unique_id for entity in entry_entities}
    assert unique_ids == {
        f"{entry.entry_id}_power",
        f"{entry.entry_id}_total_energy",
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_estimated_remaining",
        f"{entry.entry_id}_running",
    }
    created_entity_ids = [entity.entity_id for entity in entry_entities]
    assert all(hass.states.get(entity_id) is not None for entity_id in created_entity_ids)
    for key, icon in {
        "power": "mdi:flash",
        "total_energy": "mdi:lightning-bolt",
        "last_cycle_duration": "mdi:timer-check-outline",
        "estimated_remaining": "mdi:timer-sand",
    }.items():
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert hass.states.get(entity_id).attributes["icon"] == icon
    running_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_running"
    )
    assert hass.states.get(running_entity_id).attributes["icon"] == "mdi:washing-machine-off"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    remaining = {
        entity_id: hass.states.get(entity_id)
        for entity_id in created_entity_ids
        if hass.states.get(entity_id) is not None
    }
    assert set(remaining) == set(created_entity_ids)
    assert all(state.state == "unavailable" for state in remaining.values())
    assert hass.states.get(config[CONF_POWER_ENTITY]) is not None


@pytest.mark.asyncio
async def test_optional_plug_and_pending_button_controls(
    hass, config, monkeypatch, enable_custom_integrations
):
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    runtime = entry.runtime_data

    plug_entities = []
    await setup_switch_entry(hass, entry, plug_entities.extend)
    assert len(plug_entities) == 1
    plug = plug_entities[0]
    plug.hass = hass
    assert plug.available
    assert not plug.is_on
    assert plug.icon == "mdi:power-plug-off"
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    await hass.async_block_till_done()
    assert plug.icon == "mdi:power-plug"
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    assert plug.icon == "mdi:power-plug-off"

    calls = []

    async def record_service_call(
        _service_registry, domain, service, service_data, blocking=False
    ):
        calls.append((domain, service, service_data, blocking))

    monkeypatch.setattr(
        type(hass.services), "async_call", record_service_call
    )
    await plug.async_turn_on()
    await plug.async_turn_off()
    assert calls == [
        ("switch", "turn_on", {"entity_id": config[CONF_PLUG_ENTITY]}, True),
        ("switch", "turn_off", {"entity_id": config[CONF_PLUG_ENTITY]}, True),
    ]

    hass.states.async_set(config[CONF_PLUG_ENTITY], "unavailable")
    assert not plug.available
    assert not plug.is_on
    assert plug.icon == "mdi:power-plug-off-outline"
    updates = []
    monkeypatch.setattr(plug, "async_write_ha_state", lambda: updates.append(True))
    plug._handle_runtime_update()
    assert updates == [True]

    button_entities = []
    await setup_button_entry(hass, entry, button_entities.extend)
    assert len(button_entities) == 1
    runtime.pending_unload = True
    runtime.pending_reminder_count = 2
    runtime.next_pending_reminder = dt_util.utcnow() + timedelta(minutes=1)
    pending_entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_pending_unload"
    )
    runtime._notify()
    assert hass.states.get(pending_entity_id).attributes["icon"] == "mdi:bell-alert"
    await button_entities[0].async_press()
    assert button_entities[0].icon == "mdi:notification-clear-all"
    assert hass.states.get(pending_entity_id).attributes["icon"] == "mdi:bell-outline"
    assert not runtime.pending_unload
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_restored_finish_deadline_waits_for_power_to_return(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    detector = ApplianceCycleDetector()
    detector.observe_power(5, "W", current_time[0])
    detector.advance_time(current_time[0] + timedelta(seconds=15))
    detector.observe_power(0.5, "W", current_time[0] + timedelta(seconds=20))
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save({"detector": detector.export_state()})
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")

    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    restored_deadline = runtime.detector.next_deadline
    assert restored_deadline == current_time[0] + timedelta(seconds=80)

    current_time[0] += timedelta(minutes=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running
    assert runtime.detector.next_deadline == restored_deadline

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    assert runtime.detector.is_running
    assert runtime.detector.last_cycle_duration is None
    assert runtime.detector.next_deadline is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_contact_profile_tracks_louver_sensor_without_power_entities(
    hass, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running
    current_time[0] += timedelta(seconds=12)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    await hass.async_block_till_done()
    assert not entry.runtime_data.detector.is_running
    assert entry.runtime_data.detector.last_cycle_duration == timedelta(seconds=12)

    registry = er.async_get(hass)
    unique_ids = {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert unique_ids == {
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_running",
    }
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_mailbox_slot_exposes_flap_open_and_closed_state(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "mailbox_slot",
        CONF_MAIL_SLOT_ENTITY: "binary_sensor.mail_flap",
        CONF_DOOR_ENTITY: "binary_sensor.mailbox_door",
        "name": "Mailbox",
    }
    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    mail_slot_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_mail_slot"
    )

    assert mail_slot_entity_id is not None
    assert hass.states.get(mail_slot_entity_id).state == "off"
    assert hass.states.get(mail_slot_entity_id).attributes["device_class"] == "door"
    assert hass.states.get(mail_slot_entity_id).attributes["icon"] == "mdi:mailbox-up"
    assert entry.runtime_data.door_open is False
    door_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_door"
    )
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:mailbox"

    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(mail_slot_entity_id).state == "on"
    assert hass.states.get(mail_slot_entity_id).attributes["icon"] == "mdi:mailbox-open-up"
    assert entry.runtime_data.door_open is False

    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "off")
    await hass.async_block_till_done()
    assert hass.states.get(mail_slot_entity_id).state == "off"
    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(mail_slot_entity_id).attributes["icon"] == "mdi:mailbox-outline"
    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "off")
    await hass.async_block_till_done()
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:mailbox-open"
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    await hass.async_block_till_done()
    assert entry.runtime_data.door_open is False
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("appliance_type", "closed_icon", "open_icon"),
    (
        ("washer", "mdi:washing-machine", "mdi:washing-machine-alert"),
        ("dishwasher", "mdi:dishwasher", "mdi:dishwasher-alert"),
        ("dryer", "mdi:tumble-dryer", "mdi:tumble-dryer-alert"),
    ),
)
def test_laundry_door_icons_follow_appliance_type(
    appliance_type, closed_icon, open_icon
):
    runtime = type("Runtime", (), {"config": {CONF_APPLIANCE_TYPE: appliance_type}})()
    entry = MockConfigEntry(domain=DOMAIN, data={})
    door_open = False
    sensor = ApplianceBinarySensor(
        runtime, entry, "door", lambda: door_open
    )

    assert sensor.icon == closed_icon
    door_open = True
    assert sensor.icon == open_icon


@pytest.mark.parametrize(
    ("appliance_type", "source_key"),
    (
        ("mailbox_motion", CONF_MAIL_MOTION_ENTITY),
        ("mailbox_slot", CONF_MAIL_SLOT_ENTITY),
    ),
)
@pytest.mark.asyncio
async def test_mailbox_arrival_actions_pending_reminders_and_door_clear(
    hass, monkeypatch, appliance_type, source_key
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        source_key: f"binary_sensor.{appliance_type}_trigger",
        CONF_DOOR_ENTITY: f"binary_sensor.{appliance_type}_door",
        CONF_MAIL_ARRIVAL_ACTIONS: [{"action": "test.mail_arrived"}],
        CONF_PENDING_ACTIONS: [{"action": "test.mail_reminder"}],
        CONF_PENDING_DELAY_SECONDS: 10,
        CONF_PENDING_INTERVAL_SECONDS: 20,
        CONF_PENDING_REPEATS: 1,
        "name": "Mailbox",
    }
    hass.states.async_set(config[source_key], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    arrivals: list[str] = []
    reminders: list[str] = []

    monkeypatch.setattr(runtime, "_run_actions_in_background", arrivals.append)

    async def record_reminder(key: str) -> None:
        reminders.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_reminder)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[source_key], "on")
    await hass.async_block_till_done()
    assert arrivals == [CONF_MAIL_ARRIVAL_ACTIONS]
    assert runtime.pending_unload
    assert runtime.next_pending_reminder == current_time[0] + timedelta(seconds=10)

    current_time[0] += timedelta(seconds=10)
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == [CONF_PENDING_ACTIONS]
    assert runtime.pending_reminder_count == 1

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert not runtime.pending_unload
    assert runtime.next_pending_reminder is None

    hass.states.async_set(config[source_key], "off")
    await hass.async_block_till_done()
    hass.states.async_set(config[source_key], "on")
    await hass.async_block_till_done()
    assert arrivals == [CONF_MAIL_ARRIVAL_ACTIONS, CONF_MAIL_ARRIVAL_ACTIONS]
    assert runtime.pending_unload
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    await hass.async_block_till_done()
    assert runtime.next_pending_reminder == current_time[0] + timedelta(seconds=10)
    await runtime.async_unload()


@pytest.mark.parametrize(
    ("appliance_type", "source_key"),
    (
        ("mailbox_motion", CONF_MAIL_MOTION_ENTITY),
        ("mailbox_slot", CONF_MAIL_SLOT_ENTITY),
    ),
)
@pytest.mark.asyncio
async def test_mailbox_starting_with_active_trigger_does_not_report_arrival(
    hass, monkeypatch, appliance_type, source_key
):
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        source_key: f"binary_sensor.{appliance_type}_trigger",
        CONF_DOOR_ENTITY: f"binary_sensor.{appliance_type}_door",
        CONF_MAIL_ARRIVAL_ACTIONS: [{"action": "test.mail_arrived"}],
        "name": "Mailbox",
    }
    hass.states.async_set(config[source_key], "on")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    arrivals: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", arrivals.append)
    await runtime.async_setup()

    assert arrivals == []
    assert not runtime.pending_unload
    assert runtime.next_pending_reminder is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_refrigerator_creates_only_its_declared_entities(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        "name": "Refrigerator",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save(
        {
            "pending_unload": True,
            "pending_reminder_count": 2,
            "next_pending_reminder": (
                dt_util.utcnow() + timedelta(minutes=1)
            ).isoformat(),
        }
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not entry.runtime_data.pending_unload

    registry = er.async_get(hass)
    unique_ids = {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert unique_ids == {
        f"{entry.entry_id}_power",
        f"{entry.entry_id}_total_energy",
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_running",
        f"{entry.entry_id}_door",
    }
    door_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_door"
    )
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:fridge"
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:fridge-alert"
    hass.states.async_set(config[CONF_DOOR_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:fridge-alert-outline"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_smart_switch_refrigerator_creates_only_its_declared_entities(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator_switch",
        CONF_PLUG_ENTITY: "switch.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        "name": "Smart-switch refrigerator",
    }
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    unique_ids = {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert unique_ids == {
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_running",
        f"{entry.entry_id}_door",
        f"{entry.entry_id}_plug",
    }
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_smart_switch_refrigerator_tracks_switch_and_door_only(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator_switch",
        CONF_PLUG_ENTITY: "switch.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_DOOR_OPEN_DELAY_SECONDS: 2,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 3,
        CONF_ALARM_REPEAT_COUNT: 0,
        "name": "Smart-switch refrigerator",
    }
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    alarms: list[str] = []

    async def record_alarm(key: str) -> None:
        alarms.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_alarm)
    await runtime.async_setup()
    assert not runtime.detector.is_running
    assert not runtime.power_available
    assert runtime.next_compressor_alarm is None

    current_time[0] += timedelta(seconds=5)
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    await hass.async_block_till_done()
    assert runtime.detector.is_running
    assert runtime.detector.cycle_started_at == current_time[0]

    current_time[0] += timedelta(seconds=8)
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    assert not runtime.detector.is_running
    assert runtime.detector.last_cycle_duration == timedelta(seconds=8)
    assert not runtime.compressor_alarm_active

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert alarms == [CONF_DOOR_OPEN_ACTIONS]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_refrigerator_alarms_repeat_rearm_and_persist_independently(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor_alarm"}],
        CONF_DOOR_OPEN_DELAY_SECONDS: 2,
        CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 4,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 3,
        CONF_ALARM_REPEAT_COUNT: 1,
        "name": "Refrigerator",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    assert runtime.next_compressor_alarm == current_time[0] + timedelta(seconds=4)

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert not runtime.pending_unload
    current_time[0] += timedelta(seconds=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]
    current_time[0] += timedelta(seconds=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS, CONF_COMPRESSOR_INACTIVE_ACTIONS]

    await runtime.async_unload()
    restored = ApplianceRuntime(hass, entry, config)
    monkeypatch.setattr(restored, "_run_actions", record_action)
    await restored.async_setup()
    assert restored.door_alarm_fired_count == 1
    assert restored.compressor_alarm_fired_count == 1
    assert restored.next_door_alarm == current_time[0] + timedelta(seconds=1)
    assert restored.next_compressor_alarm == current_time[0] + timedelta(seconds=3)

    current_time[0] += timedelta(seconds=1)
    await _async_fire_deadline(restored, current_time[0])
    assert actions[-1] == CONF_DOOR_OPEN_ACTIONS
    assert restored.next_door_alarm is None
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    await hass.async_block_till_done()
    assert not restored.door_alarm_active
    assert restored.door_alarm_fired_count == 0
    await restored.async_unload()


@pytest.mark.asyncio
async def test_plug_off_alarm_fires_immediately_when_setup_starts_off(
    hass, monkeypatch
):
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_PLUG_ENTITY: "switch.ac_plug",
        CONF_PLUG_OFF_ACTIONS: [{"action": "test.plug_off_alarm"}],
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    await hass.async_block_till_done()

    assert actions == [CONF_PLUG_OFF_ACTIONS]
    assert runtime.plug_off_alarm_fired_count == 1
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_plug_off_alarm_repeats_pauses_persists_and_rearms(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_PLUG_ENTITY: "switch.ac_plug",
        CONF_PLUG_OFF_ACTIONS: [{"action": "test.plug_off_alarm"}],
        CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 10,
        CONF_PLUG_OFF_REPEAT_COUNT: 1,
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    monkeypatch.setattr(runtime, "_schedule_deadline", lambda: None)

    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    assert runtime.plug_off_alarm_active
    assert runtime.next_plug_off_alarm == current_time[0]
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [CONF_PLUG_OFF_ACTIONS]
    assert runtime.plug_off_alarm_fired_count == 1
    assert runtime.next_plug_off_alarm == current_time[0] + timedelta(seconds=10)

    restored = ApplianceRuntime(hass, entry, config)
    restored._restore(runtime._export_state())
    assert restored.plug_off_alarm_active
    assert restored.plug_off_alarm_fired_count == 1
    assert restored.next_plug_off_alarm == runtime.next_plug_off_alarm

    hass.states.async_set(config[CONF_PLUG_ENTITY], "unavailable")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=20)
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [CONF_PLUG_OFF_ACTIONS]

    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [CONF_PLUG_OFF_ACTIONS, CONF_PLUG_OFF_ACTIONS]
    assert runtime.next_plug_off_alarm is None

    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    await hass.async_block_till_done()
    assert not runtime.plug_off_alarm_active
    assert runtime.plug_off_alarm_fired_count == 0
    assert runtime.next_plug_off_alarm is None

    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [
        CONF_PLUG_OFF_ACTIONS,
        CONF_PLUG_OFF_ACTIONS,
        CONF_PLUG_OFF_ACTIONS,
    ]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_climate_entity_is_assigned_reassociated_and_released(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate", climate_entry.domain, "air_conditioner", config_entry=climate_entry
    )
    replacement_entry = MockConfigEntry(domain="climate_source")
    replacement_entry.add_to_hass(hass)
    replacement_climate = er.async_get(hass).async_get_or_create(
        "climate", replacement_entry.domain, "replacement", config_entry=replacement_entry
    )
    hass.states.async_set(
        climate_entity.entity_id, "cool", {"hvac_action": "cooling"}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APPLIANCE_TYPE: "air_conditioner_climate",
            CONF_CLIMATE_ENTITY: climate_entity.entity_id,
            "name": "Air conditioner",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert device is not None
    registered_climate = er.async_get(hass).async_get(climate_entity.entity_id)
    assert registered_climate is not None
    assert registered_climate.config_entry_id == climate_entry.entry_id
    assert registered_climate.device_id == device.id
    assert entry.runtime_data.detector.is_running

    hass.states.async_set(
        climate_entity.entity_id, "cool", {"hvac_action": "idle"}
    )
    await hass.async_block_till_done()
    assert not entry.runtime_data.detector.is_running
    assert entry.runtime_data.detector.last_cycle_duration is not None

    hass.states.async_set(climate_entity.entity_id, "cool")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running
    hass.states.async_set(climate_entity.entity_id, "unavailable")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running

    er.async_get(hass).async_update_entity(climate_entity.entity_id, device_id=None)
    assert (
        er.async_get(hass).async_get(climate_entity.entity_id).device_id == device.id
    )

    updated_data = dict(entry.data)
    updated_data[CONF_CLIMATE_ENTITY] = replacement_climate.entity_id
    hass.config_entries.async_update_entry(entry, data=updated_data)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id is None
    assert (
        er.async_get(hass).async_get(replacement_climate.entity_id).device_id
        == device.id
    )

    updated_data = dict(entry.data)
    updated_data.pop(CONF_CLIMATE_ENTITY)
    hass.config_entries.async_update_entry(entry, data=updated_data)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get(replacement_climate.entity_id).device_id is None
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (
        er.async_get(hass).async_get(replacement_climate.entity_id).device_id is None
    )
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id is None
    assert er.async_get(hass).async_get(climate_entity.entity_id).config_entry_id == climate_entry.entry_id


@pytest.mark.asyncio
async def test_climate_entity_with_existing_parent_is_not_reassigned(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    existing_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=climate_entry.entry_id,
        identifiers={(climate_entry.domain, "existing_device")},
        name="Existing climate device",
    )
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate",
        climate_entry.domain,
        "air_conditioner",
        config_entry=climate_entry,
        device_id=existing_device.id,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APPLIANCE_TYPE: "air_conditioner_climate",
            CONF_CLIMATE_ENTITY: climate_entity.entity_id,
            "name": "Air conditioner",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id == (
        existing_device.id
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id == (
        existing_device.id
    )


@pytest.mark.asyncio
async def test_unavailable_alarm_inputs_pause_without_clearing_or_false_alarm(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor_alarm"}],
        CONF_DOOR_OPEN_DELAY_SECONDS: 2,
        CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 4,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 3,
        CONF_ALARM_REPEAT_COUNT: 0,
        "name": "Refrigerator",
    }
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    door_deadline = runtime.next_door_alarm
    assert door_deadline == current_time[0] + timedelta(seconds=2)
    assert not runtime.compressor_alarm_active

    hass.states.async_set(config[CONF_DOOR_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert runtime.door_alarm_active
    assert runtime.next_door_alarm == door_deadline
    current_time[0] += timedelta(seconds=3)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == []

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]

    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    compressor_deadline = runtime.next_compressor_alarm
    assert compressor_deadline == current_time[0] + timedelta(seconds=4)
    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=4)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]

    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS, CONF_COMPRESSOR_INACTIVE_ACTIONS]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_compressor_alarm_rearms_after_activity_cycle(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor_alarm"}],
        CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 60,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 10,
        CONF_ALARM_REPEAT_COUNT: 0,
        "name": "Refrigerator",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    assert runtime.compressor_alarm_active

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running
    assert not runtime.compressor_alarm_active
    assert runtime.next_compressor_alarm is None

    current_time[0] += timedelta(seconds=4)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0.5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=60)
    await _async_fire_deadline(runtime, current_time[0])
    assert not runtime.detector.is_running
    assert runtime.compressor_alarm_active
    assert runtime.next_compressor_alarm == current_time[0] + timedelta(seconds=60)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_alarm_actions_do_not_overlap_on_duplicate_deadline(
    hass, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 10,
        CONF_ALARM_REPEAT_COUNT: 1,
        "name": "Refrigerator",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = True
    runtime.door_alarm_active = True
    runtime.next_door_alarm = current_time
    started = asyncio.Event()
    release = asyncio.Event()
    action_calls = 0

    async def hold_action(_key: str) -> None:
        nonlocal action_calls
        action_calls += 1
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    first_action = asyncio.create_task(
        runtime._run_alarm_if_due("door", current_time)
    )
    await started.wait()
    await runtime._run_alarm_if_due("door", current_time)
    assert action_calls == 1

    release.set()
    completed_at = dt_util.utcnow()
    await first_action
    assert runtime.door_alarm_fired_count == 1
    assert runtime.next_door_alarm >= completed_at + timedelta(seconds=10)


@pytest.mark.asyncio
async def test_old_alarm_action_does_not_overwrite_rearmed_deadline(
    hass, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_DOOR_OPEN_DELAY_SECONDS: 60,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 10,
        CONF_ALARM_REPEAT_COUNT: 1,
        "name": "Refrigerator",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = True
    runtime.door_alarm_active = True
    runtime.next_door_alarm = current_time
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_action(
        _key: str, _should_run: object | None = None
    ) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    old_action = asyncio.create_task(
        runtime._run_alarm_if_due("door", current_time)
    )
    await started.wait()

    runtime._update_alarm_condition("door", False, current_time + timedelta(seconds=1))
    runtime._update_alarm_condition("door", True, current_time + timedelta(seconds=2))
    rearmed_deadline = current_time + timedelta(seconds=62)
    release.set()
    await old_action

    assert runtime.door_alarm_fired_count == 0
    assert runtime.next_door_alarm == rearmed_deadline


@pytest.mark.asyncio
async def test_same_action_group_runs_sequentially(hass, config, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()
    active_actions = 0
    maximum_active_actions = 0

    async def hold_action(_key: str) -> None:
        nonlocal active_actions, maximum_active_actions
        active_actions += 1
        maximum_active_actions = max(maximum_active_actions, active_actions)
        if not first_started.is_set():
            first_started.set()
            await release_first.wait()
        else:
            second_started.set()
        active_actions -= 1

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    first = asyncio.create_task(runtime._run_actions_serialized(CONF_START_ACTIONS))
    await first_started.wait()
    second = asyncio.create_task(runtime._run_actions_serialized(CONF_START_ACTIONS))
    await asyncio.sleep(0)
    assert not second_started.is_set()

    release_first.set()
    await asyncio.gather(first, second)

    assert second_started.is_set()
    assert maximum_active_actions == 1


@pytest.mark.asyncio
async def test_old_pending_action_does_not_schedule_for_new_cycle(
    hass, config, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config[CONF_PENDING_ACTIONS] = [{"action": "test.pending"}]
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = False
    runtime.pending_unload = True
    runtime.next_pending_reminder = current_time
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_action(
        _key: str, _should_run: object | None = None
    ) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    old_reminder = asyncio.create_task(runtime._async_handle_deadline(current_time))
    await started.wait()

    runtime._handle_cycle_events(
        [runtime_module.CycleEvent(runtime_module.CycleTransition.STARTED, current_time)]
    )
    release.set()
    await old_reminder

    assert runtime.pending_unload
    assert runtime.next_pending_reminder is None


@pytest.mark.asyncio
async def test_due_refrigerator_alarms_start_without_blocking_each_other(
    hass, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor_alarm"}],
        "name": "Refrigerator",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = True
    runtime.door_alarm_active = True
    runtime.compressor_alarm_active = True
    runtime._power_available = True
    runtime.next_door_alarm = current_time
    runtime.next_compressor_alarm = current_time
    started = {
        CONF_DOOR_OPEN_ACTIONS: asyncio.Event(),
        CONF_COMPRESSOR_INACTIVE_ACTIONS: asyncio.Event(),
    }
    release = asyncio.Event()

    async def hold_action(key: str) -> None:
        started[key].set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    await runtime._async_handle_deadline(current_time)
    await asyncio.wait_for(
        asyncio.gather(*(event.wait() for event in started.values())), timeout=1
    )

    release.set()
    await hass.async_block_till_done()

    assert runtime.door_alarm_fired_count == 1
    assert runtime.compressor_alarm_fired_count == 1


@pytest.mark.asyncio
async def test_unavailable_input_creates_and_resolves_repair_issue(
    hass, config
):
    hass.states.async_set(
        config[CONF_POWER_ENTITY],
        "unavailable",
        {ATTR_UNIT_OF_MEASUREMENT: "W"},
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    issue_registry = async_get_issue_registry(hass)
    issue_id = f"{entry.entry_id}_{config[CONF_POWER_ENTITY]}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    hass.states.async_set(
        config[CONF_POWER_ENTITY],
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: "W"},
    )
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_slow_pending_action_does_not_reschedule_after_unload(
    hass, config, monkeypatch
):
    config[CONF_PENDING_ACTIONS] = [{"action": "test.pending"}]
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = False
    runtime.pending_unload = True
    runtime.next_pending_reminder = datetime.now(timezone.utc)
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_action(_key: str) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    await runtime._async_handle_deadline(datetime.now(timezone.utc))
    await started.wait()

    await runtime.async_unload()
    release.set()
    await hass.async_block_till_done()

    assert runtime._unsubscribe_timer is None