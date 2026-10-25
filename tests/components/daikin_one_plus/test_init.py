"""Test the Daikin One+ integration setup and controls."""

from datetime import timedelta

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVACMode,
)
from homeassistant.components.daikin_one_plus.const import (
    API_BASE_URL,
    DOMAIN,
    TOKEN_URL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_EMAIL,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

THERMOSTAT_ID = "thermostat-id"
THERMOSTAT_STATE = {
    "equipmentStatus": 0,
    "mode": 4,
    "modeLimit": 1,
    "modeEmHeatAvailable": True,
    "fan": 0,
    "fanCirculate": 1,
    "fanCirculateSpeed": 1,
    "heatSetpoint": 19.0,
    "coolSetpoint": 24.0,
    "setpointDelta": 2.0,
    "setpointMinimum": 10.0,
    "setpointMaximum": 32.0,
    "tempIndoor": 21.5,
    "humIndoor": 50.0,
    "tempOutdoor": 20.5,
    "humOutdoor": 50.0,
    "scheduleEnabled": True,
    "geofencingEnabled": True,
}


async def test_setup_and_controls(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup and temperature/schedule controls."""
    credentials = {
        CONF_API_KEY: "api-key",
        CONF_EMAIL: "home@example.com",
        CONF_API_TOKEN: "integrator-token",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=THERMOSTAT_ID,
        data=credentials,
        title="Main Thermostat",
    )
    entry.add_to_hass(hass)

    device_url = f"{API_BASE_URL}/v1/devices/"
    state_url = f"{API_BASE_URL}/v1/devices/{THERMOSTAT_ID}"
    aioclient_mock.post(
        TOKEN_URL,
        json={"accessToken": "access-token", "accessTokenExpiresIn": 900},
    )
    aioclient_mock.get(
        device_url,
        json=[
            {
                "locationName": "Home",
                "devices": [
                    {
                        "id": THERMOSTAT_ID,
                        "name": "Main Room",
                        "model": "ONEPLUS",
                        "firmwareVersion": "2.3.5",
                    }
                ],
            }
        ],
    )
    aioclient_mock.get(state_url, json=THERMOSTAT_STATE)
    aioclient_mock.put(f"{state_url}/msp", json={"message": "Write sent"})
    aioclient_mock.put(f"{state_url}/schedule", json={"message": "Write sent"})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(minutes=3)

    climate_entity = er.async_get(hass).async_get_entity_id(
        "climate", DOMAIN, THERMOSTAT_ID
    )
    assert climate_entity is not None
    climate_state = hass.states.get(climate_entity)
    assert climate_state is not None
    assert climate_state.attributes["current_temperature"] == 21.5
    assert climate_state.attributes["target_temp_low"] == 19.0
    assert climate_state.attributes["target_temp_high"] == 24.0
    assert climate_state.state == HVACMode.HEAT

    assert hass.states.get("sensor.main_room_indoor_humidity").state == "50.0"
    assert hass.states.get("sensor.main_room_outdoor_temperature").state == "20.5"
    assert hass.states.get("sensor.main_room_outdoor_humidity").state == "50.0"
    assert hass.states.get("sensor.main_room_equipment_status").state == "0"
    assert hass.states.get("sensor.main_room_mode_limit").state == "1"
    assert hass.states.get("sensor.main_room_fan_mode").state == "0"
    assert hass.states.get("sensor.main_room_fan_circulation").state == "1"
    assert hass.states.get("sensor.main_room_fan_circulation_speed").state == "1"
    assert (
        hass.states.get("sensor.main_room_minimum_setpoint_difference").state == "2.0"
    )
    assert (
        hass.states.get("binary_sensor.main_room_emergency_heat_available").state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.main_room_emergency_heat_active").state == "on"
    )
    assert hass.states.get("binary_sensor.main_room_geofencing_enabled").state == "on"

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            ATTR_ENTITY_ID: climate_entity,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_TARGET_TEMP_HIGH: 24.5,
        },
        blocking=True,
    )
    assert hass.states.get("switch.main_room_schedule").state == STATE_OFF
    assert (
        hass.states.get("binary_sensor.main_room_geofencing_enabled").state == STATE_OFF
    )
    assert aioclient_mock.mock_calls[-1][2] == {
        "mode": 4,
        "heatSetpoint": 20.0,
        "coolSetpoint": 24.5,
    }

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: climate_entity, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-1][2]["mode"] == 1

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: climate_entity, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-1][2]["mode"] == 0

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: climate_entity, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-1][2]["mode"] == 3

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: climate_entity, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-1][2] == {
        "mode": 2,
        "heatSetpoint": 20.0,
        "coolSetpoint": 24.5,
    }

    switch_entity = er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{THERMOSTAT_ID}_schedule"
    )
    assert switch_entity is not None
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: switch_entity},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-1][2] == {"scheduleEnabled": False}

    assert entry.data == credentials
    assert await hass.config_entries.async_unload(entry.entry_id)
