"""Test the Daikin One+ API client."""

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.daikin_one_plus.api import DaikinApi, DaikinApiError
from homeassistant.components.daikin_one_plus.const import API_BASE_URL, TOKEN_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def test_access_token_is_cached_and_refreshed_when_rejected(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the client caches tokens and retries a rejected token."""
    device_url = f"{API_BASE_URL}/v1/devices/"
    devices_response = [
        {
            "locationName": "Home",
            "devices": [
                {
                    "id": "thermostat-id",
                    "name": "Main Room",
                    "model": "ONEPLUS",
                    "firmwareVersion": "2.3.5",
                }
            ],
        }
    ]
    device_requests = 0
    token_requests = 0

    async def get_token_response(method, url, data):
        nonlocal token_requests
        token_requests += 1
        return aioclient_mock.request(
            "post",
            url,
            json={
                "accessToken": f"token-{token_requests}",
                "accessTokenExpiresIn": 900,
            },
        )

    async def get_devices_response(method, url, data):
        nonlocal device_requests
        device_requests += 1
        if device_requests == 1:
            return aioclient_mock.request("get", url, status=401)
        return aioclient_mock.request("get", url, json=devices_response)

    aioclient_mock.post(TOKEN_URL, side_effect=get_token_response)
    aioclient_mock.get(device_url, side_effect=get_devices_response)

    api = DaikinApi(
        async_get_clientsession(hass), "api-key", "home@example.com", "integrator-token"
    )

    devices = await api.async_get_devices()
    assert devices[0]["id"] == "thermostat-id"
    await api.async_get_devices()

    assert aioclient_mock.call_count == 5
    assert aioclient_mock.mock_calls[0][0] == "POST"
    assert str(aioclient_mock.mock_calls[0][1]) == TOKEN_URL
    assert aioclient_mock.mock_calls[0][2] == {
        "email": "home@example.com",
        "integratorToken": "integrator-token",
    }
    assert aioclient_mock.mock_calls[1][0] == "GET"
    assert str(aioclient_mock.mock_calls[1][1]) == device_url
    assert aioclient_mock.mock_calls[1][3]["Authorization"] == "Bearer token-1"
    assert aioclient_mock.mock_calls[2][0] == "POST"
    assert str(aioclient_mock.mock_calls[2][1]) == TOKEN_URL
    assert aioclient_mock.mock_calls[2][2] == {
        "email": "home@example.com",
        "integratorToken": "integrator-token",
    }
    assert aioclient_mock.mock_calls[3][0] == "GET"
    assert str(aioclient_mock.mock_calls[3][1]) == device_url
    assert aioclient_mock.mock_calls[3][3]["Authorization"] == "Bearer token-2"
    assert aioclient_mock.mock_calls[4][0] == "GET"
    assert str(aioclient_mock.mock_calls[4][1]) == device_url
    assert aioclient_mock.mock_calls[4][3]["Authorization"] == "Bearer token-2"


async def test_temperature_and_schedule_updates(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test control requests use their documented endpoints and payloads."""
    device_id = "thermostat-id"
    msp_url = f"{API_BASE_URL}/v1/devices/{device_id}/msp"
    schedule_url = f"{API_BASE_URL}/v1/devices/{device_id}/schedule"
    aioclient_mock.post(
        TOKEN_URL,
        json={"accessToken": "access-token", "accessTokenExpiresIn": 900},
    )
    aioclient_mock.put(msp_url, json={"message": "Write sent"})
    aioclient_mock.put(schedule_url, json={"message": "Write sent"})

    api = DaikinApi(
        async_get_clientsession(hass), "api-key", "home@example.com", "integrator-token"
    )
    await api.async_set_temperature_range(device_id, 1, 19.5, 23.5)
    await api.async_set_schedule(device_id, True)

    assert aioclient_mock.call_count == 3
    assert aioclient_mock.mock_calls[1][0] == "PUT"
    assert str(aioclient_mock.mock_calls[1][1]) == msp_url
    assert aioclient_mock.mock_calls[1][2] == {
        "mode": 1,
        "heatSetpoint": 19.5,
        "coolSetpoint": 23.5,
    }
    assert aioclient_mock.mock_calls[1][3]["Authorization"] == "Bearer access-token"
    assert aioclient_mock.mock_calls[2][0] == "PUT"
    assert str(aioclient_mock.mock_calls[2][1]) == schedule_url
    assert aioclient_mock.mock_calls[2][2] == {"scheduleEnabled": True}


async def test_expiring_token_is_not_reused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the access token is renewed after its reported lifetime."""
    aioclient_mock.post(
        TOKEN_URL,
        json={"accessToken": "short-lived-token", "accessTokenExpiresIn": 10},
    )
    aioclient_mock.get(f"{API_BASE_URL}/v1/devices/", json=[])

    api = DaikinApi(
        async_get_clientsession(hass), "api-key", "home@example.com", "integrator-token"
    )

    await api.async_get_devices()
    await api.async_get_devices()

    assert aioclient_mock.call_count == 4


async def test_token_request_error_includes_safe_stage_and_status(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test token API errors identify the failed request without response contents."""
    aioclient_mock.post(TOKEN_URL, status=503)
    api = DaikinApi(
        async_get_clientsession(hass), "api-key", "home@example.com", "integrator-token"
    )

    with pytest.raises(DaikinApiError) as err:
        await api.async_get_devices()

    assert err.value.stage == "token request"
    assert err.value.reason == "HTTP 503"


async def test_device_list_error_includes_safe_stage_and_status(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test device API errors identify the failed request without response contents."""
    aioclient_mock.post(
        TOKEN_URL,
        json={"accessToken": "access-token", "accessTokenExpiresIn": 900},
    )
    aioclient_mock.get(f"{API_BASE_URL}/v1/devices/", status=503)
    api = DaikinApi(
        async_get_clientsession(hass), "api-key", "home@example.com", "integrator-token"
    )

    with pytest.raises(DaikinApiError) as err:
        await api.async_get_devices()

    assert err.value.stage == "device list request"
    assert err.value.reason == "HTTP 503"
