"""Capabilities and detection sources for supported appliance types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplianceTypeProfile:
    """Describe the inputs and entities supported by an appliance type."""

    detection_sources: tuple[str, ...]
    parameter_groups: tuple[str, ...]
    action_groups: tuple[str, ...]
    output_entities: tuple[str, ...]
    supports_door_sensor: bool
    requires_door_sensor: bool
    supports_pending_unload: bool
    supports_smart_plug: bool
    estimates_remaining: bool
    supports_max_runtime: bool = True


APPLIANCE_PROFILES = {
    "washer": ApplianceTypeProfile(
        detection_sources=("power",),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_door_sensor=True,
        requires_door_sensor=False,
        supports_pending_unload=True,
        supports_smart_plug=True,
        estimates_remaining=True,
    ),
    "dishwasher": ApplianceTypeProfile(
        detection_sources=("power",),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_door_sensor=True,
        requires_door_sensor=False,
        supports_pending_unload=True,
        supports_smart_plug=True,
        estimates_remaining=True,
    ),
    "dryer": ApplianceTypeProfile(
        detection_sources=("power",),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_door_sensor=True,
        requires_door_sensor=False,
        supports_pending_unload=True,
        supports_smart_plug=True,
        estimates_remaining=True,
    ),
    "air_conditioner_contact": ApplianceTypeProfile(
        detection_sources=("running_sensor",),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("last_cycle_duration", "running", "plug"),
        supports_door_sensor=False,
        requires_door_sensor=False,
        supports_pending_unload=False,
        supports_smart_plug=True,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "air_conditioner_power": ApplianceTypeProfile(
        detection_sources=("power",),
        parameter_groups=("power_cycle",),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("power", "total_energy", "last_cycle_duration", "running", "plug"),
        supports_door_sensor=False,
        requires_door_sensor=False,
        supports_pending_unload=False,
        supports_smart_plug=True,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "refrigerator": ApplianceTypeProfile(
        detection_sources=("power",),
        parameter_groups=(
            "power_cycle",
            "door_alarm",
            "compressor_alarm",
            "alarm_repeats",
        ),
        action_groups=("door_open_alarm", "compressor_inactive_alarm"),
        output_entities=("power", "total_energy", "last_cycle_duration", "running", "door", "plug"),
        supports_door_sensor=True,
        requires_door_sensor=True,
        supports_pending_unload=False,
        supports_smart_plug=True,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "mailbox_motion": ApplianceTypeProfile(
        detection_sources=("mail_motion",),
        parameter_groups=("pending_unload",),
        action_groups=("mail_arrival", "pending_unload"),
        output_entities=("door", "pending_unload", "clear_pending"),
        supports_door_sensor=True,
        requires_door_sensor=True,
        supports_pending_unload=True,
        supports_smart_plug=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "mailbox_slot": ApplianceTypeProfile(
        detection_sources=("mail_slot",),
        parameter_groups=("pending_unload",),
        action_groups=("mail_arrival", "pending_unload"),
        output_entities=("door", "pending_unload", "clear_pending"),
        supports_door_sensor=True,
        requires_door_sensor=True,
        supports_pending_unload=True,
        supports_smart_plug=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
}

APPLIANCE_TYPES = tuple(APPLIANCE_PROFILES)


def get_appliance_profile(appliance_type: str) -> ApplianceTypeProfile:
    """Return the capability profile for an appliance type."""
    return APPLIANCE_PROFILES[appliance_type]