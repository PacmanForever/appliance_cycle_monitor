"""Unit tests for configuration schemas and translation coverage."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import pytest
import voluptuous as vol

from custom_components.home_activity_manager.config_flow import (
    ApplianceCycleMonitorConfigFlow,
    ApplianceCycleMonitorOptionsFlow,
    _action_schema,
    _identity_schema,
    _entry_options,
    _normalize_sensor_values,
    _sensor_form_values,
    _sensor_schema,
    _threshold_schema,
    _clear_pending_settings,
    _validate_alarm_settings,
    _validate_plug_off_alarm_settings,
    _validate_pending,
    _validate_thresholds,
)
from custom_components.home_activity_manager.appliance_types import (
    APPLIANCE_CATEGORIES,
    APPLIANCE_MODEL_NAMES,
    APPLIANCE_PROFILES,
    APPLIANCE_TYPES,
    get_appliance_model,
    get_appliance_profile,
)
from custom_components.home_activity_manager.const import (
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
    DEFAULT_PENDING_DELAY_SECONDS,
    DEFAULT_PENDING_INTERVAL_SECONDS,
    DEFAULT_PENDING_REPEATS,
)


class ConfigFlowSchemaTests(unittest.TestCase):
    def test_categories_map_each_profile_to_one_compatible_mode(self) -> None:
        mapped = [
            profile
            for modes in APPLIANCE_CATEGORIES.values()
            for profile in modes.values()
        ]
        self.assertEqual(len(mapped), len(set(mapped)))
        self.assertEqual(set(mapped), set(APPLIANCE_PROFILES))
        for modes in APPLIANCE_CATEGORIES.values():
            for mode, profile in modes.items():
                self.assertEqual(APPLIANCE_PROFILES[profile].detection_sources, (mode,))

    def test_device_models_cover_and_distinguish_all_profiles(self) -> None:
        self.assertEqual(set(APPLIANCE_MODEL_NAMES), set(APPLIANCE_PROFILES))
        self.assertEqual(
            get_appliance_model("air_conditioner_contact"),
            "Air conditioner (contact/opening sensor)",
        )
        self.assertEqual(
            get_appliance_model("air_conditioner_power"),
            "Air conditioner (power sensor)",
        )
        self.assertEqual(
            get_appliance_model("mailbox_slot"),
            "Mailbox (mail-slot contact/opening sensor)",
        )

    def test_identity_schema_requires_name_and_type(self) -> None:
        schema = _identity_schema({})
        with self.assertRaises(vol.Invalid):
            schema({"name": "Washer"})

        values = schema({"name": "Washer", CONF_APPLIANCE_TYPE: "washer"})

        self.assertEqual(values[CONF_APPLIANCE_TYPE], "washer")
        self.assertNotIn(CONF_POWER_ENTITY, values)

    def test_sensor_selection_fields_prefill_during_edit(self) -> None:
        values = {
            CONF_POWER_ENTITY: "sensor.dishwasher_power",
            "door_entity": "binary_sensor.dishwasher_door",
            "plug_entity": "switch.dishwasher_plug",
        }
        profile = get_appliance_profile("dishwasher")
        schema = _sensor_schema(_sensor_form_values(values, profile), profile)

        form_values = schema({})
        self.assertEqual(
            form_values["dishwasher_power_entity"], "sensor.dishwasher_power"
        )
        self.assertEqual(
            form_values["dishwasher_door_entity"], "binary_sensor.dishwasher_door"
        )
        self.assertEqual(form_values["dishwasher_plug_entity"], "switch.dishwasher_plug")
        normalized = _normalize_sensor_values(form_values, profile)
        self.assertEqual(
            normalized["door_entity"],
            "binary_sensor.dishwasher_door",
        )
        self.assertEqual(normalized[CONF_POWER_ENTITY], "sensor.dishwasher_power")

    def test_ac_profiles_offer_auxiliary_sources(self) -> None:
        contact_profile = get_appliance_profile("air_conditioner_contact")
        climate_profile = get_appliance_profile("air_conditioner_climate")
        power_profile = get_appliance_profile("air_conditioner_power")
        contact_schema = _sensor_schema({}, contact_profile)
        climate_schema = _sensor_schema({}, climate_profile)
        power_schema = _sensor_schema({}, power_profile)

        self.assertIn("air_conditioner_contact_running_entity", contact_schema.schema)
        self.assertIn("air_conditioner_contact_power_entity", contact_schema.schema)
        self.assertIn("air_conditioner_climate_climate_entity", climate_schema.schema)
        self.assertNotIn("air_conditioner_climate_running_entity", climate_schema.schema)
        self.assertIn("air_conditioner_power_power_entity", power_schema.schema)
        self.assertNotIn("air_conditioner_power_running_entity", power_schema.schema)
        self.assertIn("air_conditioner_contact_plug_entity", contact_schema.schema)
        self.assertIn("air_conditioner_power_plug_entity", power_schema.schema)
        self.assertFalse(contact_profile.supports_pending_unload)
        self.assertFalse(contact_profile.estimates_remaining)
        self.assertFalse(power_profile.supports_pending_unload)
        self.assertFalse(power_profile.estimates_remaining)

    def test_each_profile_schema_matches_its_declared_contract(self) -> None:
        parameter_keys = {
            "power_cycle": {
                "start_power_w",
                "start_duration_seconds",
                "finish_power_w",
                "finish_duration_seconds",
            },
            "max_runtime": {"max_runtime_seconds"},
            "pending_unload": {
                CONF_PENDING_DELAY_SECONDS,
                CONF_PENDING_INTERVAL_SECONDS,
                CONF_PENDING_REPEATS,
            },
            "door_alarm": {CONF_DOOR_OPEN_DELAY_SECONDS},
            "compressor_alarm": {CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS},
            "alarm_repeats": {
                CONF_ALARM_REPEAT_INTERVAL_SECONDS,
                CONF_ALARM_REPEAT_COUNT,
            },
            "plug_off_alarm": {
                CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
                CONF_PLUG_OFF_REPEAT_COUNT,
            },
        }
        action_keys = {
            "cycle_start": "start_actions",
            "cycle_finish": "finish_actions",
            "max_runtime": "max_runtime_actions",
            "pending_unload": CONF_PENDING_ACTIONS,
            "door_open_alarm": CONF_DOOR_OPEN_ACTIONS,
            "compressor_inactive_alarm": CONF_COMPRESSOR_INACTIVE_ACTIONS,
            "plug_off_alarm": CONF_PLUG_OFF_ACTIONS,
            "mail_arrival": CONF_MAIL_ARRIVAL_ACTIONS,
        }
        expected_input_wrappers = {
            "air_conditioner_contact": {CONF_RUNNING_ENTITY},
            "mailbox_motion": {CONF_MAIL_MOTION_ENTITY, CONF_DOOR_ENTITY},
            "mailbox_slot": {CONF_MAIL_SLOT_ENTITY, CONF_DOOR_ENTITY},
        }
        for appliance_type, profile in APPLIANCE_PROFILES.items():
            with self.subTest(appliance_type=appliance_type):
                self.assertEqual(
                    {
                        item.config_key
                        for item in profile.inputs_requiring_wrapper
                    },
                    expected_input_wrappers.get(appliance_type, set()),
                )
                for input_config in profile.sensor_inputs:
                    if input_config.domain == "climate":
                        self.assertIsNone(input_config.output_entity)
                    else:
                        self.assertTrue(
                            input_config.output_entity
                            or input_config in profile.inputs_requiring_wrapper
                        )
                self.assertTrue(
                    all(
                        input_config.domain == "binary_sensor"
                        for input_config in profile.inputs_requiring_wrapper
                    )
                )
                values = {
                    CONF_POWER_ENTITY: "sensor.appliance_power",
                    CONF_RUNNING_ENTITY: "binary_sensor.appliance_activity",
                    "door_entity": "binary_sensor.appliance_door",
                }
                if profile.supports_smart_plug:
                    values[CONF_PLUG_ENTITY] = "switch.appliance_plug"
                sensor_schema = _sensor_schema(_sensor_form_values(values, profile), profile)
                parameter_schema = _threshold_schema(values, profile)
                action_schema = _action_schema(values, profile)

                expected_source = next(
                    item.form_key
                    for item in profile.sensor_inputs
                    if item.detection_source is not None
                )
                self.assertIn(expected_source, sensor_schema.schema)
                self.assertEqual(
                    any(item.config_key == CONF_POWER_ENTITY for item in profile.sensor_inputs),
                    any(
                        item.form_key in sensor_schema.schema
                        for item in profile.sensor_inputs
                        if item.config_key == CONF_POWER_ENTITY
                    ),
                )
                self.assertEqual(
                    any(item.config_key == CONF_RUNNING_ENTITY for item in profile.sensor_inputs),
                    any(
                        item.form_key in sensor_schema.schema
                        for item in profile.sensor_inputs
                        if item.config_key == CONF_RUNNING_ENTITY
                    ),
                )
                self.assertEqual(
                    profile.supports_door_sensor,
                    profile.door_sensor_input is not None
                    and profile.door_sensor_input.form_key in sensor_schema.schema,
                )
                self.assertEqual(
                    "total_energy" in profile.output_entities,
                    "power" in profile.detection_sources,
                )
                self.assertEqual(
                    "estimated_remaining" in profile.output_entities,
                    profile.estimates_remaining,
                )
                self.assertEqual(
                    "pending_unload" in profile.output_entities,
                    profile.supports_pending_unload,
                )

                for group, keys in parameter_keys.items():
                    for key in keys:
                        self.assertEqual(
                            group in profile.parameter_groups,
                            key in parameter_schema.schema,
                        )
                for group, key in action_keys.items():
                    self.assertEqual(
                        group in profile.action_groups
                        and (group != "plug_off_alarm" or profile.supports_smart_plug),
                        key in action_schema.schema,
                    )

                if profile.supports_smart_plug:
                    no_plug_parameters = _threshold_schema(
                        {CONF_POWER_ENTITY: "sensor.appliance_power"}, profile
                    )
                    no_plug_actions = _action_schema(
                        {CONF_POWER_ENTITY: "sensor.appliance_power"}, profile
                    )
                    self.assertNotIn(
                        CONF_PLUG_OFF_REPEAT_COUNT, no_plug_parameters.schema
                    )
                    self.assertNotIn(CONF_PLUG_OFF_ACTIONS, no_plug_actions.schema)

    def test_plug_off_alarm_settings_validation(self) -> None:
        profile = get_appliance_profile("washer")
        valid = {
            CONF_PLUG_ENTITY: "switch.washer",
            CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 900,
            CONF_PLUG_OFF_REPEAT_COUNT: 3,
        }

        self.assertTrue(_validate_plug_off_alarm_settings(valid, profile))
        self.assertFalse(
            _validate_plug_off_alarm_settings(
                {**valid, CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 0}, profile
            )
        )
        self.assertFalse(
            _validate_plug_off_alarm_settings(
                {**valid, CONF_PLUG_OFF_REPEAT_COUNT: -1}, profile
            )
        )
        self.assertTrue(_validate_plug_off_alarm_settings({}, profile))

    def test_sensor_selectors_filter_by_domain_and_device_class(self) -> None:
        for profile in APPLIANCE_PROFILES.values():
            schema = _sensor_schema(_sensor_form_values(
                {"door_entity": "binary_sensor.door"}, profile
            ), profile)
            selectors = {
                marker.schema: entity_selector
                for marker, entity_selector in schema.schema.items()
            }
            source_input = next(
                item for item in profile.sensor_inputs
                if item.detection_source is not None
            )
            if source_input.device_classes:
                self.assertEqual(
                    selectors[source_input.form_key].config["filter"],
                    [
                        {
                            "domain": [source_input.domain],
                            "device_class": [device_class],
                        }
                        for device_class in source_input.device_classes
                    ],
                )
            else:
                self.assertEqual(
                    selectors[source_input.form_key].config["domain"],
                    [source_input.domain],
                )
            if profile.door_sensor_input is not None:
                self.assertEqual(
                    selectors[
                        profile.door_sensor_input.form_key
                    ].config["filter"],
                    [
                        {
                            "domain": [profile.door_sensor_input.domain],
                            "device_class": [device_class],
                        }
                        for device_class in profile.door_sensor_input.device_classes
                    ],
                )

    def test_refrigerator_requires_door_and_valid_alarm_limits(self) -> None:
        profile = get_appliance_profile("refrigerator")
        sensor_schema = _sensor_schema({}, profile)
        with self.assertRaises(vol.Invalid):
            sensor_schema({CONF_POWER_ENTITY: "sensor.fridge_power"})

        self.assertTrue(
            _validate_alarm_settings(
                {
                    CONF_DOOR_OPEN_DELAY_SECONDS: 120,
                    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 3600,
                    CONF_ALARM_REPEAT_INTERVAL_SECONDS: 900,
                    CONF_ALARM_REPEAT_COUNT: 3,
                }
            )
        )
        self.assertFalse(
            _validate_alarm_settings(
                {
                    CONF_DOOR_OPEN_DELAY_SECONDS: 0,
                    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 3600,
                    CONF_ALARM_REPEAT_INTERVAL_SECONDS: 900,
                    CONF_ALARM_REPEAT_COUNT: 3,
                }
            )
        )

    def test_threshold_and_alarm_validators_reject_missing_or_invalid_values(self) -> None:
        contact_profile = get_appliance_profile("air_conditioner_contact")
        self.assertTrue(_validate_thresholds({}, contact_profile))
        self.assertTrue(
            _validate_thresholds(
                {CONF_MAX_RUNTIME_SECONDS: 60}, contact_profile
            )
        )
        self.assertFalse(
            _validate_thresholds(
                {CONF_MAX_RUNTIME_SECONDS: "invalid"}, contact_profile
            )
        )
        self.assertFalse(
            _validate_thresholds({"start_power_w": 4})
        )
        self.assertFalse(_validate_pending({}))
        self.assertFalse(_validate_alarm_settings({}))

    def test_profile_change_discards_actions_not_declared_by_new_profile(self) -> None:
        options = _entry_options(
            {
                CONF_APPLIANCE_TYPE: "refrigerator",
                CONF_START_ACTIONS: [{"action": "test.start"}],
                CONF_FINISH_ACTIONS: [{"action": "test.finish"}],
                CONF_MAX_RUNTIME_ACTIONS: [{"action": "test.timeout"}],
                CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door"}],
                CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor"}],
                CONF_ALARM_REPEAT_COUNT: 3,
                CONF_ALARM_REPEAT_INTERVAL_SECONDS: 900,
            }
        )

        self.assertIn(CONF_START_ACTIONS, options)
        self.assertIn(CONF_FINISH_ACTIONS, options)
        self.assertNotIn(CONF_MAX_RUNTIME_ACTIONS, options)
        self.assertIn(CONF_DOOR_OPEN_ACTIONS, options)
        self.assertNotIn(CONF_COMPRESSOR_INACTIVE_ACTIONS, options)
        self.assertNotIn(CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS, options)
        self.assertNotIn(CONF_PLUG_OFF_ACTIONS, options)
        self.assertNotIn(CONF_PLUG_OFF_REPEAT_COUNT, options)
        self.assertIn(CONF_ALARM_REPEAT_COUNT, options)
        self.assertIn(CONF_ALARM_REPEAT_INTERVAL_SECONDS, options)

    def test_default_thresholds_and_coherence_validation(self) -> None:
        values = _threshold_schema({}, get_appliance_profile("washer"))(
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
        profile = get_appliance_profile("washer")
        without_door = _threshold_schema({}, profile)
        with_door = _threshold_schema({"door_entity": "binary_sensor.door"}, profile)
        actions_without_door = _action_schema({}, profile)
        actions_with_door = _action_schema({"door_entity": "binary_sensor.door"}, profile)

        self.assertNotIn(CONF_PENDING_DELAY_SECONDS, without_door.schema)
        self.assertIn(CONF_PENDING_DELAY_SECONDS, with_door.schema)
        self.assertNotIn(CONF_PENDING_DELAY_SECONDS, actions_with_door.schema)
        self.assertNotIn(CONF_PENDING_INTERVAL_SECONDS, actions_with_door.schema)
        self.assertNotIn(CONF_PENDING_REPEATS, actions_with_door.schema)
        self.assertNotIn(CONF_PENDING_ACTIONS, actions_without_door.schema)
        self.assertIn(CONF_PENDING_ACTIONS, actions_with_door.schema)
        values = with_door(
            {
                "start_power_w": 4,
                "finish_power_w": 1,
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
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
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
        self.assertEqual(key_shape(translations[3]), expected)
        expected_input_names = (
            ("Motion sensor", "Main-door contact/opening sensor", "Mail-slot contact/opening sensor"),
            ("Motion sensor", "Main-door contact/opening sensor", "Mail-slot contact/opening sensor"),
            ("Sensor de movimiento", "Sensor de contacto/apertura de la puerta principal", "Sensor de contacto/apertura de la trampilla"),
            ("Sensor de moviment", "Sensor de contacte/obertura de la porta principal", "Sensor de contacte/obertura de la portella"),
        )
        for translation, expected_names in zip(translations, expected_input_names):
            binary_sensor_names = translation["entity"]["binary_sensor"]
            for key, expected_name in zip(
                ("input_mail_motion", "input_door", "input_mail_slot"),
                expected_names,
            ):
                self.assertEqual(binary_sensor_names[key]["name"], expected_name)

        for translation in translations:
            for flow in ("config", "options"):
                for shared_step in ("sensors", "parameters", "actions"):
                    self.assertNotIn(shared_step, translation[flow]["step"])
        for translation in translations:
            self.assertNotIn("activity_mode", translation["config"]["step"])

        sensor_form_keys = [
            item.form_key
            for profile in APPLIANCE_PROFILES.values()
            for item in profile.sensor_inputs
        ]
        self.assertEqual(len(sensor_form_keys), len(set(sensor_form_keys)))

        catalan_options = translations[3]["selector"]["appliance_type"]["options"]
        catalan_labels = [catalan_options[appliance_type] for appliance_type in APPLIANCE_TYPES]
        self.assertEqual(catalan_labels, sorted(catalan_labels, key=str.casefold))

        for translation in translations:
            option_labels = translation["selector"]["appliance_type"]["options"]
            self.assertEqual(set(option_labels), set(APPLIANCE_PROFILES))
            for appliance_type, label in option_labels.items():
                self.assertTrue(label.strip())
                self.assertNotEqual(label, appliance_type)

            for flow, identity_step in (("config", "user"), ("options", "init")):
                for profile in APPLIANCE_PROFILES.values():
                    values = {"door_entity": "binary_sensor.door"}
                    profile_name = next(
                        name
                        for name, candidate in APPLIANCE_PROFILES.items()
                        if candidate is profile
                    )
                    step_schemas = {
                        identity_step: _identity_schema({}),
                        f"sensors_{profile_name}": _sensor_schema(
                            _sensor_form_values(values, profile), profile
                        ),
                        f"parameters_{profile_name}": _threshold_schema(values, profile),
                        f"actions_{profile_name}": _action_schema(values, profile),
                    }
                    for step, schema in step_schemas.items():
                        labels = translation[flow]["step"][step]["data"]
                        for marker in schema.schema:
                            key = marker.schema
                            self.assertIn(key, labels)
                            self.assertTrue(labels[key].strip())
                            self.assertNotEqual(labels[key], key)
                        if step.startswith("sensors_air_conditioner_"):
                            descriptions = translation[flow]["step"][step][
                                "data_description"
                            ]
                            self.assertEqual(
                                set(descriptions),
                                {marker.schema for marker in schema.schema},
                            )
                            self.assertTrue(
                                all(description.strip() for description in descriptions.values())
                            )
                    sensor_labels = translation[flow]["step"][
                        f"sensors_{profile_name}"
                    ]["data"]
                    for sensor_input in profile.sensor_inputs:
                        if not sensor_input.required:
                            self.assertTrue(
                                "(optional)" in sensor_labels[sensor_input.form_key]
                                or "(opcional)" in sensor_labels[sensor_input.form_key]
                            )
                        else:
                            self.assertTrue(
                                "(required)" in sensor_labels[sensor_input.form_key]
                                or "(obligatori)" in sensor_labels[sensor_input.form_key]
                                or "(obligatorio)" in sensor_labels[sensor_input.form_key]
                            )
                    action_labels = translation[flow]["step"][
                        f"actions_{profile_name}"
                    ]["data"].values()
                    self.assertTrue(
                        all(
                            "(optional)" in label or "(opcional)" in label
                            for label in action_labels
                        )
                    )

            mode_labels = []
            for category, modes in APPLIANCE_CATEGORIES.items():
                step = translation["config"]["step"][
                    f"activity_mode_{category}"
                ]
                labels = step["data"]
                self.assertTrue(step["title"].strip())
                self.assertTrue(labels["activity_mode"].strip())
                self.assertTrue(step["data_description"]["activity_mode"].strip())
                mode_labels.append(labels["activity_mode"])
                options = translation["selector"][
                    f"activity_mode_{category}"
                ]["options"]
                self.assertEqual(set(options), set(modes))
                self.assertTrue(all(label.strip() for label in options.values()))
            self.assertEqual(len(mode_labels), len(set(mode_labels)))


@pytest.mark.asyncio
async def test_config_flow_has_five_forward_steps_and_separates_options():
    flow = ApplianceCycleMonitorConfigFlow()
    shown_steps: list[dict[str, object]] = []
    flow.async_show_form = lambda **result: shown_steps.append(result) or result
    flow.async_create_entry = lambda **result: result

    first_result = await flow.async_step_user()
    assert first_result["step_id"] == "user"
    assert first_result["last_step"] is False

    mode_result = await flow.async_step_user(
        {
            "name": "Washer",
            "appliance_type": "washer",
        }
    )
    assert mode_result["step_id"] == "activity_mode_washer"
    sensors_result = await flow.async_step_activity_mode({"activity_mode": "power"})
    assert sensors_result["step_id"] == "sensors_washer"

    parameters_result = await flow.async_step_sensors(
        {"washer_power_entity": "sensor.washer_power"}
    )
    assert parameters_result["step_id"] == "parameters_washer"
    assert parameters_result["last_step"] is False

    actions_result = await flow.async_step_parameters(
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        }
    )
    assert actions_result["step_id"] == "actions_washer"

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
        "activity_mode_washer",
        "sensors_washer",
        "parameters_washer",
        "actions_washer",
    ]


@pytest.mark.asyncio
async def test_pending_settings_are_validated_on_parameters_step():
    flow = ApplianceCycleMonitorConfigFlow()
    flow.async_show_form = lambda **result: result
    flow.async_create_entry = lambda **result: result

    await flow.async_step_user(
        {
            "name": "Washer",
            "appliance_type": "washer",
        }
    )
    await flow.async_step_activity_mode({"activity_mode": "power"})
    await flow.async_step_sensors(
        {
            "washer_power_entity": "sensor.washer_power",
            "door_entity": "binary_sensor.washer_door",
        }
    )
    result = await flow.async_step_parameters(
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
            CONF_PENDING_DELAY_SECONDS: 0,
            CONF_PENDING_INTERVAL_SECONDS: 900,
            CONF_PENDING_REPEATS: 3,
        }
    )

    assert result["step_id"] == "parameters_washer"
    assert result["errors"] == {"base": "invalid_pending_settings"}

    result = await flow.async_step_parameters(
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
            CONF_PENDING_DELAY_SECONDS: 1200,
            CONF_PENDING_INTERVAL_SECONDS: 1800,
            CONF_PENDING_REPEATS: 2,
        }
    )
    assert result["step_id"] == "actions_washer"
    assert CONF_PENDING_DELAY_SECONDS not in result["data_schema"].schema

    created = await flow.async_step_actions(
        {
            "start_actions": [],
            "finish_actions": [],
            "max_runtime_actions": [],
            CONF_PENDING_ACTIONS: [],
        }
    )
    assert created["options"][CONF_PENDING_DELAY_SECONDS] == 1200
    assert created["options"][CONF_PENDING_INTERVAL_SECONDS] == 1800
    assert created["options"][CONF_PENDING_REPEATS] == 2


@pytest.mark.asyncio
async def test_options_flow_edits_four_steps_and_clears_removed_door_settings(
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
    sensors_result = await flow.async_step_init(
        {
            "name": "Washer 2",
            "appliance_type": "washer",
        }
    )
    assert sensors_result["step_id"] == "sensors_washer"
    parameters_result = await flow.async_step_sensors(
        {"washer_power_entity": "sensor.new_power", "washer_door_entity": None}
    )
    assert parameters_result["step_id"] == "parameters_washer"
    actions_result = await flow.async_step_parameters(
        {
            "start_power_w": 5,
            "start_duration_seconds": 30,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        }
    )
    assert actions_result["step_id"] == "actions_washer"
    created = await flow.async_step_actions(
        {"start_actions": [], "finish_actions": [], "max_runtime_actions": []}
    )

    assert [result["step_id"] for result in shown_steps] == [
        "init",
        "sensors_washer",
        "parameters_washer",
        "actions_washer",
    ]
    assert updated[0]["title"] == "Washer 2"
    assert updated[0]["data"]["power_entity"] == "sensor.new_power"
    assert CONF_PENDING_ACTIONS not in created["data"]
    assert CONF_PENDING_DELAY_SECONDS not in created["data"]
    assert CONF_PENDING_INTERVAL_SECONDS not in created["data"]
    assert CONF_PENDING_REPEATS not in created["data"]


if __name__ == "__main__":
    unittest.main()