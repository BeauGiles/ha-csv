"""Device tracker platform for Car Stats Viewer.

Combines the separate `lat` / `lon` template sensors from the old webhook
automation into a single GPS-sourced device_tracker entity, which is the
correct entity type for a moving position and plugs into the map/history
the way a phone tracker would.
"""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
# Note: as of recent Home Assistant releases, TrackerEntity/SourceType moved
# from homeassistant.components.device_tracker.config_entry to the
# top-level device_tracker package; the old path is deprecated (removal
# targeted for 2027.6) so we import from the top level directly.
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import CarStatsViewerData
from .const import ATTR_LAT, ATTR_LON, DOMAIN
from .entity import CarStatsViewerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Car Stats Viewer device tracker from a config entry."""
    runtime: CarStatsViewerData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CarStatsViewerDeviceTracker(runtime, entry)])


class CarStatsViewerDeviceTracker(CarStatsViewerEntity, RestoreEntity, TrackerEntity):
    """GPS position reported by the Car Stats Viewer app.

    See the RestoreSensor docstring on CarStatsViewerSensor (sensor.py) for
    why this restores its last known position on a Home Assistant restart
    instead of showing "Unknown" until the next GPS fix arrives.
    """

    _attr_name = "Location"
    _attr_icon = "mdi:crosshairs-gps"

    def __init__(self, runtime: CarStatsViewerData, entry: ConfigEntry) -> None:
        super().__init__(runtime, entry, "location")
        self._restored_lat: float | None = None
        self._restored_lon: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._restored_lat = last_state.attributes.get(ATTR_LATITUDE)
            self._restored_lon = last_state.attributes.get(ATTR_LONGITUDE)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        value = self._runtime.latest.get(ATTR_LAT)
        return float(value) if value is not None else self._restored_lat

    @property
    def longitude(self) -> float | None:
        value = self._runtime.latest.get(ATTR_LON)
        return float(value) if value is not None else self._restored_lon

    @property
    def available(self) -> bool:
        return self.latitude is not None and self.longitude is not None
