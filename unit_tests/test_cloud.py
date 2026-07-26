"""Tests for cloud-assisted local credential recovery."""

# ruff: noqa: S101

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_MODE

from custom_components.homeconnect_ws import cloud
from custom_components.homeconnect_ws.cloud import (
    CloudProfileError,
    _extract_encryption_credentials,
    _find_oauth_config_entry,
)
from custom_components.homeconnect_ws.const import CONF_AES_IV, CONF_PSK


def test_extract_tls_credentials() -> None:
    """Test extracting TLS credentials."""
    assert _extract_encryption_credentials({"tls": {"key": "tls-key"}}) == {
        CONF_MODE: "TLS",
        CONF_PSK: "tls-key",
        CONF_AES_IV: None,
    }


def test_extract_aes_credentials() -> None:
    """Test extracting AES credentials."""
    assert _extract_encryption_credentials({"aes": {"key": "aes-key", "iv": "aes-iv"}}) == {
        CONF_MODE: "AES",
        CONF_PSK: "aes-key",
        CONF_AES_IV: "aes-iv",
    }


def test_extract_missing_credentials() -> None:
    """Test rejecting an incomplete cloud profile."""
    with pytest.raises(CloudProfileError):
        _extract_encryption_credentials({})


def test_find_oauth_entry_for_another_appliance() -> None:
    """Test all appliances can reuse the linked account entry."""
    hass = MagicMock()
    target_entry = MagicMock()
    target_entry.data = {}
    oauth_entry = MagicMock()
    oauth_entry.data = {
        "auth_implementation": "homeconnect_ws.oauth",
        "token": {"access_token": "token"},
    }
    hass.config_entries.async_entries.return_value = [target_entry, oauth_entry]

    assert _find_oauth_config_entry(hass, target_entry) is oauth_entry


@pytest.mark.asyncio
async def test_maintain_oauth_token_before_sleeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test token validity is checked when an OAuth entry loads."""
    hass = MagicMock()
    config_entry = MagicMock()
    implementation = MagicMock()
    oauth_session = MagicMock()
    oauth_session.async_ensure_token_valid = AsyncMock()
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(
        cloud,
        "async_get_config_entry_implementation",
        AsyncMock(return_value=implementation),
    )
    monkeypatch.setattr(cloud, "OAuth2Session", MagicMock(return_value=oauth_session))
    monkeypatch.setattr(cloud.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await cloud.async_maintain_oauth_token(hass, config_entry)

    oauth_session.async_ensure_token_valid.assert_awaited_once()
