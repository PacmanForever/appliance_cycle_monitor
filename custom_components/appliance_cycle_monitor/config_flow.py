"""Configuration flows for Appliance Cycle Monitor."""

from __future__ import annotations

import math
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.helpers import selector

from .const import (
    APPLIANCE_TYPES,
    CONF_APPLIANCE_TYPE,
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

CONF_NAME = "name"
_ENTRY_DATA_KEYS = {
    CONF_NAME,
    CONF_APPLIANCE_TYPE,
    CONF_POWER_ENTITY,
    CONF_DOOR_ENTITY,
    CONF_PLUG_ENTITY,
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


def _number_selector(unit: str, step: float = 0.1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX,
            step=step,
            unit_of_measurement=unit,
        )
    )


def _entity_schema(values: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {
        _required(CONF_NAME, values): selector.TextSelector(),
        _required(CONF_APPLIANCE_TYPE, values): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(APPLIANCE_TYPES),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_APPLIANCE_TYPE,
            )
        ),
        _required(CONF_POWER_ENTITY, values): selector.EntitySelector(
            selector.EntitySelectorConfig(
                filter=[{"domain": "sensor", "device_class": "power"}]
            )
        ),
    }
    schema[_optional(CONF_DOOR_ENTITY, values)] = _OptionalEntitySelector(
        selector.EntitySelectorConfig(domain="binary_sensor")
    )
    schema[_optional(CONF_PLUG_ENTITY, values)] = _OptionalEntitySelector(
        selector.EntitySelectorConfig(domain="switch")
    )
    return vol.Schema(schema)


def _threshold_schema(values: dict[str, Any]) -> vol.Schema:
    start_power = values.get(CONF_START_POWER_W, DEFAULT_START_POWER_W)
    start_duration = values.get(
        CONF_START_DURATION_SECONDS, DEFAULT_START_DURATION_SECONDS
    )
    finish_power = values.get(CONF_FINISH_POWER_W, DEFAULT_FINISH_POWER_W)
    finish_duration = values.get(
        CONF_FINISH_DURATION_SECONDS, DEFAULT_FINISH_DURATION_SECONDS
    )
    schema: dict[Any, Any] = {
        vol.Required(CONF_START_POWER_W, default=start_power): _number_selector("W"),
        vol.Required(CONF_START_DURATION_SECONDS, default=start_duration): (
            _number_selector("s", step=1)
        ),
        vol.Required(CONF_FINISH_POWER_W, default=finish_power): _number_selector("W"),
        vol.Required(CONF_FINISH_DURATION_SECONDS, default=finish_duration): (
            _number_selector("s", step=1)
        ),
        _optional(CONF_MAX_RUNTIME_SECONDS, values): _number_selector("s", step=1),
    }
    return vol.Schema(schema)


def _action_schema(values: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Optional(CONF_START_ACTIONS, default=values.get(CONF_START_ACTIONS, [])):
            selector.ActionSelector(),
        vol.Optional(CONF_FINISH_ACTIONS, default=values.get(CONF_FINISH_ACTIONS, [])):
            selector.ActionSelector(),
        vol.Optional(
            CONF_MAX_RUNTIME_ACTIONS,
            default=values.get(CONF_MAX_RUNTIME_ACTIONS, []),
        ): selector.ActionSelector(),
    }
    if values.get(CONF_DOOR_ENTITY):
        schema.update(
            {
                vol.Optional(
                    CONF_PENDING_ACTIONS,
                    default=values.get(CONF_PENDING_ACTIONS, []),
                ): selector.ActionSelector(),
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
    return vol.Schema(schema)


def _validate_thresholds(values: dict[str, Any]) -> bool:
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


def _clear_pending_settings(values: dict[str, Any]) -> None:
    values[CONF_PENDING_ACTIONS] = []
    values[CONF_PENDING_DELAY_SECONDS] = DEFAULT_PENDING_DELAY_SECONDS
    values[CONF_PENDING_INTERVAL_SECONDS] = DEFAULT_PENDING_INTERVAL_SECONDS
    values[CONF_PENDING_REPEATS] = DEFAULT_PENDING_REPEATS


def _entry_data(values: dict[str, Any]) -> dict[str, Any]:
    return {key: values[key] for key in _ENTRY_DATA_KEYS if key in values}


def _entry_options(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key not in _ENTRY_DATA_KEYS}


class ApplianceCycleMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup of one appliance."""

    VERSION = 2

    def __init__(self) -> None:
        self._draft: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            self._draft = dict(user_input)
            self._draft.setdefault(CONF_DOOR_ENTITY, None)
            self._draft.setdefault(CONF_PLUG_ENTITY, None)
            return await self.async_step_thresholds()
        return self.async_show_form(
            step_id="user", data_schema=_entity_schema({}), last_step=False
        )

    async def async_step_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _validate_thresholds(user_input):
                errors["base"] = "invalid_thresholds"
            else:
                self._draft.update(user_input)
                return await self.async_step_actions()
        return self.async_show_form(
            step_id="thresholds",
            data_schema=_threshold_schema(self._draft),
            errors=errors,
            last_step=False,
        )

    async def async_step_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._draft.update(user_input)
            if self._draft.get(CONF_DOOR_ENTITY) and not _validate_pending(
                self._draft
            ):
                errors["base"] = "invalid_pending_settings"
            else:
                if not self._draft.get(CONF_DOOR_ENTITY):
                    _clear_pending_settings(self._draft)
                return self.async_create_entry(
                    title=self._draft[CONF_NAME],
                    data=_entry_data(self._draft),
                    options=_entry_options(self._draft),
                )
        return self.async_show_form(
            step_id="actions",
            data_schema=_action_schema(self._draft),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ApplianceCycleMonitorOptionsFlow()


class ApplianceCycleMonitorOptionsFlow(OptionsFlow):
    """Handle edits to an existing appliance using the same three steps."""

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
            self._draft = dict(user_input)
            self._draft.setdefault(CONF_DOOR_ENTITY, None)
            self._draft.setdefault(CONF_PLUG_ENTITY, None)
            return await self.async_step_thresholds()
        return self.async_show_form(
            step_id="init", data_schema=_entity_schema(self._saved), last_step=False
        )

    async def async_step_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _validate_thresholds(user_input):
                errors["base"] = "invalid_thresholds"
            else:
                self._draft.update(user_input)
                return await self.async_step_actions()
        return self.async_show_form(
            step_id="thresholds",
            data_schema=_threshold_schema(values),
            errors=errors,
            last_step=False,
        )

    async def async_step_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        errors: dict[str, str] = {}
        if user_input is not None:
            self._draft.update(user_input)
            values = {**self._saved, **self._draft}
            if values.get(CONF_DOOR_ENTITY) and not _validate_pending(values):
                errors["base"] = "invalid_pending_settings"
            else:
                if not values.get(CONF_DOOR_ENTITY):
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
            data_schema=_action_schema(values),
            errors=errors,
        )