"""Unit tests for hood select commands."""

from unittest.mock import AsyncMock, Mock

from custom_components.homeconnect_ws.entity_descriptions import HCSelectEntityDescription
from custom_components.homeconnect_ws.select import HCSelect


def create_hood_select() -> tuple[HCSelect, Mock, Mock, Mock]:
    """Create a hood select with an isolated venting program."""
    entity = Mock(
        enum={"0": "FanOff", "1": "FanStage01", "2": "FanStage02"},
        uid=55308,
        value="FanOff",
    )
    entity.name = "Cooking.Common.Option.Hood.VentingLevel"
    entity.set_value_raw = AsyncMock()
    program = Mock()
    program.start = AsyncMock()
    active_program = Mock()
    active_program.set_value_raw = AsyncMock()
    appliance = Mock(
        info={"deviceID": "device-id"},
        entities={
            "Cooking.Common.Option.Hood.VentingLevel": entity,
            "BSH.Common.Root.ActiveProgram": active_program,
        },
        programs={"Cooking.Common.Program.Hood.Venting": program},
    )
    select = HCSelect(
        HCSelectEntityDescription(
            key="select_hood_venting_level",
            entity="Cooking.Common.Option.Hood.VentingLevel",
            has_state_translation=True,
        ),
        appliance,
        Mock(),
    )
    return select, entity, program, active_program


async def test_hood_fanoff_stops_active_program() -> None:
    """Fan off should stop ventilation without putting the appliance in standby."""
    select, entity, program, active_program = create_hood_select()

    await select.async_select_option("fanoff")

    active_program.set_value_raw.assert_awaited_once_with(0)
    entity.set_value_raw.assert_not_awaited()
    program.start.assert_not_awaited()


async def test_hood_fan_stage_starts_venting_program() -> None:
    """A non-zero hood level should start the venting program."""
    select, entity, program, active_program = create_hood_select()

    await select.async_select_option("fanstage02")

    program.start.assert_awaited_once_with({55308: "2"})
    entity.set_value_raw.assert_not_awaited()
    active_program.set_value_raw.assert_not_awaited()
