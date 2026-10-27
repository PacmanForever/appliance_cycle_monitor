"""Home Assistant-managed config-flow component tests."""

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations

from custom_components.appliance_cycle_monitor import async_migrate_entry
from custom_components.appliance_cycle_monitor.const import (
    CONF_DOOR_ENTITY,
    CONF_FINISH_ACTIONS,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_POWER_ENTITY,
    CONF_START_ACTIONS,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_add_appliance_through_three_config_flow_steps(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    power_selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if marker.schema == CONF_POWER_ENTITY
    )
    assert isinstance(power_selector, selector.EntitySelector)
    assert power_selector.config["filter"] == [
        {"domain": ["sensor"], "device_class": ["power"]}
    ]
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "name": "Washer",
            "appliance_type": "washer",
            CONF_POWER_ENTITY: "sensor.washer_power",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "thresholds"

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
    assert result["step_id"] == "thresholds"
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
    assert result["data"][CONF_DOOR_ENTITY] is None
    assert "start_duration_seconds" not in result["data"]
    assert result["options"]["start_power_w"] == 4
    assert result["options"][CONF_START_ACTIONS] == []
    assert result["options"][CONF_FINISH_ACTIONS] == []


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
            "appliance_type": "washer",
            CONF_POWER_ENTITY: "sensor.new_power",
            CONF_DOOR_ENTITY: None,
        },
    )
    assert result["step_id"] == "thresholds"
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
    assert entry.options[CONF_PENDING_ACTIONS] == []
    assert entry.options[CONF_PENDING_DELAY_SECONDS] == 900
    assert entry.options[CONF_PENDING_INTERVAL_SECONDS] == 900
    assert entry.options[CONF_PENDING_REPEATS] == 3


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