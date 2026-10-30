"""Home Assistant-managed config-flow component tests."""

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr, entity_registry as er, selector
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations

from custom_components.home_activity_manager import async_migrate_entry
from custom_components.home_activity_manager.appliance_types import (
    APPLIANCE_CATEGORIES,
    APPLIANCE_PROFILES,
)
from custom_components.home_activity_manager.config_flow import (
    _validate_climate_entity,
)
from custom_components.home_activity_manager.const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_TYPE,
    CONF_CLIMATE_ENTITY,
    CONF_ENERGY_ENTITY,
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
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
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
    assert result["step_id"] == "activity_mode_washer"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "power"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors_washer"
    power_selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if marker.schema == "washer_power_entity"
    )
    assert isinstance(power_selector, selector.EntitySelector)
    assert power_selector.config["filter"] == [
        {"domain": ["sensor"], "device_class": ["power"]}
    ]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"washer_power_entity": "sensor.washer_power"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "parameters_washer"

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
    assert result["step_id"] == "parameters_washer"
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
    assert result["step_id"] == "actions_washer"

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
async def test_activity_modes_follow_the_selected_category(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": "Air conditioner", CONF_APPLIANCE_TYPE: "air_conditioner"}
    )
    assert result["step_id"] == "activity_mode_air_conditioner"
    mode_selector = next(iter(result["data_schema"].schema.values()))
    assert set(mode_selector.config["options"]) == {
        "running_sensor", "climate", "power"
    }
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "running_sensor"}
    )
    assert result["step_id"] == "sensors_air_conditioner_contact"
    assert "air_conditioner_contact_running_entity" in result["data_schema"].schema


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
            CONF_APPLIANCE_TYPE: "air_conditioner",
        },
    )
    assert result["step_id"] == "activity_mode_air_conditioner"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "running_sensor"}
    )
    assert result["step_id"] == "sensors_air_conditioner_contact"
    schema_keys = {marker.schema for marker in result["data_schema"].schema}
    assert "air_conditioner_contact_running_entity" in schema_keys
    assert "air_conditioner_contact_power_entity" in schema_keys
    assert CONF_DOOR_ENTITY not in schema_keys

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"air_conditioner_contact_running_entity": "binary_sensor.ac_vane"},
    )
    assert result["step_id"] == "parameters_air_conditioner_contact"
    schema_keys = {marker.schema for marker in result["data_schema"].schema}
    assert "start_power_w" not in schema_keys
    assert CONF_PENDING_DELAY_SECONDS not in schema_keys

    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["step_id"] == "actions_air_conditioner_contact"
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
async def test_air_conditioner_climate_requires_unparented_entity(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    parentless_entity = entity_registry.async_get_or_create(
        "climate", climate_entry.domain, "parentless", config_entry=climate_entry
    )
    climate_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=climate_entry.entry_id,
        identifiers={(climate_entry.domain, "device")},
        name="Existing climate device",
    )
    parented_entity = entity_registry.async_get_or_create(
        "climate",
        climate_entry.domain,
        "parented",
        config_entry=climate_entry,
        device_id=climate_device.id,
    )
    assert not _validate_climate_entity(hass, parented_entity.entity_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(
        flow_id,
        {"name": "Climate AC", CONF_APPLIANCE_TYPE: "air_conditioner"},
    )
    sensor_step = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "climate"}
    )
    climate_selector = next(
        value
        for marker, value in sensor_step["data_schema"].schema.items()
        if marker.schema == "air_conditioner_climate_climate_entity"
    )
    sensor_form = await hass.config_entries.flow.async_configure(
        flow_id, {"air_conditioner_climate_climate_entity": parentless_entity.entity_id}
    )
    assert sensor_form["step_id"] == "parameters_air_conditioner_climate"
    assert isinstance(climate_selector, selector.EntitySelector)
    assert climate_selector.config["domain"] == ["climate"]
    assert parented_entity.entity_id in climate_selector.config["exclude_entities"]
    assert parentless_entity.entity_id not in climate_selector.config["exclude_entities"]
    actions_form = await hass.config_entries.flow.async_configure(flow_id, {})
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []}
    )
    assert actions_form["step_id"] == "actions_air_conditioner_climate"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CLIMATE_ENTITY] == parentless_entity.entity_id

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(
        flow_id,
        {"name": "Climate AC 2", CONF_APPLIANCE_TYPE: "air_conditioner"},
    )
    await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "climate"}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(flow_id, {})


@pytest.mark.asyncio
async def test_climate_entity_must_be_replaced_in_options(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate", climate_entry.domain, "air_conditioner", config_entry=climate_entry
    )
    replacement = er.async_get(hass).async_get_or_create(
        "climate", climate_entry.domain, "replacement", config_entry=climate_entry
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Climate AC",
        data={
            "name": "Climate AC",
            CONF_APPLIANCE_TYPE: "air_conditioner_climate",
            CONF_CLIMATE_ENTITY: climate_entity.entity_id,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"name": "Climate AC"}
    )
    assert result["step_id"] == "sensors_air_conditioner_climate"
    climate_selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if marker.schema == "air_conditioner_climate_climate_entity"
    )
    assert isinstance(climate_selector, selector.EntitySelector)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            flow_id, {"air_conditioner_climate_climate_entity": None}
        )
    result = await hass.config_entries.options.async_configure(
        flow_id, {"air_conditioner_climate_climate_entity": replacement.entity_id}
    )
    assert result["step_id"] == "parameters_air_conditioner_climate"
    result = await hass.config_entries.options.async_configure(flow_id, {})
    assert result["step_id"] == "actions_air_conditioner_climate"
    result = await hass.config_entries.options.async_configure(
        flow_id, {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data.get(CONF_CLIMATE_ENTITY) == replacement.entity_id


@pytest.mark.asyncio
async def test_mailbox_slot_requires_a_separate_main_door_sensor(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(
        flow_id,
        {"name": "Mailbox", CONF_APPLIANCE_TYPE: "mailbox"},
    )
    await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "mail_slot"}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "mailbox_slot_arrival_entity": "binary_sensor.mailbox_contact",
            "mailbox_slot_door_entity": "binary_sensor.mailbox_contact",
        },
    )
    assert result["step_id"] == "sensors_mailbox_slot"
    assert result["errors"] == {"base": "mailbox_sensors_must_be_distinct"}

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "mailbox_slot_arrival_entity": "binary_sensor.mail_slot",
            "mailbox_slot_door_entity": "binary_sensor.mailbox_door",
        },
    )
    assert result["step_id"] == "parameters_mailbox_slot"


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
    assert CONF_APPLIANCE_TYPE in result["data_schema"].schema
    assert "activity_mode" in result["data_schema"].schema
    flow_id = result["flow_id"]

    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Washer 2",
        },
    )
    assert result["step_id"] == "sensors_washer"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "washer_power_entity": "sensor.new_power",
            "washer_door_entity": None,
        },
    )
    assert result["step_id"] == "parameters_washer"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "start_power_w": 5,
            "start_duration_seconds": 30,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    assert result["step_id"] == "actions_washer"
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
    assert entry.data[CONF_APPLIANCE_TYPE] == "washer"
    assert entry.data[CONF_POWER_ENTITY] == "sensor.new_power"
    assert entry.data[CONF_DOOR_ENTITY] is None
    assert CONF_PENDING_ACTIONS not in entry.options
    assert CONF_PENDING_DELAY_SECONDS not in entry.options
    assert CONF_PENDING_INTERVAL_SECONDS not in entry.options
    assert CONF_PENDING_REPEATS not in entry.options


@pytest.mark.asyncio
async def test_options_flow_shows_immutable_category_and_mode(
    hass, enable_custom_integrations
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Washer",
        data={
            "name": "Washer",
            CONF_APPLIANCE_TYPE: "washer",
            CONF_POWER_ENTITY: "sensor.washer_power",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {marker.schema: field for marker, field in result["data_schema"].schema.items()}
    assert fields[CONF_APPLIANCE_TYPE].config["options"] == ["washer"]
    assert fields["activity_mode"].config["options"] == ["power"]
    assert fields[CONF_APPLIANCE_TYPE].config["read_only"] is True
    assert fields["activity_mode"].config["read_only"] is True
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {"name": "Washer", CONF_APPLIANCE_TYPE: "dryer", "activity_mode": "power"},
    )
    assert result["errors"] == {"base": "appliance_type_immutable"}
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {"name": "Washer", CONF_APPLIANCE_TYPE: "washer", "activity_mode": "climate"},
    )
    assert result["errors"] == {"base": "appliance_type_immutable"}
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {"name": "Washer"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors_washer"


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

    assert entry.version == 5
    assert entry.options == {
        "start_duration_seconds": 15,
        "finish_duration_seconds": 60,
        "max_runtime_seconds": 5400,
        "start_power_w": 4,
    }


@pytest.mark.asyncio
async def test_migrate_future_config_entry_version_is_rejected(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=6)
    entry.add_to_hass(hass)

    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 6


@pytest.mark.parametrize(
    ("version", "appliance_type", "source_key", "source_entity"),
    (
        (2, "air_conditioner_power", CONF_POWER_ENTITY, "sensor.ac_power"),
        (3, "air_conditioner_climate", CONF_CLIMATE_ENTITY, "climate.ac"),
    ),
)
@pytest.mark.asyncio
async def test_migrate_removes_unsupported_ac_contact_sensor(
    hass, version, appliance_type, source_key, source_entity
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=version,
        data={
            CONF_APPLIANCE_TYPE: appliance_type,
            source_key: source_entity,
            CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 5
    assert entry.data == {
        CONF_APPLIANCE_TYPE: appliance_type,
        source_key: source_entity,
    }


@pytest.mark.parametrize("appliance_type", ("refrigerator", "refrigerator_switch"))
@pytest.mark.asyncio
async def test_migrate_removes_refrigerator_compressor_and_plug_alarms(
    hass, appliance_type
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data={CONF_APPLIANCE_TYPE: appliance_type},
        options={
            CONF_START_ACTIONS: [{"action": "test.start"}],
            CONF_FINISH_ACTIONS: [{"action": "test.finish"}],
            CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door"}],
            CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor"}],
            CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 3600,
            CONF_PLUG_OFF_ACTIONS: [{"action": "test.plug_off"}],
            CONF_PLUG_OFF_REPEAT_COUNT: 3,
            CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 900,
            CONF_ALARM_REPEAT_COUNT: 2,
            CONF_ALARM_REPEAT_INTERVAL_SECONDS: 600,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 5
    assert entry.options == {
        CONF_START_ACTIONS: [{"action": "test.start"}],
        CONF_FINISH_ACTIONS: [{"action": "test.finish"}],
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door"}],
        CONF_ALARM_REPEAT_COUNT: 2,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 600,
    }


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
        category, mode = next(
            (category, mode)
            for category, modes in APPLIANCE_CATEGORIES.items()
            for mode, profile_name in modes.items()
            if profile_name == appliance_type
        )
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"name": name, CONF_APPLIANCE_TYPE: category}
        )
        assert result["step_id"] == f"activity_mode_{category}"
        return await hass.config_entries.flow.async_configure(
            flow_id, {"activity_mode": mode}
        )

    def sensor_values(revision: str) -> tuple[dict[str, str], dict[str, str]]:
        form_values: dict[str, str] = {}
        stored_values: dict[str, str] = {}
        for sensor_input in profile.sensor_inputs:
            if sensor_input.config_key == CONF_POWER_ENTITY:
                entity_id = f"sensor.{revision}_power"
            elif sensor_input.config_key == CONF_ENERGY_ENTITY:
                entity_id = f"sensor.{revision}_energy"
            elif sensor_input.config_key == CONF_PLUG_ENTITY:
                entity_id = f"switch.{revision}_plug"
            elif sensor_input.config_key == CONF_RUNNING_ENTITY:
                entity_id = f"binary_sensor.{revision}_activity"
            elif sensor_input.config_key == CONF_CLIMATE_ENTITY:
                climate_source = MockConfigEntry(domain="climate_source")
                climate_source.add_to_hass(hass)
                entity_entry = er.async_get(hass).async_get_or_create(
                    "climate",
                    climate_source.domain,
                    revision,
                    config_entry=climate_source,
                )
                entity_id = entity_entry.entity_id
            elif sensor_input.config_key in {
                CONF_MAIL_MOTION_ENTITY,
                CONF_MAIL_SLOT_ENTITY,
            }:
                entity_id = f"binary_sensor.{revision}_arrival"
            else:
                entity_id = f"binary_sensor.{revision}_door"
            if sensor_input.required or sensor_input.config_key not in stored_values:
                form_values[sensor_input.form_key] = entity_id
            stored_values[sensor_input.config_key] = entity_id
        return form_values, stored_values

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
        if "plug_off_alarm" in profile.parameter_groups:
            values[CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS] = 900
            values[CONF_PLUG_OFF_REPEAT_COUNT] = 3
        return values

    action_keys = {
        "cycle_start": CONF_START_ACTIONS,
        "cycle_finish": CONF_FINISH_ACTIONS,
        "max_runtime": CONF_MAX_RUNTIME_ACTIONS,
        "pending_unload": CONF_PENDING_ACTIONS,
        "door_open_alarm": CONF_DOOR_OPEN_ACTIONS,
        "compressor_inactive_alarm": CONF_COMPRESSOR_INACTIVE_ACTIONS,
        "mail_arrival": CONF_MAIL_ARRIVAL_ACTIONS,
        "plug_off_alarm": CONF_PLUG_OFF_ACTIONS,
    }
    action_values = {action_keys[group]: [] for group in profile.action_groups}

    result = await submit_identity(f"{appliance_type} appliance")
    assert result["step_id"] == f"sensors_{appliance_type}"
    first_sensor_form, first_sensor_storage = sensor_values(
        f"{appliance_type}_first"
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, first_sensor_form
    )
    assert result["step_id"] == f"parameters_{appliance_type}"
    result = await hass.config_entries.flow.async_configure(
        flow_id, parameter_values()
    )
    assert result["step_id"] == f"actions_{appliance_type}"
    result = await hass.config_entries.flow.async_configure(flow_id, action_values)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data[CONF_APPLIANCE_TYPE] == appliance_type
    assert entry.data == {
        "name": f"{appliance_type} appliance",
        CONF_APPLIANCE_TYPE: appliance_type,
        **first_sensor_storage,
    }
    assert entry in hass.config_entries.async_entries(DOMAIN)

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    assert CONF_APPLIANCE_TYPE in options_result["data_schema"].schema
    assert "activity_mode" in options_result["data_schema"].schema
    options_flow_id = options_result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        {"name": f"{appliance_type} updated"},
    )
    assert result["step_id"] == f"sensors_{appliance_type}"
    second_sensor_form, second_sensor_storage = sensor_values(
        f"{appliance_type}_second"
    )
    result = await hass.config_entries.options.async_configure(
        options_flow_id, second_sensor_form
    )
    assert result["step_id"] == f"parameters_{appliance_type}"
    result = await hass.config_entries.options.async_configure(
        options_flow_id, parameter_values()
    )
    assert result["step_id"] == f"actions_{appliance_type}"
    result = await hass.config_entries.options.async_configure(
        options_flow_id, action_values
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == f"{appliance_type} updated"
    assert entry.data == {
        "name": f"{appliance_type} updated",
        CONF_APPLIANCE_TYPE: appliance_type,
        **second_sensor_storage,
    }

    await hass.config_entries.async_remove(entry.entry_id)
    assert entry not in hass.config_entries.async_entries(DOMAIN)