"""Cloud-assisted recovery of local appliance credentials."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from homeassistant.const import CONF_MODE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    async_get_config_entry_implementation,
)

from .const import (
    CONF_AES_IV,
    CONF_PSK,
    DOMAIN,
    OAUTH_TOKEN_KEEPALIVE_INTERVAL,
    OAUTH_TOKEN_RETRY_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import HCConfigEntry

_LOGGER = logging.getLogger(__name__)
_OAUTH_LOCKS: dict[str, asyncio.Lock] = {}

ASSET_BASE_URL = "https://eu.services.home-connect.com"
ENCRYPTION_INFORMATION_URL = (
    ASSET_BASE_URL + "/api/appliance/v2/appliances/{appliance_id}/encryption-information"
)


class CloudProfileError(Exception):
    """Raised when Home Connect does not provide local credentials."""


def _oauth_lock(config_entry: HCConfigEntry) -> asyncio.Lock:
    return _OAUTH_LOCKS.setdefault(config_entry.entry_id, asyncio.Lock())


def _find_oauth_config_entry(
    hass: HomeAssistant,
    config_entry: HCConfigEntry,
) -> HCConfigEntry | None:
    if "token" in config_entry.data and "auth_implementation" in config_entry.data:
        return config_entry

    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if "token" in entry.data and "auth_implementation" in entry.data
        ),
        None,
    )


def _extract_encryption_credentials(payload: dict[str, Any]) -> dict[str, Any]:
    tls = payload.get("tls")
    if isinstance(tls, dict) and tls.get("key"):
        return {
            CONF_MODE: "TLS",
            CONF_PSK: tls["key"],
            CONF_AES_IV: None,
        }

    aes = payload.get("aes")
    if isinstance(aes, dict) and aes.get("key") and aes.get("iv"):
        return {
            CONF_MODE: "AES",
            CONF_PSK: aes["key"],
            CONF_AES_IV: aes["iv"],
        }

    msg = "Home Connect did not return local encryption credentials"
    raise CloudProfileError(msg)


async def async_fetch_encryption_credentials(
    hass: HomeAssistant,
    appliance_id: str,
    access_token: str,
) -> dict[str, Any]:
    """Fetch local credentials with a newly authorized token."""
    url = ENCRYPTION_INFORMATION_URL.format(appliance_id=appliance_id)
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        ) as response:
            response.raise_for_status()
            payload = await response.json()
    except ClientError as ex:
        msg = "Home Connect rejected the local profile request"
        raise CloudProfileError(msg) from ex

    return _extract_encryption_credentials(payload)


async def async_refresh_encryption_credentials(
    hass: HomeAssistant,
    config_entry: HCConfigEntry,
) -> bool:
    """Refresh and install local credentials from a linked Home Connect account."""
    oauth_config_entry = _find_oauth_config_entry(hass, config_entry)
    if not oauth_config_entry:
        return False

    appliance_id = config_entry.unique_id
    if not appliance_id:
        return False

    try:
        async with _oauth_lock(oauth_config_entry):
            implementation = await async_get_config_entry_implementation(
                hass,
                oauth_config_entry,
            )
            oauth_session = OAuth2Session(hass, oauth_config_entry, implementation)
            response = await oauth_session.async_request(
                "GET",
                ENCRYPTION_INFORMATION_URL.format(appliance_id=appliance_id),
                headers={"Accept": "application/json"},
            )
            async with response:
                response.raise_for_status()
                credentials = _extract_encryption_credentials(await response.json())
    except (
        ClientError,
        CloudProfileError,
        ImplementationUnavailableError,
        OAuth2TokenRequestError,
    ) as ex:
        _LOGGER.warning(
            "Could not refresh local credentials for appliance %s: %s",
            appliance_id,
            ex,
        )
        return False

    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, **credentials},
    )
    hass.async_create_task(
        hass.config_entries.async_reload(config_entry.entry_id),
        f"Reload Home Connect Local appliance {config_entry.title}",
    )
    return True


async def async_maintain_oauth_token(
    hass: HomeAssistant,
    config_entry: HCConfigEntry,
) -> None:
    """Keep the Home Connect refresh token active."""
    while True:
        retry_delay = OAUTH_TOKEN_KEEPALIVE_INTERVAL
        try:
            async with _oauth_lock(config_entry):
                implementation = await async_get_config_entry_implementation(
                    hass,
                    config_entry,
                )
                oauth_session = OAuth2Session(hass, config_entry, implementation)
                await oauth_session.async_ensure_token_valid()
        except asyncio.CancelledError:
            raise
        except OAuth2TokenRequestReauthError as ex:
            _LOGGER.warning(
                "Home Connect OAuth requires reauthentication for %s: %s",
                config_entry.title,
                ex,
            )
            config_entry.async_start_reauth(hass)
            retry_delay = OAUTH_TOKEN_RETRY_INTERVAL
        except (
            ClientError,
            ImplementationUnavailableError,
            KeyError,
            OAuth2TokenRequestError,
        ) as ex:
            _LOGGER.warning(
                "Could not maintain Home Connect OAuth token for %s: %s",
                config_entry.title,
                ex,
            )
            retry_delay = OAUTH_TOKEN_RETRY_INTERVAL

        await asyncio.sleep(retry_delay)
