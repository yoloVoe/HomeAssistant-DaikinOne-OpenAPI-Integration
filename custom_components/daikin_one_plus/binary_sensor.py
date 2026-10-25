"""Binary sensor platform for Daikin One+."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DaikinOnePlusConfigEntry
from .api import ThermostatState
from .coordinator import DaikinOnePlusCoordinator
from .entity import DaikinOnePlusEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DaikinBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Daikin binary sensor."""

    value_fn: Callable[[ThermostatState], bool]


BINARY_SENSORS: tuple[DaikinBinarySensorEntityDescription, ...] = (
    DaikinBinarySensorEntityDescription(
        key="modeEmHeatAvailable",
        translation_key="emergency_heat_available",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state["modeEmHeatAvailable"],
    ),
    DaikinBinarySensorEntityDescription(
        key="mode",
        translation_key="emergency_heat_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state["mode"] == 4,
    ),
    DaikinBinarySensorEntityDescription(
        key="geofencingEnabled",
        translation_key="geofencing_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state["geofencingEnabled"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinOnePlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Daikin One+ binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        DaikinOnePlusBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class DaikinOnePlusBinarySensor(DaikinOnePlusEntity, BinarySensorEntity):
    """Represent a Daikin One+ binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DaikinOnePlusCoordinator,
        description: DaikinBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._value_fn = description.value_fn
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return the current binary sensor value."""
        return self._value_fn(self.coordinator.data)
