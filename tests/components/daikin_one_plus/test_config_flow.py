"""Test the Daikin One+ config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.daikin_one_plus.api import DaikinApiError, DaikinAuthError
from homeassistant.components.daikin_one_plus.config_flow import (
    CannotConnect,
    InvalidAuth,
    NoThermostat,
    validate_input,
)
from homeassistant.components.daikin_one_plus.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {
    CONF_API_KEY: "api-key",
    CONF_EMAIL: "home@example.com",
    CONF_API_TOKEN: "integrator-token",
}


async def test_validate_input(hass: HomeAssistant) -> None:
    """Test validation gets and returns the thermostat ID."""
    with (
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.async_get_clientsession"
        ),
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.DaikinApi.async_get_devices",
            autospec=True,
            return_value=[
                {
                    "id": "thermostat-id",
                    "name": "Main Room",
                    "model": "ONEPLUS",
                    "firmwareVersion": "2.3.5",
                }
            ],
        ),
    ):
        assert await validate_input(hass, USER_INPUT) == "thermostat-id"


async def test_validate_input_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid credentials are rejected."""
    with (
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.async_get_clientsession"
        ),
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.DaikinApi.async_get_devices",
            autospec=True,
            side_effect=DaikinAuthError("invalid credentials"),
        ),
        pytest.raises(InvalidAuth),
    ):
        await validate_input(hass, USER_INPUT)


async def test_validate_input_no_thermostat(hass: HomeAssistant) -> None:
    """Test an account without a thermostat cannot be configured."""
    with (
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.async_get_clientsession"
        ),
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.DaikinApi.async_get_devices",
            autospec=True,
            return_value=[],
        ),
        pytest.raises(NoThermostat),
    ):
        await validate_input(hass, USER_INPUT)


async def test_validate_input_cannot_connect(hass: HomeAssistant) -> None:
    """Test API errors are mapped to cannot connect."""
    with (
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.async_get_clientsession"
        ),
        patch(
            "homeassistant.components.daikin_one_plus.config_flow.DaikinApi.async_get_devices",
            autospec=True,
            side_effect=DaikinApiError("device list request", "HTTP 503"),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(hass, USER_INPUT)
    assert err.value.stage == "device list request"
    assert err.value.reason == "HTTP 503"


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test credentials are trimmed before validation and persistence."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    padded_input = {
        CONF_API_KEY: " \tapi-key \n",
        CONF_EMAIL: "\nhome@example.com\t ",
        CONF_API_TOKEN: "  integrator-token\r\n",
    }

    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        return_value="thermostat-id",
    ) as validate_mock:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], padded_input
        )

    normalized_input = {
        CONF_API_KEY: "api-key",
        CONF_EMAIL: "home@example.com",
        CONF_API_TOKEN: "integrator-token",
    }
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Main Thermostat"
    assert result["data"] == normalized_input
    assert result["result"].unique_id == "thermostat-id"
    validate_mock.assert_called_once_with(hass, normalized_input)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test invalid authentication can be retried."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        return_value="thermostat-id",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failures include safe diagnostic details."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        side_effect=[
            CannotConnect("device list request", "HTTP 503"),
            "thermostat-id",
        ],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert result["description_placeholders"] == {
            "stage": "device list request",
            "reason": "HTTP 503",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "thermostat-id"


async def test_form_no_thermostat(hass: HomeAssistant) -> None:
    """Test an account without a thermostat shows the matching form error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        side_effect=NoThermostat,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_thermostat"}

    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        return_value="thermostat-id",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_unexpected_error_recovers(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an unexpected validation error can be recovered from."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        side_effect=[RuntimeError("unexpected"), "thermostat-id"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
        assert "Unexpected exception" in caplog.text

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "thermostat-id"


async def test_duplicate_entry_is_aborted(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the same thermostat cannot be configured more than once."""
    with patch(
        "homeassistant.components.daikin_one_plus.config_flow.validate_input",
        return_value="thermostat-id",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        duplicate = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        duplicate = await hass.config_entries.flow.async_configure(
            duplicate["flow_id"], USER_INPUT
        )

    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"
