# Car Stats Viewer for Home Assistant

A Home Assistant custom integration for [Car Stats Viewer](https://github.com/Ixam97/CarStatsViewer). It receives the app's webhook payload and exposes the vehicle as one Home Assistant device with typed entities for location, charging, ignition, gear, speed, power, battery, and more.

## Features

- Webhook-based updates with optional Basic Authentication.
- Optional Nabu Casa cloud webhook for a short, remote-accessible URL.
- One device per configured vehicle, with stable unique IDs.
- Restored entity state after a Home Assistant restart.
- API 2.1 driving-point and charging-session events.
- Diagnostic API and app version entities, disabled by default.

## Requirements

- Home Assistant with custom integrations enabled.
- Car Stats Viewer configured to send its data to a webhook.

Home Assistant Cloud is optional and only required if you want to use a Nabu Casa cloud webhook.

## Installation

### Manual installation

1. Copy `custom_components/carstatsviewer/` into your Home Assistant configuration directory:

   ```text
   config/custom_components/carstatsviewer/
   ```

2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**.
4. Search for **Car Stats Viewer** and follow the setup flow.

### HACS

This repository can be added as a custom repository in HACS. Select **Integration** as the repository category, install **Car Stats Viewer**, and restart Home Assistant before adding the integration from the UI.

## Configuration

The setup flow asks for:

- A vehicle name, such as `Polestar 2`.
- Optional Basic Authentication credentials.
- Whether to use a Nabu Casa cloud webhook.

After setup, the confirmation screen displays the webhook URL. The URL is also available at any time under **Settings → Devices & services → Car Stats Viewer → Configure**.

Point the Car Stats Viewer app at this URL. If Basic Authentication is enabled, use the same username and password in the app.

### Nabu Casa cloud webhook

The cloud webhook option requires Home Assistant Cloud to be enabled, connected, and subscribed when the integration is configured. If Cloud connects after Home Assistant starts, the integration retries automatically. An ongoing Cloud problem is reported through **Settings → System → Repairs**.

Removing the integration also removes its cloud webhook registration. Disabling the option later switches the integration back to its normal Home Assistant webhook URL.

## Entities

Each configured vehicle creates a device with entities similar to these:

| Entity | Description |
| --- | --- |
| `device_tracker.<car>_location` | Vehicle GPS location |
| `sensor.<car>_altitude` | Altitude |
| `sensor.<car>_ambient_temperature` | Ambient temperature |
| `sensor.<car>_battery_level` | Battery level |
| `sensor.<car>_current_power` | Current power |
| `sensor.<car>_gear` | P/R/N/D gear state |
| `sensor.<car>_ignition` | Off, accessory, on, starting, locked, or undefined |
| `sensor.<car>_last_update` | Timestamp of the last update |
| `sensor.<car>_speed` | Speed in km/h |
| `sensor.<car>_state_of_charge` | State of charge percentage |
| `binary_sensor.<car>_charge_port_connected` | Whether the charge port is connected |

API and charging-session entities are added when the corresponding data is provided. API and app version entities are diagnostic entities disabled by default.

The integration also fires these events when API 2.1 data is enabled in Car Stats Viewer:

- `carstatsviewer_driving_point`
- `carstatsviewer_charging_session`

## Updating from the old YAML setup

After confirming that the new integration is receiving data:

1. Remove the old `p2csv` webhook trigger and template sensors from `configuration.yaml`.
2. Reload YAML or restart Home Assistant.
3. Update dashboards and automations to use the new entity IDs.

The new entities have new unique IDs, so Home Assistant treats their history and statistics as new streams.

### Ignition entity migration

Version 1.0.5 changed ignition from a binary sensor to an enum sensor because Car Stats Viewer reports six ignition states. After upgrading, delete the old unavailable `binary_sensor.<car>_ignition` and update references to `sensor.<car>_ignition`.

## Reducing recorder noise

Car Stats Viewer may send updates every few seconds. To exclude fast-changing entities from history and Activity, add their IDs to your Home Assistant configuration:

```yaml
recorder:
  exclude:
    entities:
      - sensor.polestar_2_last_update

logbook:
  exclude:
    entities:
      - sensor.polestar_2_last_update
```

Adjust the entity IDs to match your vehicle. Restart Home Assistant after changing this configuration.

## Multiple vehicles

Run the integration setup flow once per vehicle. Each configuration creates a separate webhook, device, and set of entities.

## Documentation

- [Car Stats Viewer API documentation](https://github.com/Ixam97/CarStatsViewer/blob/master/docs/APIDOC.md)
- [Release notes](CHANGELOG.md)
- [Issue tracker](https://github.com/BeauGiles/ha-csv/issues)
