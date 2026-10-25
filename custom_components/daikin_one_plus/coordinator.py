"""Coordinator for the Daikin One+ integration."""

from datetime import timedelta
import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    DaikinApi,
    DaikinApiError,
    DaikinAuthError,
    DaikinDevice,
    ThermostatState,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type DaikinOnePlusConfigEntry = ConfigEntry[DaikinOnePlusCoordinator]


class DaikinOnePlusCoordinator(DataUpdateCoordinator[ThermostatState]):
    """Fetch and distribute thermostat state."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DaikinApi,
        config_entry: DaikinOnePlusConfigEntry,
        device: DaikinDevice,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.api = api
        self.device = device
        self.device_id = device["id"]

    @override
    async def _async_update_data(self) -> ThermostatState:
        """Fetch latest thermostat data."""
        try:
            return await self.api.async_get_thermostat(self.device_id)
        except DaikinAuthError as err:
            raise ConfigEntryAuthFailed from err
        except DaikinApiError as err:
            raise UpdateFailed(err) from err

    async def async_set_temperature_range(
        self, mode: int, heat_setpoint: float, cool_setpoint: float
    ) -> None:
        """Update the heat and cool setpoints."""
        await self.api.async_set_temperature_range(
            self.device_id, mode, heat_setpoint, cool_setpoint
        )
        if self.data is not None:
            # Daikin documents that manual setpoint/mode updates disable both.
            self.async_set_updated_data(
                {
                    **self.data,
                    "mode": mode,
                    "heatSetpoint": heat_setpoint,
                    "coolSetpoint": cool_setpoint,
                    "scheduleEnabled": False,
                    "geofencingEnabled": False,
                }
            )

    async def async_set_schedule(self, enabled: bool) -> None:
        """Update schedule state."""
        await self.api.async_set_schedule(self.device_id, enabled)
        if self.data is not None:
            self.async_set_updated_data({**self.data, "scheduleEnabled": enabled})
