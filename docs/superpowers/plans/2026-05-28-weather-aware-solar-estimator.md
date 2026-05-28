# Weather-Aware Solar Estimator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI script that estimates one fixed solar array's hourly and daily energy for a location and date using Open-Meteo weather data and `pvlib`.

**Architecture:** Keep runtime code in `estimate_solar.py` with small functions for argument parsing, validation, weather fetching, dataframe conversion, PV modeling, and report printing. Use a focused `unittest` suite in `tests/test_estimate_solar.py` for validation, API parsing, and deterministic model behavior with synthetic weather.

**Tech Stack:** Python 3, `argparse`, `requests`, `pandas`, `pvlib`, standard-library `unittest`.

---

## File Structure

- Create `requirements.txt`: runtime dependencies for the CLI.
- Create `estimate_solar.py`: CLI entry point, Open-Meteo client, `pvlib` calculation, output formatting.
- Create `tests/test_estimate_solar.py`: unit tests for validation, Open-Meteo response parsing, and energy model output.

The Open-Meteo forecast endpoint is `https://api.open-meteo.com/v1/forecast`. The request uses `hourly=shortwave_radiation,temperature_2m,wind_speed_10m`, `start_date`, `end_date`, and `timezone=auto` by default.

---

### Task 1: Add Dependencies

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Create dependency file**

Create `requirements.txt` with exactly:

```text
requests
pandas
pvlib
```

- [ ] **Step 2: Install dependencies**

Run:

```bash
python -m pip install -r requirements.txt
```

Expected: command exits with code `0` and installs or reports existing `requests`, `pandas`, and `pvlib`.

---

### Task 2: Add Validation And Weather Parsing Tests

**Files:**
- Create: `tests/test_estimate_solar.py`
- Create minimal target module: `estimate_solar.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_estimate_solar.py`:

```python
import unittest
from datetime import date

import pandas as pd

from estimate_solar import SolarConfig, build_weather_frame, validate_config


class ValidationTests(unittest.TestCase):
    def test_valid_config_passes(self):
        config = SolarConfig(
            lat=10.8231,
            lon=106.6297,
            target_date=date(2026, 5, 28),
            capacity_kw=5.0,
            tilt=15.0,
            azimuth=180.0,
            losses=0.14,
            timezone="auto",
        )

        validate_config(config)

    def test_invalid_latitude_fails(self):
        config = SolarConfig(
            lat=91.0,
            lon=106.6297,
            target_date=date(2026, 5, 28),
            capacity_kw=5.0,
            tilt=15.0,
            azimuth=180.0,
            losses=0.14,
            timezone="auto",
        )

        with self.assertRaisesRegex(ValueError, "latitude"):
            validate_config(config)

    def test_invalid_capacity_fails(self):
        config = SolarConfig(
            lat=10.8231,
            lon=106.6297,
            target_date=date(2026, 5, 28),
            capacity_kw=0.0,
            tilt=15.0,
            azimuth=180.0,
            losses=0.14,
            timezone="auto",
        )

        with self.assertRaisesRegex(ValueError, "capacity"):
            validate_config(config)


class WeatherFrameTests(unittest.TestCase):
    def test_build_weather_frame_filters_target_date_and_timezone(self):
        payload = {
            "timezone": "Asia/Ho_Chi_Minh",
            "hourly": {
                "time": [
                    "2026-05-27T23:00",
                    "2026-05-28T00:00",
                    "2026-05-28T01:00",
                ],
                "shortwave_radiation": [0.0, 0.0, 25.0],
                "temperature_2m": [28.0, 27.5, 27.0],
                "wind_speed_10m": [1.0, 1.1, 1.2],
            },
        }

        frame = build_weather_frame(payload, date(2026, 5, 28))

        self.assertEqual(len(frame), 2)
        self.assertEqual(str(frame.index.tz), "Asia/Ho_Chi_Minh")
        self.assertEqual(frame.attrs["timezone"], "Asia/Ho_Chi_Minh")
        self.assertEqual(frame.iloc[1]["shortwave_radiation"], 25.0)

    def test_build_weather_frame_rejects_missing_hourly_field(self):
        with self.assertRaisesRegex(RuntimeError, "hourly"):
            build_weather_frame({"timezone": "UTC"}, date(2026, 5, 28))

    def test_build_weather_frame_rejects_missing_target_date(self):
        payload = {
            "timezone": "UTC",
            "hourly": {
                "time": ["2026-05-27T12:00"],
                "shortwave_radiation": [800.0],
                "temperature_2m": [25.0],
                "wind_speed_10m": [2.0],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "requested date"):
            build_weather_frame(payload, date(2026, 5, 28))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Create importable module skeleton**

Create `estimate_solar.py` with enough structure for tests to import, while leaving behavior absent so the tests fail for the right reasons:

```python
from dataclasses import dataclass
from datetime import date


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


def validate_config(config: SolarConfig) -> None:
    raise NotImplementedError("validate_config is not implemented")


def build_weather_frame(payload: dict, target_date: date):
    raise NotImplementedError("build_weather_frame is not implemented")
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m unittest tests.test_estimate_solar -v
```

Expected: tests fail with `NotImplementedError` from `validate_config` and `build_weather_frame`.

---

### Task 3: Implement Validation And Weather Frame Conversion

**Files:**
- Modify: `estimate_solar.py`

- [ ] **Step 1: Replace skeleton with validation and dataframe parsing**

Replace `estimate_solar.py` with:

```python
import argparse
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd


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
    if not -90 <= config.lat <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not -180 <= config.lon <= 180:
        raise ValueError("longitude must be between -180 and 180")
    if config.capacity_kw <= 0:
        raise ValueError("capacity must be positive")
    if not 0 <= config.tilt <= 90:
        raise ValueError("tilt must be between 0 and 90")
    if not 0 <= config.azimuth <= 360:
        raise ValueError("azimuth must be between 0 and 360")
    if not 0 <= config.losses < 1:
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

    lengths = {name: len(hourly[name]) for name in required}
    if len(set(lengths.values())) != 1:
        raise RuntimeError(f"Open-Meteo hourly field lengths differ: {lengths}")

    timezone = payload.get("timezone") or "UTC"
    try:
        tzinfo = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Open-Meteo returned unknown timezone: {timezone}") from exc

    index = pd.to_datetime(hourly["time"])
    if index.tz is None:
        index = index.tz_localize(tzinfo)
    else:
        index = index.tz_convert(tzinfo)

    frame = pd.DataFrame(
        {
            "shortwave_radiation": pd.to_numeric(hourly["shortwave_radiation"], errors="coerce"),
            "temperature_2m": pd.to_numeric(hourly["temperature_2m"], errors="coerce"),
            "wind_speed_10m": pd.to_numeric(hourly["wind_speed_10m"], errors="coerce"),
        },
        index=index,
    )
    frame = frame.dropna()
    frame = frame[frame.index.date == target_date]
    if frame.empty:
        raise RuntimeError(f"requested date {target_date.isoformat()} is not present in weather response")

    frame.attrs["timezone"] = timezone
    return frame
```

- [ ] **Step 2: Run validation and parsing tests**

Run:

```bash
python -m unittest tests.test_estimate_solar -v
```

Expected: all tests in `ValidationTests` and `WeatherFrameTests` pass.

---

### Task 4: Add PV Model Tests

**Files:**
- Modify: `tests/test_estimate_solar.py`

- [ ] **Step 1: Add model tests**

Add this import to the top of `tests/test_estimate_solar.py`:

```python
from estimate_solar import estimate_energy
```

Add this test class before the `if __name__ == "__main__":` block:

```python
class EnergyModelTests(unittest.TestCase):
    def test_estimate_energy_returns_expected_columns_and_positive_midday_output(self):
        index = pd.date_range("2026-05-28 10:00", periods=3, freq="h", tz="Asia/Ho_Chi_Minh")
        weather = pd.DataFrame(
            {
                "shortwave_radiation": [600.0, 850.0, 650.0],
                "temperature_2m": [30.0, 32.0, 31.0],
                "wind_speed_10m": [1.5, 2.0, 1.8],
            },
            index=index,
        )
        weather.attrs["timezone"] = "Asia/Ho_Chi_Minh"
        config = SolarConfig(
            lat=10.8231,
            lon=106.6297,
            target_date=date(2026, 5, 28),
            capacity_kw=5.0,
            tilt=15.0,
            azimuth=180.0,
            losses=0.14,
            timezone="auto",
        )

        result = estimate_energy(weather, config)

        self.assertEqual(
            list(result.columns),
            ["ghi_w_m2", "poa_w_m2", "power_kw", "energy_kwh"],
        )
        self.assertGreater(result["energy_kwh"].sum(), 0)
        self.assertTrue((result["power_kw"] >= 0).all())
        self.assertTrue((result["energy_kwh"] >= 0).all())
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m unittest tests.test_estimate_solar -v
```

Expected: import fails or the model test fails because `estimate_energy` is not defined.

---

### Task 5: Implement PVWatts-Style Energy Estimate

**Files:**
- Modify: `estimate_solar.py`

- [ ] **Step 1: Add imports**

Add these imports near the existing imports in `estimate_solar.py`:

```python
import pvlib
```

- [ ] **Step 2: Add energy model function**

Add this function after `build_weather_frame()`:

```python
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

    cell_temperature = pvlib.temperature.pvwatts_cell(
        poa_global=poa_global,
        temp_air=weather["temperature_2m"],
        wind_speed=weather["wind_speed_10m"],
    )
    dc_watts = pvlib.pvsystem.pvwatts_dc(
        g_poa_effective=poa_global,
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
```

- [ ] **Step 3: Run tests**

Run:

```bash
python -m unittest tests.test_estimate_solar -v
```

Expected: all tests pass.

---

### Task 6: Add Open-Meteo Fetching And CLI Reporting

**Files:**
- Modify: `estimate_solar.py`

- [ ] **Step 1: Add `requests` import and API constant**

Add these lines near the top of `estimate_solar.py`:

```python
import sys

import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
```

- [ ] **Step 2: Add fetch, argument parsing, report, and main functions**

Add these functions after `estimate_energy()`:

```python
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
        payload = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Open-Meteo request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("Open-Meteo returned invalid JSON") from exc

    if payload.get("error"):
        reason = payload.get("reason") or "unknown API error"
        raise RuntimeError(f"Open-Meteo error: {reason}")
    return payload


def parse_args(argv: list[str] | None = None) -> SolarConfig:
    parser = argparse.ArgumentParser(description="Estimate fixed-array solar energy from weather forecast data.")
    parser.add_argument("--lat", type=float, required=True, help="Latitude in decimal degrees.")
    parser.add_argument("--lon", type=float, required=True, help="Longitude in decimal degrees.")
    parser.add_argument("--date", dest="target_date", type=parse_date, required=True, help="Date in YYYY-MM-DD format.")
    parser.add_argument("--capacity-kw", type=float, required=True, help="DC array capacity in kW.")
    parser.add_argument("--tilt", type=float, default=15.0, help="Panel tilt in degrees. Default: 15.")
    parser.add_argument("--azimuth", type=float, default=180.0, help="Panel azimuth in degrees. 180 means south. Default: 180.")
    parser.add_argument("--losses", type=float, default=0.14, help="Fractional system losses. Default: 0.14.")
    parser.add_argument("--timezone", default="auto", help="Open-Meteo timezone. Default: auto.")
    args = parser.parse_args(argv)

    config = SolarConfig(
        lat=args.lat,
        lon=args.lon,
        target_date=args.target_date,
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


def main(argv: list[str] | None = None) -> int:
    try:
        config = parse_args(argv)
        payload = fetch_weather(config)
        weather = build_weather_frame(payload, config.target_date)
        estimate = estimate_energy(weather, config)
        print_report(estimate)
        return 0
    except (RuntimeError, ValueError, argparse.ArgumentTypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run unit tests**

Run:

```bash
python -m unittest tests.test_estimate_solar -v
```

Expected: all tests pass.

- [ ] **Step 4: Run bytecode compilation**

Run:

```bash
python -m py_compile estimate_solar.py tests/test_estimate_solar.py
```

Expected: command exits with code `0`.

---

### Task 7: Manual Forecast Verification

**Files:**
- No file changes.

- [ ] **Step 1: Run Ho Chi Minh City forecast example**

Run:

```bash
python estimate_solar.py --lat 10.8231 --lon 106.6297 --date 2026-05-28 --capacity-kw 5 --tilt 15 --azimuth 180
```

Expected: output starts with:

```text
time,ghi_w_m2,poa_w_m2,power_kw,energy_kwh
```

Expected: output ends with a line matching this shape:

```text
daily_total_kwh,12.345
```

The exact number depends on the current Open-Meteo forecast returned at execution time.

- [ ] **Step 2: Run invalid input smoke test**

Run:

```bash
python estimate_solar.py --lat 91 --lon 106.6297 --date 2026-05-28 --capacity-kw 5
```

Expected: command exits with code `1` and prints:

```text
error: latitude must be between -90 and 90
```

---

### Task 8: Final Review

**Files:**
- Review: `estimate_solar.py`
- Review: `requirements.txt`
- Review: `tests/test_estimate_solar.py`

- [ ] **Step 1: Confirm spec coverage**

Check these requirements are present in code:

```text
CLI accepts --lat, --lon, --date, --capacity-kw, --tilt, --azimuth, --losses, --timezone.
Open-Meteo request includes shortwave_radiation, temperature_2m, wind_speed_10m.
pvlib calculates solar position, DNI/DHI estimate, plane-of-array irradiance, cell temperature, and PVWatts DC output.
Hourly report includes local time, GHI, POA irradiance, power, and energy.
Daily total is printed.
Validation errors are explicit for coordinate, capacity, tilt, azimuth, losses, API, and missing date cases.
```

- [ ] **Step 2: Show final verification commands**

Run:

```bash
python -m unittest tests.test_estimate_solar -v
python -m py_compile estimate_solar.py tests/test_estimate_solar.py
```

Expected: both commands exit with code `0`.

- [ ] **Step 3: Commit when repository exists**

This workspace is not currently a git repository. If the user initializes git later, commit with:

```bash
git add estimate_solar.py requirements.txt tests/test_estimate_solar.py docs/superpowers/specs/2026-05-28-weather-aware-solar-estimator-design.md docs/superpowers/plans/2026-05-28-weather-aware-solar-estimator.md
git commit -m "feat: add weather-aware solar estimator"
```
