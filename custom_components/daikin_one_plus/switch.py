"""Switch platform for Daikin One+."""

from typing import override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DaikinOnePlusConfigEntry
from .coordinator import DaikinOnePlusCoordinator
from .entity import DaikinOnePlusEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinOnePlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Daikin One+ schedule switch."""
    async_add_entities([DaikinOnePlusScheduleSwitch(entry.runtime_data)])


class DaikinOnePlusScheduleSwitch(DaikinOnePlusEntity, SwitchEntity):
    """Enable or disable the thermostat schedule."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule"

    def __init__(self, coordinator: DaikinOnePlusCoordinator) -> None:
        """Initialize the schedule switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_schedule"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the schedule is enabled."""
        return self.coordinator.data["scheduleEnabled"]

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable the schedule."""
        await self.coordinator.async_set_schedule(True)

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable the schedule."""
        await self.coordinator.async_set_schedule(False)
