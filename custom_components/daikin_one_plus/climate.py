"""Climate platform for Daikin One+."""

from typing import Any, override

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DaikinOnePlusConfigEntry
from .api import ThermostatState
from .coordinator import DaikinOnePlusCoordinator
from .entity import DaikinOnePlusEntity

MODE_TO_HVAC_MODE = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.AUTO,
    4: HVACMode.HEAT,
}
# Home Assistant has no emergency-heat HVACMode; expose mode 4 as Heat and
# report the emergency-heat state separately.
HVAC_MODE_TO_MODE = {
    HVACMode.OFF: 0,
    HVACMode.HEAT: 1,
    HVACMode.COOL: 2,
    HVACMode.AUTO: 3,
}
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinOnePlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Daikin One+ climate entity."""
    async_add_entities([DaikinOnePlusClimate(entry.runtime_data)])


class DaikinOnePlusClimate(DaikinOnePlusEntity, ClimateEntity):
    """Represent a Daikin One+ thermostat."""

    _attr_has_entity_name = True
    _attr_translation_key = "thermostat"
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
    ]
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: DaikinOnePlusCoordinator) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device["id"]

    @property
    def _state(self) -> ThermostatState:
        """Return current thermostat state."""
        return self.coordinator.data

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the current operating mode."""
        return MODE_TO_HVAC_MODE.get(self._state["mode"], HVACMode.AUTO)

    @property
    @override
    def native_current_temperature(self) -> float:
        """Return the current indoor temperature."""
        return self._state["tempIndoor"]

    @property
    @override
    def native_target_temperature_low(self) -> float:
        """Return the current heat setpoint."""
        return self._state["heatSetpoint"]

    @property
    @override
    def native_target_temperature_high(self) -> float:
        """Return the current cool setpoint."""
        return self._state["coolSetpoint"]

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum allowed temperature."""
        return self._state["setpointMinimum"]

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum allowed temperature."""
        return self._state["setpointMaximum"]

    @property
    @override
    def target_temperature_step(self) -> float:
        """Return the setpoint step size."""
        return 1.0

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set heat and cool setpoints."""
        state = self._state
        heat_setpoint = kwargs.get(ATTR_TARGET_TEMP_LOW, state["heatSetpoint"])
        cool_setpoint = kwargs.get(ATTR_TARGET_TEMP_HIGH, state["coolSetpoint"])
        self._validate_setpoints(heat_setpoint, cool_setpoint)
        await self.coordinator.async_set_temperature_range(
            state["mode"], heat_setpoint, cool_setpoint
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the thermostat operating mode."""
        mode = HVAC_MODE_TO_MODE.get(hvac_mode)
        if mode is None:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        state = self._state
        await self.coordinator.async_set_temperature_range(
            mode, state["heatSetpoint"], state["coolSetpoint"]
        )

    def _validate_setpoints(self, heat_setpoint: float, cool_setpoint: float) -> None:
        """Validate the range against the thermostat's limits."""
        state = self._state
        minimum = state["setpointMinimum"]
        maximum = state["setpointMaximum"]
        # Daikin requires this minimum gap between heat and cool setpoints.
        if (
            heat_setpoint < minimum
            or heat_setpoint > maximum
            or cool_setpoint < minimum
            or cool_setpoint > maximum
            or heat_setpoint + state["setpointDelta"] > cool_setpoint
        ):
            raise HomeAssistantError("Temperature range is outside thermostat limits")
