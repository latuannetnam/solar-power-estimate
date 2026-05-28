# Solar Power Estimate

Estimate hourly and daily solar energy for one fixed PV array using Open-Meteo weather forecasts and `pvlib`.

## Setup

Install the required Python packages:

```bash
python -m pip install -r requirements.txt
```

## Basic Usage

Run the estimator with latitude, longitude, and DC array capacity:

```bash
python estimate_solar.py --lat 10.8231 --lon 106.6297 --capacity-kw 5
```

Pass `--date` when you want a date other than today:

```bash
python estimate_solar.py --lat 10.8231 --lon 106.6297 --date 2026-05-28 --capacity-kw 5
```

Example with fixed panel geometry:

```bash
python estimate_solar.py --lat 10.8231 --lon 106.6297 --date 2026-05-28 --capacity-kw 5 --tilt 15 --azimuth 180
```

## Arguments

Required:

- `--lat`: latitude in decimal degrees, from `-90` to `90`.
- `--lon`: longitude in decimal degrees, from `-180` to `180`.
- `--capacity-kw`: DC array capacity in kilowatts.

Optional:

- `--date`: forecast date in `YYYY-MM-DD` format. Default: current date.
- `--tilt`: panel tilt in degrees. Default: `15`.
- `--azimuth`: panel azimuth in degrees. Default: `180`.
- `--losses`: fractional system losses. Default: `0.14`.
- `--timezone`: timezone sent to Open-Meteo. Default: `auto`.

Azimuth uses the common `pvlib` convention:

- `0`: north
- `90`: east
- `180`: south
- `270`: west

## Output

The script prints CSV-style rows:

```text
time,ghi_w_m2,poa_w_m2,power_kw,energy_kwh
2026-05-28 10:00,637.0,607.2,2.415,2.415
daily_total_kwh,20.271
```

Columns:

- `time`: local timestamp returned by Open-Meteo.
- `ghi_w_m2`: global horizontal irradiance in W/m2.
- `poa_w_m2`: plane-of-array irradiance in W/m2 after applying tilt and azimuth.
- `power_kw`: estimated array output power in kW.
- `energy_kwh`: estimated energy for that hourly period in kWh.
- `daily_total_kwh`: sum of all hourly energy values.

## Model Notes

The estimator:

1. Fetches hourly `shortwave_radiation`, `temperature_2m`, and `wind_speed_10m` from Open-Meteo.
2. Uses `pvlib` to calculate solar position.
3. Estimates DNI and DHI from GHI using the Erbs model.
4. Converts irradiance to the fixed panel plane using panel tilt and azimuth.
5. Estimates cell temperature using the SAPM open-rack glass/glass temperature model.
6. Estimates DC output using PVWatts.
7. Applies the configured loss fraction.

This is a forecast estimate, not a guarantee of actual inverter production. Real output also depends on shading, soiling, inverter clipping, panel mismatch, wiring, curtailment, local weather accuracy, and equipment-specific behavior.

## Errors

Invalid inputs return a clear error and exit with status code `1`.

Example:

```bash
python estimate_solar.py --lat 91 --lon 106.6297 --date 2026-05-28 --capacity-kw 5
```

Output:

```text
error: latitude must be between -90 and 90
```

## Tests

Run the unit tests:

```bash
python -m unittest tests.test_estimate_solar -v
```

Check Python syntax:

```bash
python -m py_compile estimate_solar.py tests/test_estimate_solar.py
```
