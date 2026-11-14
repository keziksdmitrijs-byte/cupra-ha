"""End-to-end tests inside a real Home Assistant instance (network mocked)."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cupra.api_euda import CupraAuthError
from custom_components.cupra.api_ola import OlaBlockedError
from custom_components.cupra.const import DOMAIN

FIX = Path(__file__).parent / "fixtures"
VIN = "VSSZZZKMTEST00001"


def _euda_mocks(dataset="terramar_phev_flat.json"):
    payload = json.loads((FIX / dataset).read_text())
    return {
        "async_login": AsyncMock(),
        "async_list_vehicles": AsyncMock(return_value=[{"vin": VIN, "nickname": "Terramar"}]),
        "async_get_identifier": AsyncMock(return_value="REQ-1"),
        "async_list_datasets": AsyncMock(return_value=[
            {"name": "x_no_content_found.zip", "createdOn": "2026-11-14T10:15:00Z"},
            {"name": "data_1.zip", "createdOn": "2026-11-14T10:00:00Z"},
        ]),
        "async_download": AsyncMock(return_value=payload),
    }


async def test_config_flow(hass: HomeAssistant) -> None:
    with patch.multiple("custom_components.cupra.api_euda.EudaClient", **_euda_mocks()), \
         patch("custom_components.cupra.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_EMAIL: "a@b.lv", CONF_PASSWORD: "pw"})
        assert result["step_id"] == "model"
        assert result["data_schema"]({})["model"] == "terramar"  # guessed from nickname
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"model": "terramar", "powertrain": "auto"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Terramar"
        assert result["data"]["vin"] == VIN
        assert result["options"]["use_ola"] is True


async def test_config_flow_bad_auth(hass: HomeAssistant) -> None:
    with patch("custom_components.cupra.api_euda.EudaClient.async_login", AsyncMock(side_effect=CupraAuthError("nope"))):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_EMAIL: "a@b.lv", CONF_PASSWORD: "bad"})
        assert result["errors"] == {"base": "invalid_auth"}


async def test_setup_phev_with_ola_blocked(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=VIN, title="Terramar",
        data={CONF_EMAIL: "a@b.lv", CONF_PASSWORD: "pw", "vin": VIN, "nickname": "Terramar"},
        options={"use_ola": True, "model": "auto", "powertrain": "auto"},
    )
    entry.add_to_hass(hass)
    with patch.multiple("custom_components.cupra.api_euda.EudaClient", **_euda_mocks()), \
         patch("custom_components.cupra.api_ola.OlaClient.async_fetch_all", AsyncMock(side_effect=OlaBlockedError("403", status=403))):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    reg = er.async_get(hass)
    ids = {e.unique_id.removeprefix(VIN + "_"): e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}
    for key in ("vehicle", "soc", "fuel_level", "range_electric", "range_fuel", "mileage", "door_rl", "locked", "door_lock", "climate", "refresh"):
        assert key in ids, key
    assert "position" not in ids  # no GPS without My Cupra

    assert hass.states.get(ids["soc"]).state == "63"
    assert hass.states.get(ids["range_electric"]).state == "58"
    assert hass.states.get(ids["range_fuel"]).state == "402"
    assert hass.states.get(ids["door_rl"]).state == "on"
    assert hass.states.get(ids["locked"]).state == "off"  # lock device class: off = locked
    assert hass.states.get(ids["door_lock"]).state == "unavailable"  # OLA blocked

    veh = hass.states.get(ids["vehicle"])
    assert veh.state == "charging"
    a = veh.attributes
    assert a["model"] == "terramar" and a["body"] == "suv" and a["powertrain"] == "phev"
    assert a["commands_available"] is False
    assert a["sources"]["my_cupra"]["status"] == "blocked"
    assert a["entities"]["door_lock"] == ids["door_lock"]
    assert a["state"]["soc"] == 63

    issues = ir.async_get(hass).issues
    assert (DOMAIN, f"ola_blocked_{VIN}") in issues

    # downloads only the content ZIP, never the empty one
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_without_subscription(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=VIN, data={CONF_EMAIL: "a@b.lv", CONF_PASSWORD: "pw", "vin": VIN}, options={"use_ola": False})
    entry.add_to_hass(hass)
    mocks = _euda_mocks()
    mocks["async_get_identifier"] = AsyncMock(return_value=None)
    with patch.multiple("custom_components.cupra.api_euda.EudaClient", **mocks):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert (DOMAIN, f"no_subscription_{VIN}") in ir.async_get(hass).issues
    reg = er.async_get(hass)
    keys = {e.unique_id.removeprefix(VIN + "_") for e in er.async_entries_for_config_entry(reg, entry.entry_id)}
    assert "door_lock" not in keys and "vehicle" in keys
    vehicle = next(e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id) if e.unique_id.endswith("_vehicle"))
    assert hass.states.get(vehicle).attributes["sources"]["eu_data_act"]["status"] == "no_subscription"


async def test_ev_ola_live(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=VIN, data={CONF_EMAIL: "a@b.lv", CONF_PASSWORD: "pw", "vin": VIN, "nickname": "Born"}, options={"use_ola": True})
    entry.add_to_hass(hass)
    ola = {"mycar": {"engines": {"primary": {"fuelType": "electric", "levelPct": 55, "rangeKm": 210}}},
           "status": {}, "mileage": {}, "ranges": [], "position": {"lat": 56.9, "lon": 24.1},
           "climater": {"status": {}, "settings": {}}, "charging": {"status": {}, "info": {}}}
    with patch.multiple("custom_components.cupra.api_euda.EudaClient", **_euda_mocks("born_ev_dotted.json")), \
         patch("custom_components.cupra.api_ola.OlaClient.async_fetch_all", AsyncMock(return_value=ola)), \
         patch("custom_components.cupra.api_ola.OlaClient.async_climate", AsyncMock()) as climate:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        reg = er.async_get(hass)
        ids = {e.unique_id.removeprefix(VIN + "_"): e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}
        assert hass.states.get(ids["soc"]).state == "55"  # live OLA beats the older snapshot
        assert "position" in ids and hass.states.get(ids["position"]).attributes["latitude"] == 56.9
        assert hass.states.get(ids["door_lock"]).state != "unavailable"
        veh = hass.states.get(ids["vehicle"]).attributes
        assert veh["powertrain"] == "ev" and veh["model"] == "born" and veh["commands_available"] is True
        await hass.services.async_call("switch", "turn_on", {"entity_id": ids["climate"]}, blocking=True)
        climate.assert_awaited_once()
        assert "fuel_level" not in ids
        await hass.config_entries.async_unload(entry.entry_id)


async def test_vehicle_entity_id_language_independent(hass: HomeAssistant) -> None:
    hass.config.language = "ru"
    entry = MockConfigEntry(domain=DOMAIN, unique_id=VIN, title="Terramar", data={CONF_EMAIL: "a@b.lv", CONF_PASSWORD: "pw", "vin": VIN, "nickname": "Terramar"}, options={"use_ola": False})
    entry.add_to_hass(hass)
    with patch.multiple("custom_components.cupra.api_euda.EudaClient", **_euda_mocks()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("sensor.terramar_vehicle") is not None
