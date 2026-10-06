"""Sensor platform for Car Stats Viewer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CarStatsViewerData
from .const import (
    ATTR_ALT,
    ATTR_AMBIENT_TEMPERATURE,
    ATTR_API_VERSION,
    ATTR_APP_VERSION,
    ATTR_BATTERY_LEVEL,
    ATTR_CHARGE_TIME,
    ATTR_CHARGED_ENERGY,
    ATTR_END_EPOCH_TIME,
    ATTR_IGNITION_STATE,
    ATTR_POWER,
    ATTR_SELECTED_GEAR,
    ATTR_SPEED,
    ATTR_STATE_OF_CHARGE,
    ATTR_TIMESTAMP,
    DOMAIN,
    GEAR_ICONS,
    IGNITION_STATE_ICONS,
    IGNITION_STATE_MAP,
    IGNITION_STATE_OPTIONS,
)
from .entity import CarStatsViewerEntity


def _ms_to_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return dt_util.utc_from_timestamp(float(value) / 1000)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class CarStatsViewerSensorDescription(SensorEntityDescription):
    """Describes a Car Stats Viewer sensor and how to compute its value."""

    value_fn: Callable[[CarStatsViewerData], Any] = lambda data: None
    icon_fn: Callable[[CarStatsViewerData], str | None] | None = None


SENSOR_DESCRIPTIONS: tuple[CarStatsViewerSensorDescription, ...] = (
    CarStatsViewerSensorDescription(
        key=ATTR_ALT,
        translation_key="altitude",
        name="Altitude",
        icon="mdi:altimeter",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.latest.get(ATTR_ALT),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_AMBIENT_TEMPERATURE,
        translation_key="ambient_temperature",
        name="Ambient Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.latest.get(ATTR_AMBIENT_TEMPERATURE),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_BATTERY_LEVEL,
        translation_key="battery_level",
        name="Battery Level",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            float(data.latest[ATTR_BATTERY_LEVEL]) / 1000
            if data.latest.get(ATTR_BATTERY_LEVEL) is not None
            else None
        ),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_POWER,
        translation_key="current_power",
        name="Current Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            float(data.latest[ATTR_POWER]) / 1_000_000
            if data.latest.get(ATTR_POWER) is not None
            else None
        ),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_SELECTED_GEAR,
        translation_key="gear",
        name="Gear",
        device_class=SensorDeviceClass.ENUM,
        options=["P", "R", "N", "D"],
        value_fn=lambda data: data.latest.get(ATTR_SELECTED_GEAR),
        icon_fn=lambda data: GEAR_ICONS.get(
            data.latest.get(ATTR_SELECTED_GEAR), "mdi:car"
        ),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_IGNITION_STATE,
        translation_key="ignition",
        name="Ignition",
        device_class=SensorDeviceClass.ENUM,
        options=IGNITION_STATE_OPTIONS,
        value_fn=lambda data: IGNITION_STATE_MAP.get(
            str(data.latest.get(ATTR_IGNITION_STATE, "")).strip().lower()
        ),
        icon_fn=lambda data: IGNITION_STATE_ICONS.get(
            IGNITION_STATE_MAP.get(
                str(data.latest.get(ATTR_IGNITION_STATE, "")).strip().lower()
            ),
            "mdi:car-key",
        ),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_SPEED,
        translation_key="speed",
        name="Speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: (
            float(data.latest[ATTR_SPEED]) * 3.6
            if data.latest.get(ATTR_SPEED) is not None
            else None
        ),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_STATE_OF_CHARGE,
        translation_key="state_of_charge",
        name="State of Charge",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(float(data.latest[ATTR_STATE_OF_CHARGE]) * 100, 1)
            if data.latest.get(ATTR_STATE_OF_CHARGE) is not None
            else None
        ),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_TIMESTAMP,
        translation_key="last_update",
        name="Last Update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _ms_to_dt(data.latest.get(ATTR_TIMESTAMP)),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_API_VERSION,
        translation_key="api_version",
        name="API Version",
        icon="mdi:api",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.latest.get(ATTR_API_VERSION),
    ),
    CarStatsViewerSensorDescription(
        key=ATTR_APP_VERSION,
        translation_key="app_version",
        name="App Version",
        icon="mdi:cellphone-information",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.latest.get(ATTR_APP_VERSION),
    ),
    # --- Optional API 2.1 "last charging session" summary -----------------
    CarStatsViewerSensorDescription(
        key="last_charging_energy",
        translation_key="last_charging_energy",
        name="Last Charging Energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        # TOTAL (not TOTAL_INCREASING): this is a per-session snapshot that
        # can legitimately be smaller than the previous session's value, so
        # it must not be treated as a monotonically increasing meter.
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda data: (
            round(float(data.last_charging_session[ATTR_CHARGED_ENERGY]) / 1000, 2)
            if data.last_charging_session
            and data.last_charging_session.get(ATTR_CHARGED_ENERGY) is not None
            else None
        ),
    ),
    CarStatsViewerSensorDescription(
        key="last_charging_duration",
        translation_key="last_charging_duration",
        name="Last Charging Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            round(float(data.last_charging_session[ATTR_CHARGE_TIME]) / 60000, 1)
            if data.last_charging_session
            and data.last_charging_session.get(ATTR_CHARGE_TIME) is not None
            else None
        ),
    ),
    CarStatsViewerSensorDescription(
        key="last_charging_session_end",
        translation_key="last_charging_session_end",
        name="Last Charging Session End",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _ms_to_dt(data.last_charging_session.get(ATTR_END_EPOCH_TIME))
            if data.last_charging_session
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Car Stats Viewer sensors from a config entry."""
    runtime: CarStatsViewerData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CarStatsViewerSensor(runtime, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class CarStatsViewerSensor(CarStatsViewerEntity, RestoreSensor):
    """A single Car Stats Viewer telemetry value.

    Mixes in RestoreSensor so the last known value survives a Home
    Assistant restart: runtime.latest starts empty every boot (it's push-
    based, in-memory only), so without this every sensor would show
    "Unknown" until the next webhook call happens to include that
    particular field again - which the old trigger-based template sensors
    never suffered from, since HA's template platform restores state
    automatically. The restored value is only ever used as a fallback: the
    moment real webhook data arrives for a field (value_fn stops returning
    None), live data takes over and wins permanently for the rest of that
    boot session.
    """

    entity_description: CarStatsViewerSensorDescription

    def __init__(
        self,
        runtime: CarStatsViewerData,
        entry: ConfigEntry,
        description: CarStatsViewerSensorDescription,
    ) -> None:
        super().__init__(runtime, entry, description.key)
        self.entity_description = description
        self._restored_value: Any = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_sensor_data()) is not None:
            self._restored_value = last_data.native_value

    @property
    def native_value(self) -> Any:
        value = self.entity_description.value_fn(self._runtime)
        return value if value is not None else self._restored_value

    @property
    def icon(self) -> str | None:
        if self.entity_description.icon_fn is not None:
            return self.entity_description.icon_fn(self._runtime)
        return self.entity_description.icon
