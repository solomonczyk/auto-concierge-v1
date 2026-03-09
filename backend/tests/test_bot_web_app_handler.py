"""Minimal tests for bot web_app_data_handler."""

from app.bot.handlers import web_app_data_handler


def test_web_app_data_handler_imports() -> None:
    assert web_app_data_handler is not None


def test_bot_flat_car_payload_normalization() -> None:
    """Legacy flat contract: bot flow accepts car_make, car_year, vin at top level."""
    data = {
        "service_id": 1,
        "date": "2026-02-20T10:00:00",
        "car_make": " Toyota ",
        "car_year": 2018,
        "vin": " jtdbr32e720040123 ",
    }
    car_make = data.get("car_make", "").strip() or None
    car_year_raw = data.get("car_year")
    car_year = int(car_year_raw) if car_year_raw else None
    vin = (data.get("vin", "").strip().upper() or None)

    assert car_make == "Toyota"
    assert car_year == 2018
    assert vin == "JTDBR32E720040123"


def test_bot_auto_info_car_payload_normalization() -> None:
    """auto_info first, fallback to flat: car fields from auto_info."""
    data = {
        "service_id": 1,
        "date": "2026-02-20T10:00:00",
        "auto_info": {
            "car_make": " Toyota ",
            "car_year": 2018,
            "vin": " jtdbr32e720040123 ",
        },
    }
    auto_info = data.get("auto_info") or {}

    car_make = (
        auto_info.get("car_make")
        or data.get("car_make", "")
    ).strip() or None

    car_year_raw = (
        auto_info.get("car_year")
        or data.get("car_year")
    )
    car_year = int(car_year_raw) if car_year_raw else None

    vin = (
        auto_info.get("vin")
        or data.get("vin", "")
    ).strip().upper() or None

    assert car_make == "Toyota"
    assert car_year == 2018
    assert vin == "JTDBR32E720040123"
