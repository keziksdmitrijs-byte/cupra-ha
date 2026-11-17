"""Offline tests for the pure data layer."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cupra_parser", ROOT / "custom_components/cupra/parser.py")
parser = importlib.util.module_from_spec(spec)
sys.modules["cupra_parser"] = parser
spec.loader.exec_module(parser)

FIX = Path(__file__).parent / "fixtures"


def _state(name):
    fields, captured = parser.parse_dataset(json.loads((FIX / name).read_text()))
    return parser.finalize_state(parser.extract_state(fields)), fields, captured


def test_terramar_phev_flat():
    s, fields, captured = _state("terramar_phev_flat.json")
    assert captured.isoformat() == "2026-11-14T10:00:00+00:00"
    assert s["soc"] == 63 and s["fuel_level"] == 41
    assert s["mileage"] == 12873  # uint32 sentinel ignored
    assert s["range_total"] == 460
    assert s["locked"] is True
    assert s["door_rl"] is True and s["door_fl"] is False
    assert "hood" not in s  # 0 = unsupported
    assert s["window_rr"] is True and s["windows_open"] is True and s["doors_open"] is True
    assert abs(s["outside_temp"] - 4.95) <= 0.06
    assert s["plug_connected"] is True and s["charging"] is True
    assert s["charge_power"] == 7.2
    assert s["charge_remaining_min"] == 95
    assert s["inspection_days"] == 210 and s["inspection_km"] == 17100
    assert s["tyre_fl"] == 2.5 and "tyre_fr" not in s
    assert s["battery_12v"] == 12.45
    assert s["trip_long_fuel"] == 6.3
    assert s["climate_remaining_min"] == 0
    pt = parser.detect_powertrain(s, fields)
    assert pt == "phev"
    el, fuel = parser.electric_and_fuel_ranges(s, pt)
    assert (el, fuel) == (58, 402)


def test_born_ev_dotted():
    s, fields, captured = _state("born_ev_dotted.json")
    assert captured.isoformat() == "2026-11-14T10:00:00+00:00"
    assert s["soc"] == 77.0 and s["range_primary"] == 301 and s["mileage"] == 5400
    assert s["charging"] is False
    assert s["doors_open"] is False
    assert s["outside_temp"] == 8.5
    assert parser.detect_powertrain(s, fields) == "ev"


def test_sticky_merge_keeps_old_values():
    old, _ = parser.parse_dataset({"Data": [{"dataFieldName": "fuel_level_current_level", "value": "50", "timestampUtc": "2026-11-14T09:00:00Z"}]})
    new, _ = parser.parse_dataset({"Data": [{"dataFieldName": "mileage", "value": "100", "timestampUtc": "2026-11-14T10:00:00Z"}]})
    merged = parser.merge_fields(old, new)
    assert merged["fuel_level_current_level"].value == 50 and merged["mileage"].value == 100
    older, _ = parser.parse_dataset({"Data": [{"dataFieldName": "mileage", "value": "90", "timestampUtc": "2026-11-13T10:00:00Z"}]})
    assert parser.merge_fields(merged, older)["mileage"].value == 100


def test_ola_mapping():
    ola = {
        "status": {"doors": {"frontLeft": {"open": "false", "locked": "true"}, "frontRight": {"open": "true", "locked": "true"},
                             "rearLeft": {"open": "false", "locked": "true"}, "rearRight": {"open": "false", "locked": "true"}},
                   "windows": {"frontLeft": "closed", "frontRight": "open"}, "trunk": {"open": "false"}},
        "mycar": {"engines": {"primary": {"fuelType": "gasoline", "levelPct": 40, "rangeKm": 390},
                              "secondary": {"fuelType": "electric", "levelPct": 80, "rangeKm": 60}}},
        "position": {"lat": 56.95, "lon": 24.1},
        "climater": {"status": {"climatisationStatus": {"climatisationState": "heating", "remainingClimatisationTimeInMinutes": 12}}},
    }
    s = parser.finalize_state(parser.extract_ola_state(ola))
    assert s["door_fr"] is True and s["locked"] is True and s["window_fr"] is True
    assert s["fuel_level"] == 40 and s["soc"] == 80
    assert s["latitude"] == 56.95 and s["climate_on"] is True
    pt = parser.detect_powertrain(s)
    assert pt == "phev"
    assert parser.electric_and_fuel_ranges(s, pt) == (60, 390)


def test_parse_value_and_timestamps():
    assert parser.parse_value("True") is True
    assert parser.parse_value("12") == 12
    assert parser.parse_value("12.5") == 12.5
    assert parser.parse_value("300s") == 300.0
    assert parser.parse_timestamp("2026-06-12T16:53:49.000+02:00").hour == 14


def test_get_your_data_file():
    """One-off "Get your data" export: mostly value-less slots, units in values."""
    import json
    from pathlib import Path

    from custom_components.cupra import parser as p

    payload = json.loads((Path(__file__).parent / "fixtures" / "terramar_get_your_data.json").read_text())
    fields, captured = p.parse_dataset(payload)
    state = p.extract_state(fields)
    assert state["mileage"] == 30000
    assert state["battery_12v"] == 13.3
    assert state["outside_temp"] == 6
    assert state["inspection_km"] == 29000
    assert captured is not None and captured.isoformat().startswith("2026-11-15T10:57:32")


async def test_euda_falls_back_to_one_off_request():
    """No customised request -> use the "Get your data" (type=all) request."""
    from unittest.mock import AsyncMock

    from custom_components.cupra.api_euda import CupraApiError, EudaClient

    client = EudaClient(None, "a@b.lv", "pw")

    async def fake_json(path, headers=None):
        if path.endswith("/partial"):
            raise CupraApiError("no request", status=404)
        return {"Name": "Request File", "Identifier": "ALL-1"}

    client._json = fake_json
    assert await client.async_get_identifier("VIN") == "ALL-1"
    assert client.request_type("ALL-1") == "all"

    client._request = AsyncMock(return_value=(200, '[{"name": "f.zip", "createdOn": "2026-11-15T14:20:11Z"}]'))
    files = await client.async_list_datasets("VIN", "ALL-1")
    assert files[0]["name"] == "f.zip"
    assert client._request.call_args.args[1] == {"type": "all"}


def test_dataset_created_from_field_and_name():
    from datetime import UTC, datetime

    from custom_components.cupra.api_euda import dataset_created

    assert dataset_created({"name": "x.zip", "createdOn": "2026-11-17T06:41:23Z"}) == datetime(2026, 11, 17, 6, 41, 23, tzinfo=UTC)
    assert dataset_created({"name": "20261117064052_VSSZZZKP8T1005911.zip"}) == datetime(2026, 11, 17, 6, 40, 52, tzinfo=UTC)
    assert dataset_created({"name": "odd.zip"}) is None
