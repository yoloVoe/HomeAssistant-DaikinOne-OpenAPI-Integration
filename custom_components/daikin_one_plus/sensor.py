"""Sensor platform for Daikin One+."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DaikinOnePlusConfigEntry
from .api import ThermostatState
from .coordinator import DaikinOnePlusCoordinator
from .entity import DaikinOnePlusEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DaikinSensorEntityDescription(SensorEntityDescription):
    """Describe a Daikin sensor."""

    value_fn: Callable[[ThermostatState], int | float]


SENSORS: tuple[DaikinSensorEntityDescription, ...] = (
    DaikinSensorEntityDescription(
        key="equipmentStatus",
        translation_key="equipment_status",
        value_fn=lambda state: state["equipmentStatus"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DaikinSensorEntityDescription(
        key="modeLimit",
        translation_key="mode_limit",
        value_fn=lambda state: state["modeLimit"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DaikinSensorEntityDescription(
        key="fan",
        translation_key="fan_mode",
        value_fn=lambda state: state["fan"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DaikinSensorEntityDescription(
        key="fanCirculate",
        translation_key="fan_circulate",
        value_fn=lambda state: state["fanCirculate"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DaikinSensorEntityDescription(
        key="fanCirculateSpeed",
        translation_key="fan_circulate_speed",
        value_fn=lambda state: state["fanCirculateSpeed"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DaikinSensorEntityDescription(
        key="setpointDelta",
        translation_key="setpoint_delta",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state["setpointDelta"],
    ),
    DaikinSensorEntityDescription(
        key="humIndoor",
        translation_key="indoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state["humIndoor"],
    ),
    DaikinSensorEntityDescription(
        key="tempOutdoor",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state["tempOutdoor"],
    ),
    DaikinSensorEntityDescription(
        key="humOutdoor",
        translation_key="outdoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state["humOutdoor"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinOnePlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Daikin One+ sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        DaikinOnePlusSensor(coordinator, description) for description in SENSORS
    )


class DaikinOnePlusSensor(DaikinOnePlusEntity, SensorEntity):
    """Represent a Daikin One+ sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DaikinOnePlusCoordinator,
        description: DaikinSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._value_fn = description.value_fn
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> int | float:
        """Return the current sensor value."""
        return self._value_fn(self.coordinator.data)
