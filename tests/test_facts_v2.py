"""Engine facts-v2 (Nov 9; stock-engine PM proxy decisions 35-39): the 5-day and 52-week clauses and the MARKET FACTS
block, parsed, rendered and checked. Lines in the older format must keep parsing (the next email may still be one)."""
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]
import check  # noqa: E402
import fixtures  # noqa: E402
import render  # noqa: E402

# Lines the engine printed from real data on 2026-11-09 (closes of 2026-11-06), verbatim.
REAL = [
    "ABBV closed at 291.31 USD on 2026-11-06, up 1.1% on the day and down 1.2% over 5 days, 1.2% below its 52-week high "
    "of 294.89; EV/EBIT 27.6x against a 10-year median of 19.8x.",
    "BAM.TO closed at 74.82 CAD on 2026-11-06, up 1.6% on the day and 10.9% over 5 days, 3.8% below its 52-week high of "
    "77.78.",
    "MELI closed at 1,510.00 USD on 2026-11-06, down 1.3% on the day and 7.1% over 5 days, 34.2% below its 52-week high "
    "of 2,295.00; EV/EBIT 28.8x against a 10-year median of 44.8x.",
    "SNDK closed at 835.06 USD on 2026-11-06, up 3.6% on the day and down 27.4% over 5 days, 64.2% below its 52-week "
    "high of 2,335.00; EV/EBIT 5.4x.",
]
OWNER = ("RY.TO closed at 285.86 CAD on 2026-11-05, down 2.3% on the day and 3.1% over 5 days, 4.6% below its 52-week "
         "high of 299.70; P/TBV 3.5x against a 10-year median of 2.2x.")


def fields(line):
    f = render.parse_fact(line)
    return (f["close"], f["pct1d"], f["pct5d"], f["vs52"], f["high52"], f["val"])


class ParseBothFormats(unittest.TestCase):
    def test_owner_example(self):
        self.assertEqual(fields(OWNER), (285.86, -2.3, -3.1, -4.6, 299.70, "P/TBV 3.5x against a 10-year median of 2.2x"))

    def test_real_engine_lines(self):
        self.assertEqual(fields(REAL[0])[:5], (291.31, 1.1, -1.2, -1.2, 294.89))
        self.assertEqual(fields(REAL[1]), (74.82, 1.6, 10.9, -3.8, 77.78, None))
        self.assertEqual(fields(REAL[2])[:5], (1510.0, -1.3, -7.1, -34.2, 2295.0))
        self.assertEqual(fields(REAL[3]), (835.06, 3.6, -27.4, -64.2, 2335.0, "EV/EBIT 5.4x"))

    def test_every_new_wording(self):
        base = "X closed at 10.00 USD on 2026-11-06"
        cases = {", unchanged on the day and down 3.1% over 5 days.": (0.0, -3.1, None),
                 ", down 3.1% over 5 days, 4.6% below its 52-week high of 12.00.": (None, -3.1, -4.6),
                 ", up 0.2% on the day and unchanged over 5 days.": (0.2, 0.0, None),
                 ", up 0.2% on the day, at its 52-week high of 10.00.": (0.2, None, 0.0),
                 ", 4.6% below its 52-week high of 12.00.": (None, None, -4.6)}
        for tail, want in cases.items():
            f = render.parse_fact(base + tail)
            self.assertIsNotNone(f, tail)
            self.assertEqual((f["pct1d"], f["pct5d"], f["vs52"]), want, tail)

    def test_old_format_unchanged(self):
        f = render.parse_fact("MSFT closed at 535.93 USD on 2026-11-05, up 0.4% on the day; EV/EBIT 24.2x against a "
                              "10-year median of 24.8x.")
        self.assertEqual((f["close"], f["pct1d"], f["pct5d"], f["vs52"], f["high52"]), (535.93, 0.4, None, None, None))
        self.assertEqual(f["val"], "EV/EBIT 24.2x against a 10-year median of 24.8x")
        self.assertFalse(render.facts_v2(render.facts_by_sym(fixtures.facts_lines())))
        self.assertTrue(render.facts_v2(render.facts_by_sym(fixtures.facts_lines(v2=True))))

    def test_market_block_and_lines(self):
        text = fixtures.facts_email(fixtures.facts_lines(v2=True), fixtures.MARKET)
        self.assertEqual(render.market_block(text), fixtures.MARKET)
        self.assertEqual(len(render.facts_block(text)), 30)
        self.assertIsNone(render.market_block(fixtures.facts_email(fixtures.facts_lines())))
        M = render.parse_market(fixtures.MARKET)
        self.assertEqual({k: v.get("pct1d", v.get("rate")) for k, v in M.items()},
                         {"spx": 0.3, "ndx": -1.0, "tsx": 0.0, "usdcad": 1.4113})
        self.assertEqual(render.parse_market(["S&P 500 closed at 7,376.86 on 2026-11-06."])["spx"]["pct1d"], None)


def price_row(h, ticker):
    for row in check.ROW.findall(h):
        cells = [check.txt(c[1]) for c in check.CELL.findall(row)]
        if len(cells) == 5 and cells[0] == ticker:
            return cells
    return None


def market_rows(h):
    out = {}
    for row in check.ROW.findall(h):
        cells = [check.txt(c[1]) for c in check.CELL.findall(row)]
        if len(cells) == 2:
            out.setdefault(cells[0], cells[1])
    return out


class Render(unittest.TestCase):
    def test_v2_columns_come_from_the_line_never_the_web(self):
        d = fixtures.note(v2=True)
        h, _ = render.render_note(d)
        F = render.facts_by_sym(d["facts"])
        for t in ("ABBV", "AMZN", "BN", "ENB", "GOOGL"):
            f = F[render.facts_sym(t)]
            cells = price_row(h, t)
            self.assertEqual(cells[3], check.txt(render.pct(f["pct5d"])), t)
            self.assertEqual(cells[4], check.txt(render.pct(f["vs52"])), t)
        self.assertEqual(price_row(h, "BN")[3], "n/a")   # no 5-day clause: n/a, not the CLOSES history
        self.assertEqual(price_row(h, "ENB")[4], "n/a")  # no 52-week clause: n/a, not the web high52
        self.assertEqual(price_row(h, "GOOGL")[4], "0.0%")
        self.assertIn("52-week highs from the engine", check.txt(h))

    def test_old_format_keeps_todays_columns(self):
        d = fixtures.note()
        h, _ = render.render_note(d)
        p = d["prices"]["holdings"][0]
        f = render.facts_by_sym(d["facts"])["ABBV"]
        cells = price_row(h, "ABBV")
        self.assertEqual(cells[3], check.txt(render.pct(render.pct_val(f["close"], p["close_5d_ago"]))))
        self.assertEqual(cells[4], check.txt(render.pct(render.pct_val(f["close"], p["high52"]))))

    def test_market_box_from_the_block(self):
        h, _ = render.render_note(fixtures.note(v2=True, market=fixtures.MARKET))
        m = market_rows(h)
        self.assertEqual((m["S&P 500"], m["Nasdaq 100"], m["S&P/TSX"], m["USD/CAD"]), ("+0.3%", "-1.0%", "0.0%", "1.4113"))
        self.assertEqual(m["US 10Y"], "4.12%, -3 bp")  # Treasury, not in the block: kept
        self.assertIn("S&P 500 same day +0.3%", check.txt(h))

    def test_rows_the_block_lacks(self):
        h, _ = render.render_note(fixtures.note(v2=True, market=fixtures.MARKET[:1] + fixtures.MARKET[3:]))
        m = market_rows(h)
        self.assertNotIn("Nasdaq 100", m)  # StockAnalysis QQQ: left out
        self.assertEqual(m["S&P/TSX"], "+0.2%")  # CP24/BNN close story: kept
        self.assertIn("Nasdaq 100: not in the engine's market facts today.", check.txt(h))
        h, _ = render.render_note(fixtures.note(v2=True, market=fixtures.MARKET[3:]))
        self.assertNotIn("S&P 500", market_rows(h))
        self.assertIn("S&P 500 and Nasdaq 100: not in the engine's market facts today.", check.txt(h))
        self.assertIn("S&P 500 same day n/a", check.txt(h))

    def test_no_market_facts_keeps_todays_box(self):
        m = market_rows(render.render_note(fixtures.note(v2=True))[0])
        self.assertEqual((m["S&P 500"], m["Nasdaq 100"], m["USD/CAD"]), ("+0.6%", "+0.9%", "1.3912"))


class CheckV2(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.d = fixtures.note(v2=True, market=fixtures.MARKET)
        self.src = fixtures.facts_email(fixtures.facts_lines(v2=True), fixtures.MARKET)

    def run_check(self, d=None, h=None, src=None):
        d = d or self.d
        rh, t = render.render_note(d)
        paths = [os.path.join(self.dir, n) for n in ("n.json", "n.html", "n.txt", "f.txt")]
        json.dump(d, open(paths[0], "w"))
        open(paths[1], "w").write(rh if h is None else h)
        open(paths[2], "w").write(t)
        open(paths[3], "w").write(self.src if src is None else src)
        return check.check_note(*paths)

    def assertFails(self, res, words):
        self.assertTrue(any(words in f for f in res[0]), "no FAIL containing %r in %r" % (words, res[0]))

    def test_v2_note_passes(self):
        F, W, ok = self.run_check()
        self.assertEqual(F, [])
        self.assertTrue(ok.startswith("PASS"))
        self.assertIn("No 52-week high: ENB, SLF, SEZL", W)  # exactly the lines without the clause (fixture i % 9 == 7)

    def test_old_format_email_still_passes(self):
        d, src = fixtures.note(), fixtures.facts_email(fixtures.facts_lines())
        F, W, _ = self.run_check(d, src=src)
        self.assertEqual(F, [])
        self.assertIn("No MARKET FACTS block in the source email: market numbers are from the web", W)

    def cell_swap(self, ticker, k, new):
        h, _ = render.render_note(self.d)
        row = next(r for r in check.ROW.findall(h) if price_row("<tr>%s</tr>" % r, ticker))
        cells = check.CELL.findall(row)
        bad_row = row.replace(">%s<" % cells[k][1], ">%s<" % new, 1) if cells[k][1] in row else None
        self.assertIsNotNone(bad_row)
        return h.replace(row, bad_row, 1)

    def test_tampered_5_day_and_52_week_cells(self):
        self.assertFails(self.run_check(h=self.cell_swap("ABBV", 3, "+9.9%")), "ABBV 5-day shows +9.9%, its facts line says +1.1%")
        self.assertFails(self.run_check(h=self.cell_swap("ABBV", 4, "-9.9%")), "ABBV vs 52-week high shows -9.9%")
        self.assertFails(self.run_check(h=self.cell_swap("BN", 3, "+2.0%")), "BN 5-day shows +2.0%, its facts line says n/a")

    def test_source_5_day_differs_from_note(self):
        src = self.src.replace("up 1.1% over 5 days", "up 1.2% over 5 days", 1)
        self.assertFails(self.run_check(src=src), "ABBV 5-day shows +1.1%, its facts line says +1.2%")

    def test_market_facts_not_verbatim(self):
        d = fixtures.with_(self.d, market_facts=[l.replace("7,376.86", "7,376.87") for l in fixtures.MARKET])
        self.assertFails(self.run_check(d), "Market facts line 1 differs from the source")

    def test_market_number_tampered(self):
        h, _ = render.render_note(self.d)
        self.assertFails(self.run_check(h=h.replace(">1.4113<", ">1.4100<")), "USD/CAD shows 1.4100, the facts block says 1.4113")
        bad = re.sub(r"(Nasdaq 100</td><td[^>]*>)(.*?)(</td>)", lambda m: m.group(1) + "+5.0%" + m.group(3), h, 1)
        self.assertFails(self.run_check(h=bad), "Nasdaq 100 shows +5.0%")
        self.assertFails(self.run_check(h=h.replace("same day <font", "same day <b>x</b><font", 1)),
                         "S&P 500 same day shows")

    def test_web_market_box_is_checked_against_the_block(self):
        d = fixtures.note(v2=True)  # no market_facts: the box shows the web's +0.6% S&P 500
        F, W, _ = self.run_check(d)
        self.assertTrue(any("S&P 500 shows +0.6%, the facts block says +0.3%" in f for f in F), F)
        self.assertTrue(any("note.json has no market_facts" in w for w in W), W)

    def test_market_facts_without_a_source_block(self):
        self.assertFails(self.run_check(src=fixtures.facts_email(fixtures.facts_lines(v2=True))),
                         "note.json has market_facts but the source email has no MARKET FACTS block")

    def test_row_left_out_of_the_box(self):
        h, _ = render.render_note(self.d)
        row = re.search(r"<tr><td[^>]*>Nasdaq 100</td><td[^>]*>.*?</td></tr>", h).group(0)
        self.assertFails(self.run_check(h=h.replace(row, "", 1)), "Nasdaq 100 is in the facts block but not in the note's market box")


if __name__ == "__main__":
    unittest.main()
