import unittest

from units import celsius_to_fahrenheit, convert_length, format_quantity


class ConvertLengthTests(unittest.TestCase):
    def test_kilometres_to_metres(self) -> None:
        self.assertAlmostEqual(convert_length(1.5, "km", "m"), 1500.0)

    def test_feet_to_inches(self) -> None:
        self.assertAlmostEqual(convert_length(1, "ft", "in"), 12.0)

    def test_unknown_unit(self) -> None:
        with self.assertRaises(ValueError):
            convert_length(1, "mile", "m")


class TemperatureTests(unittest.TestCase):
    def test_freezing_point(self) -> None:
        self.assertEqual(celsius_to_fahrenheit(0), 32)

    def test_boiling_point(self) -> None:
        self.assertEqual(celsius_to_fahrenheit(100), 212)


class FormatQuantityTests(unittest.TestCase):
    def test_two_places_by_default(self) -> None:
        self.assertEqual(format_quantity(1.5, "km"), "1.50 km")

    def test_no_places(self) -> None:
        self.assertEqual(format_quantity(3, "m", places=0), "3 m")


if __name__ == "__main__":
    unittest.main()
