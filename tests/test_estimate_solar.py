import unittest
from datetime import date
from math import inf

import pandas as pd

from estimate_solar import SolarConfig, build_weather_frame, estimate_energy, parse_args, validate_config


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

    def test_non_finite_capacity_fails(self):
        config = SolarConfig(
            lat=10.8231,
            lon=106.6297,
            target_date=date(2026, 5, 28),
            capacity_kw=inf,
            tilt=15.0,
            azimuth=180.0,
            losses=0.14,
            timezone="auto",
        )

        with self.assertRaisesRegex(ValueError, "capacity"):
            validate_config(config)


class ParseArgsTests(unittest.TestCase):
    def test_parse_args_defaults_date_to_today(self):
        config = parse_args(
            [
                "--lat",
                "10.8231",
                "--lon",
                "106.6297",
                "--capacity-kw",
                "5",
            ]
        )

        self.assertEqual(config.target_date, date.today())

    def test_parse_args_keeps_explicit_date(self):
        config = parse_args(
            [
                "--lat",
                "10.8231",
                "--lon",
                "106.6297",
                "--date",
                "2026-05-28",
                "--capacity-kw",
                "5",
            ]
        )

        self.assertEqual(config.target_date, date(2026, 5, 28))


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

    def test_build_weather_frame_rejects_scalar_hourly_field(self):
        payload = {
            "timezone": "UTC",
            "hourly": {
                "time": ["2026-05-28T12:00"],
                "shortwave_radiation": 800.0,
                "temperature_2m": [25.0],
                "wind_speed_10m": [2.0],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "hourly fields must be arrays"):
            build_weather_frame(payload, date(2026, 5, 28))

    def test_build_weather_frame_rejects_malformed_numeric_value(self):
        payload = {
            "timezone": "UTC",
            "hourly": {
                "time": ["2026-05-28T12:00"],
                "shortwave_radiation": ["not-a-number"],
                "temperature_2m": [25.0],
                "wind_speed_10m": [2.0],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "malformed numeric"):
            build_weather_frame(payload, date(2026, 5, 28))

    def test_build_weather_frame_rejects_invalid_timestamp(self):
        payload = {
            "timezone": "UTC",
            "hourly": {
                "time": ["not-a-time"],
                "shortwave_radiation": [800.0],
                "temperature_2m": [25.0],
                "wind_speed_10m": [2.0],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "invalid hourly timestamp"):
            build_weather_frame(payload, date(2026, 5, 28))


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


if __name__ == "__main__":
    unittest.main()
