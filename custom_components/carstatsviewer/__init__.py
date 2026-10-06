"""The Car Stats Viewer integration.

Receives telemetry pushed by the Car Stats Viewer Android app
(https://github.com/Ixam97/CarStatsViewer) over its webhook API and exposes
it as a single Home Assistant device with proper sensor / binary_sensor /
device_tracker entities, instead of a pile of ungrouped template sensors.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aiohttp import BasicAuth, hdrs, web

from homeassistant.components import webhook

# Note: homeassistant.components.cloud is intentionally NOT imported at
# module level. It pulls in the hass_nabucasa package, which is only
# guaranteed installed once the user has actually set up Home Assistant
# Cloud. Importing it eagerly here would break this integration entirely
# on installs that don't have Cloud configured. It's imported lazily inside
# _async_get_webhook_url() instead, after confirming "cloud" is a loaded
# component.
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_CHARGING_SESSIONS,
    ATTR_DRIVING_POINTS,
    CONF_PASSWORD,
    CONF_USE_BASIC_AUTH,
    CONF_USE_CLOUDHOOK,
    CONF_USERNAME,
    CONF_VEHICLE_NAME,
    CONF_WEBHOOK_ID,
    DOMAIN,
    EVENT_CHARGING_SESSION,
    EVENT_DRIVING_POINT,
    MANUFACTURER,
    PLATFORMS,
    SIGNAL_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CarStatsViewerData:
    """Runtime state for one configured vehicle."""

    entry: ConfigEntry
    latest: dict[str, Any] = field(default_factory=dict)
    last_charging_session: dict[str, Any] | None = None
    last_driving_point: dict[str, Any] | None = None
    # Set while waiting for Home Assistant Cloud to connect so a cloudhook
    # can be retried automatically; see _async_ensure_cloud_retry_listener.
    cloud_retry_unsub: Callable[[], None] | None = None


def device_info(entry: ConfigEntry) -> dr.DeviceInfo:
    """Shared DeviceInfo so all platforms attach to the same device."""
    return dr.DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data[CONF_VEHICLE_NAME],
        manufacturer=MANUFACTURER,
        model="Car Stats Viewer webhook",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Car Stats Viewer from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    runtime = CarStatsViewerData(entry=entry)
    hass.data[DOMAIN][entry.entry_id] = runtime

    webhook_id = entry.data[CONF_WEBHOOK_ID]

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        return await _handle_webhook(hass, entry, runtime, request)

    webhook.async_register(
        hass,
        DOMAIN,
        entry.data[CONF_VEHICLE_NAME],
        webhook_id,
        handle_webhook,
        local_only=False,
    )

    entry.async_on_unload(
        lambda: webhook.async_unregister(hass, webhook_id)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    # Belt-and-braces cleanup for the cloud connection-change listener; see
    # _async_ensure_cloud_retry_listener. Safe to call even if it was
    # already cleared to None (nothing left to unsubscribe).
    entry.async_on_unload(
        lambda: runtime.cloud_retry_unsub() if runtime.cloud_retry_unsub else None
    )

    # is_retry=False: on a normal boot, Home Assistant Cloud almost always
    # hasn't finished (re)connecting yet by the time config entries are set
    # up - that's expected, not a problem, so it must not raise a Repair on
    # this first attempt. See _async_refresh_webhook_url for what happens
    # next.
    await _async_refresh_webhook_url(hass, entry, webhook_id, runtime, is_retry=False)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up the Nabu Casa cloudhook (if any) when the entry is deleted."""
    ir.async_delete_issue(hass, DOMAIN, f"cloudhook_unavailable_{entry.entry_id}")

    if not entry.data.get(CONF_USE_CLOUDHOOK):
        return
    if "cloud" not in hass.config.components:
        return
    from homeassistant.components import cloud  # noqa: PLC0415

    try:
        await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
    except cloud.CloudNotAvailable:
        pass
    except Exception:  # noqa: BLE001 - best-effort cleanup, never block removal
        _LOGGER.debug(
            "Could not clean up cloudhook for %s on removal", entry.title,
            exc_info=True,
        )


async def _async_get_webhook_url(
    hass: HomeAssistant, entry: ConfigEntry, webhook_id: str
) -> tuple[str, bool, str | None]:
    """Return (url, used_cloudhook, error_reason_if_any).

    Pure lookup with no side effects (no Repairs, no listeners) - used both
    for on-demand display (the options flow) and as the first step of
    _async_refresh_webhook_url below. Falls back to the normal
    local/external webhook URL if the user hasn't opted into a Nabu Casa
    cloudhook, or if creating one fails for any reason (Cloud not set up,
    not logged in, not connected yet, ...).
    """
    try:
        local_url = webhook.async_generate_url(hass, webhook_id)
    except Exception:  # noqa: BLE001 - e.g. NoURLAvailableError, no base URL set
        local_url = (
            f"<your Home Assistant URL>{webhook.async_generate_path(webhook_id)}"
        )

    if not entry.data.get(CONF_USE_CLOUDHOOK):
        return local_url, False, None

    if "cloud" not in hass.config.components:
        return local_url, False, "Home Assistant Cloud is not set up"

    # Deferred import: see note at the top of this module.
    from homeassistant.components import cloud  # noqa: PLC0415

    try:
        cloudhook_url = await cloud.async_get_or_create_cloudhook(
            hass, webhook_id
        )
    except cloud.CloudNotConnected:
        return local_url, False, "Home Assistant Cloud is not connected"
    except cloud.CloudNotAvailable:
        return local_url, False, "not logged in to Home Assistant Cloud"
    except Exception as err:  # noqa: BLE001 - fall back rather than fail setup
        _LOGGER.warning("Could not create Nabu Casa cloudhook: %s", err)
        return local_url, False, str(err)

    return cloudhook_url, True, None


async def _async_refresh_webhook_url(
    hass: HomeAssistant,
    entry: ConfigEntry,
    webhook_id: str,
    runtime: CarStatsViewerData,
    *,
    is_retry: bool,
) -> None:
    """Look up the webhook URL and act on the result: log it, and manage
    the cloudhook Repair issue / retry listener.

    Key behavior: on a normal boot (is_retry=False), Home Assistant Cloud
    is almost always still connecting when config entries are set up, so a
    bare "not connected yet" is expected and must NOT raise a Repair -
    that would nag on every single restart even though Cloud goes on to
    connect fine a few seconds later, requiring a manual reload just to
    clear it (the exact complaint this replaced). Instead, a one-time
    listener is registered to retry once Cloud actually connects
    (is_retry=True on that call), and a Repair is only raised if that
    retry *also* fails, or if Cloud isn't set up at all (nothing to wait
    for in that case).
    """
    vehicle_name = entry.data[CONF_VEHICLE_NAME]
    issue_id = f"cloudhook_unavailable_{entry.entry_id}"
    webhook_url, via_cloudhook, error_reason = await _async_get_webhook_url(
        hass, entry, webhook_id
    )

    if not entry.data.get(CONF_USE_CLOUDHOOK):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        _LOGGER.info(
            "Car Stats Viewer webhook for %s is available at %s",
            vehicle_name,
            webhook_url,
        )
        return

    if via_cloudhook:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        _LOGGER.info(
            "Car Stats Viewer webhook for %s is available at %s (Nabu Casa cloudhook)",
            vehicle_name,
            webhook_url,
        )
        if runtime.cloud_retry_unsub is not None:
            runtime.cloud_retry_unsub()
            runtime.cloud_retry_unsub = None
        return

    # Didn't get a cloudhook. "Cloud not set up at all" can't resolve
    # itself by waiting, so that's worth flagging immediately. Anything
    # else (not connected / not logged in / other transient error) only
    # becomes a Repair once a retry has already had a chance and still
    # failed.
    cloud_not_configured = "cloud" not in hass.config.components
    if is_retry or cloud_not_configured:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="cloudhook_unavailable",
            translation_placeholders={
                "vehicle_name": vehicle_name,
                "reason": error_reason or "unknown error",
            },
        )
    _LOGGER.info(
        "Car Stats Viewer webhook for %s is available at %s "
        "(cloudhook not ready yet: %s)",
        vehicle_name,
        webhook_url,
        error_reason,
    )

    if not cloud_not_configured:
        _async_ensure_cloud_retry_listener(hass, entry, webhook_id, runtime)


def _async_ensure_cloud_retry_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
    webhook_id: str,
    runtime: CarStatsViewerData,
) -> None:
    """Retry the cloudhook automatically once Cloud connects.

    No-ops if a listener is already registered (e.g. this is the second
    failed attempt in a row) so they don't stack up across repeated
    connect/disconnect cycles.
    """
    if runtime.cloud_retry_unsub is not None:
        return

    # Deferred import: see note at the top of this module.
    from homeassistant.components import cloud  # noqa: PLC0415

    async def _on_connection_change(state: cloud.CloudConnectionState) -> None:
        if state is cloud.CloudConnectionState.CLOUD_CONNECTED:
            await _async_refresh_webhook_url(
                hass, entry, webhook_id, runtime, is_retry=True
            )

    runtime.cloud_retry_unsub = cloud.async_listen_connection_change(
        hass, _on_connection_change
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options (auth, webhook id) change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _check_basic_auth(entry: ConfigEntry, request: web.Request) -> bool:
    """Return True if the request satisfies the configured basic auth."""
    if not entry.data.get(CONF_USE_BASIC_AUTH):
        return True

    header = request.headers.get(hdrs.AUTHORIZATION)
    if not header:
        return False
    try:
        auth = BasicAuth.decode(header)
    except ValueError:
        return False
    return (
        auth.login == entry.data.get(CONF_USERNAME, "")
        and auth.password == entry.data.get(CONF_PASSWORD, "")
    )


async def _handle_webhook(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: CarStatsViewerData,
    request: web.Request,
) -> web.Response:
    """Handle an incoming Car Stats Viewer webhook call."""
    if not _check_basic_auth(entry, request):
        return web.Response(status=401, text="Unauthorized")

    try:
        payload: dict[str, Any] = await request.json()
    except ValueError:
        _LOGGER.warning("Received non-JSON payload on %s webhook", DOMAIN)
        return web.Response(status=400, text="Invalid JSON")

    if not isinstance(payload, dict):
        return web.Response(status=400, text="Expected a JSON object")

    driving_points = payload.pop(ATTR_DRIVING_POINTS, None)
    charging_sessions = payload.pop(ATTR_CHARGING_SESSIONS, None)

    # Real-time root fields (alt, lat/lon, power, speed, SOC, ...)
    if payload:
        runtime.latest.update(payload)

    if driving_points:
        runtime.last_driving_point = driving_points[-1]
        for point in driving_points:
            hass.bus.async_fire(EVENT_DRIVING_POINT, {**point, "entry_id": entry.entry_id})

    if charging_sessions:
        runtime.last_charging_session = charging_sessions[-1]
        for session in charging_sessions:
            # Strip the (potentially long) per-point array before firing the
            # event; consumers that want it can read it from the payload
            # directly via an automation trigger.templated field if needed.
            summary = {k: v for k, v in session.items() if k != "chargingPoints"}
            hass.bus.async_fire(
                EVENT_CHARGING_SESSION, {**summary, "entry_id": entry.entry_id}
            )

    async_dispatcher_send(hass, SIGNAL_UPDATE.format(entry_id=entry.entry_id))

    return web.Response(status=200, text="OK")
