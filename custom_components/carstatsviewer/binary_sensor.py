"""Binary sensor platform for Car Stats Viewer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import CarStatsViewerData
from .const import ATTR_CHARGE_PORT_CONNECTED, DOMAIN
from .entity import CarStatsViewerEntity


@dataclass(frozen=True, kw_only=True)
class CarStatsViewerBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Car Stats Viewer binary sensor."""

    is_on_fn: Callable[[CarStatsViewerData], bool | None] = lambda data: None


BINARY_SENSOR_DESCRIPTIONS: tuple[CarStatsViewerBinarySensorDescription, ...] = (
    CarStatsViewerBinarySensorDescription(
        key=ATTR_CHARGE_PORT_CONNECTED,
        translation_key="charge_port_connected",
        name="Charge Port Connected",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn=lambda data: data.latest.get(ATTR_CHARGE_PORT_CONNECTED),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Car Stats Viewer binary sensors from a config entry."""
    runtime: CarStatsViewerData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CarStatsViewerBinarySensor(runtime, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class CarStatsViewerBinarySensor(CarStatsViewerEntity, RestoreEntity, BinarySensorEntity):
    """A boolean/tri-state Car Stats Viewer value.

    See the RestoreSensor docstring on CarStatsViewerSensor for why this
    restores its last state on a Home Assistant restart.
    """

    entity_description: CarStatsViewerBinarySensorDescription

    def __init__(
        self,
        runtime: CarStatsViewerData,
        entry: ConfigEntry,
        description: CarStatsViewerBinarySensorDescription,
    ) -> None:
        super().__init__(runtime, entry, description.key)
        self.entity_description = description
        self._restored_is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in ("on", "off"):
                self._restored_is_on = last_state.state == "on"

    @property
    def is_on(self) -> bool | None:
        value = self.entity_description.is_on_fn(self._runtime)
        return value if value is not None else self._restored_is_on
