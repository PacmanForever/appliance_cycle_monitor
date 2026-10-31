"""Binary sensors for Home Activity Manager."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .appliance_types import SensorInput, get_appliance_model
from .const import CONF_DOOR_ENTITY, CONF_MAIL_SLOT_ENTITY, DOMAIN
from .runtime import ApplianceRuntime


_RUNNING_ICONS = {
    "washer": ("mdi:washing-machine", "mdi:washing-machine-off"),
    "dishwasher": ("mdi:dishwasher", "mdi:dishwasher-off"),
    "dryer": ("mdi:tumble-dryer", "mdi:tumble-dryer-off"),
    "air_conditioner_climate": ("mdi:hvac", "mdi:hvac-off"),
    "air_conditioner_contact": ("mdi:hvac", "mdi:hvac-off"),
    "air_conditioner_power": ("mdi:hvac", "mdi:hvac-off"),
    "refrigerator": ("mdi:fridge", "mdi:fridge-off"),
    "refrigerator_switch": ("mdi:fridge", "mdi:fridge-off"),
}

_DOOR_ICONS = {
    "washer": ("mdi:washing-machine-alert", "mdi:washing-machine", "mdi:washing-machine"),
    "dishwasher": ("mdi:dishwasher-alert", "mdi:dishwasher", "mdi:dishwasher"),
    "dryer": ("mdi:tumble-dryer-alert", "mdi:tumble-dryer", "mdi:tumble-dryer"),
    "refrigerator": ("mdi:fridge-alert", "mdi:fridge", "mdi:fridge-alert-outline"),
    "refrigerator_switch": ("mdi:fridge-alert", "mdi:fridge", "mdi:fridge-alert-outline"),
    "mailbox_motion": ("mdi:mailbox-open", "mdi:mailbox", "mdi:mailbox-outline"),
    "mailbox_slot": ("mdi:mailbox-open", "mdi:mailbox", "mdi:mailbox-outline"),
}


class ApplianceBinarySensor(BinarySensorEntity):
    """A binary sensor backed by one runtime value."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        key: str,
        value_fn: Callable[[], bool | None],
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        self._runtime = runtime
        self._key = key
        self._value_fn = value_fn
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=runtime.config.get("name", entry.title),
            model=get_appliance_model(runtime.config.get("appliance_type")),
        )

    @property
    def is_on(self) -> bool | None:
        """Return the current runtime state."""
        return self._value_fn()

    @property
    def available(self) -> bool:
        """Reflect availability of the source for input-backed entities."""
        source_key = {"door": CONF_DOOR_ENTITY, "mail_slot": CONF_MAIL_SLOT_ENTITY}.get(
            self._key
        )
        if source_key is not None:
            state = self.hass.states.get(self._runtime.config.get(source_key))
            return state is not None and state.state != "unavailable"
        source_input = next(
            (
                item
                for item in self._runtime.profile.sensor_inputs
                if item.detection_source == "running_sensor"
            ),
            None,
        )
        if self._key == "running" and source_input is not None:
            state = self.hass.states.get(
                self._runtime.config.get(source_input.config_key)
            )
            return state is not None and state.state in ("on", "off")
        return super().available

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Identify the configured input represented by this output."""
        source_key = None
        if self._key == "running":
            source_input = next(
                (
                    item
                    for item in self._runtime.profile.sensor_inputs
                    if item.detection_source is not None
                ),
                None,
            )
            source_key = source_input.config_key if source_input is not None else None
        elif self._key == "door":
            source_key = CONF_DOOR_ENTITY
        elif self._key == "mail_slot":
            source_key = CONF_MAIL_SLOT_ENTITY
        source_entity = self._runtime.config.get(source_key) if source_key else None
        return {"source_entity": source_entity} if source_entity else None

    @property
    def icon(self) -> str:
        """Return an icon that identifies the entity and its current state."""
        appliance_type = self._runtime.config.get("appliance_type")
        if self._key == "running":
            icons = _RUNNING_ICONS.get(appliance_type)
            if icons is None:
                return "mdi:power-cycle"
            return icons[1] if self.is_on is False else icons[0]
        if self._key == "door":
            icons = _DOOR_ICONS.get(appliance_type)
            if icons is not None:
                if self.is_on is None:
                    return icons[2]
                return icons[0] if self.is_on else icons[1]
            if self.is_on is None:
                return "mdi:door"
            return "mdi:door-open" if self.is_on else "mdi:door-closed"
        if self._key == "mail_slot":
            if self.is_on is None:
                return "mdi:mailbox-outline"
            return "mdi:mailbox-open-up" if self.is_on else "mdi:mailbox-up"
        if self._key == "pending_unload":
            if appliance_type in ("mailbox_motion", "mailbox_slot"):
                return "mdi:email-alert" if self.is_on else "mdi:email-outline"
            return "mdi:bell-alert" if self.is_on else "mdi:bell-outline"
        return "mdi:checkbox-marked-circle-outline"

    async def async_added_to_hass(self) -> None:
        """Subscribe to changes from the shared runtime."""
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self._handle_runtime_update))

    @callback
    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()


class ApplianceInputBinarySensor(BinarySensorEntity):
    """Expose a configured binary input that has no equivalent output."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        input_config: SensorInput,
    ) -> None:
        self._runtime = runtime
        self._source_entity_id = runtime.config[input_config.config_key]
        input_name = input_config.config_key.removesuffix("_entity")
        self._input_name = input_name
        self._attr_unique_id = f"{entry.entry_id}_input_{input_name}"
        self._attr_translation_key = f"input_{input_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=runtime.config.get("name", entry.title),
            model=get_appliance_model(runtime.config.get("appliance_type")),
        )
        if input_config.device_classes:
            self._attr_device_class = BinarySensorDeviceClass(
                input_config.device_classes[0]
            )

    @property
    def is_on(self) -> bool | None:
        """Return the source's raw binary state."""
        state = self.hass.states.get(self._source_entity_id)
        if state is None or state.state not in ("on", "off"):
            return None
        return state.state == "on"

    @property
    def available(self) -> bool:
        """Return whether the source is available."""
        state = self.hass.states.get(self._source_entity_id)
        return state is not None and state.state != "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"source_entity": self._source_entity_id}

    @property
    def icon(self) -> str | None:
        """Show a state-specific icon for contact and opening inputs."""
        if self._input_name == "running":
            return "mdi:door-sliding-open" if self.is_on else "mdi:door-sliding"
        if self._input_name == "door":
            if self.is_on is None:
                return "mdi:door"
            return "mdi:door-open" if self.is_on else "mdi:door-closed"
        if self._input_name == "mail_slot":
            if self.is_on is None:
                return "mdi:mailbox-outline"
            return "mdi:mailbox-open-up" if self.is_on else "mdi:mailbox-up"
        return super().icon

    async def async_added_to_hass(self) -> None:
        """Subscribe to source updates through the appliance runtime."""
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self._handle_runtime_update))

    @callback
    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up appliance binary sensors."""
    runtime: ApplianceRuntime = entry.runtime_data
    entities = []
    if "running" in runtime.profile.output_entities:
        entities.append(ApplianceBinarySensor(
            runtime,
            entry,
            "running",
            lambda: runtime.detector.is_running,
            BinarySensorDeviceClass.RUNNING,
        ))
    if (
        "door" in runtime.profile.output_entities
        and runtime.config.get(CONF_DOOR_ENTITY)
    ):
        entities.append(
            ApplianceBinarySensor(
                runtime,
                entry,
                "door",
                lambda: runtime.door_open,
                BinarySensorDeviceClass.DOOR,
            )
        )
    if (
        "pending_unload" in runtime.profile.output_entities
        and runtime.config.get(CONF_DOOR_ENTITY)
    ):
        entities.append(
            ApplianceBinarySensor(
                runtime,
                entry,
                "pending_unload",
                lambda: runtime.pending_unload,
            )
        )
    if (
        "mail_slot" in runtime.profile.output_entities
        and runtime.config.get(CONF_MAIL_SLOT_ENTITY)
    ):
        entities.append(
            ApplianceBinarySensor(
                runtime,
                entry,
                "mail_slot",
                lambda: runtime.mail_slot_open,
                BinarySensorDeviceClass.DOOR,
            )
        )
    input_wrappers = tuple(
        input_config
        for input_config in runtime.profile.inputs_requiring_wrapper
        if input_config.domain == "binary_sensor"
        and runtime.config.get(input_config.config_key)
    )
    registry = er.async_get(hass)
    expected_unique_ids = {
        f"{entry.entry_id}_input_{input_config.config_key.removesuffix('_entity')}"
        for input_config in input_wrappers
    }
    input_prefix = f"{entry.entry_id}_input_"
    for registered_entity in tuple(registry.entities.values()):
        if (
            registered_entity.config_entry_id == entry.entry_id
            and registered_entity.unique_id.startswith(input_prefix)
            and registered_entity.unique_id not in expected_unique_ids
        ):
            registry.async_remove(registered_entity.entity_id)

    entities.extend(
        ApplianceInputBinarySensor(runtime, entry, input_config)
        for input_config in input_wrappers
    )
    async_add_entities(entities)
