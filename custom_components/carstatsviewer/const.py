"""Constants for the Car Stats Viewer integration.

Reference: https://github.com/Ixam97/CarStatsViewer/blob/master/docs/APIDOC.md
"""
from __future__ import annotations

DOMAIN = "carstatsviewer"
PLATFORMS = ["sensor", "binary_sensor", "device_tracker"]

MANUFACTURER = "CarStatsViewer"

# Config entry keys
CONF_VEHICLE_NAME = "vehicle_name"
CONF_WEBHOOK_ID = "webhook_id"
CONF_USE_BASIC_AUTH = "use_basic_auth"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_USE_CLOUDHOOK = "use_cloudhook"

DEFAULT_VEHICLE_NAME = "Car"

# Signal fired via async_dispatcher_send whenever a new payload arrives for
# a given config entry. Entities subscribe to this to update their state.
SIGNAL_UPDATE = f"{DOMAIN}_update_{{entry_id}}"

# Events fired on the HA event bus for automation use. These are *not*
# turned into entities because they are arrays of historical points, not a
# single current state.
EVENT_DRIVING_POINT = f"{DOMAIN}_driving_point"
EVENT_CHARGING_SESSION = f"{DOMAIN}_charging_session"

# --- Real-time payload keys (API 2.0 / 2.1 root object) -------------------
ATTR_ALT = "alt"
ATTR_AMBIENT_TEMPERATURE = "ambientTemperature"
ATTR_API_VERSION = "apiVersion"
ATTR_APP_VERSION = "appVersion"
ATTR_BATTERY_LEVEL = "batteryLevel"  # Wh
ATTR_CHARGE_PORT_CONNECTED = "chargePortConnected"
ATTR_IGNITION_STATE = "ignitionState"
ATTR_LAT = "lat"
ATTR_LON = "lon"
ATTR_POWER = "power"  # mW
ATTR_SELECTED_GEAR = "selectedGear"
ATTR_SPEED = "speed"  # m/s
ATTR_STATE_OF_CHARGE = "stateOfCharge"  # 0.0 - 1.0
ATTR_TIMESTAMP = "timestamp"  # epoch ms

# --- Optional API 2.1 arrays -----------------------------------------------
ATTR_DRIVING_POINTS = "drivingPoints"
ATTR_CHARGING_SESSIONS = "chargingSessions"

# Charging session summary fields (used to populate "last session" sensors)
ATTR_CHARGE_TIME = "chargeTime"  # ms
ATTR_CHARGED_ENERGY = "charged_energy"  # Wh
ATTR_CHARGED_SOC = "charged_soc"
ATTR_CHARGING_SESSION_ID = "charging_session_id"
ATTR_END_EPOCH_TIME = "end_epoch_time"
ATTR_START_EPOCH_TIME = "start_epoch_time"
ATTR_OUTSIDE_TEMP = "outside_temp"

GEAR_ICONS = {
    "P": "mdi:alpha-p-circle",
    "R": "mdi:alpha-r-circle",
    "N": "mdi:alpha-n-circle",
    "D": "mdi:alpha-d-circle",
}

# Car Stats Viewer reports ignitionState as the human-readable name of
# Android Automotive's android.car.VehicleIgnitionState property, which has
# six values, not just on/off: UNDEFINED, LOCK, OFF, ACC ("accessory" - the
# radio/accessories are powered but the engine and cluster are off), ON, and
# START (cranking). Treating this as a plain on/off binary_sensor meant
# every ACC reading (very common - e.g. a Polestar/Volvo sits in ACC for a
# while after you get out, or briefly on start) fell through to "Unknown".
# Normalized to a small set of canonical display labels so it works
# regardless of the exact casing/spelling the app sends; unrecognized raw
# values fall back to None (which in turn falls back to the last restored
# value rather than a hard "Unknown").
IGNITION_STATE_OPTIONS = ["off", "accessory", "on", "starting", "locked", "undefined"]
IGNITION_STATE_MAP = {
    "off": "off",
    "on": "on",
    "acc": "accessory",
    "accessory": "accessory",
    "start": "starting",
    "starting": "starting",
    "cranking": "starting",
    "lock": "locked",
    "locked": "locked",
    "undefined": "undefined",
}
IGNITION_STATE_ICONS = {
    "off": "mdi:car-key",
    "accessory": "mdi:car-key",
    "on": "mdi:car-key",
    "starting": "mdi:engine",
    "locked": "mdi:steering",
    "undefined": "mdi:help",
}
