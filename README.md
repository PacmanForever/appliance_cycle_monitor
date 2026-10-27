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

A local Home Assistant integration for washers, dishwashers, dryers, air conditioners, refrigerators, and mailboxes. It detects appliance activity from a power sensor or, for an air conditioner's louver, a binary contact, and detects mail from an interior motion sensor or mail-slot flap contact. Each appliance or mailbox is managed as its own Home Assistant device with configurable actions and no external service or credentials.

## Features

- Detect cycle start and finish from power thresholds with configurable confirmation times.
- Detect an air conditioner's activity either from its louver contact or from power; choose the power profile when both sensors are available.
- Monitor refrigerator compressor activity and door-open duration with independent, configurable alarms.
- Detect mail through mailbox interior motion or a mail-slot flap contact, run arrival actions, and track mail pending collection.
- Track lifetime energy, last-cycle duration, estimated remaining time, and running state.
- Optionally monitor laundry-appliance doors and smart plugs, and track pending unloading.
- Configure profile-specific Home Assistant actions and persist cycle, reminder, and alarm state across Home Assistant restarts.

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

Each appliance has a separate config entry and device. Setup and editing use four steps:

1. Select the appliance type and enter a name.
2. Select the sensors required or supported by that profile. Laundry doors and smart plugs are optional; a refrigerator requires power and a door contact; an AC uses either its louver contact or power; a mailbox uses an arrival sensor and its main-door contact.
3. Configure the selected profile's thresholds, delays, and reminder parameters.
4. Configure the available actions for that profile.

Power-cycle defaults are 4 W for 15 seconds to start and 1 W for 60 seconds to finish. All configurable durations use seconds. Turning off a configured plug ends an active period immediately. Laundry pending-unload reminders and refrigerator alarms run once, then repeat up to the configured number of additional repetitions.

## Entities and automations

Outputs depend on the selected profile. Power-based profiles provide power and lifetime energy; appliance profiles provide activity state and last-activity duration. Estimated remaining time is limited to laundry profiles. Refrigerator devices expose their door state and independent door-open/compressor-inactive actions. Mailboxes expose their main-door and pending-to-unload states, plus a button to clear pending status. An arrival sensor detects mail and runs its configured actions; opening the main door clears pending status and cancels reminders. An AC contact profile exposes activity without power or energy sensors. A selected smart plug is exposed as a switch on the device.

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