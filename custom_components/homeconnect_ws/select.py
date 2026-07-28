"""Select entities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .entity import HCEntity
from .helpers import create_entities

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeconnect_websocket import HomeAppliance
    from homeconnect_websocket.entities import SelectedProgram

    from . import HCConfigEntry
    from .entity_descriptions.descriptions_definitions import HCSelectEntityDescription

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: HCConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up select platform."""
    entities = create_entities(
        {"select": HCSelect, "program": HCProgram},
        config_entry.runtime_data,
    )
    async_add_entites(entities)


class HCSelect(HCEntity, SelectEntity):
    """Select Entity."""

    entity_description: HCSelectEntityDescription
    _rev_options: dict[str, str]

    def __init__(
        self,
        entity_description: HCSelectEntityDescription,
        appliance: HomeAppliance,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(entity_description, appliance, device_info)

        self._rev_options = {}
        if entity_description.options:
            self._attr_options = entity_description.options
        elif self._entity.enum:
            self._attr_options = []
            if self.entity_description.has_state_translation:
                for value in self._entity.enum.values():
                    self._attr_options.append(str(value).lower())
            else:
                for value in self._entity.enum.values():
                    self._attr_options.append(str(value))

        if self.entity_description.has_state_translation and self._entity.enum:
            for value in self._entity.enum.values():
                self._rev_options[str(value).lower()] = value

    @property
    def current_option(self) -> str:
        value = self._resolve_entity_value(self._entity)
        if value is None:
            return None
        if self.entity_description.has_state_translation:
            translated_value = str(value).lower()
            if translated_value in self._attr_options:
                return translated_value
        option = str(value)
        if option in self._attr_options:
            return option
        return None

    async def async_select_option(self, option: str) -> None:
        if self._entity.name == "Cooking.Common.Option.Hood.VentingLevel":
            program = self._appliance.programs.get("Cooking.Common.Program.Hood.Venting")
            if program is not None:
                raw_value: str | int | bool = option
                if self._entity.enum:
                    option_lower = option.lower()
                    for enum_key, enum_value in self._entity.enum.items():
                        if str(enum_value).lower() == option_lower:
                            raw_value = enum_key
                            break
                try:
                    await program.start({self._entity.uid: raw_value})
                    return
                except Exception:
                    _LOGGER.debug(
                        "Failed to set hood venting via program start, falling back to direct option write",
                        exc_info=True,
                    )

        real_option = option
        if self._rev_options and option in self._rev_options:
            real_option = self._rev_options[option]
        try:
            await self._entity.set_value(real_option)
        except Exception:
            if not self._entity.enum:
                raise
            option_lower = option.lower()
            for enum_key, enum_value in self._entity.enum.items():
                if str(enum_value).lower() == option_lower:
                    await self._entity.set_value(enum_key)
                    return
            raise


class HCProgram(HCSelect):
    """Program select Entity."""

    _entity: SelectedProgram

    def __init__(
        self,
        entity_description: HCSelectEntityDescription,
        appliance: HomeAppliance,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(entity_description, appliance, device_info)
        self._programs = entity_description.mapping
        self._rev_programs = {value: key for key, value in self._programs.items()}

    @property
    def options(self) -> list[str] | None:
        return list(self._programs.values())

    @property
    def current_option(self) -> list[str] | None:
        if self._appliance.selected_program:
            if self._appliance.selected_program.name in self._programs:
                return self._programs[self._appliance.selected_program.name]
            return self._appliance.selected_program.name
        return None

    async def async_select_option(self, option: str) -> None:
        await self._appliance.programs[self._rev_programs[option]].select()