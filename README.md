# Home Activity Manager

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPacmanForever%2Fhome_activity_manager%2Fmain%2Fcustom_components%2Fhome_activity_manager%2Fmanifest.json&query=%24.version&prefix=v&label=version)](https://github.com/PacmanForever/home_activity_manager/releases)
[![Unit Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml/badge.svg?branch=main&job=unit)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml)
[![Component Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml/badge.svg?branch=main&job=component)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml)
[![HACS Validation Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hacs.yml/badge.svg?branch=main)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hacs.yml)
[![HA Validation Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hassfest.yml/badge.svg?branch=main)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hassfest.yml)
[![License](https://img.shields.io/github/license/PacmanForever/home_activity_manager?label=GPLv3)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-%3E%3D95%25-brightgreen)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml)
[![Home Assistant](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPacmanForever%2Fhome_activity_manager%2Fmain%2Fdocs%2Fhome_assistant_compatibility.json&query=%24.tested_version&suffix=%20tested&label=home%20assistant&color=blue)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/daily-ha.yml)
[![Daily HA compatibility](https://github.com/PacmanForever/home_activity_manager/actions/workflows/daily-ha.yml/badge.svg?branch=main)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/daily-ha.yml)

Home Activity Manager brings compatible Home Assistant entities together under a dedicated device, making it easier to monitor household equipment and manage its activity, actions, reminders, and alarms. It is especially useful for non-smart devices monitored with existing sensors. Its extensible profiles currently cover washers, dishwashers, dryers, air conditioners, refrigerators, and mailboxes, with room for additional device types. It needs no cloud service, credentials, external helpers, or automations.

## Features

- **Washer**
	- Detect cycles from power thresholds and configurable confirmation times.
	- Optionally monitor the door and control a smart plug; track pending unloading and reminders.
- **Dishwasher**
	- Detect cycles from power thresholds and configurable confirmation times.
	- Optionally monitor the door and control a smart plug; track pending unloading and reminders.
- **Dryer**
	- Detect cycles from power thresholds and configurable confirmation times.
	- Optionally monitor the door and control a smart plug; track pending unloading and reminders.
- **Air conditioner**
	- **Climate-entity option:** use an existing climate entity with no parent device as the activity source. The original entity and controls are assigned directly to the managed device; no wrapper is created. Activity follows the climate mode (`off` versus any active mode), including periods when `hvac_action` is idle. Replacing the entity or removing the managed device returns it to no device if it is still assigned to this device.
	- **Contact/opening-sensor option:** detect activity from a binary contact/opening sensor.
	- **Power option:** detect activity from power readings and configurable thresholds.
	- The contact/opening sensor is required in contact mode and is not offered in climate or power mode. Other auxiliary sensors and smart-plug controls are available according to each mode. Only the selected activity source determines running state.
- **Refrigerator**
	- **Power option:** requires a power sensor and door contact. Cycle-start/end actions follow compressor activity; the door-open alarm is configurable. A controllable smart plug is optional and does not trigger an off alarm.
	- **Smart-switch option:** requires a smart switch and separate door contact. Cycle-start/end actions follow the switch state; optional power and energy sensors do not change activity. The door-open alarm is configurable; the switch does not trigger an off alarm.
- **Mailbox**
	- **Interior-motion option:** detect incoming mail with a motion sensor inside the mailbox.
	- **Mail-slot option:** detect incoming mail with a contact on the letter flap and expose its open/closed state as **Mail slot**.
	- Both options track the mailbox cycle from detected arrival until collection. Cycle-start actions run on arrival; cycle-end actions run when the main door opens or pending collection is cleared. Reminders remain separate, and both options use a separate main-door contact.
- **Across all profiles**
	- Configure consistent actions when a cycle starts and ends, plus any profile-specific reminders or alarms; restore cycle, reminder, and alarm state after Home Assistant restarts.
	- On washer, dishwasher, dryer, and mailbox profiles, configure a separate action for when pending contents are removed or collected; it runs when the main door opens or pending status is cleared.
	- See running state and last-active duration for cycle-based profiles; estimated remaining time is limited to laundry profiles.
	- Monitor power and energy independently of activity detection for profiles with a selected power sensor. Use a cumulative energy sensor's total or calculate energy from power.
	- Get a Repairs issue when a configured input is missing or unavailable; the issue clears when the input recovers.
	- Run configured actions in order. Reminders and alarms wait for the previous run to finish before repeating.
	- In compatible profiles, configure an immediate smart-plug-off alarm with its own repeat interval and count; it pauses while the plug state is unavailable and rearms when switched on.

## Installation

### HACS

This integration is not yet in the default HACS store. Add it as a custom repository:

1. In HACS, open **Integrations** and select **Custom repositories** from the menu.
2. Add `https://github.com/PacmanForever/home_activity_manager` with the category **Integration**.
3. Find **Home Activity Manager**, install it, and restart Home Assistant.

### Manual

Download or clone this repository and copy `custom_components/home_activity_manager` into the `custom_components` directory of your Home Assistant configuration. Restart Home Assistant, then add **Home Activity Manager** from **Settings > Devices & services**.

The integration works on supported Home Assistant versions; displaying its local icon and logo requires Home Assistant 2026.3 or newer.

## Configuration

Each configured device has a separate config entry. Its general type and activity mode are fixed after setup and shown when editing; create a new device to change either. Setup uses five steps:

1. Select a device profile and enter a name.
2. Select the activity mode available for that type.
3. Select the required activity source and optional compatible sensors and controls. A refrigerator also requires a door contact; a mailbox requires a separate main-door contact.
4. Configure the mode's thresholds, delays, and reminder parameters.
5. Configure the available actions.

Editing shows the fixed type and mode alongside the name, followed by sensors, parameters and actions. The activity source can be replaced with a compatible entity; a climate source must be replaced rather than cleared. A running cycle retains its start time after replacement unless the new source confirms it has stopped. An unavailable source does not cause a transition.

Each device-type-and-mode profile uses its own sensor, parameter and action fields. Cycle-start and cycle-end actions use the same labels across profiles; optional fields are marked explicitly in the selected profile's form.

For profiles with a power sensor, a cumulative energy sensor can be selected independently of the activity source. Its total is displayed in kWh and is never reset by this integration. Leave it empty to calculate a persistent total from power readings; a device button resets only this locally calculated total. The calculated total is maintained separately, so switching energy sources can change the displayed total; an unavailable external sensor does not fall back to the calculated total.

Power-cycle defaults are 4 W for 15 seconds to start and 1 W for 60 seconds to finish. All configurable durations use seconds. An auxiliary plug controls the managed device's power but does not override its selected activity source. In power-based profiles, the power sensor determines when activity ends; in the switch-based refrigerator profile, the switch itself determines activity. Laundry pending-unload reminders and refrigerator door alarms run once, then repeat up to the configured number of additional repetitions. The plug-off alarm is available only in profiles that declare it; refrigerator plugs do not trigger alarms.

## Entities and automations

Outputs depend on the selected profile and configured inputs. A selected power sensor provides a power entity; an energy sensor or power sensor provides an energy entity. Cycle-based profiles provide activity state and last-activity duration; estimated remaining time is limited to laundry profiles. Both refrigerator modes expose activity and a door-open alarm; neither has a compressor-inactivity or plug-off alarm. Mailboxes expose their main-door and pending-collection states, plus a button to clear pending status. Detecting mail starts the mailbox cycle and runs its start actions; opening the main door or pressing the clear button ends the cycle, runs its end actions, and cancels reminders. A selected smart plug is exposed as a switch on the managed device.

Configured inputs are represented by their corresponding integration output when one exists. The air conditioner's louver sensor is represented by its running state, without a separate input entity. Mailbox sensors likewise do not create standalone input wrappers; the main-door, pending-collection, and mail-slot outputs remain available. The air conditioner's original climate entity is associated directly with the managed device so its controls are preserved.

Integration outputs update with their sources, including unknown, unavailable, missing, and recovered states. Power and energy are displayed in W and kWh. When a power source is unavailable, its output does not present the previous reading as current; the integration retains its internal state without falsely ending the cycle.

External automations can react to state changes of the running and pending-status binary sensors. The integration does not currently fire custom events on the Home Assistant event bus. Pending laundry unload or mailbox collection clears when its main door opens or when the clear button is pressed.

Runtime state is restored after Home Assistant restarts. The integration does not create external helpers, scripts, or automations, and it does not remove selected external entities when a device entry is deleted.

## License

This project is distributed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for the full text.