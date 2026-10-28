"""Smart plug switch platform for Appliance Cycle Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .appliance_types import get_appliance_model
from .const import CONF_PLUG_ENTITY, DOMAIN
from .runtime import ApplianceRuntime


class AppliancePlugSwitch(SwitchEntity):
    """Expose control of the selected external smart plug."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "plug"

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._runtime = runtime
        self._entity_id = runtime.config[CONF_PLUG_ENTITY]
        self._attr_unique_id = f"{entry.entry_id}_plug"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=runtime.config.get("name", entry.title),
            model=get_appliance_model(runtime.config.get("appliance_type")),
        )

    @property
    def is_on(self) -> bool:
        """Return the selected plug's current state."""
        state = self.hass.states.get(self._entity_id)
        return state is not None and state.state == "on"

    @property
    def icon(self) -> str:
        """Reflect whether the selected smart plug is on or off."""
        if not self.available:
            return "mdi:power-plug-off-outline"
        return "mdi:power-plug" if self.is_on else "mdi:power-plug-off"

    @property
    def available(self) -> bool:
        """Return whether the selected plug is available."""
        state = self.hass.states.get(self._entity_id)
        return state is not None and state.state in ("on", "off")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the selected external plug."""
        await self.hass.services.async_call(
            "switch", "turn_on", {"entity_id": self._entity_id}, blocking=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the selected external plug."""
        await self.hass.services.async_call(
            "switch", "turn_off", {"entity_id": self._entity_id}, blocking=True
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime state changes."""
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
    """Set up the selected smart plug, if configured."""
    runtime: ApplianceRuntime = entry.runtime_data
    if (
        "plug" in runtime.profile.output_entities
        and runtime.config.get(CONF_PLUG_ENTITY)
    ):
        async_add_entities([AppliancePlugSwitch(runtime, entry)])