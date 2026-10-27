"""Unit tests for configuration schemas and translation coverage."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import pytest
import voluptuous as vol

from custom_components.appliance_cycle_monitor.config_flow import (
    ApplianceCycleMonitorConfigFlow,
    ApplianceCycleMonitorOptionsFlow,
    _action_schema,
    _entity_schema,
    _threshold_schema,
    _clear_pending_settings,
    _validate_pending,
    _validate_thresholds,
)
from custom_components.appliance_cycle_monitor.const import (
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    DEFAULT_PENDING_DELAY_SECONDS,
    DEFAULT_PENDING_INTERVAL_SECONDS,
    DEFAULT_PENDING_REPEATS,
)


class ConfigFlowSchemaTests(unittest.TestCase):
    def test_appliance_type_and_power_sensor_are_required(self) -> None:
        schema = _entity_schema({})
        with self.assertRaises(vol.Invalid):
            schema({"name": "Washer", "power_entity": "sensor.washer_power"})

        values = schema(
            {
                "name": "Washer",
                "appliance_type": "washer",
                "power_entity": "sensor.washer_power",
            }
        )

        self.assertEqual(values["power_entity"], "sensor.washer_power")
        self.assertEqual(values["appliance_type"], "washer")
        self.assertNotIn("door_entity", values)
        self.assertNotIn("plug_entity", values)

    def test_sensor_selection_fields_prefill_during_edit(self) -> None:
        schema = _entity_schema(
            {
                "name": "Dishwasher",
                "appliance_type": "dishwasher",
                "power_entity": "sensor.dishwasher_power",
                "door_entity": "binary_sensor.dishwasher_door",
                "plug_entity": "switch.dishwasher_plug",
            }
        )

        values = schema({})
        self.assertEqual(values["name"], "Dishwasher")
        self.assertEqual(values["power_entity"], "sensor.dishwasher_power")
        self.assertEqual(values["door_entity"], "binary_sensor.dishwasher_door")
        self.assertEqual(values["plug_entity"], "switch.dishwasher_plug")

    def test_default_thresholds_and_coherence_validation(self) -> None:
        values = _threshold_schema({})(
            {
                "start_power_w": 4,
                "finish_power_w": 1,
            }
        )

        self.assertEqual(values["start_power_w"], 4)
        self.assertEqual(values["start_duration_seconds"], 15)
        self.assertEqual(values["finish_duration_seconds"], 60)
        self.assertTrue(_validate_thresholds(values))
        self.assertFalse(
            _validate_thresholds(
                {
                    **values,
                    "start_power_w": 1,
                    "finish_power_w": 1,
                }
            )
        )

    def test_pending_fields_are_only_shown_with_door_sensor(self) -> None:
        without_door = _action_schema({})
        with_door = _action_schema({"door_entity": "binary_sensor.door"})

        self.assertNotIn(CONF_PENDING_ACTIONS, without_door.schema)
        values = with_door(
            {
                "start_actions": [],
                "finish_actions": [],
                "max_runtime_actions": [],
                "pending_actions": [],
            }
        )
        self.assertEqual(values[CONF_PENDING_DELAY_SECONDS], DEFAULT_PENDING_DELAY_SECONDS)
        self.assertEqual(
            values[CONF_PENDING_INTERVAL_SECONDS], DEFAULT_PENDING_INTERVAL_SECONDS
        )
        self.assertEqual(values[CONF_PENDING_REPEATS], DEFAULT_PENDING_REPEATS)

    def test_pending_limits_require_positive_integer_seconds(self) -> None:
        self.assertTrue(
            _validate_pending(
                {
                    CONF_PENDING_DELAY_SECONDS: 900,
                    CONF_PENDING_INTERVAL_SECONDS: 900,
                    CONF_PENDING_REPEATS: 3,
                }
            )
        )
        self.assertFalse(
            _validate_pending(
                {
                    CONF_PENDING_DELAY_SECONDS: 0,
                    CONF_PENDING_INTERVAL_SECONDS: 900,
                    CONF_PENDING_REPEATS: 3,
                }
            )
        )
        self.assertFalse(
            _validate_pending(
                {
                    CONF_PENDING_DELAY_SECONDS: 900,
                    CONF_PENDING_INTERVAL_SECONDS: 1.5,
                    CONF_PENDING_REPEATS: 3,
                }
            )
        )

    def test_removing_door_clears_saved_pending_actions(self) -> None:
        values = {
            CONF_PENDING_ACTIONS: [{"action": "notify.send_message"}],
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 5,
        }

        _clear_pending_settings(values)

        self.assertEqual(values[CONF_PENDING_ACTIONS], [])
        self.assertEqual(values[CONF_PENDING_DELAY_SECONDS], 900)
        self.assertEqual(values[CONF_PENDING_INTERVAL_SECONDS], 900)
        self.assertEqual(values[CONF_PENDING_REPEATS], 3)


    def test_all_translation_files_have_matching_keys(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "appliance_cycle_monitor"
        translations = [
            json.loads((root / "strings.json").read_text(encoding="utf-8")),
            json.loads((root / "translations" / "en.json").read_text(encoding="utf-8")),
            json.loads((root / "translations" / "es.json").read_text(encoding="utf-8")),
            json.loads((root / "translations" / "ca.json").read_text(encoding="utf-8")),
        ]

        def key_shape(value):
            if isinstance(value, dict):
                return {key: key_shape(child) for key, child in value.items()}
            if isinstance(value, list):
                return [key_shape(child) for child in value]
            return None

        expected = key_shape(translations[0])
        self.assertEqual(key_shape(translations[1]), expected)
        self.assertEqual(key_shape(translations[2]), expected)


@pytest.mark.asyncio
async def test_config_flow_has_three_forward_steps_and_separates_options():
    flow = ApplianceCycleMonitorConfigFlow()
    shown_steps: list[dict[str, object]] = []
    flow.async_show_form = lambda **result: shown_steps.append(result) or result
    flow.async_create_entry = lambda **result: result

    first_result = await flow.async_step_user()
    assert first_result["step_id"] == "user"
    assert first_result["last_step"] is False

    thresholds_result = await flow.async_step_user(
        {
            "name": "Washer",
            "appliance_type": "washer",
            "power_entity": "sensor.washer_power",
        }
    )
    assert thresholds_result["step_id"] == "thresholds"
    assert thresholds_result["last_step"] is False

    actions_result = await flow.async_step_thresholds(
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        }
    )
    assert actions_result["step_id"] == "actions"

    created = await flow.async_step_actions(
        {
            "start_actions": [],
            "finish_actions": [],
            "max_runtime_actions": [],
        }
    )
    assert created["title"] == "Washer"
    assert created["data"]["power_entity"] == "sensor.washer_power"
    assert "start_power_w" not in created["data"]
    assert created["options"]["start_power_w"] == 4
    assert [result["step_id"] for result in shown_steps] == [
        "user",
        "thresholds",
        "actions",
    ]


@pytest.mark.asyncio
async def test_options_flow_edits_three_steps_and_clears_removed_door_settings(
    monkeypatch,
):
    entry = SimpleNamespace(
        data={
            "name": "Washer",
            "appliance_type": "washer",
            "power_entity": "sensor.washer_power",
            "door_entity": "binary_sensor.washer_door",
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
        title="Washer",
    )
    updated: list[dict[str, object]] = []
    monkeypatch.setattr(
        ApplianceCycleMonitorOptionsFlow,
        "config_entry",
        property(lambda _self: entry),
    )
    flow = ApplianceCycleMonitorOptionsFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda _entry, **kwargs: updated.append(kwargs)
        )
    )
    shown_steps: list[dict[str, object]] = []
    flow.async_show_form = lambda **result: shown_steps.append(result) or result
    flow.async_create_entry = lambda **result: result

    first_result = await flow.async_step_init()
    assert first_result["step_id"] == "init"
    assert first_result["data_schema"]({})["name"] == "Washer"
    thresholds_result = await flow.async_step_init(
        {
            "name": "Washer 2",
            "appliance_type": "washer",
            "power_entity": "sensor.new_power",
            "door_entity": None,
        }
    )
    assert thresholds_result["step_id"] == "thresholds"
    actions_result = await flow.async_step_thresholds(
        {
            "start_power_w": 5,
            "start_duration_seconds": 30,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        }
    )
    assert actions_result["step_id"] == "actions"
    created = await flow.async_step_actions(
        {"start_actions": [], "finish_actions": [], "max_runtime_actions": []}
    )

    assert [result["step_id"] for result in shown_steps] == [
        "init",
        "thresholds",
        "actions",
    ]
    assert updated[0]["title"] == "Washer 2"
    assert updated[0]["data"]["power_entity"] == "sensor.new_power"
    assert created["data"][CONF_PENDING_ACTIONS] == []
    assert created["data"][CONF_PENDING_DELAY_SECONDS] == 900
    assert created["data"][CONF_PENDING_INTERVAL_SECONDS] == 900
    assert created["data"][CONF_PENDING_REPEATS] == 3


if __name__ == "__main__":
    unittest.main()