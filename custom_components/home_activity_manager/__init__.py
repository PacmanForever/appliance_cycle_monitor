"""Home Activity Manager integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.storage import Store

from .const import CONF_CLIMATE_ENTITY, DOMAIN
from .runtime import ApplianceRuntime

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
	Platform.SENSOR,
	Platform.BINARY_SENSOR,
	Platform.SWITCH,
	Platform.BUTTON,
]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	await hass.config_entries.async_reload(entry.entry_id)


def _async_appliance_device_id(
	hass: HomeAssistant, entry: ConfigEntry | str
) -> str | None:
	entry_id = entry.entry_id if isinstance(entry, ConfigEntry) else entry
	registry = dr.async_get(hass)
	get_by_identifier = getattr(registry, "async_get_device_by_identifier", None)
	device = (
		get_by_identifier((DOMAIN, entry_id), entry_id)
		if get_by_identifier is not None
		else registry.async_get_device(identifiers={(DOMAIN, entry_id)})
	)
	return device.id if device is not None else None


def _async_assign_climate_entity(
	hass: HomeAssistant, entry: ConfigEntry, climate_entity_id: str | None
) -> None:
	if climate_entity_id is None:
		return

	entity_registry = er.async_get(hass)
	entity_entry = entity_registry.async_get(climate_entity_id)
	device_id = _async_appliance_device_id(hass, entry)
	if entity_entry is None or device_id is None:
		return
	if entity_entry.device_id is None:
		entity_registry.async_update_entity(climate_entity_id, device_id=device_id)
	elif entity_entry.device_id != device_id:
		_LOGGER.warning(
			"Climate input %s has been assigned to a different device; leaving it unchanged",
			climate_entity_id,
		)


def _async_release_climate_entity(
	hass: HomeAssistant, entry: ConfigEntry, climate_entity_id: str | None
) -> None:
	if climate_entity_id is None:
		return

	device_id = _async_appliance_device_id(hass, entry)
	entity_registry = er.async_get(hass)
	entity_entry = entity_registry.async_get(climate_entity_id)
	if (
		device_id is not None
		and entity_entry is not None
		and entity_entry.device_id == device_id
	):
		entity_registry.async_update_entity(climate_entity_id, device_id=None)


def _async_climate_entity_registry_listener(
	hass: HomeAssistant, entry: ConfigEntry
):
	@callback
	def _handle_registry_update(event: Event) -> None:
		climate_entity_id = {**entry.data, **entry.options}.get(CONF_CLIMATE_ENTITY)
		if (
			event.data.get("action") != "update"
			or event.data.get("entity_id") != climate_entity_id
		):
			return
		if "device_id" not in event.data.get("changes", {}):
			return
		entity_registry = er.async_get(hass)
		entity_entry = entity_registry.async_get(climate_entity_id)
		if entity_entry is not None and entity_entry.device_id is None:
			_async_assign_climate_entity(hass, entry, climate_entity_id)

	return _handle_registry_update


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Set up one configured appliance."""
	config = {**entry.data, **entry.options}
	runtime = ApplianceRuntime(hass, entry, config)
	await runtime.async_setup()
	entry.runtime_data = runtime
	entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
	await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
	climate_entity_id = config.get(CONF_CLIMATE_ENTITY)
	if climate_entity_id is not None:
		entry.runtime_data._unsubscribe_entity_registry = hass.bus.async_listen(
			EVENT_ENTITY_REGISTRY_UPDATED,
			_async_climate_entity_registry_listener(hass, entry),
		)
		_async_assign_climate_entity(hass, entry, climate_entity_id)
	return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Unload one configured appliance."""
	if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
		return False
	runtime = entry.runtime_data
	if runtime._unsubscribe_entity_registry is not None:
		runtime._unsubscribe_entity_registry()
		runtime._unsubscribe_entity_registry = None
	_async_release_climate_entity(
		hass, entry, runtime.config.get(CONF_CLIMATE_ENTITY)
	)
	await runtime.async_unload()
	return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	"""Remove this appliance's integration-owned persistent state."""
	_async_release_climate_entity(
		hass, entry, {**entry.data, **entry.options}.get(CONF_CLIMATE_ENTITY)
	)
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