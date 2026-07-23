"""Sensor entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeconnect_websocket import HomeAppliance

from .entity import HCEntity
from .helpers import create_entities

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import DeviceInfo
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeconnect_websocket import HomeAppliance

    from . import HCConfigEntry
    from .entity_descriptions.descriptions_definitions import HCSensorEntityDescription

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: HCConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    entities = create_entities(
        {"sensor": HCSensor, "event_sensor": HCEventSensor, "active_program": HCActiveProgram},
        config_entry.runtime_data,
    )
    async_add_entites(entities)


class HCSensor(HCEntity, SensorEntity):
    """Sensor Entity."""

    entity_description: HCSensorEntityDescription

    def __init__(
        self,
        entity_description: HCSensorEntityDescription,
        appliance: HomeAppliance,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(entity_description, appliance, device_info)
        if self._entity.enum and self.entity_description.device_class in (
            None,
            SensorDeviceClass.ENUM,
        ):
            self._attr_device_class = SensorDeviceClass.ENUM
            if self.entity_description.has_state_translation:
                self._attr_options = [str(value).lower() for value in self._entity.enum.values()]
            else:
                self._attr_options = [str(value) for value in self._entity.enum.values()]

    @property
    def native_value(self) -> int | float | str:
        value = self._resolve_entity_value(self._entity)
        if value is None:
            return None
        if self._entity.enum and self.entity_description.has_state_translation:
            return str(value).lower()
        return value


class HCEventSensor(HCEntity, SensorEntity):
    """Event Sensor Entity."""

    entity_description: HCSensorEntityDescription

    @property
    def native_value(self) -> str:
        if self.entity_description.options:
            for entity, value in zip(self._entities, self.entity_description.options, strict=False):
                entity_value = self._resolve_entity_value(entity)
                if (entity.enum is not None and entity_value in {"Present", "Confirmed"}) or (
                    entity.enum is None and bool(entity_value)
                ):
                    return value
        return self.entity_description.options[-1]

    @property
    def available(self) -> bool:
        return self._appliance.session.connected


class HCActiveProgram(HCSensor):
    """Active Program Sensor Entity."""

    entity_description: HCSensorEntityDescription

    def __init__(
        self,
        entity_description: HCSensorEntityDescription,
        appliance: HomeAppliance,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(entity_description, appliance, device_info)
        self._attr_options = list(entity_description.mapping.values())

    @property
    def native_value(self) -> str | None:
        if self._appliance.active_program:
            if self._appliance.active_program.name in self.entity_description.mapping:
                return self.entity_description.mapping[self._appliance.active_program.name]
            return self._appliance.active_program.name
        return None
