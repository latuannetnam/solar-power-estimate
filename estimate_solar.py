import argparse
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import pvlib
import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class SolarConfig:
    lat: float
    lon: float
    target_date: date
    capacity_kw: float
    tilt: float
    azimuth: float
    losses: float
    timezone: str


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--date must use YYYY-MM-DD format") from exc


def validate_config(config: SolarConfig) -> None:
    if not math.isfinite(config.lat) or not -90 <= config.lat <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not math.isfinite(config.lon) or not -180 <= config.lon <= 180:
        raise ValueError("longitude must be between -180 and 180")
    if not math.isfinite(config.capacity_kw) or config.capacity_kw <= 0:
        raise ValueError("capacity must be positive")
    if not math.isfinite(config.tilt) or not 0 <= config.tilt <= 90:
        raise ValueError("tilt must be between 0 and 90")
    if not math.isfinite(config.azimuth) or not 0 <= config.azimuth <= 360:
        raise ValueError("azimuth must be between 0 and 360")
    if not math.isfinite(config.losses) or not 0 <= config.losses < 1:
        raise ValueError("losses must be at least 0 and less than 1")
    if not config.timezone:
        raise ValueError("timezone must not be empty")


def build_weather_frame(payload: dict, target_date: date) -> pd.DataFrame:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise RuntimeError("Open-Meteo response is missing hourly data")

    required = ["time", "shortwave_radiation", "temperature_2m", "wind_speed_10m"]
    missing = [name for name in required if name not in hourly]
    if missing:
        raise RuntimeError(f"Open-Meteo response is missing hourly fields: {', '.join(missing)}")
    if any(isinstance(hourly[name], (str, bytes)) or not isinstance(hourly[name], Sequence) for name in required):
        raise RuntimeError("Open-Meteo hourly fields must be arrays")

    lengths = {name: len(hourly[name]) for name in required}
    if len(set(lengths.values())) != 1:
        raise RuntimeError(f"Open-Meteo hourly field lengths differ: {lengths}")

    timezone = payload.get("timezone") or "UTC"
    try:
        tzinfo = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Open-Meteo returned unknown timezone: {timezone}") from exc

    try:
        index = pd.to_datetime(hourly["time"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Open-Meteo response contains invalid hourly timestamp data") from exc
    if index.tz is None:
        index = index.tz_localize(tzinfo)
    else:
        index = index.tz_convert(tzinfo)

    columns = {}
    for name in required[1:]:
        series = pd.Series(pd.to_numeric(hourly[name], errors="coerce"))
        if series.isna().any():
            raise RuntimeError(f"Open-Meteo response contains malformed numeric data in {name}")
        columns[name] = series.to_numpy()

    frame = pd.DataFrame(
        columns,
        index=index,
    )
    frame = frame[frame.index.date == target_date]
    if frame.empty:
        raise RuntimeError(f"requested date {target_date.isoformat()} is not present in weather response")

    frame.attrs["timezone"] = timezone
    return frame


def estimate_energy(weather: pd.DataFrame, config: SolarConfig) -> pd.DataFrame:
    timezone = weather.attrs.get("timezone") or config.timezone
    if timezone == "auto":
        timezone = str(weather.index.tz)

    location = pvlib.location.Location(
        latitude=config.lat,
        longitude=config.lon,
        tz=timezone,
    )
    times = weather.index
    solar_position = location.get_solarposition(times)

    ghi = weather["shortwave_radiation"].clip(lower=0)
    erbs = pvlib.irradiance.erbs(
        ghi=ghi,
        zenith=solar_position["apparent_zenith"],
        datetime_or_doy=times,
    )
    irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=config.tilt,
        surface_azimuth=config.azimuth,
        dni=erbs["dni"].clip(lower=0),
        ghi=ghi,
        dhi=erbs["dhi"].clip(lower=0),
        solar_zenith=solar_position["apparent_zenith"],
        solar_azimuth=solar_position["azimuth"],
    )
    poa_global = irradiance["poa_global"].fillna(0).clip(lower=0)

    temperature_params = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"]
    cell_temperature = pvlib.temperature.sapm_cell(
        poa_global=poa_global,
        temp_air=weather["temperature_2m"],
        wind_speed=weather["wind_speed_10m"],
        **temperature_params,
    )
    dc_watts = pvlib.pvsystem.pvwatts_dc(
        effective_irradiance=poa_global,
        temp_cell=cell_temperature,
        pdc0=config.capacity_kw * 1000,
        gamma_pdc=-0.003,
    )
    power_kw = (dc_watts / 1000).fillna(0).clip(lower=0) * (1 - config.losses)

    result = pd.DataFrame(
        {
            "ghi_w_m2": ghi,
            "poa_w_m2": poa_global,
            "power_kw": power_kw,
            "energy_kwh": power_kw,
        },
        index=weather.index,
    )
    return result


def fetch_weather(config: SolarConfig) -> dict:
    params = {
        "latitude": config.lat,
        "longitude": config.lon,
        "hourly": "shortwave_radiation,temperature_2m,wind_speed_10m",
        "start_date": config.target_date.isoformat(),
        "end_date": config.target_date.isoformat(),
        "timezone": config.timezone,
        "wind_speed_unit": "ms",
    }
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Open-Meteo request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Open-Meteo returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Open-Meteo returned invalid payload")
    if payload.get("error"):
        reason = payload.get("reason") or "unknown error"
        raise RuntimeError(f"Open-Meteo returned an error: {reason}")

    return payload


def parse_args(argv=None) -> SolarConfig:
    parser = argparse.ArgumentParser(description="Estimate daily solar energy from Open-Meteo weather data")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--date", dest="target_date")
    parser.add_argument("--capacity-kw", type=float, required=True)
    parser.add_argument("--tilt", type=float, default=15.0)
    parser.add_argument("--azimuth", type=float, default=180.0)
    parser.add_argument("--losses", type=float, default=0.14)
    parser.add_argument("--timezone", default="auto")
    args = parser.parse_args(argv)

    config = SolarConfig(
        lat=args.lat,
        lon=args.lon,
        target_date=parse_date(args.target_date) if args.target_date else date.today(),
        capacity_kw=args.capacity_kw,
        tilt=args.tilt,
        azimuth=args.azimuth,
        losses=args.losses,
        timezone=args.timezone,
    )
    validate_config(config)
    return config


def print_report(estimate: pd.DataFrame) -> None:
    print("time,ghi_w_m2,poa_w_m2,power_kw,energy_kwh")
    for timestamp, row in estimate.iterrows():
        print(
            f"{timestamp.strftime('%Y-%m-%d %H:%M')},"
            f"{row['ghi_w_m2']:.1f},"
            f"{row['poa_w_m2']:.1f},"
            f"{row['power_kw']:.3f},"
            f"{row['energy_kwh']:.3f}"
        )
    print(f"daily_total_kwh,{estimate['energy_kwh'].sum():.3f}")


def main(argv=None) -> int:
    try:
        config = parse_args(argv)
        payload = fetch_weather(config)
        weather = build_weather_frame(payload, config.target_date)
        estimate = estimate_energy(weather, config)
        print_report(estimate)
    except (RuntimeError, ValueError, argparse.ArgumentTypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
