"""Config flow for Car Stats Viewer."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_PASSWORD,
    CONF_USE_BASIC_AUTH,
    CONF_USE_CLOUDHOOK,
    CONF_USERNAME,
    CONF_VEHICLE_NAME,
    CONF_WEBHOOK_ID,
    DEFAULT_VEHICLE_NAME,
    DOMAIN,
)


class CarStatsViewerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Car Stats Viewer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step: name the vehicle and pick auth options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            use_basic_auth = user_input.get(CONF_USE_BASIC_AUTH, False)
            if use_basic_auth and not user_input.get(CONF_PASSWORD):
                errors["base"] = "password_required"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_VEHICLE_NAME].strip().lower()
                )
                self._abort_if_unique_id_configured()

                webhook_id = webhook.async_generate_id()
                # Stashed on the flow instance and picked up by
                # async_step_confirm below; a ConfigFlow instance lives for
                # the whole flow, so this is safe across steps.
                self._pending_data = {
                    CONF_VEHICLE_NAME: user_input[CONF_VEHICLE_NAME].strip(),
                    CONF_WEBHOOK_ID: webhook_id,
                    CONF_USE_BASIC_AUTH: use_basic_auth,
                    CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                    CONF_USE_CLOUDHOOK: user_input.get(CONF_USE_CLOUDHOOK, False),
                }
                return await self.async_step_confirm()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_VEHICLE_NAME, default=DEFAULT_VEHICLE_NAME
                ): str,
                vol.Optional(CONF_USE_BASIC_AUTH, default=False): bool,
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_USE_CLOUDHOOK, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the webhook URL once, then create the entry.

        This is the only place the URL is shown automatically. It is
        deliberately NOT re-shown as a notification on every restart /
        reload - see the note in __init__.py's async_setup_entry. You can
        always look it up again later via Configure on the integration.
        """
        data = self._pending_data

        if user_input is not None:
            return self.async_create_entry(title=data[CONF_VEHICLE_NAME], data=data)

        try:
            webhook_url = webhook.async_generate_url(
                self.hass, data[CONF_WEBHOOK_ID]
            )
        except Exception:  # noqa: BLE001 - e.g. no base URL configured yet
            webhook_url = (
                "<your Home Assistant URL>"
                f"{webhook.async_generate_path(data[CONF_WEBHOOK_ID])}"
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"webhook_url": webhook_url},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CarStatsViewerOptionsFlow:
        """Get the options flow for this handler."""
        return CarStatsViewerOptionsFlow()


class CarStatsViewerOptionsFlow(config_entries.OptionsFlow):
    """Options flow: lets the user rotate the webhook or auth after setup.

    No __init__ / stored config_entry here on purpose: since HA 2024.11
    `self.config_entry` is provided automatically by the base class, and
    manually assigning it is deprecated (removed behavior as of 2025.12).
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        current = self.config_entry.data

        if user_input is not None:
            use_basic_auth = user_input.get(CONF_USE_BASIC_AUTH, False)
            if use_basic_auth and not user_input.get(CONF_PASSWORD):
                errors["base"] = "password_required"
            else:
                new_data = dict(current)
                new_data[CONF_USE_BASIC_AUTH] = use_basic_auth
                new_data[CONF_USERNAME] = user_input.get(CONF_USERNAME, "")
                new_data[CONF_PASSWORD] = user_input.get(CONF_PASSWORD, "")
                new_data[CONF_USE_CLOUDHOOK] = user_input.get(
                    CONF_USE_CLOUDHOOK, False
                )
                if user_input.get("regenerate_webhook_id"):
                    new_data[CONF_WEBHOOK_ID] = webhook.async_generate_id()
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USE_BASIC_AUTH,
                    default=current.get(CONF_USE_BASIC_AUTH, False),
                ): bool,
                vol.Optional(
                    CONF_USERNAME, default=current.get(CONF_USERNAME, "")
                ): str,
                vol.Optional(
                    CONF_PASSWORD, default=current.get(CONF_PASSWORD, "")
                ): str,
                vol.Optional(
                    CONF_USE_CLOUDHOOK,
                    default=current.get(CONF_USE_CLOUDHOOK, False),
                ): bool,
                vol.Optional("regenerate_webhook_id", default=False): bool,
            }
        )

        # Deferred import: avoids a circular import at module load time
        # (this module isn't imported by __init__.py, but importing at the
        # top would still run __init__.py's module body before this class
        # finishes defining, since HA imports config_flow.py on demand).
        from . import _async_get_webhook_url  # noqa: PLC0415

        webhook_url, via_cloudhook, _ = await _async_get_webhook_url(
            self.hass, self.config_entry, current[CONF_WEBHOOK_ID]
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "webhook_url": webhook_url,
                "via_cloudhook": "yes" if via_cloudhook else "no",
            },
        )
