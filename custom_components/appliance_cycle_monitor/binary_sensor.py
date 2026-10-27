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

from .const import CONF_DOOR_ENTITY, DOMAIN
from .runtime import ApplianceRuntime


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
        self._value_fn = value_fn
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=runtime.config.get("name", entry.title),
            model=(runtime.config.get("appliance_type") or "").replace(
                "_", " "
            ).title()
            or None,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the current runtime state."""
        return self._value_fn()

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
    entities = [
        ApplianceBinarySensor(
            runtime,
            entry,
            "running",
            lambda: runtime.detector.is_running,
            BinarySensorDeviceClass.RUNNING,
        )
    ]
    if runtime.config.get(CONF_DOOR_ENTITY):
        entities.extend(
            [
                ApplianceBinarySensor(
                    runtime,
                    entry,
                    "door",
                    lambda: runtime.door_open,
                    BinarySensorDeviceClass.DOOR,
                ),
                ApplianceBinarySensor(
                    runtime,
                    entry,
                    "pending_unload",
                    lambda: runtime.pending_unload,
                ),
            ]
        )
    async_add_entities(entities)