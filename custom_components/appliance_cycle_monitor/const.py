"""Constants for Appliance Cycle Monitor."""

DOMAIN = "appliance_cycle_monitor"

CONF_APPLIANCE_TYPE = "appliance_type"
CONF_POWER_ENTITY = "power_entity"
CONF_DOOR_ENTITY = "door_entity"
CONF_PLUG_ENTITY = "plug_entity"
CONF_START_POWER_W = "start_power_w"
CONF_START_DURATION_SECONDS = "start_duration_seconds"
CONF_FINISH_POWER_W = "finish_power_w"
CONF_FINISH_DURATION_SECONDS = "finish_duration_seconds"
CONF_MAX_RUNTIME_SECONDS = "max_runtime_seconds"
CONF_START_ACTIONS = "start_actions"
CONF_FINISH_ACTIONS = "finish_actions"
CONF_MAX_RUNTIME_ACTIONS = "max_runtime_actions"
CONF_PENDING_ACTIONS = "pending_actions"
CONF_PENDING_DELAY_SECONDS = "pending_delay_seconds"
CONF_PENDING_INTERVAL_SECONDS = "pending_interval_seconds"
CONF_PENDING_REPEATS = "pending_repeats"

DEFAULT_START_POWER_W = 4.0
DEFAULT_START_DURATION_SECONDS = 15
DEFAULT_FINISH_POWER_W = 1.0
DEFAULT_FINISH_DURATION_SECONDS = 60
DEFAULT_PENDING_DELAY_SECONDS = 900
DEFAULT_PENDING_INTERVAL_SECONDS = 900
DEFAULT_PENDING_REPEATS = 3

APPLIANCE_TYPES = ("washer", "dishwasher", "dryer")