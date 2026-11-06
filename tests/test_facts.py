import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]
import render  # noqa: E402

ENGINE_MAP = os.path.join(os.path.dirname(HERE), "..", "stock-engine", "config", "book_symbol_map.yaml")


class ParseFact(unittest.TestCase):
    def test_up_with_valuation(self):
        f = render.parse_fact("MSFT closed at 535.93 USD on 2026-11-05, up 0.4% on the day; EV/EBIT 24.2x against a "
                              "10-year median of 24.8x.")
        self.assertEqual((f["sym"], f["close"], f["ccy"], f["date"], f["pct1d"]), ("MSFT", 535.93, "USD", "2026-11-05", 0.4))
        self.assertEqual(f["val"], "EV/EBIT 24.2x against a 10-year median of 24.8x")

    def test_down_comma_close_no_valuation(self):
        f = render.parse_fact("KLAC closed at 1,234.56 USD on 2026-11-05, down 2.3% on the day.")
        self.assertEqual((f["close"], f["pct1d"], f["val"], f["close_text"]), (1234.56, -2.3, None, "1,234.56"))

    def test_unchanged_and_no_move_clause(self):
        self.assertEqual(render.parse_fact("RY.TO closed at 170.10 CAD on 2026-11-05, unchanged on the day.")["pct1d"], 0.0)
        f = render.parse_fact("NEWCO closed at 9.99 USD on 2026-11-05.")
        self.assertEqual((f["close"], f["pct1d"]), (9.99, None))

    def test_no_price_and_unknown(self):
        f = render.parse_fact("DAVE: no price on 2026-11-06 (no bars).")
        self.assertEqual((f["sym"], f["close"], f["val"]), ("DAVE", None, None))
        self.assertIsNone(render.parse_fact("Something else entirely."))

    def test_valuation_is_text_after_first_semicolon(self):
        line = "BN.TO closed at 80.00 CAD on 2026-11-05, up 1.0% on the day; P/E 20.1x; odd tail."
        self.assertEqual(render.valuation(line), "P/E 20.1x; odd tail")

    def test_block_between_markers_verbatim(self):
        text = "head\r\n--- BOOK FACTS ---\r\nA closed at 1.00 USD on 2026-11-05.\r\n\r\n  B: no price on x (y).\r\n--- END FACTS ---\r\nfoot"
        self.assertEqual(render.facts_block(text), ["A closed at 1.00 USD on 2026-11-05.", "  B: no price on x (y)."])
        self.assertIsNone(render.facts_block("no block here"))


class Map(unittest.TestCase):
    def test_tsx_names(self):
        self.assertEqual(render.facts_sym("RY"), "RY.TO")
        self.assertEqual(render.facts_sym("BIP"), "BIP-UN.TO")
        self.assertEqual(render.facts_sym("MSFT"), "MSFT")
        self.assertEqual(render.book_ticker("RY.TO"), "RY")

    @unittest.skipUnless(os.path.exists(ENGINE_MAP), "stock-engine checkout not next to this repo")
    def test_matches_stock_engine_map(self):
        pairs = dict(re.findall(r"^\s+([A-Z.\-]+):\s*([A-Z.\-]+)\s*$", open(ENGINE_MAP, encoding="utf-8").read(), re.M))
        self.assertEqual(pairs, render.SYMBOL_MAP)


if __name__ == "__main__":
    unittest.main()
