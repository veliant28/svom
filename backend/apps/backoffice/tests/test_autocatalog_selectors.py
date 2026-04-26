from django.test import TestCase

from apps.autocatalog.models import CarMake, CarModel, CarModification
from apps.backoffice.selectors.autocatalog_selectors import apply_autocatalog_filters
from apps.autocatalog.selectors import get_autocatalog_modifications_queryset


class BackofficeAutocatalogSelectorTests(TestCase):
    def test_selected_make_filter_is_exact_not_substring(self):
        suzuki = CarMake.objects.create(name="Suzuki", slug="suzuki")
        swift = CarModel.objects.create(make=suzuki, name="Swift", slug="swift")
        maruti_suzuki = CarMake.objects.create(name="Maruti Suzuki", slug="maruti-suzuki")
        baleno = CarModel.objects.create(make=maruti_suzuki, name="Baleno", slug="baleno")

        CarModification.objects.create(
            make=suzuki,
            model=swift,
            year=2017,
            modification="1.2",
            capacity="1242",
            engine="K12C",
        )
        CarModification.objects.create(
            make=maruti_suzuki,
            model=baleno,
            year=2017,
            modification="1.2",
            capacity="1242",
            engine="K12M",
        )

        queryset = apply_autocatalog_filters(
            queryset=get_autocatalog_modifications_queryset(),
            params={"make": "Suzuki"},
        )

        self.assertEqual(list(queryset.values_list("make__name", flat=True)), ["Suzuki"])
