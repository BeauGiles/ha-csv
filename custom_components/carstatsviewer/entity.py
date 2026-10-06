"""Shared base entity for Car Stats Viewer platforms."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import CarStatsViewerData, device_info
from .const import DOMAIN, SIGNAL_UPDATE


class CarStatsViewerEntity(Entity):
    """Base entity: pushed updates, no polling, shared device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: CarStatsViewerData,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        self._runtime = runtime
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to dispatcher updates once added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(entry_id=self._entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Handle a dispatcher signal.

        Must be decorated @callback: without it, Home Assistant's job
        dispatcher can't tell this is a cheap, non-blocking function and
        may run it in an executor thread instead of the event loop.
        async_write_ha_state() then trips the thread-safety guard and the
        state update is dropped (logged as a RuntimeError), which is why
        entities can stay stuck at "unavailable" even though the webhook is
        receiving data successfully.
        """
        self.async_write_ha_state()
