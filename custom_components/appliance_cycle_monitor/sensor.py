"""Sensors for Appliance Cycle Monitor."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .appliance_types import get_appliance_model
from .const import DOMAIN
from .runtime import ApplianceRuntime


class ApplianceSensor(SensorEntity):
    """A sensor backed by one runtime value."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        key: str,
        value_fn: Callable[[], Any],
        unit: str,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass,
    ) -> None:
        self._runtime = runtime
        self._key = key
        self._value_fn = value_fn
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_icon = {
            "power": "mdi:flash",
            "total_energy": "mdi:lightning-bolt",
            "last_cycle_duration": "mdi:timer-check-outline",
            "estimated_remaining": "mdi:timer-sand",
        }[key]
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=runtime.config.get("name", entry.title),
            model=get_appliance_model(runtime.config.get("appliance_type")),
        )

    @property
    def native_value(self) -> Any:
        """Return the latest value from the appliance runtime."""
        return self._value_fn()

    @property
    def available(self) -> bool:
        """Keep a power value available after at least one valid reading."""
        return self._key != "power" or self._runtime.display_power_w is not None

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
    """Set up appliance sensors."""
    runtime: ApplianceRuntime = entry.runtime_data
    sensors = {
        "power": ApplianceSensor(
            runtime,
            entry,
            "power",
            lambda: runtime.display_power_w,
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        "total_energy": ApplianceSensor(
            runtime,
            entry,
            "total_energy",
            lambda: runtime.energy_kwh,
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        "last_cycle_duration": ApplianceSensor(
            runtime,
            entry,
            "last_cycle_duration",
            lambda: (
                runtime.detector.last_cycle_duration.total_seconds()
                if runtime.detector.last_cycle_duration is not None
                else None
            ),
            UnitOfTime.SECONDS,
            SensorDeviceClass.DURATION,
            SensorStateClass.MEASUREMENT,
        ),
        "estimated_remaining": ApplianceSensor(
            runtime,
            entry,
            "estimated_remaining",
            lambda: runtime.remaining_seconds,
            UnitOfTime.SECONDS,
            SensorDeviceClass.DURATION,
            SensorStateClass.MEASUREMENT,
        ),
    }
    async_add_entities(
        [sensor for key, sensor in sensors.items() if key in runtime.profile.output_entities]
    )