"""Component tests for the Home Assistant runtime."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations

from custom_components.appliance_cycle_monitor.const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_TYPE,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
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
async def test_power_entity_availability_tracks_input_validity(hass, config):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    power = ApplianceSensor(
        runtime,
        entry,
        "power",
        lambda: runtime.detector.power_w,
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    )

    assert not power.available
    runtime._power_available = True
    assert power.available


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
    await button_entities[0].async_press()
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
    assert await hass.config_entries.async_unload(entry.entry_id)


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
    await first_action
    assert runtime.door_alarm_fired_count == 1
    assert runtime.next_door_alarm == current_time + timedelta(seconds=10)