import unittest
from datetime import timedelta

from tests.fixtures import BASE, SUNRISE, SUNSET, current_json, forecast_json
from weatherdesk import processing as P
from weatherdesk.errors import DataError
from weatherdesk.models import Condition
from weatherdesk.utils import local_now


class ClassificationTests(unittest.TestCase):
    def test_condition_mapping(self):
        table = {200: Condition.STORM, 232: Condition.STORM, 300: Condition.RAIN, 502: Condition.RAIN,
                 600: Condition.SNOW, 622: Condition.SNOW, 701: Condition.FOG, 741: Condition.FOG,
                 781: Condition.STORM, 800: Condition.CLEAR, 801: Condition.PARTLY,
                 802: Condition.PARTLY, 803: Condition.CLOUDS, 804: Condition.CLOUDS}
        for wid, expected in table.items():
            self.assertEqual(P.classify_condition(wid), expected, wid)


class ParseCurrentTests(unittest.TestCase):
    def test_fields(self):
        cw = P.parse_current(current_json())
        self.assertEqual((cw.city, cw.country), ("Mumbai", "IN"))
        self.assertAlmostEqual(cw.temp_c, 29.4)
        self.assertAlmostEqual(cw.feels_like_c, 33.1)
        self.assertEqual((cw.humidity, cw.pressure_hpa, cw.visibility_m, cw.cloudiness), (70, 1009, 6000, 40))
        self.assertEqual(cw.condition, Condition.PARTLY)
        self.assertEqual(cw.utc_offset, 19800)
        self.assertEqual((cw.observed_at.hour, cw.observed_at.minute), (12, 30))
        self.assertEqual((cw.sunrise.hour, cw.sunrise.minute), (6, 30))
        self.assertEqual((cw.sunset.hour, cw.sunset.minute), (17, 50))
        self.assertFalse(cw.is_night)

    def test_night_detection(self):
        night = BASE + timedelta(hours=8)                    # 20:30 local
        cw = P.parse_current(current_json(dt=int(night.timestamp())))
        self.assertTrue(cw.is_night)

    def test_optional_fields_missing(self):
        data = current_json(name="")
        del data["visibility"]
        del data["wind"]["deg"]
        cw = P.parse_current(data)
        self.assertEqual(cw.city, "Unknown location")
        self.assertIsNone(cw.visibility_m)
        self.assertIsNone(cw.wind_deg)

    def test_missing_sun_times_uses_fallback(self):
        data = current_json()
        data["sys"] = {"country": "NO"}
        cw = P.parse_current(data)
        self.assertEqual(cw.sunrise.hour, 6)
        self.assertEqual(cw.sunset.hour, 18)

    def test_malformed_raises_data_error(self):
        for bad in ({}, {"weather": []}, current_json(main={}), current_json(dt="x")):
            with self.assertRaises(DataError):
                P.parse_current(bad)


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.cw = P.parse_current(current_json())
        self.entries = P.parse_forecast(forecast_json(), self.cw.sunrise, self.cw.sunset)

    def test_parse_forecast(self):
        self.assertEqual(len(self.entries), 40)
        self.assertEqual(self.entries[0].condition, Condition.RAIN)
        self.assertTrue(all(a.time < b.time for a, b in zip(self.entries, self.entries[1:])))
        self.assertEqual((self.entries[0].time - self.cw.observed_at), timedelta(hours=3))

    def test_pod_controls_night_flag(self):
        for e in self.entries:
            self.assertEqual(e.is_night, e.time.hour < 6 or e.time.hour >= 18)

    def test_bad_items_are_skipped_but_empty_raises(self):
        data = forecast_json(count=4)
        data["list"][1] = {"dt": "oops"}
        self.assertEqual(len(P.parse_forecast(data, self.cw.sunrise, self.cw.sunset)), 3)
        with self.assertRaises(DataError):
            P.parse_forecast({"list": []}, self.cw.sunrise, self.cw.sunset)
        with self.assertRaises(DataError):
            P.parse_forecast({}, self.cw.sunrise, self.cw.sunset)

    def test_six_hour_outlook_uses_real_three_hour_points(self):
        now = local_now(19800, BASE)
        outlook = P.six_hour_outlook(self.entries, now)
        self.assertIn(len(outlook), (2, 3))
        self.assertTrue(all(now - timedelta(minutes=30) <= e.time <= now + timedelta(hours=6) for e in outlook))
        gaps = {(b.time - a.time) for a, b in zip(outlook, outlook[1:])}
        self.assertEqual(gaps, {timedelta(hours=3)})

    def test_daily_summary(self):
        days = P.daily_summary(self.entries, days=5)
        self.assertEqual(len(days), 5)
        self.assertEqual(days[0].day, self.cw.observed_at.date())
        for d in days:
            self.assertLessEqual(d.temp_min_c, d.temp_max_c)
            self.assertAlmostEqual(d.pop_max, 0.4)
        full_day = days[1]
        temps = [e.temp_c for e in self.entries if e.time.date() == full_day.day]
        self.assertEqual((full_day.temp_min_c, full_day.temp_max_c), (min(temps), max(temps)))


class DescriptorTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(P.humidity_label(20), "Dry air")
        self.assertEqual(P.humidity_label(85), "Very humid")
        self.assertEqual(P.pressure_label(1000), "Low")
        self.assertEqual(P.pressure_label(1030), "High")
        self.assertEqual(P.pressure_label(1013), "Normal")
        self.assertEqual(P.visibility_label(10000), "Excellent")
        self.assertEqual(P.visibility_label(None), "No data")
        self.assertEqual(P.cloud_label(5), "Clear skies")
        self.assertEqual(P.cloud_label(100), "Overcast")
        self.assertEqual(P.feels_like_label(20, 24), "Warmer than actual")
        self.assertEqual(P.feels_like_label(20, 16), "Cooler than actual")
        self.assertEqual(P.feels_like_label(20, 20.5), "Close to actual")


if __name__ == "__main__":
    unittest.main()
