# Changelog

## 0.1.0 - 2026-10-27

First public release of Appliance Cycle Monitor.

### Added

- Detect washer, dishwasher, and dryer cycles from power sensor readings.
- Configure per-appliance start, finish, maximum-runtime, and pending-unload actions.
- Track lifetime energy, last-cycle duration, estimated remaining time, and running state.
- Optionally monitor a door and smart plug, with pending-unload reminders and a clear-state button.
- Restore cycle and reminder state across Home Assistant restarts.

### Compatibility

- Component tests passed with Home Assistant 2026.10.4.
