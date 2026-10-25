"""Client for the Daikin One+ API."""

import asyncio
from collections.abc import Mapping
import time
from typing import TypedDict, cast

import aiohttp

from .const import API_BASE_URL, TOKEN_URL

_TOKEN_REFRESH_BUFFER = 30
_MAX_CONCURRENT_REQUESTS = 3


class DaikinApiError(Exception):
    """Error communicating with the Daikin API."""

    def __init__(self, stage: str, reason: str) -> None:
        """Initialize the API error with safe diagnostic details."""
        super().__init__(stage, reason)
        self.stage = stage
        self.reason = reason


class DaikinAuthError(DaikinApiError):
    """Error authenticating with the Daikin API."""

    def __init__(self, message: str) -> None:
        """Initialize the authentication error."""
        super().__init__("authentication", message)


class DaikinDevice(TypedDict):
    """Thermostat information from the devices endpoint."""

    id: str
    name: str
    model: str
    firmwareVersion: str


class DaikinLocation(TypedDict):
    """Location data from the devices endpoint."""

    locationName: str
    devices: list[DaikinDevice]


class ThermostatState(TypedDict):
    """Thermostat state returned by the Daikin API."""

    equipmentStatus: int
    mode: int
    modeLimit: int
    modeEmHeatAvailable: bool
    fan: int
    fanCirculate: int
    fanCirculateSpeed: int
    heatSetpoint: float
    coolSetpoint: float
    setpointDelta: float
    setpointMinimum: float
    setpointMaximum: float
    tempIndoor: float
    humIndoor: float
    tempOutdoor: float
    humOutdoor: float
    scheduleEnabled: bool
    geofencingEnabled: bool


class DaikinApi:
    """Asynchronous Daikin One+ API client with in-memory token caching."""

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, email: str, api_token: str
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._api_key = api_key
        self._email = email
        self._api_token = api_token
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        # Tokens are short-lived; keep them only for this runtime API client.
        self._token_lock = asyncio.Lock()
        # Daikin limits concurrent API requests for an account.
        self._request_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)

    async def async_get_devices(self) -> list[DaikinDevice]:
        """Get the thermostats registered to the account."""
        locations = cast(
            list[DaikinLocation],
            await self._async_request(
                "GET", "/v1/devices/", stage="device list request"
            ),
        )
        return [device for location in locations for device in location["devices"]]

    async def async_get_thermostat(self, device_id: str) -> ThermostatState:
        """Get thermostat state."""
        return cast(
            ThermostatState,
            await self._async_request(
                "GET",
                f"/v1/devices/{device_id}",
                stage="thermostat state request",
            ),
        )

    async def async_set_temperature_range(
        self,
        device_id: str,
        mode: int,
        heat_setpoint: float,
        cool_setpoint: float,
    ) -> None:
        """Set operating mode and heat/cool setpoints."""
        await self._async_request(
            "PUT",
            f"/v1/devices/{device_id}/msp",
            stage="temperature update",
            json={
                "mode": mode,
                "heatSetpoint": heat_setpoint,
                "coolSetpoint": cool_setpoint,
            },
            expect_json=False,
        )

    async def async_set_schedule(self, device_id: str, enabled: bool) -> None:
        """Enable or disable the thermostat schedule."""
        await self._async_request(
            "PUT",
            f"/v1/devices/{device_id}/schedule",
            stage="schedule update",
            json={"scheduleEnabled": enabled},
            expect_json=False,
        )

    async def _async_get_access_token(self) -> str:
        """Return the current access token or acquire a new one."""
        if (
            self._access_token is not None
            and time.monotonic() < self._access_token_expires_at
        ):
            return self._access_token

        async with self._token_lock:
            if (
                self._access_token is not None
                and time.monotonic() < self._access_token_expires_at
            ):
                return self._access_token

            try:
                async with (
                    self._request_semaphore,
                    self._session.post(
                        TOKEN_URL,
                        headers={"x-api-key": self._api_key},
                        json={"email": self._email, "integratorToken": self._api_token},
                    ) as response,
                ):
                    if response.status in (401, 403):
                        raise DaikinAuthError("Invalid Daikin credentials")
                    response.raise_for_status()
                    token_data = cast(Mapping[str, str | int], await response.json())
            except aiohttp.ClientResponseError as err:
                raise DaikinApiError("token request", f"HTTP {err.status}") from err
            except (aiohttp.ClientError, TimeoutError) as err:
                raise DaikinApiError(
                    "token request", f"network error ({type(err).__name__})"
                ) from err

            self._access_token = str(token_data["accessToken"])
            # Renew early so a request does not start with a nearly expired token.
            self._access_token_expires_at = (
                time.monotonic()
                + int(token_data["accessTokenExpiresIn"])
                - _TOKEN_REFRESH_BUFFER
            )
            return self._access_token

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        stage: str,
        json: Mapping[str, object] | None = None,
        expect_json: bool = True,
    ) -> object:
        """Make an authenticated API request, refreshing a rejected token once."""
        url = f"{API_BASE_URL}{path}"
        for attempt in range(2):
            token = await self._async_get_access_token()
            status = 0
            result: object = None
            try:
                async with (
                    self._request_semaphore,
                    self._session.request(
                        method,
                        url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "x-api-key": self._api_key,
                        },
                        json=json,
                    ) as response,
                ):
                    status = response.status
                    if status not in (401, 403):
                        response.raise_for_status()
                        if expect_json:
                            result = await response.json()
            except aiohttp.ClientResponseError as err:
                raise DaikinApiError(stage, f"HTTP {err.status}") from err
            except (aiohttp.ClientError, TimeoutError) as err:
                raise DaikinApiError(
                    stage, f"network error ({type(err).__name__})"
                ) from err

            if status == 401 and attempt == 0:
                # Another concurrent request may already have replaced this token.
                async with self._token_lock:
                    if self._access_token == token:
                        self._access_token = None
                continue
            if status in (401, 403):
                raise DaikinAuthError("Daikin rejected the access token")
            return result

        raise DaikinAuthError("Daikin rejected the refreshed access token")
