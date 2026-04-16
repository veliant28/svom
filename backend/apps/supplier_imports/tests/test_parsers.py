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
