from django.test import SimpleTestCase

from apps.autodb.services.construction_interval import parse_construction_interval_years


class ConstructionIntervalParserTests(SimpleTestCase):
    def test_known_interval_is_parsed(self):
        parsed = parse_construction_interval_years("01.1992 - 05.1994")

        self.assertEqual(parsed.year_from, 1992)
        self.assertEqual(parsed.year_to, 1994)
        self.assertEqual(parsed.raw_construction_interval, "01.1992 - 05.1994")

    def test_unknown_interval_does_not_fail(self):
        parsed = parse_construction_interval_years("unknown")

        self.assertIsNone(parsed.year_from)
        self.assertIsNone(parsed.year_to)
        self.assertEqual(parsed.raw_construction_interval, "unknown")
