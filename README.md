# Car Stats Viewer integration

Replaces the `p2csv` webhook trigger + template sensors with a proper custom
integration. Everything lands on one device instead of eleven loose entities,
with correct entity types (device_tracker for GPS, binary_sensor for
ignition/charge port, enum sensor for gear, timestamp sensor for last
update) instead of generic template sensors.

Source of truth for the payload: [CarStatsViewer API docs](https://github.com/Ixam97/CarStatsViewer/blob/master/docs/APIDOC.md).

## v1.0.1: fix entities never updating

If you installed v1.0.0: the webhook was receiving data fine (the app shows
success), but every update crashed silently after that. The dispatcher
callback in `entity.py` that pushes new values into each entity wasn't
decorated `@callback`, so Home Assistant ran it in an executor thread
instead of the event loop and `async_write_ha_state()` — which must run on
the event loop — threw `RuntimeError: Detected that custom integration
'carstatsviewer' calls async_write_ha_state from a thread other than the
event loop`, logged once per incoming payload and otherwise silent (no
crash, no visible error unless you went looking in the log). Entities
stayed on "unavailable" forever as a result.

Fixed in `entity.py` by adding `@callback` to `_handle_update`. Just
replace the whole `custom_components/carstatsviewer/` folder with this
version and restart Home Assistant — no need to remove and re-add the
integration, your existing config entry and webhook URL are unaffected.

## v1.0.2: stop re-notifying on every restart

v1.0.0/v1.0.1 recreated a persistent notification with the webhook URL on
*every* `async_setup_entry` call — meaning every Home Assistant restart and
every integration reload, not just the first time. If you had "Use a Nabu
Casa cloud webhook" on without an active Cloud connection, you'd also get
the ⚠️ fallback warning every single time, forever.

Changed in v1.0.2:
- The webhook URL is now shown once, in a confirmation step at the end of
  setup (Settings → Devices & Services → Add Integration flow) — not as a
  notification.
- You can see the current URL again any time via Configure on the
  integration (Settings → Devices & Services → Car Stats Viewer →
  Configure) — it's shown in the form description, computed live.
- The cloudhook-unavailable warning moved to Home Assistant's **Repairs**
  system (Settings → System → Repairs) instead of a notification.

Re-adding the integration is *not* necessary — just replace the
`custom_components/carstatsviewer/` folder and restart; the existing
config entry keeps working, only the notification behavior changes on
setup/reload.

## v1.0.3: stop the Repair from firing (and needing a manual reload) on every boot

Turned out v1.0.2's Repair had the same underlying problem as the
notification it replaced, just less annoying: Home Assistant Cloud
connects to Nabu Casa *asynchronously*, a few seconds after Home Assistant
itself finishes starting. This integration's setup code runs earlier than
that, so on basically every normal boot, Cloud genuinely isn't connected
yet the moment we ask for a cloudhook — that's not a problem, it resolves
itself a few seconds later on its own. v1.0.2 didn't know the difference
between "not connected yet, wait a sec" and "actually broken," so it raised
the Repair immediately every time and only cleared it the next time
`async_setup_entry` happened to run again (i.e., only after a manual
reload) — exactly the "annoying" behavior reported.

Fixed in v1.0.3: setup no longer raises a Repair on that first check. If
Cloud isn't connected yet, it quietly registers a listener for Cloud's
connection-state-changed event and retries automatically the moment Cloud
connects — no manual reload, and normal boots where Cloud connects
successfully within a few seconds never show a Repair at all. A Repair
only appears if that retry *also* fails (a real, ongoing problem — Cloud
not logged in, subscription lapsed, etc.), or immediately if Home
Assistant Cloud isn't set up at all (nothing to wait for in that case).

Same update method as before: replace the folder, restart, no need to
remove/re-add the integration.

## v1.0.4: entities going to "Unknown" after a restart

Reported symptom: after restarting Home Assistant, some (not all) entities
showed "Unknown" even though the webhook was actively receiving data again
(visible in the Activity log) and the entity's *history* clearly had real
values from before the restart.

Root cause: these entities are push-only — there's no polling, they just
hold whatever the last webhook payload said. That state (`runtime.latest`)
is in-memory only, and starts completely empty on every restart. A sensor
only shows a real value once a payload arrives that happens to include
that specific field. Car Stats Viewer doesn't necessarily send every field
on every call (e.g., speed/state of charge/ignition can be genuinely
missing while the fields that don't need a live vehicle connection, like
gear or battery level, keep flowing) — so depending on what the car was
doing at the moment of restart, some entities would refill within seconds
and others could sit on "Unknown" for a long time, until a payload
happened to include them again. The old YAML template sensors never
showed this because Home Assistant's template platform automatically
restores each sensor's last known value on startup — this custom
integration wasn't doing the equivalent.

Fixed in v1.0.4 by adding that restore behavior explicitly (`RestoreSensor`
for sensors, `RestoreEntity` for the ignition/charge-port binary sensors
and the location tracker's lat/lon). On restart, each entity now shows its
last known value immediately instead of "Unknown", exactly like the old
YAML did — and the moment a fresh webhook payload actually includes that
field again, live data takes over as normal.

Same update method: replace the folder, restart, no reconfiguration
needed.

## v1.0.5: Ignition showing "Unknown" instead of Off

Reported symptom: the Ignition entity's history alternated between "On" and
"Unknown", never "Off".

Root cause: Car Stats Viewer's `ignitionState` isn't actually a two-state
on/off value — it's the human-readable name of Android Automotive's
`android.car.VehicleIgnitionState` vehicle property, which has six possible
states: `UNDEFINED`, `LOCK`, `OFF`, `ACC` ("accessory" - radio/accessories
powered, engine and cluster off), `ON`, and `START` (cranking). `ACC` is
common — cars regularly sit in accessory mode for a while after you get out,
or briefly on start — but v1.0.4's `binary_sensor` only recognized exactly
"on"/"off" and mapped everything else, including "Accessory", to `None`
("Unknown").

Fixed in v1.0.5 by changing Ignition from a `binary_sensor` to an `enum`
`sensor` (same approach already used for Gear), with all six states mapped
to clean labels: Off, Accessory, On, Starting, Locked, Undefined. History
now shows the real state Car Stats Viewer is reporting instead of bouncing
between On and Unknown.

**One-time cleanup needed after this update**: because the entity moved
from the `binary_sensor` domain to the `sensor` domain, Home Assistant will
create a new `sensor.<car>_ignition` entity and leave the old
`binary_sensor.<car>_ignition` behind as unavailable/orphaned (it's no
longer provided by the integration, but Home Assistant doesn't delete old
entities automatically). After restarting, go to Settings → Devices &
Services → Entities, find the old `binary_sensor.<car>_ignition`, and delete
it — then update any dashboards/automations that referenced it to use the
new `sensor.<car>_ignition` (states are now `off`/`accessory`/`on`/
`starting`/`locked`/`undefined` instead of `on`/`off`).

Same update method otherwise: replace the folder, restart, no need to
remove/re-add the integration itself.

## What you get vs. the old YAML

| Old template sensor | New entity | Why it's better |
|---|---|---|
| `CSV Altitude` | `sensor.<car>_altitude` | unchanged, now on the device |
| `CSV Latitude` + `CSV Longitude` | `device_tracker.<car>_location` | single GPS entity, shows on the map/history like a phone tracker |
| `CSV Temp` | `sensor.<car>_ambient_temperature` | proper `temperature` device class |
| `CSV Battery Level` | `sensor.<car>_battery_level` | `energy_storage` device class (kWh level, not a cumulative total) |
| `CSV Ignition State` | `sensor.<car>_ignition` | `enum` device class covering all six real states (Off/Accessory/On/Starting/Locked/Undefined), not just a raw "On"/"Off" string |
| `CSV Current Power` | `sensor.<car>_current_power` | unchanged (kW) |
| `CSV Gear` | `sensor.<car>_gear` | `enum` device class with fixed P/R/N/D options |
| `CSV Speed km/s` | `sensor.<car>_speed` | unchanged (km/h, name typo fixed) |
| `CSV SOC` | `sensor.<car>_state_of_charge` | unchanged (%) |
| `CSV Timestamp` + `CSV Last Update` (duplicates) | `sensor.<car>_last_update` | one `timestamp` sensor instead of two identical string sensors |
| *(not previously exposed)* | `binary_sensor.<car>_charge_port_connected` | was in the payload (`chargePortConnected`), just unused |
| *(not previously exposed)* | `sensor.<car>_api_version` / `_app_version` | diagnostic, disabled by default |
| *(not previously exposed)* | `sensor.<car>_last_charging_energy` / `_last_charging_duration` / `_last_charging_session_end` | populated from the optional API 2.1 `chargingSessions` array, if your app sends it |

If your Car Stats Viewer app has "drive points" or "charging sessions"
enabled (API 2.1), each point/session is also fired as a Home Assistant
event — `carstatsviewer_driving_point` and `carstatsviewer_charging_session`
— so you can build automations or log full history without turning every
GPS point into an entity.

## Install

1. Copy `custom_components/carstatsviewer/` into your Home Assistant
   `config/custom_components/` folder (so you end up with
   `config/custom_components/carstatsviewer/manifest.json`, etc.).
2. Restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → search
   "Car Stats Viewer".
4. Enter a vehicle name (e.g. "Polestar 2"). Optionally enable Basic Auth
   and set a username/password — Car Stats Viewer supports Basic Auth
   natively, so you no longer need `local_only: false` with no auth at all.
5. The integration creates a webhook and registers a device with all the
   entities above (unavailable until the first payload arrives).

## Find your webhook URL

The last step of setup shows the webhook URL once, directly in the config
flow ("Point the app at this webhook"). Point the Car Stats Viewer app's
webhook setting at that URL. If you turned on Basic Auth, enter the same
username/password in the app.

Need it again later (new phone, reinstalled the app, etc.)? Open Settings →
Devices & Services → Car Stats Viewer → **Configure** — the current URL is
shown live in the description, no notification digging required.

## Shorter URL via Nabu Casa

If you have a [Home Assistant Cloud](https://www.nabucasa.com/) subscription,
check "Use a Nabu Casa cloud webhook" during setup (or later in Configure).
This is the same mechanism as [manually creating a cloud webhook](https://support.nabucasa.com/hc/en-us/articles/25619382358685-Triggering-an-automation-with-a-webhook-trigger)
from the Cloud panel — a short `https://hooks.nabucasa.com/...`-style URL
that Nabu Casa relays to your instance — except the integration requests it
automatically via `cloud.async_get_or_create_cloudhook()`.

Requirements: Home Assistant Cloud must be enabled and connected (logged in
+ an active subscription) *at the time the integration is set up or
reloaded*. If it isn't yet, setup falls back to the normal local/external
URL and a Repair shows up under Settings → System → Repairs explaining why
— it clears itself automatically once Cloud connects and the integration
reloads (or once you turn the option off). It does **not** re-notify you
every restart; see the v1.0.2 changelog above. The `local_only` flag on the
underlying webhook is still left `False` either way, matching Nabu Casa's
own instructions.

Deleting the integration entirely also removes the cloudhook registration
on Nabu Casa's side. Un-checking the option later just stops the
integration from *using* the cloudhook (it reverts to the local/external
URL) — the cloudhook registration itself is only cleaned up on removal.

## Remove the old automation

Once the new integration is receiving data (check that the entities show a
value instead of "unavailable"), delete the `p2csv` trigger-based template
sensor YAML block and reload YAML / restart Home Assistant. The old
`sensor.polestar_2_csv_*` entities will go away; update any dashboards or
automations that referenced them to use the new entity IDs listed in the
table above (also check `long-term statistics` if you want to keep history
for the energy/battery sensors — HA will treat the new unique IDs as new
statistics streams).

## Reducing recorder / logbook noise

While the car is driving, Car Stats Viewer can push an update every ~5
seconds, and *every* entity gets a new state each time — that's a lot of
rows in the recorder database and a lot of Activity/Logbook entries.
`sensor.<car>_last_update` is usually the least useful one to keep full
history for (it's just a timestamp of itself), but there's no way for the
integration's code to opt an entity out of recording — Home Assistant only
supports this via the `recorder` (history/statistics) and `logbook`
(Activity) integrations' own `exclude` config, set by you, not by the
integration. Add this to `configuration.yaml` (adjust the entity IDs to
match yours — check Settings → Devices & Services → Car Stats Viewer for
the exact ones):

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

`recorder.exclude` stops it going into the history database at all
(saves storage); `logbook.exclude` stops it appearing in the Activity
panel specifically — you can set either or both. If other fast-changing
entities from this integration (speed, power, altitude) are also cluttering
things and you don't care about their history, add them to the same lists;
`entity_globs: ["sensor.polestar_2_*"]` under `exclude` would cover the
whole device in one line if you'd rather exclude everything and add back
just the ones you want via `include`. Restart Home Assistant after editing
`configuration.yaml` for the change to take effect.

## Multiple vehicles

The config flow can be run multiple times with different vehicle names —
each gets its own webhook, device, and entity set, so this also works if
you (or family members) have more than one car reporting via Car Stats
Viewer.
