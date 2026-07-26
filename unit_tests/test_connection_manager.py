"""Tests for the appliance connection manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from aiohttp import ClientConnectorSSLError
from homeassistant.const import CONF_HOST

from custom_components import homeconnect_ws
from custom_components.homeconnect_ws import HCData


@pytest.mark.asyncio
async def test_auth_failure_starts_reauth_without_retrying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an invalid appliance key starts reauthentication once."""
    hass = MagicMock()
    appliance = MagicMock()
    appliance.session.connected = False
    appliance.connect = AsyncMock(
        side_effect=ClientConnectorSSLError(MagicMock(), OSError())
    )
    config_entry = MagicMock()
    config_entry.data = {CONF_HOST: "1.2.3.4"}
    config_entry.runtime_data = HCData(
        appliance=appliance,
        device_info=MagicMock(),
        available_entity_descriptions={},
        session=MagicMock(),
        connection_signal="homeconnect_ws_test_connection",
    )
    sleep = AsyncMock()
    dispatcher_send = Mock()
    refresh_credentials = AsyncMock(return_value=False)
    monkeypatch.setattr(homeconnect_ws.asyncio, "sleep", sleep)
    monkeypatch.setattr(homeconnect_ws, "async_dispatcher_send", dispatcher_send)
    monkeypatch.setattr(
        homeconnect_ws,
        "async_refresh_encryption_credentials",
        refresh_credentials,
    )

    await homeconnect_ws._async_manage_connection(hass, config_entry)  # noqa: SLF001

    appliance.connect.assert_awaited_once()
    sleep.assert_not_awaited()
    dispatcher_send.assert_called_once_with(
        hass,
        config_entry.runtime_data.connection_signal,
    )
    refresh_credentials.assert_awaited_once_with(hass, config_entry)
    config_entry.async_start_reauth.assert_called_once_with(hass)


@pytest.mark.asyncio
async def test_auth_failure_uses_linked_account_before_reauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a linked account refreshes the local key without user action."""
    hass = MagicMock()
    appliance = MagicMock()
    appliance.session.connected = False
    appliance.connect = AsyncMock(
        side_effect=ClientConnectorSSLError(MagicMock(), OSError())
    )
    config_entry = MagicMock()
    config_entry.data = {CONF_HOST: "1.2.3.4"}
    config_entry.runtime_data = HCData(
        appliance=appliance,
        device_info=MagicMock(),
        available_entity_descriptions={},
        session=MagicMock(),
        connection_signal="homeconnect_ws_test_connection",
    )
    refresh_credentials = AsyncMock(return_value=True)
    monkeypatch.setattr(homeconnect_ws, "async_dispatcher_send", Mock())
    monkeypatch.setattr(
        homeconnect_ws,
        "async_refresh_encryption_credentials",
        refresh_credentials,
    )

    await homeconnect_ws._async_manage_connection(hass, config_entry)  # noqa: SLF001

    appliance.connect.assert_awaited_once()
    refresh_credentials.assert_awaited_once_with(hass, config_entry)
    config_entry.async_start_reauth.assert_not_called()
