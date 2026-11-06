"""Test fixtures: a small note, a synthetic maximum note, and a matching BOOK FACTS email. Stdlib only.

The full note uses check.py's own caps (top 5, AI 8, earnings preview 4 paragraphs), every other section filled
(4 earnings blocks, peers 6, coming up 10, also today 10) and a 30-name book (20 holdings, 10 watch, the size of the
list on 2026-11-06), each name with `items` items of about 240 characters and 2 links, and a pre-market quote of 1%
or more (shown under the name and in the pre-market line) on the first `premarket` names.
"""
import copy

HOLD = ["ABBV", "AMZN", "APO", "BAM", "BIP", "BN", "BX", "ENB", "GOOGL", "KKR",
        "KLAC", "MA", "MDT", "MELI", "MSFT", "RY", "SLF", "TD", "TSN", "VRTX"]
WATCH = ["CLS", "CRDO", "DAVE", "LITE", "PACS", "SEZL", "SNDK", "STRL", "TTMI", "VICR"]
TSX = {"BAM": "BAM.TO", "BN": "BN.TO", "CLS": "CLS.TO", "ENB": "ENB.TO", "RY": "RY.TO", "SLF": "SLF.TO",
       "TD": "TD.TO", "BIP": "BIP-UN.TO"}
SESSION = "2026-11-05"


def facts_line(t, i):
    sym = TSX.get(t, t)
    ccy = "CAD" if t in TSX else "USD"
    close = 1234.56 if t == "KLAC" else 100 + i * 7.25
    if t == "MSFT":
        close = 535.93
    move = ", unchanged on the day" if i % 7 == 3 else ", %s %.1f%% on the day" % ("up" if i % 2 else "down", 0.4 + i / 10)
    line = "%s closed at %s %s on %s%s" % (sym, "{:,.2f}".format(close), ccy, SESSION, move)
    if i % 5 != 4:  # every fifth name has no valuation clause
        line += "; EV/EBIT %.1fx against a 10-year median of %.1fx" % (18 + i / 3, 20 + i / 4)
    return line + "."


def facts_lines(hold=HOLD, watch=WATCH):
    return [facts_line(t, i) for i, t in enumerate(list(hold) + list(watch))]


def facts_email(lines):
    return ("Book facts 2026-11-06: no change\n\nNo change in any of the 30 names.\n\n--- BOOK FACTS ---\n"
            + "\n".join(lines) + "\n--- END FACTS ---\n\nEmail a ticker to someone for the full page.\n")


def _links(n=2):
    return [{"name": "Company release %d" % k, "url": "https://www.example.com/news/2026/11/05/item-%d" % k} for k in range(n)]


def _price(t, i):
    return {"ticker": t, "currency": "CAD" if t in TSX else "USD", "close": 536.21 if t == "MSFT" else 101 + i * 7.25,
            "prev_close": 99 + i * 7.25, "close_5d_ago": 95 + i * 7, "high52": 150 + i * 8,
            "day_low": 90 + i * 7, "day_high": 120 + i * 8, "close_date": SESSION, "avg_target": 110 + i * 7}


def note(hold=HOLD, watch=WATCH, items=1, facts=True):
    names = list(hold) + list(watch)
    text = ("Company said third-quarter revenue rose 12% to 4.1 billion dollars, ahead of its own guidance range, and "
            "raised the full-year outlook; the release names higher volumes in its core segment and a one-time "
            "charge of 85 million dollars tied to a plant closure.")
    tk = lambda t: {"ticker": t, "company": t + " Corporation Holdings Inc.",
                    "items": [{"date": "2026-11-05", "category": "Earnings", "text": text, "links": _links()}
                              for _ in range(items)]}
    d = {"subject": "Book update 2026-11-06", "date_label": "Friday, November 6, 2026", "window": "06:00 to 06:00",
         "price_session": "Thu Nov 5", "price_session_date": SESSION, "premarket_as_of": "07:10 ET",
         "version": "v0.9", "summary": "Earnings day for four names; the book rose with the market.",
         "market": {"day": "Thu", "spx": 0.6, "ndx": 0.9, "tsx": 0.2, "us10y": 4.12, "us10y_bp": -3, "usdcad": 1.3912,
                    "notes": ["Treasury yields fell after the jobless claims report."], "links": _links(1)},
         "top": [{"ticker": t, "headline": "Third-quarter results beat its guidance; outlook raised", "status": "results"}
                 for t in names[:5]],
         "holdings": [tk(t) for t in hold], "watchlist": [tk(t) for t in watch],
         "prices": {"holdings": [_price(t, i) for i, t in enumerate(hold)],
                    "watchlist": [_price(t, len(hold) + i) for i, t in enumerate(watch)],
                    "source": {"name": "StockAnalysis", "url": "https://stockanalysis.com/"}},
         "list": {"hold": list(hold), "watch": list(watch), "targets": "400 on CLS", "ciks": "none"},
         "sedi_names": ["RY", "TD"], "gaps": []}
    if facts:
        d["facts"] = facts_lines(hold, watch)
    return d


def full_note(items=1, premarket=0):
    d = note(items=items)
    para = ("Analysts expect revenue near 12.4 billion dollars and earnings per share of 2.31; the company guided to "
            "growth of 9% to 11% and named data-centre demand as the main driver for the quarter.")
    d["earnings"] = [{"ticker": t, "status": "after close", "label": "Fiscal Q3 2026, reported Nov 5", "kind": "preview",
                      "table": {"est_header": "Consensus", "note": "Consensus from StockAnalysis.",
                                "rows": [{"label": l, "actual": "12.6 B", "est": "12.4 B", "yr_ago": "11.1 B"}
                                         for l in ("Revenue", "EPS", "Operating margin", "Free cash flow")]},
                      "paragraphs": [{"label": "Point %d" % k, "text": para, "links": _links(1)} for k in range(4)],
                      "doc_links": _links(2)} for t in ("MSFT", "KLAC", "VRTX", "MELI")]
    d["no_source_moves"] = [{"ticker": "SEZL", "status": "watch", "pct": 4.2}]
    d["peers"] = [{"date": "2026-11-05", "category": "Earnings", "text": "Peer reported results above estimates; "
                   "shares rose 6% after hours on higher guidance.", "links": _links()} for _ in range(6)]
    d["ai"] = [{"name": "Company %d" % k, "company": "Private lab", "date": "2026-11-05", "category": "Deal",
                "text": "Signed a multi-year compute agreement worth about 10 billion dollars, per the release.",
                "links": _links()} for k in range(8)]
    d["coming_up"] = [{"date": "2026-11-1%d" % k, "who": "MSFT", "text": "Annual shareholder meeting", "links": _links(1)}
                      for k in range(10)]
    d["next_earnings"] = [{"date": "2026-11-1%d" % k, "names": ["CRDO*", "LITE"]} for k in range(5)]
    d["also_today"] = [{"ticker": t, "text": "Declared a quarterly dividend, unchanged from the last one.",
                        "links": _links(1)} for t in HOLD[:10]]
    for p in (d["prices"]["holdings"] + d["prices"]["watchlist"])[:premarket]:
        p["premarket"] = {"price": p["close"] * 1.02, "time": "07:05"}
    d["gaps"] = ["SEDI not checked."]
    return d


def with_(d, **kw):
    out = copy.deepcopy(d)
    out.update(kw)
    return out
