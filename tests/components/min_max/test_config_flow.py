"""Test the Min/Max config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.min_max import DOMAIN, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    registry = er.async_get(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.min_max.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "My min_max", "entity_ids": input_sensors, "type": "max"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "My min_max"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_ids": input_sensors,
        "name": "My min_max",
        "round_digits": 2.0,
        "type": "max",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_ids": input_sensors,
        "name": "My min_max",
        "round_digits": 2.0,
        "type": "max",
    }
    assert config_entry.title == "My min_max"

    # Check the entity is registered in the entity registry
    assert registry.async_get(f"{platform}.my_min_max") is not None

    # Check the platform is setup correctly
    state = hass.states.get(f"{platform}.my_min_max")
    assert state.state == "20.0"
    assert state.attributes["count_sensors"] == 2


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize("platform", ("sensor",))
async def test_options(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")
    hass.states.async_set("sensor.input_three", "33.33")

    input_sensors1 = ["sensor.input_one", "sensor.input_two"]
    input_sensors2 = ["sensor.input_one", "sensor.input_two", "sensor.input_three"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "entity_ids": input_sensors1,
            "name": "My min_max",
            "round_digits": 0,
            "type": "min",
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{platform}.my_min_max")
    assert state.state == "10.0"
    assert state.attributes["count_sensors"] == 2

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_ids": input_sensors1,
        "name": "My min_max",
        "round_digits": 0,
        "type": "min",
    }

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "options"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "entity_ids") == input_sensors1
    assert get_suggested(schema, "round_digits") == 0
    assert get_suggested(schema, "type") == "min"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entity_ids": input_sensors2,
            "round_digits": 1,
            "type": "mean",
        },
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "entity_ids": input_sensors2,
        "name": "My min_max",
        "round_digits": 1,
        "type": "mean",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_ids": input_sensors2,
        "name": "My min_max",
        "round_digits": 1,
        "type": "mean",
    }
    assert config_entry.title == "My min_max"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 4

    # TODO Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_min_max")
    assert state.state == "21.1"
    assert state.attributes["count_sensors"] == 3
