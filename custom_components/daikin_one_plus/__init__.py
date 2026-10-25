"""The Daikin One+ integration."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DaikinApi, DaikinApiError, DaikinAuthError
from .coordinator import DaikinOnePlusCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]
POLL_INTERVAL = timedelta(minutes=3)

type DaikinOnePlusConfigEntry = ConfigEntry[DaikinOnePlusCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: DaikinOnePlusConfigEntry
) -> bool | None:
    """Set up Daikin One+ from a config entry."""
    api = DaikinApi(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        entry.data[CONF_EMAIL],
        entry.data[CONF_API_TOKEN],
    )

    try:
        devices = await api.async_get_devices()
    except DaikinAuthError as err:
        raise ConfigEntryAuthFailed from err
    except DaikinApiError as err:
        raise ConfigEntryNotReady from err

    if entry.unique_id is None:
        raise ConfigEntryNotReady("The thermostat has no unique ID")
    # The device list order can change, so reconnect to the ID saved at setup.
    device = next(
        (device for device in devices if device["id"] == entry.unique_id), None
    )
    if device is None:
        raise ConfigEntryNotReady("The configured thermostat was not found")

    coordinator = DaikinOnePlusCoordinator(
        hass, api, entry, device, update_interval=POLL_INTERVAL
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if __package__.startswith("custom_components."):
        return True
    return None


async def async_unload_entry(
    hass: HomeAssistant, entry: DaikinOnePlusConfigEntry
) -> bool | None:
    """Unload a config entry."""
    if __package__.startswith("custom_components."):
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    return None
