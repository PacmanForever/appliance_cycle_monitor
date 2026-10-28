"""Capabilities and detection sources for supported appliance types."""

from dataclasses import dataclass

from .const import (
    CONF_DOOR_ENTITY,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_PLUG_ENTITY,
    CONF_POWER_ENTITY,
    CONF_RUNNING_ENTITY,
)


@dataclass(frozen=True, slots=True)
class SensorInput:
    """Describe one profile-owned entity selector and its stored setting."""

    form_key: str
    config_key: str
    domain: str
    device_classes: tuple[str, ...] = ()
    required: bool = False
    detection_source: str | None = None


@dataclass(frozen=True, slots=True)
class ApplianceTypeProfile:
    """Describe the inputs and entities supported by an appliance type."""

    sensor_inputs: tuple[SensorInput, ...]
    parameter_groups: tuple[str, ...]
    action_groups: tuple[str, ...]
    output_entities: tuple[str, ...]
    supports_pending_unload: bool
    estimates_remaining: bool
    supports_max_runtime: bool = True

    @property
    def detection_sources(self) -> tuple[str, ...]:
        return tuple(
            item.detection_source
            for item in self.sensor_inputs
            if item.detection_source is not None
        )

    @property
    def supports_door_sensor(self) -> bool:
        return self.door_sensor_input is not None

    @property
    def door_sensor_input(self) -> SensorInput | None:
        return next(
            (item for item in self.sensor_inputs if item.config_key == CONF_DOOR_ENTITY),
            None,
        )

    @property
    def requires_door_sensor(self) -> bool:
        door_input = self.door_sensor_input
        return door_input is not None and door_input.required

    @property
    def supports_smart_plug(self) -> bool:
        return any(item.config_key == CONF_PLUG_ENTITY for item in self.sensor_inputs)


APPLIANCE_PROFILES = {
    "washer": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
            ),
            SensorInput(
                form_key="washer_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
            ),
            SensorInput(
                form_key="plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch"
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_pending_unload=True,
        estimates_remaining=True,
    ),
    "dishwasher": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
            ),
            SensorInput(
                form_key="dishwasher_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
            ),
            SensorInput(
                form_key="plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch"
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_pending_unload=True,
        estimates_remaining=True,
    ),
    "dryer": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
            ),
            SensorInput(
                form_key="dryer_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
            ),
            SensorInput(
                form_key="plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch"
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_pending_unload=True,
        estimates_remaining=True,
    ),
    "air_conditioner_contact": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="running_entity",
                config_key=CONF_RUNNING_ENTITY,
                domain="binary_sensor",
                device_classes=("opening",),
                required=True,
                detection_source="running_sensor",
            ),
            SensorInput(
                form_key="plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch"
            ),
        ),
        parameter_groups=("plug_off_alarm",),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("last_cycle_duration", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "air_conditioner_power": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
            ),
            SensorInput(
                form_key="plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch"
            ),
        ),
        parameter_groups=("power_cycle", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("power", "total_energy", "last_cycle_duration", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "refrigerator": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
            ),
            SensorInput(
                form_key="refrigerator_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
                required=True,
            ),
            SensorInput(
                form_key="plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch"
            ),
        ),
        parameter_groups=(
            "power_cycle",
            "door_alarm",
            "compressor_alarm",
            "alarm_repeats",
            "plug_off_alarm",
        ),
        action_groups=("door_open_alarm", "compressor_inactive_alarm", "plug_off_alarm"),
        output_entities=("power", "total_energy", "last_cycle_duration", "running", "door", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
        "refrigerator_switch": ApplianceTypeProfile(
            sensor_inputs=(
                SensorInput(
                    form_key="smart_plug_entity",
                    config_key=CONF_PLUG_ENTITY,
                    domain="switch",
                    required=True,
                    detection_source="smart_plug",
                ),
                SensorInput(
                    form_key="refrigerator_switch_door_entity",
                    config_key=CONF_DOOR_ENTITY,
                    domain="binary_sensor",
                    device_classes=("door",),
                    required=True,
                ),
            ),
            parameter_groups=("door_alarm", "alarm_repeats", "plug_off_alarm"),
            action_groups=("door_open_alarm", "plug_off_alarm"),
            output_entities=("last_cycle_duration", "running", "door", "plug"),
            supports_pending_unload=False,
            estimates_remaining=False,
            supports_max_runtime=False,
        ),
    "mailbox_motion": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="mail_motion_entity",
                config_key=CONF_MAIL_MOTION_ENTITY,
                domain="binary_sensor",
                device_classes=("motion",),
                required=True,
                detection_source="mail_motion",
            ),
            SensorInput(
                form_key="mailbox_motion_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door",),
                required=True,
            ),
        ),
        parameter_groups=("pending_unload",),
        action_groups=("mail_arrival", "pending_unload"),
        output_entities=("door", "pending_unload", "clear_pending"),
        supports_pending_unload=True,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "mailbox_slot": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="mail_slot_entity",
                config_key=CONF_MAIL_SLOT_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
                required=True,
                detection_source="mail_slot",
            ),
            SensorInput(
                form_key="mailbox_slot_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door",),
                required=True,
            ),
        ),
        parameter_groups=("pending_unload",),
        action_groups=("mail_arrival", "pending_unload"),
        output_entities=("door", "mail_slot", "pending_unload", "clear_pending"),
        supports_pending_unload=True,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
}

# Keep the selector alphabetized by its Catalan display labels.
APPLIANCE_TYPES = (
    "air_conditioner_contact",
    "air_conditioner_power",
    "dryer",
    "mailbox_slot",
    "mailbox_motion",
        "refrigerator_switch",
        "refrigerator",
        "washer",
        "dishwasher",
)


APPLIANCE_MODEL_NAMES = {
    "washer": "Washer",
    "dishwasher": "Dishwasher",
    "dryer": "Dryer",
    "air_conditioner_contact": "Air conditioner (louver contact)",
    "air_conditioner_power": "Air conditioner (power sensor)",
    "refrigerator": "Refrigerator (power sensor)",
    "refrigerator_switch": "Refrigerator (smart switch)",
    "mailbox_motion": "Mailbox (interior motion sensor)",
    "mailbox_slot": "Mailbox (mail-slot flap contact)",
}


def get_appliance_model(appliance_type: str | None) -> str | None:
    """Return the English device model name for an appliance profile."""
    if appliance_type is None:
        return None
    return APPLIANCE_MODEL_NAMES.get(appliance_type)


def get_appliance_profile(appliance_type: str) -> ApplianceTypeProfile:
    """Return the capability profile for an appliance type."""
    return APPLIANCE_PROFILES[appliance_type]