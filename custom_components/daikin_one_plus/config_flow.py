"""Config flow for the daikin_one_plus_thermostat integration."""

import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow as BaseConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DaikinApi, DaikinApiError, DaikinAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        # Developer API key
        probatio.Required(CONF_API_KEY): str,
        # Email of user
        probatio.Required(CONF_EMAIL): str,
        # Integrator API token of user
        probatio.Required(CONF_API_TOKEN): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = DaikinApi(
        async_get_clientsession(hass),
        data[CONF_API_KEY],
        data[CONF_EMAIL],
        data[CONF_API_TOKEN],
    )
    try:
        devices = await api.async_get_devices()
    except DaikinAuthError as err:
        raise InvalidAuth from err
    except DaikinApiError as err:
        raise CannotConnect(err.stage, err.reason) from err
    if not devices:
        raise NoThermostat
    return devices[0]["id"]


class ConfigFlow(BaseConfigFlow, domain=DOMAIN):
    """Handle a config flow for daikin_one_plus_thermostat."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            normalized_input = {
                CONF_API_KEY: user_input[CONF_API_KEY].strip(),
                CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                CONF_API_TOKEN: user_input[CONF_API_TOKEN].strip(),
            }
            try:
                device_id = await validate_input(self.hass, normalized_input)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                description_placeholders = {
                    "stage": err.stage,
                    "reason": err.reason,
                }
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoThermostat:
                errors["base"] = "no_thermostat"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Main Thermostat", data=normalized_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""

    def __init__(self, stage: str, reason: str) -> None:
        """Initialize the connection error with safe diagnostic details."""
        super().__init__(stage, reason)
        self.stage = stage
        self.reason = reason


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


class NoThermostat(Exception):
    """Error to indicate that no thermostat is registered to the account."""
