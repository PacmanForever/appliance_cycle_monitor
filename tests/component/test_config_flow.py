"""Home Assistant-managed config-flow component tests."""

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations

from custom_components.appliance_cycle_monitor import async_migrate_entry
from custom_components.appliance_cycle_monitor.appliance_types import APPLIANCE_PROFILES
from custom_components.appliance_cycle_monitor.const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_TYPE,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_DOOR_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_FINISH_ACTIONS,
    CONF_MAIL_ARRIVAL_ACTIONS,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_POWER_ENTITY,
    CONF_PLUG_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_START_ACTIONS,
    CONF_MAX_RUNTIME_ACTIONS,
    CONF_MAX_RUNTIME_SECONDS,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_add_appliance_through_four_config_flow_steps(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_POWER_ENTITY not in {
        marker.schema for marker in result["data_schema"].schema
    }
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "name": "Washer",
            CONF_APPLIANCE_TYPE: "washer",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"
    power_selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if marker.schema == CONF_POWER_ENTITY
    )
    assert isinstance(power_selector, selector.EntitySelector)
    assert power_selector.config["filter"] == [
        {"domain": ["sensor"], "device_class": ["power"]}
    ]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_POWER_ENTITY: "sensor.washer_power"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "parameters"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "start_power_w": 1,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "parameters"
    assert result["errors"] == {"base": "invalid_thresholds"}

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "actions"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_START_ACTIONS: [],
            CONF_FINISH_ACTIONS: [],
            "max_runtime_actions": [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Washer"
    assert result["data"][CONF_POWER_ENTITY] == "sensor.washer_power"
    assert result["data"]["appliance_type"] == "washer"
    assert CONF_DOOR_ENTITY not in result["data"]
    assert "start_duration_seconds" not in result["data"]
    assert result["options"]["start_power_w"] == 4
    assert result["options"][CONF_START_ACTIONS] == []
    assert result["options"][CONF_FINISH_ACTIONS] == []


@pytest.mark.asyncio
async def test_add_air_conditioner_with_opening_sensor(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "name": "Air conditioner",
            CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        },
    )
    assert result["step_id"] == "sensors"
    schema_keys = {marker.schema for marker in result["data_schema"].schema}
    assert CONF_RUNNING_ENTITY in schema_keys
    assert CONF_POWER_ENTITY not in schema_keys
    assert CONF_DOOR_ENTITY not in schema_keys

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_RUNNING_ENTITY: "binary_sensor.ac_vane"},
    )
    assert result["step_id"] == "parameters"
    schema_keys = {marker.schema for marker in result["data_schema"].schema}
    assert "start_power_w" not in schema_keys
    assert CONF_PENDING_DELAY_SECONDS not in schema_keys

    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["step_id"] == "actions"
    assert CONF_PENDING_ACTIONS not in {
        marker.schema for marker in result["data_schema"].schema
    }

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RUNNING_ENTITY] == "binary_sensor.ac_vane"
    assert CONF_POWER_ENTITY not in result["data"]


@pytest.mark.asyncio
async def test_options_flow_updates_entry_and_clears_removed_door_configuration(
    hass, enable_custom_integrations
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Washer",
        data={
            "name": "Washer",
            "appliance_type": "washer",
            CONF_POWER_ENTITY: "sensor.washer_power",
            CONF_DOOR_ENTITY: "binary_sensor.washer_door",
        },
        options={
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
            CONF_PENDING_ACTIONS: [{"action": "notify.send_message"}],
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 5,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    flow_id = result["flow_id"]

    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Washer 2",
            CONF_APPLIANCE_TYPE: "washer",
        },
    )
    assert result["step_id"] == "sensors"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {CONF_POWER_ENTITY: "sensor.new_power", CONF_DOOR_ENTITY: None},
    )
    assert result["step_id"] == "parameters"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "start_power_w": 5,
            "start_duration_seconds": 30,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    assert result["step_id"] == "actions"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            CONF_START_ACTIONS: [],
            CONF_FINISH_ACTIONS: [],
            "max_runtime_actions": [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Washer 2"
    assert entry.data[CONF_POWER_ENTITY] == "sensor.new_power"
    assert entry.data[CONF_DOOR_ENTITY] is None
    assert CONF_PENDING_ACTIONS not in entry.options
    assert CONF_PENDING_DELAY_SECONDS not in entry.options
    assert CONF_PENDING_INTERVAL_SECONDS not in entry.options
    assert CONF_PENDING_REPEATS not in entry.options


@pytest.mark.asyncio
async def test_migrate_saved_duration_options_from_minutes_to_seconds(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        options={
            "start_duration_minutes": 0.25,
            "finish_duration_minutes": 1,
            "max_runtime_minutes": 90,
            "start_power_w": 4,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert entry.options == {
        "start_duration_seconds": 15,
        "finish_duration_seconds": 60,
        "max_runtime_seconds": 5400,
        "start_power_w": 4,
    }


@pytest.mark.asyncio
async def test_migrate_future_config_entry_version_is_rejected(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=3)
    entry.add_to_hass(hass)

    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 3


@pytest.mark.parametrize("appliance_type", tuple(APPLIANCE_PROFILES))
@pytest.mark.asyncio
async def test_every_profile_supports_config_entry_crud(
    hass, enable_custom_integrations, appliance_type
):
    profile = APPLIANCE_PROFILES[appliance_type]
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = flow_result["flow_id"]

    async def submit_identity(name: str):
        return await hass.config_entries.flow.async_configure(
            flow_id, {"name": name, CONF_APPLIANCE_TYPE: appliance_type}
        )

    def sensor_values(revision: str) -> dict[str, str]:
        values = {}
        if "running_sensor" in profile.detection_sources:
            values[CONF_RUNNING_ENTITY] = f"binary_sensor.{revision}_activity"
        elif "mail_motion" in profile.detection_sources:
            values[CONF_MAIL_MOTION_ENTITY] = f"binary_sensor.{revision}_motion"
        elif "mail_slot" in profile.detection_sources:
            values[CONF_MAIL_SLOT_ENTITY] = f"binary_sensor.{revision}_slot"
        elif "power" in profile.detection_sources:
            values[CONF_POWER_ENTITY] = f"sensor.{revision}_power"
        if profile.supports_door_sensor:
            values[CONF_DOOR_ENTITY] = f"binary_sensor.{revision}_door"
        if profile.supports_smart_plug:
            values[CONF_PLUG_ENTITY] = f"switch.{revision}_plug"
        return values

    def parameter_values() -> dict[str, int | float]:
        values: dict[str, int | float] = {}
        if "power_cycle" in profile.parameter_groups:
            values.update(
                {
                    "start_power_w": 4,
                    "start_duration_seconds": 15,
                    "finish_power_w": 1,
                    "finish_duration_seconds": 60,
                }
            )
        if "max_runtime" in profile.parameter_groups:
            values[CONF_MAX_RUNTIME_SECONDS] = 3600
        if "pending_unload" in profile.parameter_groups:
            values.update(
                {
                    CONF_PENDING_DELAY_SECONDS: 120,
                    CONF_PENDING_INTERVAL_SECONDS: 300,
                    CONF_PENDING_REPEATS: 2,
                }
            )
        if "door_alarm" in profile.parameter_groups:
            values[CONF_DOOR_OPEN_DELAY_SECONDS] = 120
        if "compressor_alarm" in profile.parameter_groups:
            values[CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS] = 3600
        if "alarm_repeats" in profile.parameter_groups:
            values[CONF_ALARM_REPEAT_INTERVAL_SECONDS] = 900
            values[CONF_ALARM_REPEAT_COUNT] = 3
        return values

    action_keys = {
        "cycle_start": CONF_START_ACTIONS,
        "cycle_finish": CONF_FINISH_ACTIONS,
        "max_runtime": CONF_MAX_RUNTIME_ACTIONS,
        "pending_unload": CONF_PENDING_ACTIONS,
        "door_open_alarm": CONF_DOOR_OPEN_ACTIONS,
        "compressor_inactive_alarm": CONF_COMPRESSOR_INACTIVE_ACTIONS,
        "mail_arrival": CONF_MAIL_ARRIVAL_ACTIONS,
    }
    action_values = {action_keys[group]: [] for group in profile.action_groups}

    result = await submit_identity(f"{appliance_type} appliance")
    assert result["step_id"] == "sensors"
    result = await hass.config_entries.flow.async_configure(
        flow_id, sensor_values(f"{appliance_type}_first")
    )
    assert result["step_id"] == "parameters"
    result = await hass.config_entries.flow.async_configure(
        flow_id, parameter_values()
    )
    assert result["step_id"] == "actions"
    result = await hass.config_entries.flow.async_configure(flow_id, action_values)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data[CONF_APPLIANCE_TYPE] == appliance_type
    assert entry.data == {
        "name": f"{appliance_type} appliance",
        CONF_APPLIANCE_TYPE: appliance_type,
        **sensor_values(f"{appliance_type}_first"),
    }
    assert entry in hass.config_entries.async_entries(DOMAIN)

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    options_flow_id = options_result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        {"name": f"{appliance_type} updated", CONF_APPLIANCE_TYPE: appliance_type},
    )
    assert result["step_id"] == "sensors"
    result = await hass.config_entries.options.async_configure(
        options_flow_id, sensor_values(f"{appliance_type}_second")
    )
    assert result["step_id"] == "parameters"
    result = await hass.config_entries.options.async_configure(
        options_flow_id, parameter_values()
    )
    assert result["step_id"] == "actions"
    result = await hass.config_entries.options.async_configure(
        options_flow_id, action_values
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == f"{appliance_type} updated"
    assert entry.data == {
        "name": f"{appliance_type} updated",
        CONF_APPLIANCE_TYPE: appliance_type,
        **sensor_values(f"{appliance_type}_second"),
    }

    await hass.config_entries.async_remove(entry.entry_id)
    assert entry not in hass.config_entries.async_entries(DOMAIN)