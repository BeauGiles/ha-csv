# Changelog

All notable changes to the Car Stats Viewer Home Assistant integration are documented here.

## [1.0.5] - 2026-07-20

### Fixed

- Report ignition as an enum sensor instead of a binary sensor. Car Stats Viewer can report `Undefined`, `Locked`, `Off`, `Accessory`, `On`, and `Starting`.

### Migration

- Home Assistant creates `sensor.<car>_ignition` and leaves the old `binary_sensor.<car>_ignition` unavailable. Delete the old entity and update dashboards and automations.

## [1.0.4] - 2026-07-20

### Fixed

- Restore sensor, binary sensor, and location state after a Home Assistant restart so entities do not remain unknown until each field appears in a new webhook payload.

## [1.0.3] - 2026-07-20

### Fixed

- Avoid raising a Cloud Repair during normal startup while Home Assistant Cloud is still connecting.
- Retry cloud webhook setup automatically when Cloud connects.

## [1.0.2] - 2026-07-20

### Changed

- Show the webhook URL in the setup confirmation and Configure flow instead of creating a persistent notification on every restart.
- Report an unavailable cloud webhook through Home Assistant Repairs.

## [1.0.1] - 2026-07-20

### Fixed

- Mark dispatcher callbacks correctly so webhook updates write entity state on Home Assistant's event loop.

## [1.0.0]

### Added

- Initial Car Stats Viewer custom integration with config flow, webhook support, typed vehicle entities, optional Basic Authentication, Nabu Casa cloud webhooks, and API 2.1 driving and charging events.

