"""Tests for entity descriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

from custom_components.homeconnect_ws import entity_descriptions
from custom_components.homeconnect_ws.entity_descriptions import (
    HCBinarySensorEntityDescription,
    HCSelectEntityDescription,
    HCSensorEntityDescription,
    HCSwitchEntityDescription,
)
from custom_components.homeconnect_ws.entity_descriptions.common import (
    generate_power_switch,
    generate_program,
)
from custom_components.homeconnect_ws.entity_descriptions.cooking import generate_hob_zones
from custom_components.homeconnect_ws.helpers import merge_dicts
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass
from homeconnect_websocket.entities import Access, DeviceDescription, EntityDescription

if TYPE_CHECKING:
    import pytest
    from homeconnect_websocket.testutils import MockAppliance, MockApplianceType


def test_merge_dicts() -> None:
    """Test merge dicts."""
    dict1 = {"a": [1, 2], "b": [3, 4]}
    dict2 = {"b": [5, 6], "c": [7, 8]}
    out_dict = merge_dicts(dict1, dict2)
    assert out_dict == {"a": [1, 2], "b": [3, 4, 5, 6], "c": [7, 8]}


MOCK_ENTITY_DESCRIPTIONS = {
    "binary_sensor": [
        HCBinarySensorEntityDescription(key="binary_sensor_available", entity="Test.BinarySensor"),
        HCBinarySensorEntityDescription(
            key="binary_sensor_not_available", entity="Test.BinarySensor2"
        ),
    ],
    "event_sensor": [
        HCSensorEntityDescription(
            key="sensor_event_available",
            entities=[
                "Test.Event1",
                "Test.Event2",
            ],
        ),
        HCSensorEntityDescription(
            key="sensor_event_not_available",
            entities=[
                "Test.Event1",
                "Test.Event3",
            ],
        ),
    ],
}


def test_get_available_entities(
    mock_appliance: MockAppliance, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_available_entities."""
    monkeypatch.setattr(
        entity_descriptions,
        "get_all_entity_description",
        Mock(return_value=MOCK_ENTITY_DESCRIPTIONS),
    )
    entities = entity_descriptions.get_available_entities(mock_appliance)
    assert entities["binary_sensor"] == [
        HCBinarySensorEntityDescription(key="binary_sensor_available", entity="Test.BinarySensor")
    ]
    assert entities["event_sensor"] == [
        HCSensorEntityDescription(
            key="sensor_event_available",
            entities=[
                "Test.Event1",
                "Test.Event2",
            ],
        )
    ]


POWER_SWITCH = {
    "setting": [
        {
            "access": "readwrite",
            "available": True,
            "enumeration": {"0": "MainsOff", "1": "Off", "2": "On", "3": "Standby"},
            "min": 0,
            "max": 2,
            "uid": 539,
            "name": "BSH.Common.Setting.PowerState",
        },
    ]
}


async def test_power_switch(mock_homeconnect_appliance: MockApplianceType) -> None:
    """Test dynamic Power switch."""
    device_description = POWER_SWITCH.copy()

    # On/Off Switch
    device_description["setting"][0]["min"] = 1
    device_description["setting"][0]["max"] = 2
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert switch_description["switch"][0] == HCSwitchEntityDescription(
        key="switch_power_state",
        entity="BSH.Common.Setting.PowerState",
        device_class=SwitchDeviceClass.SWITCH,
        value_mapping=("On", "Off"),
    )
    assert "select" not in switch_description

    # No Switch
    device_description["setting"][0]["min"] = 0
    device_description["setting"][0]["max"] = 4
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert "switch" not in switch_description
    assert switch_description["select"][0] == HCSelectEntityDescription(
        key="select_power_state",
        entity="BSH.Common.Setting.PowerState",
        options=["mainsoff", "off", "on", "standby"],
        has_state_translation=True,
    )

    # On/MainsOff Switch
    device_description["setting"][0]["enumeration"] = {"0": "MainsOff", "2": "On"}
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert switch_description["switch"][0] == HCSwitchEntityDescription(
        key="switch_power_state",
        entity="BSH.Common.Setting.PowerState",
        device_class=SwitchDeviceClass.SWITCH,
        value_mapping=("On", "MainsOff"),
    )

    # Standby/Off Switch
    device_description["setting"][0]["enumeration"] = {"1": "Off", "3": "Standby"}
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert switch_description["switch"][0] == HCSwitchEntityDescription(
        key="switch_power_state",
        entity="BSH.Common.Setting.PowerState",
        device_class=SwitchDeviceClass.SWITCH,
        value_mapping=("Standby", "Off"),
    )


PROGRAM = DeviceDescription(
    setting=[
        EntityDescription(
            uid=101,
            name="BSH.Common.Setting.Favorite.001.Name",
            access=Access.READ_WRITE,
            available=True,
            max=30,
            min=0,
            default="Named Favorite",
        ),
        EntityDescription(
            uid=102,
            name="BSH.Common.Setting.Favorite.002.Name",
            access=Access.READ_WRITE,
            available=True,
            max=30,
            min=0,
            default="",
        ),
    ],
    program=[
        EntityDescription(
            uid=201,
            name="BSH.Common.Program.Favorite.001",
            available=True,
        ),
        EntityDescription(
            uid=202,
            name="BSH.Common.Program.Favorite.002",
            available=True,
        ),
        EntityDescription(
            uid=500,
            name="BSH.Common.Program.Program1",
        ),
    ],
)


async def test_program(mock_homeconnect_appliance: MockApplianceType) -> None:
    """Test dynamic Program."""
    appliance = await mock_homeconnect_appliance(description=PROGRAM)
    program_description = generate_program(appliance)
    assert program_description["program"][0] == HCSelectEntityDescription(
        key="select_program",
        entity="BSH.Common.Root.SelectedProgram",
        has_state_translation=False,
        mapping={
            "BSH.Common.Program.Favorite.001": "Named Favorite",
            "BSH.Common.Program.Favorite.002": "favorite_002",
            "BSH.Common.Program.Program1": "bsh_common_program_program1",
        },
    )
    assert program_description["active_program"][0] == HCSensorEntityDescription(
        key="sensor_active_program",
        entity="BSH.Common.Root.ActiveProgram",
        has_state_translation=False,
        device_class=SensorDeviceClass.ENUM,
        mapping={
            "BSH.Common.Program.Favorite.001": "Named Favorite",
            "BSH.Common.Program.Favorite.002": "favorite_002",
            "BSH.Common.Program.Program1": "bsh_common_program_program1",
        },
    )

    appliance = await mock_homeconnect_appliance(description={})


async def test_program_not_created_for_hob(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """Skip common program controls for hobs."""
    appliance = await mock_homeconnect_appliance(description=PROGRAM)
    appliance.info["type"] = "Hob"

    assert generate_program(appliance) == {}


HOB_ZONES = DeviceDescription(
    status=[
        EntityDescription(
            uid=1200,
            name="Cooking.Hob.Status.Zone.120.State",
            access=Access.READ,
            available=True,
            enumeration={"0": "Off", "1": "Active"},
        ),
        EntityDescription(
            uid=1201,
            name="Cooking.Hob.Status.Zone.120.PowerLevel",
            access=Access.READ,
            available=True,
            enumeration={"0": "Off", "50": "50"},
        ),
        EntityDescription(
            uid=1202,
            name="Cooking.Hob.Status.Zone.120.CurrentTemperature",
            access=Access.READ,
            available=True,
        ),
        EntityDescription(
            uid=1203,
            name="Cooking.Hob.Status.Zone.120.HeatupProgress",
            access=Access.READ,
            available=True,
        ),
        EntityDescription(
            uid=1210,
            name="Cooking.Hob.Status.Zone.121.State",
            access=Access.READ,
            available=True,
            enumeration={"0": "Off", "1": "Active"},
        ),
    ]
)


async def test_generate_hob_zones(mock_homeconnect_appliance: MockApplianceType) -> None:
    """Dynamic hob zones should use translated names and stable per-zone numbering."""
    appliance = await mock_homeconnect_appliance(description=HOB_ZONES)
    descriptions = generate_hob_zones(appliance)
    descriptions_by_key = {description.key: description for description in descriptions["sensor"]}

    assert descriptions_by_key["sensor_hob_zone_120_state"] == HCSensorEntityDescription(
        key="sensor_hob_zone_120_state",
        translation_key="sensor_hob_zone_state",
        translation_placeholders={"group_name": "1"},
        entity="Cooking.Hob.Status.Zone.120.State",
        has_state_translation=True,
    )
    assert descriptions_by_key["sensor_hob_zone_120_power"] == HCSensorEntityDescription(
        key="sensor_hob_zone_120_power",
        translation_key="sensor_hob_zone_power_level",
        translation_placeholders={"group_name": "1"},
        entity="Cooking.Hob.Status.Zone.120.PowerLevel",
        has_state_translation=True,
    )
    assert descriptions_by_key[
        "sensor_hob_zone_120_current_temperature"
    ] == HCSensorEntityDescription(
        key="sensor_hob_zone_120_current_temperature",
        translation_key="sensor_hob_zone_current_temperature",
        translation_placeholders={"group_name": "1"},
        entity="Cooking.Hob.Status.Zone.120.CurrentTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        entity_registry_enabled_default=False,
    )
    assert descriptions_by_key["sensor_hob_zone_121_state"] == HCSensorEntityDescription(
        key="sensor_hob_zone_121_state",
        translation_key="sensor_hob_zone_state",
        translation_placeholders={"group_name": "2"},
        entity="Cooking.Hob.Status.Zone.121.State",
        has_state_translation=True,
    )
