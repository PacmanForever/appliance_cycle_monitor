"""Appliance Cycle Monitor integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .runtime import ApplianceRuntime

PLATFORMS = [
	Platform.SENSOR,
	Platform.BINARY_SENSOR,
	Platform.SWITCH,
	Platform.BUTTON,
]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Set up one configured appliance."""
	config = {**entry.data, **entry.options}
	runtime = ApplianceRuntime(hass, entry, config)
	await runtime.async_setup()
	entry.runtime_data = runtime
	entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
	await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
	return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Unload one configured appliance."""
	if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
		return False
	await entry.runtime_data.async_unload()
	return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	"""Remove this appliance's integration-owned persistent state."""
	store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
	await store.async_remove()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Convert duration options saved in minutes to seconds."""
	if entry.version > 2:
		return False
	if entry.version == 1:
		options = dict(entry.options)
		for old_key, new_key in (
			("start_duration_minutes", "start_duration_seconds"),
			("finish_duration_minutes", "finish_duration_seconds"),
			("max_runtime_minutes", "max_runtime_seconds"),
		):
			if old_key in options:
				value = options.pop(old_key)
				if value not in (None, ""):
					options[new_key] = float(value) * 60
		hass.config_entries.async_update_entry(entry, options=options, version=2)
	return True