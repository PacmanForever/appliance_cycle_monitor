"""Manual state-clear button platform."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DOOR_ENTITY, DOMAIN
from .runtime import ApplianceRuntime


class ClearPendingButton(ButtonEntity):
    """Allow manually clearing pending-to-unload state."""

    _attr_has_entity_name = True
    _attr_translation_key = "clear_pending"

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_clear_pending"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=runtime.config.get("name", entry.title),
            model=(runtime.config.get("appliance_type") or "").replace(
                "_", " "
            ).title()
            or None,
        )

    async def async_press(self) -> None:
        """Clear the pending state and cancel its reminders."""
        self._runtime.clear_pending_unload()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the manual-clear button when a door sensor is configured."""
    runtime: ApplianceRuntime = entry.runtime_data
    if runtime.config.get(CONF_DOOR_ENTITY):
        async_add_entities([ClearPendingButton(runtime, entry)])