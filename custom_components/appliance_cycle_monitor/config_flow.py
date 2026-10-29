"""Configuration flows for Appliance Cycle Monitor."""

from __future__ import annotations

import math
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, selector

from . import _async_appliance_device_id
from .appliance_types import (
    APPLIANCE_CATEGORIES,
    APPLIANCE_TYPES,
    ApplianceTypeProfile,
    get_appliance_profile,
)
from .const import (
    CONF_APPLIANCE_TYPE,
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_CLIMATE_ENTITY,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_DOOR_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    CONF_FINISH_ACTIONS,
    CONF_FINISH_DURATION_SECONDS,
    CONF_FINISH_POWER_W,
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
    CONF_START_DURATION_SECONDS,
    CONF_START_POWER_W,
    DEFAULT_FINISH_DURATION_SECONDS,
    DEFAULT_FINISH_POWER_W,
    DEFAULT_ALARM_REPEAT_COUNT,
    DEFAULT_ALARM_REPEAT_INTERVAL_SECONDS,
    DEFAULT_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    DEFAULT_DOOR_OPEN_DELAY_SECONDS,
    DEFAULT_PENDING_DELAY_SECONDS,
    DEFAULT_PENDING_INTERVAL_SECONDS,
    DEFAULT_PENDING_REPEATS,
    DEFAULT_PLUG_OFF_REPEAT_COUNT,
    DEFAULT_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    DEFAULT_START_DURATION_SECONDS,
    DEFAULT_START_POWER_W,
    DOMAIN,
)

CONF_NAME = "name"
_ENTRY_DATA_KEYS = {
    CONF_NAME,
    CONF_APPLIANCE_TYPE,
    CONF_POWER_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_CLIMATE_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_DOOR_ENTITY,
    CONF_PLUG_ENTITY,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
}


def _required(key: str, values: dict[str, Any]) -> vol.Required:
    if key in values and values[key] is not None:
        return vol.Required(key, default=values[key])
    return vol.Required(key)


def _optional(key: str, values: dict[str, Any]) -> vol.Optional:
    if key in values:
        return vol.Optional(key, default=values[key])
    return vol.Optional(key)


class _OptionalEntitySelector(selector.EntitySelector):
    def __call__(self, data: Any) -> str | list[str] | None:
        if data is None:
            return None
        return super().__call__(data)


class _LockedSelectSelector(selector.SelectSelector):
    def __call__(self, data: Any) -> Any:
        return data


def _number_selector(unit: str, step: float = 0.1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX,
            step=step,
            unit_of_measurement=unit,
        )
    )


def _identity_schema(
    values: dict[str, Any],
    appliance_types: tuple[str, ...] = APPLIANCE_TYPES,
    translation_key: str = CONF_APPLIANCE_TYPE,
) -> vol.Schema:
    return vol.Schema(
        {
        _required(CONF_NAME, values): selector.TextSelector(),
        _required(CONF_APPLIANCE_TYPE, values): (
            _LockedSelectSelector(
                selector.SelectSelectorConfig(
                    options=list(appliance_types),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=translation_key,
                )
            )
            if len(appliance_types) == 1
            else selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(appliance_types),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=translation_key,
                )
            )
        ),
        }
    )


def _activity_mode_schema(category: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("activity_mode"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(APPLIANCE_CATEGORIES[category]),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="activity_mode",
                )
            )
        }
    )


def _options_identity_schema(values: dict[str, Any]) -> vol.Schema:
    category, mode = _profile_identity(values[CONF_APPLIANCE_TYPE])
    return vol.Schema(
        {
            _required(CONF_NAME, values): selector.TextSelector(),
            vol.Required(CONF_APPLIANCE_TYPE, default=category): _LockedSelectSelector(
                selector.SelectSelectorConfig(
                    options=[category],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="appliance_category",
                    read_only=True,
                )
            ),
            vol.Required("activity_mode", default=mode): _LockedSelectSelector(
                selector.SelectSelectorConfig(
                    options=[mode],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="activity_mode",
                    read_only=True,
                )
            ),
        }
    )


def _profile_identity(profile_name: str) -> tuple[str, str]:
    return next(
        (category, mode)
        for category, modes in APPLIANCE_CATEGORIES.items()
        for mode, name in modes.items()
        if name == profile_name
    )


def _sensor_form_values(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> dict[str, Any]:
    form_values = dict(values)
    for sensor_input in profile.sensor_inputs:
        if sensor_input.config_key in values:
            form_values[sensor_input.form_key] = values[sensor_input.config_key]
    return form_values


def _normalize_sensor_values(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> dict[str, Any]:
    normalized = dict(values)
    for sensor_input in profile.sensor_inputs:
        if sensor_input.form_key != sensor_input.config_key:
            if sensor_input.form_key in normalized:
                normalized[sensor_input.config_key] = normalized.pop(
                    sensor_input.form_key
                )
    return normalized


def _sensor_schema(
    values: dict[str, Any],
    profile: ApplianceTypeProfile,
    hass: HomeAssistant | None = None,
) -> vol.Schema:
    schema: dict[Any, Any] = {}
    for sensor_input in profile.sensor_inputs:
        marker = (
            _required(sensor_input.form_key, values)
            if sensor_input.required
            else _optional(sensor_input.form_key, values)
        )
        if sensor_input.device_classes:
            entity_filter = [
                {"domain": sensor_input.domain, "device_class": device_class}
                for device_class in sensor_input.device_classes
            ]
            selector_config = selector.EntitySelectorConfig(filter=entity_filter)
        elif sensor_input.domain == "climate":
            selected_entity_id = values.get(sensor_input.config_key)
            excluded_entities = (
                [
                    entity.entity_id
                    for entity in er.async_get(hass).entities.values()
                    if entity.domain == "climate"
                    and entity.device_id is not None
                    and entity.entity_id != selected_entity_id
                ]
                if hass is not None
                else []
            )
            selector_config = selector.EntitySelectorConfig(
                domain=sensor_input.domain, exclude_entities=excluded_entities
            )
        else:
            selector_config = selector.EntitySelectorConfig(domain=sensor_input.domain)
        entity_selector = selector.EntitySelector(selector_config)
        schema[marker] = (
            entity_selector
            if sensor_input.required
            else _OptionalEntitySelector(selector_config)
        )
    return vol.Schema(schema)


def _threshold_schema(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> vol.Schema:
    start_power = values.get(CONF_START_POWER_W, DEFAULT_START_POWER_W)
    start_duration = values.get(
        CONF_START_DURATION_SECONDS, DEFAULT_START_DURATION_SECONDS
    )
    finish_power = values.get(CONF_FINISH_POWER_W, DEFAULT_FINISH_POWER_W)
    finish_duration = values.get(
        CONF_FINISH_DURATION_SECONDS, DEFAULT_FINISH_DURATION_SECONDS
    )
    schema: dict[Any, Any] = {}
    if "power_cycle" in profile.parameter_groups:
        schema.update(
            {
                vol.Required(CONF_START_POWER_W, default=start_power): _number_selector("W"),
                vol.Required(CONF_START_DURATION_SECONDS, default=start_duration): (
                    _number_selector("s", step=1)
                ),
                vol.Required(CONF_FINISH_POWER_W, default=finish_power): _number_selector("W"),
                vol.Required(CONF_FINISH_DURATION_SECONDS, default=finish_duration): (
                    _number_selector("s", step=1)
                ),
            }
        )
    if "max_runtime" in profile.parameter_groups:
        schema[_optional(CONF_MAX_RUNTIME_SECONDS, values)] = _number_selector(
            "s", step=1
        )
    if "pending_unload" in profile.parameter_groups and values.get(CONF_DOOR_ENTITY):
        schema.update(
            {
                vol.Required(
                    CONF_PENDING_DELAY_SECONDS,
                    default=values.get(
                        CONF_PENDING_DELAY_SECONDS, DEFAULT_PENDING_DELAY_SECONDS
                    ),
                ): _number_selector("s", step=1),
                vol.Required(
                    CONF_PENDING_INTERVAL_SECONDS,
                    default=values.get(
                        CONF_PENDING_INTERVAL_SECONDS,
                        DEFAULT_PENDING_INTERVAL_SECONDS,
                    ),
                ): _number_selector("s", step=1),
                vol.Required(
                    CONF_PENDING_REPEATS,
                    default=values.get(CONF_PENDING_REPEATS, DEFAULT_PENDING_REPEATS),
                ): _number_selector("", step=1),
            }
        )
    if "door_alarm" in profile.parameter_groups:
        schema[vol.Required(
            CONF_DOOR_OPEN_DELAY_SECONDS,
            default=values.get(
                CONF_DOOR_OPEN_DELAY_SECONDS, DEFAULT_DOOR_OPEN_DELAY_SECONDS
            ),
        )] = _number_selector("s", step=1)
    if "compressor_alarm" in profile.parameter_groups:
        schema[vol.Required(
            CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
            default=values.get(
                CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
                DEFAULT_COMPRESSOR_INACTIVE_DELAY_SECONDS,
            ),
        )] = _number_selector("s", step=1)
    if "alarm_repeats" in profile.parameter_groups:
        schema[vol.Required(
            CONF_ALARM_REPEAT_INTERVAL_SECONDS,
            default=values.get(
                CONF_ALARM_REPEAT_INTERVAL_SECONDS,
                DEFAULT_ALARM_REPEAT_INTERVAL_SECONDS,
            ),
        )] = _number_selector("s", step=1)
        schema[vol.Required(
            CONF_ALARM_REPEAT_COUNT,
            default=values.get(CONF_ALARM_REPEAT_COUNT, DEFAULT_ALARM_REPEAT_COUNT),
        )] = _number_selector("", step=1)
    if "plug_off_alarm" in profile.parameter_groups and values.get(CONF_PLUG_ENTITY):
        schema[vol.Required(
            CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
            default=values.get(
                CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
                DEFAULT_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
            ),
        )] = _number_selector("s", step=1)
        schema[vol.Required(
            CONF_PLUG_OFF_REPEAT_COUNT,
            default=values.get(
                CONF_PLUG_OFF_REPEAT_COUNT, DEFAULT_PLUG_OFF_REPEAT_COUNT
            ),
        )] = _number_selector("", step=1)
    return vol.Schema(schema)


def _action_schema(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> vol.Schema:
    action_keys = {
        "cycle_start": CONF_START_ACTIONS,
        "cycle_finish": CONF_FINISH_ACTIONS,
        "max_runtime": CONF_MAX_RUNTIME_ACTIONS,
        "pending_unload": CONF_PENDING_ACTIONS,
        "door_open_alarm": CONF_DOOR_OPEN_ACTIONS,
        "compressor_inactive_alarm": CONF_COMPRESSOR_INACTIVE_ACTIONS,
        "plug_off_alarm": CONF_PLUG_OFF_ACTIONS,
        "mail_arrival": CONF_MAIL_ARRIVAL_ACTIONS,
    }
    schema: dict[Any, Any] = {}
    for group in profile.action_groups:
        if group == "plug_off_alarm" and not values.get(CONF_PLUG_ENTITY):
            continue
        if group == "pending_unload" and not values.get(CONF_DOOR_ENTITY):
            continue
        key = action_keys[group]
        schema[vol.Optional(key, default=values.get(key, []))] = (
            selector.ActionSelector()
        )
    return vol.Schema(schema)


def _validate_thresholds(
    values: dict[str, Any], profile: ApplianceTypeProfile | None = None
) -> bool:
    if profile is not None and "power" not in profile.detection_sources:
        maximum = values.get(CONF_MAX_RUNTIME_SECONDS)
        if maximum in (None, ""):
            return True
        try:
            max_runtime = float(maximum)
        except (TypeError, ValueError, OverflowError):
            return False
        return math.isfinite(max_runtime) and max_runtime > 0

    try:
        start_power = float(values[CONF_START_POWER_W])
        finish_power = float(values[CONF_FINISH_POWER_W])
        start_duration = float(values[CONF_START_DURATION_SECONDS])
        finish_duration = float(values[CONF_FINISH_DURATION_SECONDS])
        maximum = values.get(CONF_MAX_RUNTIME_SECONDS)
        max_runtime = None if maximum in (None, "") else float(maximum)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False

    return (
        all(math.isfinite(value) for value in (start_power, finish_power))
        and finish_power >= 0
        and start_power > finish_power
        and all(
            math.isfinite(value) and value >= 0
            for value in (start_duration, finish_duration)
        )
        and (max_runtime is None or (math.isfinite(max_runtime) and max_runtime > 0))
    )


def _validate_sensor_values(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> bool:
    arrival_input = next(
        (
            item
            for item in profile.sensor_inputs
            if item.detection_source in ("mail_motion", "mail_slot")
        ),
        None,
    )
    if arrival_input is None:
        return True
    arrival_entity = values.get(arrival_input.config_key)
    door_entity = values.get(CONF_DOOR_ENTITY)
    return arrival_entity is None or door_entity is None or arrival_entity != door_entity


def _validate_climate_entity(
    hass: HomeAssistant, entity_id: str | None, config_entry_id: str | None = None
) -> bool:
    if entity_id is None:
        return False
    entity_entry = er.async_get(hass).async_get(entity_id)
    if entity_entry is None or entity_entry.domain != "climate":
        return False
    if entity_entry.device_id is None:
        return True
    if config_entry_id is None:
        return False
    appliance_device_id = _async_appliance_device_id(hass, config_entry_id)
    return appliance_device_id is not None and entity_entry.device_id == appliance_device_id


def _validate_pending(values: dict[str, Any]) -> bool:
    try:
        delay = float(values[CONF_PENDING_DELAY_SECONDS])
        interval = float(values[CONF_PENDING_INTERVAL_SECONDS])
        repeats = float(values[CONF_PENDING_REPEATS])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return (
        math.isfinite(delay)
        and delay > 0
        and delay.is_integer()
        and math.isfinite(interval)
        and interval > 0
        and interval.is_integer()
        and math.isfinite(repeats)
        and repeats >= 0
        and repeats.is_integer()
    )


def _validate_alarm_settings(
    values: dict[str, Any], profile: ApplianceTypeProfile | None = None
) -> bool:
    groups = (
        profile.parameter_groups
        if profile is not None
        else ("door_alarm", "compressor_alarm", "alarm_repeats")
    )
    positive_keys = []
    if "door_alarm" in groups:
        positive_keys.append(CONF_DOOR_OPEN_DELAY_SECONDS)
    if "compressor_alarm" in groups:
        positive_keys.append(CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS)
    if "alarm_repeats" in groups:
        positive_keys.append(CONF_ALARM_REPEAT_INTERVAL_SECONDS)

    try:
        positive_values = [float(values[key]) for key in positive_keys]
        repeats = (
            float(values[CONF_ALARM_REPEAT_COUNT])
            if "alarm_repeats" in groups
            else None
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return False

    if not all(
        math.isfinite(value) and value > 0 and value.is_integer()
        for value in positive_values
    ):
        return False
    return repeats is None or (
        math.isfinite(repeats) and repeats >= 0 and repeats.is_integer()
    )


def _validate_plug_off_alarm_settings(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> bool:
    if "plug_off_alarm" not in profile.parameter_groups or not values.get(
        CONF_PLUG_ENTITY
    ):
        return True
    try:
        interval = float(values[CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS])
        repeats = float(values[CONF_PLUG_OFF_REPEAT_COUNT])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return (
        math.isfinite(interval)
        and interval > 0
        and interval.is_integer()
        and math.isfinite(repeats)
        and repeats >= 0
        and repeats.is_integer()
    )


def _clear_pending_settings(values: dict[str, Any]) -> None:
    values[CONF_PENDING_ACTIONS] = []
    values[CONF_PENDING_DELAY_SECONDS] = DEFAULT_PENDING_DELAY_SECONDS
    values[CONF_PENDING_INTERVAL_SECONDS] = DEFAULT_PENDING_INTERVAL_SECONDS
    values[CONF_PENDING_REPEATS] = DEFAULT_PENDING_REPEATS


def _entry_data(values: dict[str, Any]) -> dict[str, Any]:
    profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
    keys = _ENTRY_DATA_KEYS.copy()
    source_keys = {
        "power": CONF_POWER_ENTITY,
        "climate": CONF_CLIMATE_ENTITY,
        "running_sensor": CONF_RUNNING_ENTITY,
        "mail_motion": CONF_MAIL_MOTION_ENTITY,
        "mail_slot": CONF_MAIL_SLOT_ENTITY,
    }
    for source, key in source_keys.items():
        if source not in profile.detection_sources and not any(
            sensor_input.config_key == key for sensor_input in profile.sensor_inputs
        ):
            keys.discard(key)
    if not profile.supports_door_sensor:
        keys.discard(CONF_DOOR_ENTITY)
    if not profile.supports_smart_plug:
        keys.discard(CONF_PLUG_ENTITY)
    return {key: values[key] for key in keys if key in values}


def _entry_options(values: dict[str, Any]) -> dict[str, Any]:
    profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
    unsupported = set(_ENTRY_DATA_KEYS)
    if "power" not in profile.detection_sources:
        unsupported.update(
            {
                CONF_START_POWER_W,
                CONF_START_DURATION_SECONDS,
                CONF_FINISH_POWER_W,
                CONF_FINISH_DURATION_SECONDS,
            }
        )
    if "max_runtime" not in profile.parameter_groups:
        unsupported.update({CONF_MAX_RUNTIME_SECONDS, CONF_MAX_RUNTIME_ACTIONS})
    if "cycle_start" not in profile.action_groups:
        unsupported.add(CONF_START_ACTIONS)
    if "cycle_finish" not in profile.action_groups:
        unsupported.add(CONF_FINISH_ACTIONS)
    if "mail_arrival" not in profile.action_groups:
        unsupported.add(CONF_MAIL_ARRIVAL_ACTIONS)
    if "door_open_alarm" not in profile.action_groups:
        unsupported.update({CONF_DOOR_OPEN_ACTIONS, CONF_DOOR_OPEN_DELAY_SECONDS})
    if "compressor_inactive_alarm" not in profile.action_groups:
        unsupported.update(
            {CONF_COMPRESSOR_INACTIVE_ACTIONS, CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS}
        )
    if not any(
        group in profile.action_groups
        for group in ("door_open_alarm", "compressor_inactive_alarm")
    ):
        unsupported.update({CONF_ALARM_REPEAT_COUNT, CONF_ALARM_REPEAT_INTERVAL_SECONDS})
    if "plug_off_alarm" not in profile.action_groups or not values.get(
        CONF_PLUG_ENTITY
    ):
        unsupported.update(
            {
                CONF_PLUG_OFF_ACTIONS,
                CONF_PLUG_OFF_REPEAT_COUNT,
                CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
            }
        )
    if "pending_unload" not in profile.parameter_groups or not values.get(
        CONF_DOOR_ENTITY
    ):
        unsupported.update(
            {
                CONF_PENDING_ACTIONS,
                CONF_PENDING_DELAY_SECONDS,
                CONF_PENDING_INTERVAL_SECONDS,
                CONF_PENDING_REPEATS,
            }
        )
    return {key: value for key, value in values.items() if key not in unsupported}


class ApplianceCycleMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup of one appliance."""

    VERSION = 2

    def __init__(self) -> None:
        self._draft: dict[str, Any] = {}
        self._category: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            self._draft = dict(user_input)
            self._category = self._draft[CONF_APPLIANCE_TYPE]
            return await self.async_step_activity_mode()
        return self.async_show_form(
            step_id="user",
            data_schema=_identity_schema(
                {}, tuple(APPLIANCE_CATEGORIES), "appliance_category"
            ),
            last_step=False,
        )

    async def async_step_activity_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert self._category is not None
        if user_input is not None:
            self._draft[CONF_APPLIANCE_TYPE] = APPLIANCE_CATEGORIES[self._category][
                user_input["activity_mode"]
            ]
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="activity_mode",
            data_schema=_activity_mode_schema(self._category),
            last_step=False,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
            self._draft.update(_normalize_sensor_values(user_input, profile))
            if not _validate_sensor_values(self._draft, profile):
                return self.async_show_form(
                    step_id="sensors",
                    data_schema=_sensor_schema(
                        _sensor_form_values(self._draft, profile), profile, self.hass
                    ),
                    errors={"base": "mailbox_sensors_must_be_distinct"},
                    last_step=False,
                )
            if "climate" in profile.detection_sources and not _validate_climate_entity(
                self.hass, self._draft.get(CONF_CLIMATE_ENTITY)
            ):
                return self.async_show_form(
                    step_id="sensors",
                    data_schema=_sensor_schema(
                        _sensor_form_values(self._draft, profile), profile, self.hass
                    ),
                    errors={"base": "climate_entity_requires_no_device"},
                    last_step=False,
                )
            return await self.async_step_parameters()
        profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
        return self.async_show_form(
            step_id="sensors",
            data_schema=_sensor_schema(
                _sensor_form_values(self._draft, profile), profile, self.hass
            ),
            last_step=False,
        )

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _validate_thresholds(user_input, profile):
                errors["base"] = "invalid_thresholds"
            elif (
                "pending_unload" in profile.parameter_groups
                and self._draft.get(CONF_DOOR_ENTITY)
                and not _validate_pending(user_input)
            ):
                errors["base"] = "invalid_pending_settings"
            elif (
                "alarm_repeats" in profile.parameter_groups
                and not _validate_alarm_settings(user_input, profile)
            ):
                errors["base"] = "invalid_alarm_settings"
            elif not _validate_plug_off_alarm_settings(
                {**self._draft, **user_input}, profile
            ):
                errors["base"] = "invalid_plug_off_alarm_settings"
            else:
                self._draft.update(user_input)
                return await self.async_step_actions()
        return self.async_show_form(
            step_id="parameters",
            data_schema=_threshold_schema(self._draft, profile),
            errors=errors,
            last_step=False,
        )

    async def async_step_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            self._draft.update(user_input)
            profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
            if "pending_unload" not in profile.parameter_groups or not self._draft.get(
                CONF_DOOR_ENTITY
            ):
                _clear_pending_settings(self._draft)
            return self.async_create_entry(
                title=self._draft[CONF_NAME],
                data=_entry_data(self._draft),
                options=_entry_options(self._draft),
            )
        return self.async_show_form(
            step_id="actions",
            data_schema=_action_schema(
                self._draft, get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ApplianceCycleMonitorOptionsFlow()


class ApplianceCycleMonitorOptionsFlow(OptionsFlow):
    """Handle edits to an existing appliance using the same four steps."""

    def __init__(self) -> None:
        self._draft: dict[str, Any] = {}
        self._saved: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self._saved:
            self._saved = {**self.config_entry.data, **self.config_entry.options}
            self._saved.setdefault(CONF_NAME, self.config_entry.title)
        if user_input is not None:
            category, mode = _profile_identity(self._saved[CONF_APPLIANCE_TYPE])
            if (
                user_input.get(CONF_APPLIANCE_TYPE, category) != category
                or user_input.get("activity_mode", mode) != mode
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=_options_identity_schema(self._saved),
                    errors={"base": "appliance_type_immutable"},
                    last_step=False,
                )
            self._draft = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_APPLIANCE_TYPE: self._saved[CONF_APPLIANCE_TYPE],
            }
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="init",
            data_schema=_options_identity_schema(self._saved),
            last_step=False,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        if user_input is not None:
            profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
            self._draft.update(_normalize_sensor_values(user_input, profile))
            values = {**self._saved, **self._draft}
            if not _validate_sensor_values(values, profile):
                return self.async_show_form(
                    step_id="sensors",
                    data_schema=_sensor_schema(
                        _sensor_form_values(values, profile), profile, self.hass
                    ),
                    errors={"base": "mailbox_sensors_must_be_distinct"},
                    last_step=False,
                )
            if (
                "climate" in profile.detection_sources
                and not _validate_climate_entity(
                    self.hass,
                    values.get(CONF_CLIMATE_ENTITY),
                    self.config_entry.entry_id,
                )
            ):
                return self.async_show_form(
                    step_id="sensors",
                    data_schema=_sensor_schema(
                        _sensor_form_values(values, profile), profile, self.hass
                    ),
                    errors={"base": "climate_entity_requires_no_device"},
                    last_step=False,
                )
            return await self.async_step_parameters()
        profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
        return self.async_show_form(
            step_id="sensors",
            data_schema=_sensor_schema(
                _sensor_form_values(values, profile), profile, self.hass
            ),
            last_step=False,
        )

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _validate_thresholds(user_input, profile):
                errors["base"] = "invalid_thresholds"
            elif (
                "pending_unload" in profile.parameter_groups
                and values.get(CONF_DOOR_ENTITY)
                and not _validate_pending(user_input)
            ):
                errors["base"] = "invalid_pending_settings"
            elif (
                "alarm_repeats" in profile.parameter_groups
                and not _validate_alarm_settings(user_input, profile)
            ):
                errors["base"] = "invalid_alarm_settings"
            elif not _validate_plug_off_alarm_settings(
                {**values, **user_input}, profile
            ):
                errors["base"] = "invalid_plug_off_alarm_settings"
            else:
                self._draft.update(user_input)
                return await self.async_step_actions()
        return self.async_show_form(
            step_id="parameters",
            data_schema=_threshold_schema(values, profile),
            errors=errors,
            last_step=False,
        )

    async def async_step_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        if user_input is not None:
            self._draft.update(user_input)
            values = {**self._saved, **self._draft}
            profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
            if "pending_unload" not in profile.parameter_groups or not values.get(
                CONF_DOOR_ENTITY
            ):
                _clear_pending_settings(values)
                _clear_pending_settings(self._draft)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=_entry_data(values),
                title=values[CONF_NAME],
            )
            return self.async_create_entry(
                title="", data=_entry_options(values)
            )
        return self.async_show_form(
            step_id="actions",
            data_schema=_action_schema(
                values, get_appliance_profile(values[CONF_APPLIANCE_TYPE])
            ),
        )