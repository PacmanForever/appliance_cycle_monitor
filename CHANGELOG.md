# Changelog

## 0.3.0 - 2026-10-27

### Added

- Add profile-owned sensor inputs with profile-specific labels, descriptions, entity domains, and device-class filters.
- Add a smart-switch refrigerator profile with switch-based activity detection and a separate door sensor.
- Allow an optional controllable smart plug on the power-based refrigerator profile without replacing power-based detection.

### Changed

- Distinguish the capabilities of power-based and smart-switch refrigerators: the switch profile has no power, energy, or compressor-inactivity entities or alarm.
- Normalize profile-specific form fields to the existing canonical configuration keys to preserve stored configuration compatibility.
- Expand CRUD and runtime coverage for profile-specific selectors and smart-switch refrigerator behavior.

## 0.2.0 - 2026-10-27

### Added

- Add profile-specific configuration and entities for washers, dishwashers, dryers, air conditioners, and refrigerators.
- Detect air-conditioner activity from either power readings or a louver contact, and add independent refrigerator door and compressor alarms.
- Add mailbox profiles using an interior motion sensor or mail-slot flap contact, with arrival actions, pending-to-unload state, reminders, and main-door clearing.
- Add four-step profile-aware setup and options flows, with English, Spanish, and Catalan translations.
- Persist cycle, reminder, and alarm state and verify profile creation, editing, and deletion with unit and Home Assistant component tests.

### Compatibility

- Component tests passed with Home Assistant 2026.10.4.

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
