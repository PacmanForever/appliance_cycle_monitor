"""Binary sensors for Appliance Cycle Monitor."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .appliance_types import get_appliance_model
from .const import CONF_DOOR_ENTITY, CONF_MAIL_SLOT_ENTITY, DOMAIN
from .runtime import ApplianceRuntime


_RUNNING_ICONS = {
    "washer": ("mdi:washing-machine", "mdi:washing-machine-off"),
    "dishwasher": ("mdi:dishwasher", "mdi:dishwasher-off"),
    "dryer": ("mdi:tumble-dryer", "mdi:tumble-dryer-off"),
    "air_conditioner_contact": ("mdi:air-conditioner", "mdi:air-conditioner"),
    "air_conditioner_power": ("mdi:air-conditioner", "mdi:air-conditioner"),
    "refrigerator": ("mdi:fridge", "mdi:fridge-off"),
    "refrigerator_switch": ("mdi:fridge", "mdi:fridge-off"),
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
    def icon(self) -> str:
        """Return an icon that identifies the entity and its current state."""
        appliance_type = self._runtime.config.get("appliance_type")
        if self._key == "running":
            icons = _RUNNING_ICONS.get(appliance_type)
            if icons is None:
                return "mdi:power-cycle"
            return icons[1] if self.is_on is False else icons[0]
        if self._key == "door":
            if appliance_type in ("refrigerator", "refrigerator_switch"):
                if self.is_on is None:
                    return "mdi:fridge-alert-outline"
                return "mdi:fridge-alert" if self.is_on else "mdi:fridge"
            if appliance_type in ("mailbox_motion", "mailbox_slot"):
                if self.is_on is None:
                    return "mdi:mailbox-outline"
                return "mdi:mailbox-open" if self.is_on else "mdi:mailbox"
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
    async_add_entities(entities)