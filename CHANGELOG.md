# Changelog

## v0.9.7 - 2026-10-30

### Changed

- Display cycle duration and estimated remaining time as `HH:MM:SS`.
- Detect air-conditioner activity from its climate mode so idle periods do not suppress cycle actions.
- Skip empty parameter forms when no optional settings are available.

## v0.9.6 - 2026-10-30

### Added

- Add optional actions for when pending laundry or mailbox contents are removed.

### Changed

- Use contact-specific open/closed icons for air-conditioner, mailbox-slot, and main-door input wrappers.

## v0.9.5 - 2026-10-30

### Changed

- Use consistent cycle-start and cycle-end action labels across appliance profiles and translations.
- Treat mailbox activity as a cycle from detected mail arrival until collection, with separate start and finish actions; preserve existing arrival actions.
- Use state-specific icons for air-conditioner activity and contact-based louver state.

## v0.9.4 - 2026-10-30

### Changed

- Rename the air-conditioner louver-contact mode and inputs to contact/opening sensor in all translations and documentation.
- Remove the contact/opening sensor from power-managed air-conditioner configuration and migrate existing entries to drop the obsolete selection.
- Remove the auxiliary contact/opening sensor from climate-managed air conditioners and mark the required climate entity explicitly in every translation.
- Clarify the mailbox slot input as a contact/opening sensor in its mode, field, model, and requirements labels.
- Add configurable activity start/finish actions to both refrigerator profiles.
- Remove compressor-inactivity and plug-off alarms from refrigerator profiles; keep the door alarm.
- Restore refrigerator sensor and action descriptions in all translations and config forms.

## v0.9.3 - 2026-10-30

### Fixed

- Keep running and pending states separate from input wrappers, including the air conditioner louver contact.
- Update mailbox motion wrappers for every source transition and reflect unavailable or missing inputs across all profiles.
- Avoid presenting a stale power reading as current while its source is unavailable.

## v0.9.2 - 2026-10-29

### Changed

- Refresh the integration icon to represent connected household devices.

## v0.9.1 - 2026-10-29

### Changed

- Publish the Home Activity Manager name in HACS repository metadata.

## v0.9.0 - 2026-10-29

### Added

- Give each appliance profile and activity category its own configuration steps and translated labels.
- Wrap configured binary input entities on the appliance device while preserving the original climate entity exception.
- Mark optional profile fields explicitly and verify all profiles and locales in tests.

### Fixed

- Pass the config-entry ID to Home Assistant's device-registry identifier lookup.

## v0.8.0 - 2026-10-29

### Added

- Represent configured input entities on each appliance device, reusing an equivalent integration output to avoid duplicate entities; keep original climate entities directly associated with the appliance.

### Changed

- Keep appliance type and activity mode read-only when editing, and clarify activity-source and accumulated-energy labels in Catalan, English, and Spanish.
- Use consistent binary-sensor terminology in the interface and documentation.

### Fixed

- Use the current Home Assistant device-registry lookup API for climate association, with a compatibility fallback for older versions.

## v0.7.0 - 2026-10-29

### Added

- Separate general appliance type from the required activity-detection mode; both remain visible and immutable after setup.
- Allow compatible auxiliary contact, power, energy, and smart-plug inputs independently of the selected activity source.
- Support an existing energy sensor's accumulated total or persistent energy calculation from power.

### Changed

- Preserve cycle timing when replacing an activity source; unavailable sources do not cause false transitions, and auxiliary power or plug states do not override the selected source.
- Require a replacement when changing the configured climate activity entity, preserving its original Home Assistant entity and controls.
- Update setup, options, translations, and documentation for the category-and-mode configuration flow.

## v0.6.1 - 2026-10-28

### Fixed

- Exclude climate entities with a parent device from the air-conditioner climate selector.

## v0.6.0 - 2026-10-28

### Added

- Add an air-conditioner profile that uses an existing unparented `climate` entity for activity detection and associates the original entity with the appliance device without creating a wrapper.
- Preserve the climate entity's original integration and controls, and return it to no device when deselected, replaced, or when the appliance is removed.

### Changed

- Use appliance-specific icons for laundry door states.
- Document the climate-backed air-conditioner profile and remove its obsolete under-consideration proposal.

## v0.5.2 - 2026-10-28

### Fixed

- Keep the derived power sensor available before its first valid reading; it reports an unknown value until a reading is available.

### Documentation

- Record read-only `climate` input for air-conditioner cycle detection as an area under consideration.

## v0.5.1 - 2026-10-28

### Changed

- Add state-aware MDI icons for appliance activity, doors, mailbox flap, pending status, and smart plugs, plus specific icons for sensors and the clear-pending button.

## v0.5.0 - 2026-10-28

### Added

- Add an immediate smart-plug-off alarm to every compatible appliance profile, with independent actions, repeat interval, repeat count, persistence, and rearming when the plug turns on.
- Distinguish appliance profile variants in the Home Assistant device model and expose the mail-slot flap state as a separate entity.

### Changed

- Keep the last valid power reading available through temporary sensor outages, including a valid reading of 0 W.
- Keep the configured appliance type fixed and omit it from the options form after setup.

## v0.4.0 - 2026-10-28

### Added

- Report configured input entities that are missing or unavailable as Home Assistant Repairs issues, and clear the issues when inputs recover.
- Keep the appliance profile fixed after setup; create a new device to use a different profile.
- Validate that mailbox arrival and main-door detection use separate entities.

### Changed

- Serialize actions within each event group and run reminder and alarm actions outside the deadline callback.
- Prevent stale alarm and reminder actions from changing a later state, and avoid catch-up bursts after slow actions or runtime unload.
- Start repeat intervals after the previous action completes.

## v0.3.0 - 2026-10-27

### Added

- Add profile-owned sensor inputs with profile-specific labels, descriptions, entity domains, and device-class filters.
- Add a smart-switch refrigerator profile with switch-based activity detection and a separate door sensor.
- Allow an optional controllable smart plug on the power-based refrigerator profile without replacing power-based detection.

### Changed

- Distinguish the capabilities of power-based and smart-switch refrigerators: the switch profile has no power, energy, or compressor-inactivity entities or alarm.
- Normalize profile-specific form fields to the existing canonical configuration keys to preserve stored configuration compatibility.
- Expand CRUD and runtime coverage for profile-specific selectors and smart-switch refrigerator behavior.

## v0.2.0 - 2026-10-27

### Added

- Add profile-specific configuration and entities for washers, dishwashers, dryers, air conditioners, and refrigerators.
- Detect air-conditioner activity from either power readings or a louver contact, and add independent refrigerator door and compressor alarms.
- Add mailbox profiles using an interior motion sensor or mail-slot flap contact, with arrival actions, pending-to-unload state, reminders, and main-door clearing.
- Add four-step profile-aware setup and options flows, with English, Spanish, and Catalan translations.
- Persist cycle, reminder, and alarm state and verify profile creation, editing, and deletion with unit and Home Assistant component tests.

### Compatibility

- Component tests passed with Home Assistant 2026.10.4.

## v0.1.0 - 2026-10-27

First public release of Home Activity Manager.

### Added

- Detect washer, dishwasher, and dryer cycles from power sensor readings.
- Configure per-appliance start, finish, maximum-runtime, and pending-unload actions.
- Track lifetime energy, last-cycle duration, estimated remaining time, and running state.
- Optionally monitor a door and smart plug, with pending-unload reminders and a clear-state button.
- Restore cycle and reminder state across Home Assistant restarts.

### Compatibility

- Component tests passed with Home Assistant 2026.10.4.
