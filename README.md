# Appliance Cycle Monitor

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPacmanForever%2Fappliance_cycle_monitor%2Fmain%2Fcustom_components%2Fappliance_cycle_monitor%2Fmanifest.json&query=%24.version&prefix=v&label=version)](https://github.com/PacmanForever/appliance_cycle_monitor/releases)
[![Unit Tests](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/tests.yml/badge.svg?branch=main&job=unit)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/tests.yml)
[![Component Tests](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/tests.yml/badge.svg?branch=main&job=component)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/tests.yml)
[![HACS Validation Tests](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hacs.yml/badge.svg?branch=main)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hacs.yml)
[![HA Validation Tests](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hassfest.yml/badge.svg?branch=main)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hassfest.yml)
[![License](https://img.shields.io/github/license/PacmanForever/appliance_cycle_monitor?label=GPLv3)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-%3E%3D95%25-brightgreen)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/tests.yml)
[![Home Assistant](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPacmanForever%2Fappliance_cycle_monitor%2Fmain%2Fdocs%2Fhome_assistant_compatibility.json&query=%24.tested_version&suffix=%20tested&label=home%20assistant&color=blue)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/daily-ha.yml)
[![Daily HA compatibility](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/daily-ha.yml/badge.svg?branch=main)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/daily-ha.yml)

A local Home Assistant integration for washers, dishwashers, dryers, air conditioners, refrigerators, and mailboxes. Refrigerator activity can be detected from power readings or a required smart-switch state. The power-based refrigerator profile requires a power sensor and door contact, and can optionally include a controllable smart plug; the smart-switch profile requires the switch as its activity source and a separate door contact, with optional power and energy inputs. Other appliance activity comes from power, an air-conditioner's louver contact, or an existing climate entity. Mail is detected from an interior motion sensor or mail-slot flap contact. Each device has its own configurable actions, with no external service or credentials.

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
	- **Climate-entity option:** use an existing climate entity with no parent device as the activity source. The original entity and controls are assigned directly to the appliance device; no wrapper is created. Activity follows `hvac_action` when available and falls back to the climate state. Replacing the entity or removing the appliance returns it to no device if it is still assigned to this appliance.
	- **Louver-contact option:** detect activity from a binary sensor on the louver.
	- **Power option:** detect activity from power readings and configurable thresholds.
	- In any mode, a louver contact, power sensor, energy sensor and controllable smart plug can be selected independently. Only the chosen activity source determines running state.
- **Refrigerator**
	- **Power option:** requires a power sensor and door contact. A controllable smart plug is optional; compressor-activity and door-open alarms are available.
	- **Smart-switch option:** requires a smart switch and separate door contact. The switch detects activity; optional power and energy sensors do not change that activity. A door-open alarm is available, but not a compressor-inactivity alarm.
- **Mailbox**
	- **Interior-motion option:** detect incoming mail with a motion sensor inside the mailbox.
	- **Mail-slot option:** detect incoming mail with a contact on the letter flap and expose its open/closed state as **Mail slot**.
	- Both options track pending collection, support arrival actions and reminders, and use a separate main-door contact to clear pending status.
- **Across all profiles**
	- Configure Home Assistant actions per device and restore cycle, reminder, and alarm state after Home Assistant restarts.
	- See running state and last-active duration for appliances; estimated remaining time is limited to laundry profiles.
	- Monitor power and energy independently of activity detection for plugged-in appliances. Use a cumulative energy sensor's total or calculate energy from power.
	- Get a Repairs issue when a configured input is missing or unavailable; the issue clears when the input recovers.
	- Run configured actions in order. Reminders and alarms wait for the previous run to finish before repeating.
	- In compatible profiles, configure an immediate smart-plug-off alarm with its own repeat interval and count; it pauses while the plug state is unavailable and rearms when switched on.

## Installation

### HACS

This integration is not yet in the default HACS store. Add it as a custom repository:

1. In HACS, open **Integrations** and select **Custom repositories** from the menu.
2. Add `https://github.com/PacmanForever/appliance_cycle_monitor` with the category **Integration**.
3. Find **Appliance Cycle Monitor**, install it, and restart Home Assistant.

### Manual

Download or clone this repository and copy `custom_components/appliance_cycle_monitor` into the `custom_components` directory of your Home Assistant configuration. Restart Home Assistant, then add **Appliance Cycle Monitor** from **Settings > Devices & services**.

The integration works on supported Home Assistant versions; displaying its local icon and logo requires Home Assistant 2026.3 or newer.

## Configuration

Each appliance has a separate config entry and device. The general appliance type and activity mode are fixed after setup and shown when editing; create a new device to change either. Setup uses five steps:

1. Select the appliance type and enter a name.
2. Select the activity mode available for that type.
3. Select the required activity source and optional compatible sensors and controls. A refrigerator also requires a door contact; a mailbox requires a separate main-door contact.
4. Configure the mode's thresholds, delays, and reminder parameters.
5. Configure the available actions.

Editing shows the fixed type and mode alongside the name, followed by sensors, parameters and actions. The activity source can be replaced with a compatible entity; a climate source must be replaced rather than cleared. A running cycle retains its start time after replacement unless the new source confirms it has stopped. An unavailable source does not cause a transition.

Each appliance-and-mode profile uses its own sensor, parameter and action steps, field keys and labels. Optional sensor and action fields are marked explicitly in the selected profile's form.

For plugged-in appliances, a cumulative energy sensor can be selected independently of the activity source and power sensor. Its total is displayed in kWh without resetting it. Leave it empty to calculate a persistent total from a selected power sensor. The calculated total is maintained separately, so switching energy sources can change the displayed total; an unavailable external sensor does not fall back to the calculated total.

Power-cycle defaults are 4 W for 15 seconds to start and 1 W for 60 seconds to finish. All configurable durations use seconds. An auxiliary plug controls the appliance's power but does not override its selected activity source. For a power-based appliance, the power sensor determines when the activity period ends; for a switch-based refrigerator, the switch itself determines activity. Laundry pending-unload reminders and refrigerator alarms run once, then repeat up to the configured number of additional repetitions. The plug-off alarm runs its configured actions immediately, then repeats on its own interval (900 seconds and 3 additional repetitions by default) while the plug remains off. Switching it on cancels pending repetitions and resets the count; an unavailable state delays alarms until the plug state is known again.

## Entities and automations

Outputs depend on the selected mode and configured inputs. A selected power sensor provides a power entity; an energy sensor or power sensor provides an energy entity. Appliance profiles provide activity state and last-activity duration; estimated remaining time is limited to laundry profiles. A power-sensed refrigerator exposes compressor activity and independent door-open/compressor-inactive alarms; a switch-sensed refrigerator exposes a door-open alarm but no compressor-inactivity alarm. Mailboxes expose their main-door and pending-to-unload states, plus a button to clear pending status. An arrival sensor detects mail and runs its configured actions; opening the main door clears pending status and cancels reminders. A selected smart plug is exposed as a switch on the device.

Configured input entities are represented on the appliance device by integration entities. When an existing output already mirrors an input, that output is reused rather than creating a duplicate; climate inputs remain the original entities and are associated directly with the appliance device so their controls are preserved.

External automations can react to state changes of the running and pending-unload binary sensors. The integration does not currently fire custom events on the Home Assistant event bus. Pending unload clears when the door opens or when the clear button is pressed.

Runtime state is restored after Home Assistant restarts. The integration does not create external helpers, scripts, or automations, and it does not remove selected external entities when an appliance entry is deleted.

## License

This project is distributed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for the full text.