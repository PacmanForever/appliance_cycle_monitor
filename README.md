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

A local Home Assistant integration for washers, dishwashers, dryers, air conditioners, refrigerators, and mailboxes. Refrigerator activity can be detected from power readings or a required smart-switch state. The power-based refrigerator profile requires a power sensor and door contact, and can optionally include a controllable smart plug; the smart-switch profile requires the switch as its activity source and a separate door contact. Other appliance activity comes from power or, for an air conditioner's louver, a binary contact. Mail is detected from an interior motion sensor or mail-slot flap contact. Each device has its own configurable actions, with no external service or credentials.

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
	- **Louver-contact option:** detect activity from a binary contact on the louver; no power or energy entities are created.
	- **Power option:** detect activity from power readings and configurable thresholds. When both sources are available, choose this profile to use power.
- **Refrigerator**
	- **Power option:** requires a power sensor and door contact. A controllable smart plug is optional; compressor-activity and door-open alarms are available.
	- **Smart-switch option:** requires a smart switch and separate door contact. The switch detects activity; no power, energy, or compressor-inactivity alarm is provided. A door-open alarm is available.
- **Mailbox**
	- **Interior-motion option:** detect incoming mail with a motion sensor inside the mailbox.
	- **Mail-slot option:** detect incoming mail with a contact on the letter flap.
	- Both options track pending collection, support arrival actions and reminders, and use a separate main-door contact to clear pending status.
- **Shared features**
	- Provide per-device Home Assistant actions and restore cycle, reminder, and alarm state after Home Assistant restarts.
	- Expose running state and last-active duration; power-based profiles also track lifetime energy, while estimated remaining time is limited to laundry profiles.
	- Serialize each action group, report unavailable configured inputs through Repairs, and clear the repair issue when an input recovers.

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

Each appliance has a separate config entry and device. Setup and editing use four steps. The appliance type is fixed after setup; create a new device to use a different profile.

1. Select the appliance type and enter a name.
2. Select the sensors required or supported by that profile. Laundry doors and smart plugs are optional. A power-based refrigerator requires a power sensor and door contact; its controllable smart plug is optional and does not replace power detection. A smart-switch refrigerator requires the switch and a separate door contact. An AC uses either its louver contact or power; a mailbox uses an arrival sensor and its main-door contact.
3. Configure the selected profile's thresholds, delays, and reminder parameters.
4. Configure the available actions for that profile.

Power-cycle defaults are 4 W for 15 seconds to start and 1 W for 60 seconds to finish. All configurable durations use seconds. Turning off a configured plug cuts appliance power and ends an active period immediately. On a power-based refrigerator, the power sensor remains the activity detector; the optional plug can still end a detected period when switched off. Laundry pending-unload reminders and refrigerator alarms run once, then repeat up to the configured number of additional repetitions.

## Entities and automations

Outputs depend on the selected profile. Power-based profiles provide power and lifetime energy; appliance profiles provide activity state and last-activity duration. Estimated remaining time is limited to laundry profiles. A power-sensed refrigerator exposes compressor activity and independent door-open/compressor-inactive alarms; its optional smart plug is exposed as a controllable switch. A smart-switch refrigerator requires a switch that both controls the appliance and supplies its activity state; it exposes a door-open alarm but no power, energy, or compressor-inactivity entities. Mailboxes expose their main-door and pending-to-unload states, plus a button to clear pending status. An arrival sensor detects mail and runs its configured actions; opening the main door clears pending status and cancels reminders. An AC contact profile exposes activity without power or energy sensors. A selected smart plug is exposed as a switch on the device.

External automations can react to state changes of the running and pending-unload binary sensors. The integration does not currently fire custom events on the Home Assistant event bus. Pending unload clears when the door opens or when the clear button is pressed.

Runtime state is restored after Home Assistant restarts. The integration does not create external helpers, scripts, or automations, and it does not remove selected external entities when an appliance entry is deleted.

## Development and tests

Install `requirements-test.txt`, then run:

```sh
python3 -m pytest -q --cov=custom_components.appliance_cycle_monitor --cov-report=term-missing --cov-fail-under=95
```

GitHub Actions runs unit and component tests with combined coverage enforcement, HACS validation, Hassfest, and a daily component test against the latest stable Home Assistant release. Checks run on pushes and pull requests to `main`, and can also be started manually.

The Home Assistant badge shows the latest stable version that passed the daily component tests and updates automatically after a successful run.

## License

This project is distributed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for the full text.