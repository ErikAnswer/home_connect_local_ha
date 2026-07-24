"""The Home Connect Websocket integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from aiohttp import (
    ClientConnectionError,
    ClientSession,
    ClientTimeout,
    ClientWebSocketResponse,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DESCRIPTION, CONF_DEVICE_ID, CONF_HOST
from homeassistant.exceptions import (
    ConfigEntryError,
    ServiceValidationError,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.util.hass_dict import HassKey
from homeconnect_websocket import HomeAppliance
from homeconnect_websocket.message import Message

from .const import (
    CONF_AES_IV,
    CONF_DEV_OVERRIDE_HOST,
    CONF_DEV_OVERRIDE_PSK,
    CONF_DEV_SETUP_FROM_DUMP,
    CONF_PSK,
    DOMAIN,
    PLATFORMS,
    SOCKET_CONNECT_TIMEOUT,
    SOCKET_KEEPALIVE_INTERVAL,
    SOCKET_RECONNECT_DELAY,
)
from .entity_descriptions import get_available_entities

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
    from homeassistant.helpers.typing import ConfigType

    from .entity_descriptions import _EntityDescriptionsType

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_DEV_SETUP_FROM_DUMP, default=False): vol.Boolean(),
            vol.Optional(CONF_DEV_OVERRIDE_HOST): str,
            vol.Optional(CONF_DEV_OVERRIDE_PSK): str,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class HCData:
    """Dataclass for runtime data."""

    appliance: HomeAppliance
    device_info: DeviceInfo
    available_entity_descriptions: _EntityDescriptionsType
    session: HomeConnectClientSession
    connection_signal: str
    connection_task: asyncio.Task[None] | None = None


@dataclass
class HCConfig:
    """Dataclass for hass.data."""

    setup_from_dump: bool = False
    override_host: str | None = None
    override_psk: str | None = None


type HCConfigEntry = ConfigEntry[HCData]

HC_KEY: HassKey[HCConfig] = HassKey(DOMAIN)


class HomeConnectClientSession:
    """Own the appliance session and disable incompatible websocket heartbeats."""

    def __init__(self, timeout: ClientTimeout) -> None:
        """Initialize the underlying client session."""
        self._session = ClientSession(timeout=timeout)

    async def ws_connect(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> ClientWebSocketResponse:
        """Connect without the heartbeat rejected by Bosch appliances."""
        kwargs.pop("heartbeat", None)
        return await self._session.ws_connect(*args, **kwargs)

    async def close(self) -> None:
        """Close the underlying client session."""
        await self._session.close()


async def _async_establish_connection(
    appliance: HomeAppliance,
    host: str,
) -> None:
    while not appliance.session.connected:
        receive_task = vars(appliance.session).get("_recv_task")
        if receive_task is None or receive_task.done():
            socket = vars(appliance.session).get("_socket")
            if socket and not socket.closed:
                with contextlib.suppress(Exception):
                    await socket.close()

            try:
                await appliance.connect()
            except asyncio.CancelledError:
                raise
            except TimeoutError, ClientConnectionError:
                _LOGGER.debug("Appliance %s is not ready, retrying", host)
            except Exception:
                _LOGGER.exception("Failed to connect to appliance %s, retrying", host)

            receive_task = vars(appliance.session).get("_recv_task")
            if (
                not appliance.session.connected
                and receive_task is not None
                and not receive_task.done()
            ):
                socket = vars(appliance.session).get("_socket")
                if socket and not socket.closed:
                    with contextlib.suppress(Exception):
                        await socket.close()
        else:
            appliance.session.retry_count = 0

        await asyncio.sleep(SOCKET_RECONNECT_DELAY)


async def _async_manage_connection(
    hass: HomeAssistant,
    config_entry: HCConfigEntry,
) -> None:
    appliance = config_entry.runtime_data.appliance
    host = config_entry.data[CONF_HOST]
    keepalive_enabled = appliance.info.get("type") == "Hob"

    while True:
        await _async_establish_connection(appliance, host)
        async_dispatcher_send(hass, config_entry.runtime_data.connection_signal)
        next_keepalive = hass.loop.time() + SOCKET_KEEPALIVE_INTERVAL

        while appliance.session.connected:
            if keepalive_enabled and hass.loop.time() >= next_keepalive:
                try:
                    await appliance.session.send(Message(resource="/ni/info"))
                except ClientConnectionError, ConnectionError, RuntimeError:
                    _LOGGER.debug(
                        "Keepalive failed for appliance %s",
                        host,
                        exc_info=True,
                    )
                next_keepalive = hass.loop.time() + SOCKET_KEEPALIVE_INTERVAL

            await asyncio.sleep(SOCKET_RECONNECT_DELAY)

        async_dispatcher_send(hass, config_entry.runtime_data.connection_signal)


def _validate_appliance_info(appliance: HomeAppliance) -> None:
    if not appliance.info:
        msg = "Appliance has no device info"
        raise ConfigEntryError(msg)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration global config."""
    hass.data.setdefault(DOMAIN, HCConfig())
    if DOMAIN in config:
        hass.data[HC_KEY].setup_from_dump = config[DOMAIN].get(CONF_DEV_SETUP_FROM_DUMP, False)
        hass.data[HC_KEY].override_host = config[DOMAIN].get(CONF_DEV_OVERRIDE_HOST)
        hass.data[HC_KEY].override_psk = config[DOMAIN].get(CONF_DEV_OVERRIDE_PSK)

    async def handle_start_program(call: ServiceCall) -> ServiceResponse:
        config_entry_ids = await async_extract_config_entry_ids(hass, call)
        for config_entry_id in config_entry_ids:
            options = {}
            config_entry: HCConfigEntry = hass.config_entries.async_get_entry(config_entry_id)
            if config_entry.domain != DOMAIN:
                continue
            appliance = config_entry.runtime_data.appliance
            if "start_in" in call.data:
                if start_in_entity := appliance.entities.get("BSH.Common.Option.StartInRelative"):
                    relative_time_in_seconds = (
                        int(call.data["start_in"].get("hours", 0)) * 3600
                        + int(call.data["start_in"].get("minutes", 0)) * 60
                        + int(call.data["start_in"].get("seconds", 0))
                    )
                    options[start_in_entity.uid] = relative_time_in_seconds
                else:
                    msg = "'Start in' is not available on this Appliance"
                    raise ServiceValidationError(msg)
            if appliance.selected_program:
                await appliance.selected_program.start(options)
            else:
                msg = "No Program selected"
                raise ServiceValidationError(msg)

    hass.services.async_register(DOMAIN, "start_program", handle_start_program)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HCConfigEntry,
) -> bool:
    """Set up this integration using config entry."""
    _LOGGER.debug("Setting up %s", config_entry.data[CONF_DESCRIPTION]["info"].get("model"))
    session = HomeConnectClientSession(
        ClientTimeout(
            connect=SOCKET_CONNECT_TIMEOUT,
            sock_connect=SOCKET_CONNECT_TIMEOUT,
        ),
    )
    appliance = HomeAppliance(
        description=config_entry.data[CONF_DESCRIPTION],
        host=config_entry.data[CONF_HOST],
        app_name="Homeassistant",
        app_id=config_entry.data[CONF_DEVICE_ID],
        psk64=config_entry.data[CONF_PSK],
        iv64=config_entry.data.get(CONF_AES_IV, None),
        session=session,
    )

    try:
        _validate_appliance_info(appliance)

        device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, format_mac(appliance.info["mac"]))},
            hw_version=appliance.info["hwVersion"],
            identifiers={(DOMAIN, appliance.info["deviceID"])},
            name=f"{appliance.info['brand'].capitalize()} {appliance.info['type']}",
            manufacturer=appliance.info["brand"].capitalize(),
            model=f"{appliance.info['type']}",
            model_id=appliance.info["vib"],
            sw_version=appliance.info["swVersion"],
        )
        available_entities = get_available_entities(appliance)
        connection_signal = f"{DOMAIN}_{config_entry.entry_id}_connection"
        config_entry.runtime_data = HCData(
            appliance,
            device_info,
            available_entities,
            session,
            connection_signal,
        )
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
        config_entry.runtime_data.connection_task = config_entry.async_create_background_task(
            hass,
            _async_manage_connection(hass, config_entry),
            f"Home Connect connection manager for {config_entry.title}",
        )
    except Exception:
        await appliance.close()
        await session.close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HCConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading %s", entry.data[CONF_DESCRIPTION]["info"].get("vib"))
    if connection_task := entry.runtime_data.connection_task:
        connection_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await connection_task
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.appliance.close()
        await entry.runtime_data.session.close()
    return unload_ok
