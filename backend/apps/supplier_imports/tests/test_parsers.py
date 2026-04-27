from django.test import SimpleTestCase

from apps.supplier_imports.parsers import ParserContext
from apps.supplier_imports.parsers.gpl_parser import GPLParser
from apps.supplier_imports.parsers.utr_parser import UTRParser


class UTRParserTests(SimpleTestCase):
    def test_parse_json_details_payload(self):
        content = """
        {
          "details": [
            {
              "id": 58023,
              "productCode": "0095421",
              "article": "OC90",
              "displayBrand": "MAHLE - KNECHT",
              "title": "Фильтр оливи",
              "yourPrice": {"amount": 127.89, "currency": {"code": "UAH"}},
              "remains": [{"remain": "4"}, {"remain": "> 10"}]
            }
          ]
        }
        """

        result = UTRParser().parse_content(
            content,
            file_name="utr.json",
            context=ParserContext(source_code="utr"),
        )

        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.offers), 1)

        offer = result.offers[0]
        self.assertEqual(offer.external_sku, "0095421")
        self.assertEqual(offer.article, "OC90")
        self.assertEqual(offer.brand_name, "MAHLE - KNECHT")
        self.assertEqual(str(offer.price), "127.89")
        self.assertEqual(offer.currency, "UAH")
        self.assertEqual(offer.stock_qty, 14)

    def test_parse_table_ignores_json_like_fragments_without_false_issues(self):
        content = """Артикул UTR;Артикул;Найменування;Бренд;Валюта;Ціна;Київська обл.
SBL 407533;407533;Стійка [1,2,3];STABILUS;UAH;13343.22;1
"""

        result = UTRParser().parse_content(
            content,
            file_name="utr.csv",
            context=ParserContext(source_code="utr"),
        )

        self.assertEqual(len(result.offers), 1)
        self.assertEqual(len(result.issues), 0)

    def test_parse_rows_uses_table_rows_directly(self):
        rows = [
            (
                2,
                {
                    "Артикул UTR": "SBL 407533",
                    "Артикул": "407533",
                    "Найменування": "Стійка [1,2,3]",
                    "Бренд": "STABILUS",
                    "Валюта": "UAH",
                    "Ціна": "13343.22",
                    "Київська обл.": "1",
                },
            )
        ]

        result = UTRParser().parse_rows(
            rows,
            file_name="utr.xlsx",
            context=ParserContext(source_code="utr"),
        )

        self.assertEqual(len(result.offers), 1)
        self.assertEqual(result.offers[0].external_sku, "SBL 407533")
        self.assertEqual(result.offers[0].stock_qty, 1)


class GPLParserTests(SimpleTestCase):
    def test_parse_prices_items_payload(self):
        content = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "opt2_currency_980": "100.00",
                "opt4_currency_980": "90.00",
                "opt10_currency_980": "80.00",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95",
                "count_warehouse_4": " > 100"
              }
            ]
          }
        }
        """

        result = GPLParser().parse_content(
            content,
            file_name="gpl.json",
            context=ParserContext(source_code="gpl"),
        )

        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.offers), 1)

        offer = result.offers[0]
        self.assertEqual(offer.external_sku, "0007523")
        self.assertEqual(offer.article, "AR-20488")
        self.assertEqual(offer.brand_name, "ARAL")
        self.assertEqual(str(offer.price), "140.24")
        self.assertEqual(offer.currency, "UAH")
        self.assertEqual(offer.stock_qty, 195)
        self.assertEqual([level["label"] for level in offer.price_levels], ["ОПТ2", "ОПТ4", "ОПТ10", "РРЦ"])
        self.assertEqual(offer.price_levels[-1]["value"], "140.24")
        self.assertTrue(offer.price_levels[-1]["is_primary"])

    def test_parse_table_ignores_json_like_fragments_without_false_issues(self):
        content = """Код;Категорія;Артикул;Найменування;Група ТД;РРЦ грн.;Склад ПЛТВ
0001;ARAL;AR-20488;Aral [1,2,3];ARAL;140.24;15
"""

        result = GPLParser().parse_content(
            content,
            file_name="gpl.csv",
            context=ParserContext(source_code="gpl"),
        )

        self.assertEqual(len(result.offers), 1)
        self.assertEqual(len(result.issues), 0)

    def test_parse_rows_uses_table_rows_directly(self):
        rows = [
            (
                2,
                {
                    "Код": "0001",
                    "Категорія": "ARAL",
                    "Артикул": "AR-20488",
                    "Найменування": "Aral [1,2,3]",
                    "Група ТД": "ARAL",
                    "Ціна ОПТ2 грн.": "100.00",
                    "Ціна ОПТ4 грн.": "90.00",
                    "Ціна ОПТ10 грн.": "80.00",
                    "РРЦ грн.": "140.24",
                    "Склад ПЛТВ": "15",
                },
            )
        ]

        result = GPLParser().parse_rows(
            rows,
            file_name="gpl.xlsx",
            context=ParserContext(source_code="gpl"),
        )

        self.assertEqual(len(result.offers), 1)
        self.assertEqual(result.offers[0].external_sku, "0001")
        self.assertEqual(str(result.offers[0].price), "140.24")
        self.assertEqual(result.offers[0].stock_qty, 15)
        self.assertEqual([level["label"] for level in result.offers[0].price_levels], ["ОПТ2", "ОПТ4", "ОПТ10", "РРЦ"])
