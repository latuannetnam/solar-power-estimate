# Weather-Aware Solar Estimator Design

## Goal

Build a simple Python CLI script that estimates solar energy production for one fixed photovoltaic array at a given location and date.

The script should use weather forecast data from Open-Meteo and model the array with `pvlib`, so the estimate accounts for sun position, panel tilt, panel azimuth, irradiance, ambient temperature, wind speed, and configurable system losses.

## Scope

The first version supports one fixed array. It does not support multiple arrays, battery simulation, grid import/export, tariffs, historical billing analysis, or inverter telemetry.

## User Interface

Create a script named `estimate_solar.py`.

Required CLI arguments:

- `--lat`: latitude in decimal degrees.
- `--lon`: longitude in decimal degrees.
- `--date`: target date in `YYYY-MM-DD` format.
- `--capacity-kw`: DC array capacity in kilowatts.

Optional CLI arguments:

- `--tilt`: fixed panel tilt in degrees. Default: `15`.
- `--azimuth`: fixed panel azimuth in degrees. Default: `180`, where `180` means south-facing.
- `--losses`: fractional system losses. Default: `0.14`.
- `--timezone`: timezone sent to Open-Meteo. Default: `auto`.

Example:

```bash
python estimate_solar.py --lat 10.8231 --lon 106.6297 --date 2026-05-28 --capacity-kw 5 --tilt 15 --azimuth 180
```

## Data Source

Use the Open-Meteo forecast API with hourly values:

- `shortwave_radiation`
- `temperature_2m`
- `wind_speed_10m`

The script will request the selected date as both `start_date` and `end_date`.

## Architecture

Keep the implementation in one script, but split behavior into small functions:

- `parse_args()`: parse and validate CLI arguments.
- `fetch_weather()`: call Open-Meteo and return hourly weather data.
- `build_weather_frame()`: convert API response into a timezone-aware pandas dataframe.
- `estimate_energy()`: run the `pvlib` model and return hourly estimated production.
- `print_report()`: print hourly rows and daily total energy.

This keeps the script easy to read while leaving clear boundaries for future tests or module extraction.

## Modeling Approach

The script will:

1. Fetch hourly weather data for the target location and date.
2. Build a `pvlib.location.Location` from latitude, longitude, and timezone.
3. Calculate solar position for each hourly timestamp.
4. Estimate DNI and DHI from global horizontal irradiance using `pvlib.irradiance.erbs`.
5. Transpose irradiance onto the fixed panel plane using tilt and azimuth.
6. Estimate cell temperature from plane-of-array irradiance, ambient temperature, and wind speed.
7. Estimate DC output using a PVWatts-style model with the requested `capacity_kw`.
8. Apply configured losses.
9. Convert hourly average power to hourly energy and sum daily kWh.

## Output

Print an hourly table with:

- local time
- global horizontal irradiance in W/m2
- plane-of-array irradiance in W/m2
- estimated array power in kW
- estimated hourly energy in kWh

Print a final daily total in kWh.

## Error Handling

The script should fail with clear messages when:

- latitude is outside `-90..90`
- longitude is outside `-180..180`
- capacity is not positive
- tilt is outside `0..90`
- azimuth is outside `0..360`
- losses are outside `0..1`
- Open-Meteo returns an error or malformed data
- the requested date is not present in the API response

## Dependencies

Create `requirements.txt` with:

```text
requests
pandas
pvlib
```

## Verification

Minimum verification for the first implementation:

- Run Python bytecode compilation on `estimate_solar.py`.
- Run the script for Ho Chi Minh City with a small system and confirm it prints hourly output plus a daily total.

Optional later tests:

- Unit test argument validation.
- Unit test energy calculation using a small synthetic dataframe.
- Mock Open-Meteo response for API parsing.
