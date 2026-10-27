# Appliance Cycle Monitor

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Tests and coverage](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/tests.yml)
[![HACS validation](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hacs.yml/badge.svg?branch=main)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hassfest.yml/badge.svg?branch=main)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/hassfest.yml)
[![Daily HA compatibility](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/daily-ha.yml/badge.svg?branch=main)](https://github.com/PacmanForever/appliance_cycle_monitor/actions/workflows/daily-ha.yml)

A local Home Assistant integration that detects washer, dishwasher, and dryer cycles from an existing power sensor. It manages each appliance as its own Home Assistant device, with configurable actions and no external service or credentials.

## Features

- Detect cycle start and finish from power thresholds with configurable confirmation times.
- Track lifetime energy, last-cycle duration, estimated remaining time, and running state.
- Optionally monitor a door and smart plug, and track pending unloading.
- Configure separate Home Assistant actions for cycle start, cycle finish, maximum runtime, and pending-unload reminders.
- Persist cycle and reminder state across Home Assistant restarts.

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

Each appliance has a separate config entry and device. Setup and editing use three steps:

1. Select the appliance type and power sensor, optionally select a door sensor and smart-plug switch, and enter a name.
2. Set power thresholds, confirmation times, and an optional maximum runtime.
3. Configure actions for cycle start, cycle finish, maximum runtime, and pending-unload reminders.

Defaults are 4 W for 15 seconds to start a cycle and 1 W for 60 seconds to finish. All configurable durations use seconds. Turning off a configured plug ends an active cycle immediately. Pending-unload reminders start after 900 seconds and repeat at the configured interval, up to the configured number of additional repetitions.

## Entities and automations

Each appliance provides power, lifetime energy, last-cycle duration, estimated remaining time, and a running binary sensor. When configured, the door sensor also enables door and pending-unload binary sensors and a button to clear the pending state. A selected smart plug is exposed as a switch on the appliance device.

External automations can react to state changes of the running and pending-unload binary sensors. The integration does not currently fire custom events on the Home Assistant event bus. Pending unload clears when the door opens or when the clear button is pressed.

Runtime state is restored after Home Assistant restarts. The integration does not create external helpers, scripts, or automations, and it does not remove selected external entities when an appliance entry is deleted.

## Development and tests

Install `requirements-test.txt`, then run:

```sh
python3 -m pytest -q --cov=custom_components.appliance_cycle_monitor --cov-report=term-missing --cov-fail-under=95
```

GitHub Actions runs unit and component tests with combined coverage enforcement, HACS validation, Hassfest, and a daily component test against the latest stable Home Assistant release. Checks run on pushes and pull requests to `main`, and can also be started manually.

## License

This project is distributed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for the full text.