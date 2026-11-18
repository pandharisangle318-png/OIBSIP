import unittest
from datetime import datetime, timezone

from weatherdesk import utils


class TemperatureTests(unittest.TestCase):
    def test_known_conversions(self):
        self.assertAlmostEqual(utils.c_to_f(0), 32.0)
        self.assertAlmostEqual(utils.c_to_f(100), 212.0)
        self.assertAlmostEqual(utils.c_to_f(-40), -40.0)
        self.assertAlmostEqual(utils.c_to_f(37), 98.6, places=1)

    def test_round_trip(self):
        for c in (-30.5, 0, 12.3, 45):
            self.assertAlmostEqual(utils.f_to_c(utils.c_to_f(c)), c)

    def test_convert_temp_units(self):
        self.assertEqual(utils.convert_temp(20, "C"), 20)
        self.assertAlmostEqual(utils.convert_temp(20, "F"), 68.0)

    def test_format_temp(self):
        self.assertEqual(utils.format_temp(21.4, "C"), "21\u00b0")
        self.assertEqual(utils.format_temp(21.5, "C"), "22\u00b0")
        self.assertEqual(utils.format_temp(-0.2, "C"), "0\u00b0")      # never "-0"
        self.assertEqual(utils.format_temp(-2.5, "C"), "-3\u00b0")
        self.assertEqual(utils.format_temp(0, "F"), "32\u00b0")


class FormattingTests(unittest.TestCase):
    def test_wind_units(self):
        self.assertEqual(utils.format_wind(10, "C"), "36 km/h")
        self.assertEqual(utils.format_wind(10, "F"), "22 mph")

    def test_compass(self):
        self.assertEqual(utils.compass_direction(0), "N")
        self.assertEqual(utils.compass_direction(90), "E")
        self.assertEqual(utils.compass_direction(250), "WSW")
        self.assertEqual(utils.compass_direction(359), "N")
        self.assertEqual(utils.compass_direction(None), "")

    def test_visibility(self):
        self.assertEqual(utils.format_visibility(10000), "10 km")
        self.assertEqual(utils.format_visibility(6000), "6 km")
        self.assertEqual(utils.format_visibility(1500), "1.5 km")
        self.assertEqual(utils.format_visibility(None), "n/a")
        self.assertEqual(utils.format_visibility(10000, "F"), "6.2 mi")

    def test_coords(self):
        self.assertEqual(utils.format_coords(19.0144, 72.8479), "19.01\u00b0 N, 72.85\u00b0 E")
        self.assertEqual(utils.format_coords(-33.87, -70.5), "33.87\u00b0 S, 70.50\u00b0 W")

    def test_duration_and_case(self):
        self.assertEqual(utils.format_duration(11 * 60 + 20), "11h 20m")
        self.assertEqual(utils.sentence_case("light rain"), "Light rain")
        self.assertEqual(utils.sentence_case(""), "")


class TimeTests(unittest.TestCase):
    def test_local_now_applies_offset(self):
        utc = datetime(2024, 11, 15, 7, 0, tzinfo=timezone.utc)
        local = utils.local_now(19800, utc)
        self.assertEqual((local.hour, local.minute), (12, 30))
        self.assertEqual(utils.local_now(-18000, utc).hour, 2)

    def test_clock_format(self):
        utc = datetime(2024, 11, 15, 7, 5, tzinfo=timezone.utc)
        text = utils.format_clock(utils.local_now(0, utc))
        self.assertIn("Friday, 15 November", text)
        self.assertIn("07:05", text)


if __name__ == "__main__":
    unittest.main()
