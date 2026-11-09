#!/usr/bin/env python3
# book-monitor v0.10 renderer, layout B (desktop briefing; Oct 27: target gaps admin only; Nov 6: prices from the
# engine's BOOK FACTS block; Nov 9: 5-day %, vs 52w high and the market box from the engine's facts-v2 lines and
# MARKET FACTS block): render.py note|admin data.json out_dir | render.py closes facts_email.txt
import json, sys, os, html, re
SANS = "Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
INK, NAVY, MUTED, RULE, SOFT, BOX = "#1a1a1a", "#14243a", "#5f5f5f", "#ececec", "#e3e3e3", "#c9d2de"
UP, DOWN, GREY, LINK = "#137333", "#b3261e", "#5f5f5f", "#1f4e8c"
WRAP = ('<div style="max-width:760px;margin:0 auto;padding:16px 8px;font-family:%s;font-size:14px;line-height:1.5;color:%s">'
        % (SANS, INK))
TARGET_GAP = 0.60
G = "color:%s" % MUTED
TB = '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse%s">%s</table>'
GROUPS = ("holdings", "watchlist")

# The engine's 06:45 "Book facts" email carries one sentence per name between these markers (stock-engine
# book/morning.py fact_sentence; PM proxy decisions 24-29). note.json "facts" holds those lines verbatim.
FACTS_START, FACTS_END = "--- BOOK FACTS ---", "--- END FACTS ---"
# Book ticker -> the engine's symbol, copied from stock-engine config/book_symbol_map.yaml (PM proxy decision 22,
# 2026-11-05). Any other ticker is the engine's <TICKER>.US, which the facts lines print without ".US".
SYMBOL_MAP = {"BAM": "BAM.TO", "BN": "BN.TO", "CLS": "CLS.TO", "ENB": "ENB.TO", "RY": "RY.TO", "SLF": "SLF.TO",
              "TD": "TD.TO", "BIP": "BIP-UN.TO"}
BOOK_TICKER = {v: k for k, v in SYMBOL_MAP.items()}
# Nov 9 (engine facts-v2, PM proxy decisions 35-39): a line may add the 5-day move (its direction word left out when it
# is the day's) and the distance from the 52-week closing high; lines without them (the older format) still match.
FACT_RE = re.compile(r"^(?P<sym>\S+) closed at (?P<close>\d[\d,]*\.\d+) (?:(?P<ccy>[A-Z]{3}) )?on (?P<date>\d{4}-\d{2}-\d{2})"
                     r"(?:, (?P<dir>up|down) (?P<pct>\d+(?:\.\d+)?)% on the day|(?P<flat>, unchanged on the day))?"
                     r"(?:(?: and|,) (?:(?P<dir5>up|down) )?(?P<pct5>\d+(?:\.\d+)?)% over 5 days|(?: and|,) (?P<flat5>unchanged) over 5 days)?"
                     r"(?:, (?P<below>\d+(?:\.\d+)?)% below its 52-week high of (?P<hi>\d[\d,]*\.\d+)"
                     r"|, (?P<athi>at) its 52-week high of (?P<hi_at>\d[\d,]*\.\d+))?(?:; |\.$)")
NOPRICE_RE = re.compile(r"^(?P<sym>\S+): no price on ")
# The engine's MARKET FACTS block (index closes and 1-day %, Bank of Canada USD/CAD); note.json "market_facts" holds its
# lines verbatim. Rows the block lacks keep their other sources (S&P/TSX from the CP24/BNN close story, US 10Y from
# Treasury); S&P 500 and Nasdaq 100 are never taken from StockAnalysis when the block is there.
MARKET_START, MARKET_END = "--- MARKET FACTS ---", "--- END MARKET ---"
MARKET_KEYS = {"S&P 500": "spx", "Nasdaq 100": "ndx", "S&P/TSX Composite": "tsx"}
INDEX_RE = re.compile(r"^(?P<name>S&P 500|Nasdaq 100|S&P/TSX Composite) closed at (?P<close>\d[\d,]*\.\d+) on "
                      r"(?P<date>\d{4}-\d{2}-\d{2})(?:, (?P<dir>up|down) (?P<pct>\d+(?:\.\d+)?)% on the day"
                      r"|(?P<flat>, unchanged on the day))?\.$")
FX_RE = re.compile(r"^USD/CAD (?P<rate>\d+\.\d+) on (?P<date>\d{4}-\d{2}-\d{2}) \(Bank of Canada\)\.$")
WEB_ONLY = ("spx", "ndx")  # StockAnalysis SPY/QQQ: left out, not shown from the web, when the block lacks them


def e(s):
    return html.escape(str(s), quote=True)


def pct_val(c, p):
    if c in (None, "") or p in (None, "") or float(p) == 0:
        return None
    return (float(c) / float(p) - 1) * 100


def pct(v):
    # <font color> renders the same colour as a styled span in 6 fewer bytes; it repeats about 150 times
    if v is None:
        return '<font color="%s">n/a</font>' % GREY
    r = round(v, 1)
    return '<font color="%s">%s%%</font>' % ((UP, "+%.1f" % r) if r > 0 else (DOWN, "%.1f" % r) if r < 0 else (GREY, "0.0"))


def money(x):
    return "n/a" if x is None else "{:,.2f}".format(float(x))


def link(l):
    return '<a href="%s" style="color:%s;text-decoration:none">%s</a>' % (e(l["url"]), LINK, e(l["name"]))


def links(ls):
    return " &middot; ".join(link(l) for l in (ls or []))


def div(style, body):
    return '<div style="%s">%s</div>' % (style, body)


def td(style, body, extra=""):
    return '<td%s%s>%s</td>' % (extra, ' style="%s"' % style if style else "", body)


def tr(*cells):
    """A row whose cells sit at the top: valign once on the row, not vertical-align on every cell."""
    return '<tr valign="top">%s</tr>' % "".join(cells)


def serif_head(t, size=22, top=32):
    return div("font-family:%s;font-size:%dpx;line-height:1.2;color:%s;margin:%dpx 0 6px" % (SERIF, size, NAVY, top), e(t))


def small_caps(t):
    return '<span style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:%s;font-weight:700">%s</span>' % (MUTED, t)


def quote_of(p, k):
    q = p.get(k)
    if q and q.get("price") is not None and p.get("close") is not None:
        return pct_val(q["price"], p["close"]), q
    return None, None


def two_col(left, right, gap=28):
    half = gap // 2
    return TB % (";width:100%;table-layout:fixed", '<tr>%s%s</tr>' % (
        td("vertical-align:top;width:50%%;padding-right:%dpx" % half, left), td("vertical-align:top;width:50%%;padding-left:%dpx" % half, right)))


def facts_sym(ticker):
    return SYMBOL_MAP.get(ticker, ticker)


def book_ticker(sym):
    return BOOK_TICKER.get(sym, sym)


def _block(text, start, end):
    lines = text.replace("\r\n", "\n").split("\n")
    if start not in lines or end not in lines[lines.index(start):]:
        return None
    i = lines.index(start)
    return [l for l in lines[i + 1:lines.index(end, i)] if l.strip()]


def facts_block(text):
    """The lines between the BOOK FACTS markers of a saved email, verbatim (blank lines skipped); None without a block."""
    return _block(text, FACTS_START, FACTS_END)


def market_block(text):
    """The lines between the MARKET FACTS markers of a saved email, verbatim; None without a block (older emails)."""
    return _block(text, MARKET_START, MARKET_END)


def _signed(dr, v, flat):
    return 0.0 if flat else None if v is None else float(v) * (1 if dr == "up" else -1)


def parse_market(lines):
    """{spx|ndx|tsx: {close, date, pct1d}, usdcad: {rate, date}} from the MARKET FACTS lines; lines not understood
    are left out (check.py warns)."""
    out = {}
    for l in lines or []:
        m = INDEX_RE.match(l)
        if m:
            out[MARKET_KEYS[m.group("name")]] = {"close": float(m.group("close").replace(",", "")), "date": m.group("date"),
                                                 "pct1d": _signed(m.group("dir"), m.group("pct"), m.group("flat")), "line": l}
            continue
        m = FX_RE.match(l)
        if m:
            out["usdcad"] = {"rate": float(m.group("rate")), "date": m.group("date"), "line": l}
    return out


def with_market(d):
    """The note's market numbers with every value the MARKET FACTS block carries taken from it. Without
    "market_facts" (an older email) the note is returned as it is. S&P 500 or Nasdaq 100 missing from the block is
    left out (None, listed in "facts_missing"), never shown from StockAnalysis; S&P/TSX, US 10Y and USD/CAD missing
    from it keep their other sources."""
    if not d.get("market_facts"):
        return d
    M = parse_market(d["market_facts"])
    m = dict(d["market"], from_facts=sorted(M), facts_missing=[])
    for k in ("spx", "ndx", "tsx"):
        if k in M:
            m[k] = M[k]["pct1d"]
        elif k in WEB_ONLY:
            m[k] = None
            m["facts_missing"].append(k)
    if "usdcad" in M:
        m["usdcad"] = M["usdcad"]["rate"]
    return dict(d, market=m)


def valuation(line):
    """The valuation part of a price line: the text after the first "; ", without the final full stop."""
    if not FACT_RE.match(line) or "; " not in line:
        return None
    v = line.split("; ", 1)[1]
    return v[:-1] if v.endswith(".") else v


def parse_fact(line):
    """{sym, close, ccy, date, pct1d, pct5d, high52, vs52, val, line} from one facts line; close None for a "no
    price" line; None if the line is neither form. pct5d and vs52 are the stated figures (signed %), not recomputed;
    None when the line has no such clause (the older format, or too little history). A 5-day figure without its own
    direction word takes the day's."""
    m = FACT_RE.match(line)
    if m:
        pc = _signed(m.group("dir"), m.group("pct"), m.group("flat"))
        d5 = m.group("dir5") or m.group("dir")
        p5 = 0.0 if m.group("flat5") else None if m.group("pct5") is None or d5 is None else _signed(d5, m.group("pct5"), None)
        hi = m.group("hi") or m.group("hi_at")
        v52 = 0.0 if m.group("athi") else None if m.group("below") is None else -float(m.group("below"))
        return {"sym": m.group("sym"), "close": float(m.group("close").replace(",", "")), "ccy": m.group("ccy"),
                "date": m.group("date"), "pct1d": pc, "pct5d": p5, "high52": float(hi.replace(",", "")) if hi else None,
                "vs52": v52, "val": valuation(line), "line": line, "close_text": m.group("close")}
    m = NOPRICE_RE.match(line)
    if m:
        return {"sym": m.group("sym"), "close": None, "ccy": None, "date": None, "pct1d": None, "pct5d": None,
                "high52": None, "vs52": None, "val": None, "line": line}
    return None


def facts_v2(F):
    """True when any line of the block carries a 5-day or 52-week clause: then those columns come only from it."""
    return any(f.get("pct5d") is not None or f.get("vs52") is not None for f in F.values())


def facts_by_sym(lines):
    out = {}
    for l in lines or []:
        f = parse_fact(l)
        if f:
            out.setdefault(f["sym"], f)
    return out


def with_facts(d):
    """The note with every close, currency, close date and 1-day % taken from its facts line (one price per name).
    A name with no line, or a "no price" line, has no close. The web day range is dropped (another vendor's).
    When the block carries 5-day and 52-week clauses, the 5-day % and vs-52w figures come from it too (facts_v2).
    Without a facts block the note is returned as it is."""
    if not d.get("facts"):
        return d
    F = facts_by_sym(d["facts"])
    v2 = facts_v2(F)
    out = dict(d, prices=dict(d["prices"]))
    for g in GROUPS:
        lst = []
        for p in d["prices"][g]:
            f = F.get(facts_sym(p["ticker"])) or {}
            q = dict(p, close=f.get("close"), pct1d=f.get("pct1d"), close_date=f.get("date"), valuation=f.get("val"),
                     from_facts=True, day_low=None, day_high=None)
            if v2:  # 5-day % and the 52-week high from the line, n/a without its clause: never the web's
                q.update(facts_v2=True, pct5d=f.get("pct5d"), vs52=f.get("vs52"), high52=f.get("high52"))
            if f.get("ccy"):
                q["currency"] = f["ccy"]
            lst.append(q)
        out["prices"][g] = lst
    return out


def day_pct(p):
    return p.get("pct1d") if p.get("from_facts") else pct_val(p.get("close"), p.get("prev_close"))


def five_day_pct(p):
    return p.get("pct5d") if p.get("facts_v2") else pct_val(p.get("close"), p.get("close_5d_ago"))


def vs_high_pct(p):
    if p.get("facts_v2"):
        return p.get("vs52")
    return pct_val(p.get("close"), p.get("high52")) if p.get("high52") else None


def closes_lines(text):
    """"YYYY-MM-DD TICKER=close,..." lines (one per close date) from a saved Book facts email, for the admin CLOSES
    block: book tickers, no thousands separator, "no price" names left out."""
    by_date = {}
    for l in facts_block(text) or []:
        f = parse_fact(l)
        if f and f["close"] is not None:
            by_date.setdefault(f["date"], []).append("%s=%s" % (book_ticker(f["sym"]), f["close_text"].replace(",", "")))
    return ["%s %s" % (dt, ",".join(v)) for dt, v in sorted(by_date.items())]


def data_checks(d):
    out, session = [], d.get("price_session_date")
    for g in ("holdings", "watchlist"):
        for p in d["prices"][g]:
            t, c = p["ticker"], p.get("close")
            if c is None:
                continue
            lo, hi = p.get("day_low"), p.get("day_high")
            if lo is not None and hi is not None and not (float(lo) <= float(c) <= float(hi)):
                out.append("%s close %s is outside its day range %s to %s" % (t, money(c), money(lo), money(hi)))
            if session and p.get("close_date") and p["close_date"] != session:
                out.append("%s price is dated %s, not %s" % (t, p["close_date"], session))
    return out


def target_gaps(d):
    # admin only: an average analyst target far from the close is often real after a big move, so it never shows in the note
    out = []
    for g in ("holdings", "watchlist"):
        for p in d["prices"][g]:
            t, c, tg = p["ticker"], p.get("close"), p.get("avg_target")
            if c is not None and tg is not None and float(c) > 0 and abs(float(tg) / float(c) - 1) > TARGET_GAP:
                out.append("%s average analyst target %s %s is %+d%% from the %s close"
                           % (t, p.get("currency", "USD"), money(tg), round((float(tg) / float(c) - 1) * 100), money(c)))
    return out


def earnings_block(eb):
    o = [div("border-top:2px solid %s;padding-top:8px" % NAVY,
             '<span style="font-size:18px;font-weight:700">%s</span> <span style="font-size:12px;%s">%s</span>'
             % (e(eb["ticker"]), G, e(eb["status"]))),
         div("font-size:12px;%s;margin:0 0 6px" % G, e(eb["label"]))]
    tb = eb.get("table")
    if tb:
        h, R = "padding:3px 4px;border-bottom:1px solid #d9d9d9;color:%s;font-size:11px" % MUTED, ' align="right"'
        rows = ['<tr>%s%s%s%s</tr>' % (td("padding:3px 0;border-bottom:1px solid #d9d9d9", ""), td(h, "Actual", R),
                                        td(h, e(tb["est_header"]), R), td(h, "Yr ago", R))]
        c = "padding:4px;border-bottom:1px solid #f0f0f0"
        for r in tb["rows"]:
            rows.append('<tr>%s%s%s%s</tr>' % (td("padding:4px 0;border-bottom:1px solid #f0f0f0", e(r["label"])),
                                                td(c + ";font-weight:700", e(r["actual"]), R), td(c, e(r.get("est", "n/a")), R),
                                                td(c, e(r.get("yr_ago", "n/a")), R)))
        o.append(TB % (";width:100%;font-size:13px", "".join(rows)))
        if tb.get("note"):
            o.append(div("font-size:11px;%s;margin:4px 0 0" % G, e(tb["note"])))
    for pa in eb.get("paragraphs", []):
        o.append(div("margin:8px 0 0;font-size:13px", '<span style="font-size:11px;letter-spacing:1px;text-transform:uppercase;%s">%s</span><br>%s%s'
                     % (G, e(pa["label"]), e(pa["text"]), (" " + links(pa["links"])) if pa.get("links") else "")))
    if eb.get("doc_links"):
        o.append(div("font-size:12px;margin:8px 0 0", links(eb["doc_links"])))
    return "".join(o)


def item_cells(it, rule=RULE, w=True):
    # widths only on a table's first row: the column takes them from there
    return (td(("width:84px;" if w else "") + "padding:7px 10px 7px 0;border-top:1px solid %s;font-size:12px;%s" % (rule, G),
               "%s<br>%s" % (e(it["date"]), e(it["category"]))) +
            td("padding:7px 0;border-top:1px solid %s" % rule, "%s %s" % (e(it["text"]), links(it.get("links")))))


def item_rows(name_cell, items, top_rule, w=True):
    # one name cell spanning the name's items (it used to repeat, empty, on every item row)
    span = ' rowspan="%d"' % len(items) if len(items) > 1 else ""
    first = tr(td(("width:130px;" if w else "") + "padding:7px 10px 7px 0;border-top:%s" % top_rule, name_cell, span),
               item_cells(items[0], w=w) if items else "")
    return first + "".join(tr(item_cells(it, w=False)) for it in items[1:])


def price_table(title, lst):
    h, R = "padding:0 6px 4px;color:%s;font-size:11px" % MUTED, ' align="right"'
    rows = ['<tr>%s%s%s%s%s</tr>' % (td("padding:0 0 4px;color:%s;font-size:11px;font-weight:700;letter-spacing:1.5px" % MUTED, title),
                                      td(h, "Close", R), td(h, "1 day", R), td(h, "5 days", R), td(h.replace("0 6px 4px", "0 0 4px 6px"), "vs 52w high", R))]
    c = "padding:3px 6px;border-top:1px solid %s" % RULE
    for p in lst:
        cl = p.get("close")
        rows.append('<tr>%s%s%s%s%s</tr>' % (td("padding:3px 0;border-top:1px solid %s;font-weight:700" % RULE, e(p["ticker"])),
                                              td(c, money(cl), R), td(c, pct(day_pct(p)), R),
                                              td(c, pct(five_day_pct(p)), R),
                                              td(c.replace("3px 6px", "3px 0 3px 6px"), pct(vs_high_pct(p)), R)))
        if p.get("valuation"):  # the valuation part of the name's facts line, verbatim (PM proxy decision 26)
            rows.append('<tr><td colspan="5" style="padding:0 0 4px;font-size:11px;%s">%s</td></tr>' % (G, e(p["valuation"])))
    return TB % (";width:100%;font-size:13px", "".join(rows))


def render_note(d):
    d = with_market(with_facts(d))
    late, m = bool(d.get("late_run")), d["market"]
    prices = {p["ticker"]: p for g in ("holdings", "watchlist") for p in d["prices"][g]}
    o = [WRAP, div("font-family:%s;font-size:34px;line-height:1.1;color:%s" % (SERIF, NAVY), "Book update"),
         TB % (";width:100%;border-bottom:1px solid " + NAVY, "<tr>%s%s</tr>" % (
             td("padding:6px 0 10px;font-size:13px;%s" % G, e(d["date_label"])),
             td("padding:6px 0 10px;font-size:13px;text-align:right;%s" % G,
                "News %s ET &middot; Prices: %s close" % (e(d["window"]), e(d["price_session"])))))]
    if late:
        o.append(div("font-size:13px;margin-top:8px", "Late run: prices are the %s close, not live; pre-market quotes left out." % e(d["price_session"])))
    if d.get("header_note"):
        o.append(div("font-size:13px;margin-top:8px", e(d["header_note"])))

    left = []
    if d.get("summary"):
        left.append(div("margin:0 0 12px;font-family:%s;font-size:20px;line-height:1.4;color:%s" % (SERIF, NAVY), e(d["summary"])))
    if d.get("top"):
        left.append(TB % (";width:100%", "".join(tr(
            td("width:56px;padding:7px 8px 7px 0;border-top:1px solid %s;font-weight:700" % SOFT, e(r["ticker"])),
            td("padding:7px 8px 7px 0;border-top:1px solid %s" % SOFT, e(r["headline"])),
            td("padding:7px 0;border-top:1px solid %s;font-size:12px;%s;white-space:nowrap" % (SOFT, G), e(r["status"]), ' align="right"'))
            for r in d["top"])))
    else:
        left.append(div("padding:7px 0;border-top:1px solid %s" % SOFT, "Nothing material on your names."))

    def num(x, f):
        return '<span style="color:%s">n/a</span>' % GREY if x is None else f.format(x)
    bp = "" if m.get("us10y_bp") is None else ", %+d bp" % m["us10y_bp"]
    gone = set(m.get("facts_missing") or [])
    mrows = [(l, v) for k, l, v in (("spx", "S&amp;P 500", pct(m.get("spx"))), ("ndx", "Nasdaq 100", pct(m.get("ndx"))),
                                    ("tsx", "S&amp;P/TSX", pct(m.get("tsx"))), ("us10y", "US 10Y", num(m.get("us10y"), "{:.2f}%") + bp),
                                    ("usdcad", "USD/CAD", num(m.get("usdcad"), "{:.4f}"))) if k not in gone]
    box = [div("margin:0 0 6px", small_caps("%s close" % e(m["day"]))),
           TB % (";width:100%;font-size:14px", "".join('<tr>%s%s</tr>' % (
               td("padding:3px 0;border-bottom:1px solid #eef1f5;color:#444444", l),
               td("padding:3px 0;border-bottom:1px solid #eef1f5;text-align:right;font-weight:700", v)) for l, v in mrows))]
    if gone:
        box.append(div("font-size:12px;%s;margin:8px 0 0;line-height:1.4" % G, "%s: not in the engine's market facts today."
                       % " and ".join({"spx": "S&amp;P 500", "ndx": "Nasdaq 100"}[k] for k in ("spx", "ndx") if k in gone)))
    if m.get("notes"):
        box.append(div("font-size:12px;%s;margin:8px 0 0;line-height:1.4" % G, " ".join(e(n) for n in m["notes"])))
    if m.get("links"):
        box.append(div("font-size:12px;margin:6px 0 0", links(m["links"])))
    o.append(TB % (";width:100%;margin:20px 0 0", '<tr>%s%s%s</tr>' % (
        td("vertical-align:top", "".join(left)), td("width:28px", "&nbsp;"),
        td("width:220px;vertical-align:top;border:1px solid %s;padding:12px 14px" % BOX, "".join(box)))))

    if d.get("earnings"):
        o.append(serif_head("Earnings"))
        blocks = [earnings_block(eb) for eb in d["earnings"]]
        for i in range(0, len(blocks), 2):
            if i + 1 < len(blocks):
                o.append(two_col(blocks[i], blocks[i + 1]))
            else:
                o.append(div("", blocks[i]))
            o.append(div("height:14px;line-height:14px;font-size:1px", "&nbsp;"))

    for sec, title in (("holdings", "Holdings"), ("watchlist", "Watchlist")):
        if not d.get(sec):
            continue
        o.append(serif_head(title))
        rows = []
        for k, t in enumerate(d[sec]):
            p = prices.get(t["ticker"], {})
            c = p.get("close")
            sub = ("%s %s %s" % (e(p.get("currency", "USD")), money(c), pct(day_pct(p)))) if c is not None else "close not confirmed"
            v, q = quote_of(p, "premarket")
            if not late and q is not None and abs(v) >= 1.0:
                sub += "<br>pre-mkt %s %s" % (pct(v), e(q.get("time", "")))
            cell = '<b style="font-size:14px">%s</b><br><span style="font-size:12px;%s">%s</span><br><span style="font-size:12px">%s</span>' % (
                e(t["ticker"]), G, e(t["company"]), sub)
            rows.append(item_rows(cell, t["items"], "1px solid #b9c3d0", k == 0))
        o.append(TB % (";width:100%;font-size:13.5px", "".join(rows)))
    if d.get("no_source_moves"):
        o.append(div("font-size:13px;color:#444444;margin:10px 0 0", '<span style="%s">Moves with no news found:</span> ' % G +
                     ", ".join("<b>%s</b> (%s) %s vs S&amp;P 500" % (e(x["ticker"]), e(x.get("status", "")), pct(x["pct"])) for x in d["no_source_moves"])))

    if d.get("peers"):
        o.append(serif_head("Peers"))
        o.append(TB % (";width:100%;font-size:13.5px", "".join(tr(item_cells(it, w=k == 0)) for k, it in enumerate(d["peers"]))))

    if d.get("ai"):
        rows = []
        for k, it in enumerate(d["ai"]):
            rows.append(tr(
                td(("width:130px;" if k == 0 else "") + "padding:7px 10px 7px 0;border-top:1px solid #e3e8ef",
                   '<b>%s</b><br><span style="font-size:12px;%s">%s</span>' % (e(it["name"]), G, e(it.get("company", "")))),
                item_cells(it, "#e3e8ef", k == 0)))
        inner = (TB % (";width:100%", '<tr>%s%s</tr>' % (
            td("font-family:%s;font-size:22px;color:%s" % (SERIF, NAVY), "AI, market-wide"),
            td("text-align:right;font-size:12px;%s;vertical-align:bottom" % G, "Companies not on your list"))) +
                 div("font-size:12px;%s;margin:2px 0 6px" % G, "AI news on your own names stays under the ticker above.") +
                 TB % (";width:100%;font-size:13.5px", "".join(rows)))
        o.append(TB % (";width:100%;margin:32px 0 0", "<tr>%s</tr>" % td("border:1px solid %s;padding:14px 18px" % BOX, inner)))

    left, right = [], []
    if d.get("coming_up") or d.get("next_earnings"):
        left.append(serif_head("Coming up", 20, 0))
        if d.get("coming_up"):
            left.append(TB % (";width:100%;font-size:13px", "".join(tr(
                td("width:84px;padding:4px 8px 4px 0;border-top:1px solid %s;%s" % (RULE, G), e(c["date"])),
                td("padding:4px 0;border-top:1px solid %s" % RULE, "<b>%s</b> %s %s" % (e(c["who"]), e(c["text"]), links(c.get("links")))))
                for c in d["coming_up"])))
        if d.get("next_earnings"):
            left.append(div("font-size:12px;color:#444444;margin:10px 0 0;line-height:1.5",
                            '<span style="%s">Next earnings, 30 days (* company-confirmed):</span> ' % G +
                            " &middot; ".join("%s %s" % (e(g["date"]), e(", ".join(g["names"]))) for g in d["next_earnings"])))
    if d.get("also_today"):
        right.append(serif_head("Also today", 20, 0))
        right.append(TB % (";width:100%;font-size:13px;color:#333333", "".join(tr(
            td("width:52px;padding:4px 8px 4px 0;border-top:1px solid %s;font-weight:700;color:%s" % (RULE, INK), e(a["ticker"])),
            td("padding:4px 0;border-top:1px solid %s" % RULE, "%s %s" % (e(a["text"]), links(a.get("links")))))
            for a in d["also_today"])))
    if left or right:
        o.append(div("height:32px;line-height:32px;font-size:1px", "&nbsp;"))
        o.append(two_col("".join(left), "".join(right)))

    o.append(serif_head("Prices"))
    ok = n = 0
    groups = []
    for g, label in (("holdings", "HOLDINGS"), ("watchlist", "WATCHLIST")):
        lst = sorted(d["prices"][g], key=lambda p: (day_pct(p) is None, -(day_pct(p) or 0)))
        n += len(lst)
        ok += sum(1 for p in lst if day_pct(p) is not None)
        curs = "/".join(sorted(set(p.get("currency", "USD") for p in lst)) or ["USD"])
        groups.append(price_table("%s (%s)" % (label, curs), lst))
    gaps = list(d.get("gaps") or [])
    if not d.get("facts"):
        o.append(div("font-size:13px;margin:0 0 6px", "Prices from the web: the engine's Book facts were not available."))
    v2 = any(p.get("facts_v2") for g in GROUPS for p in d["prices"][g])
    src = ("closes, 1-day and 5-day % and 52-week highs from the engine's Book facts" if v2 else
           "closes and 1-day % from the engine's Book facts") if d.get("facts") else link(d["prices"]["source"])
    if n and ok * 2 < n:
        gaps.insert(0, "Prices: 1-day %% missing for %d names." % (n - ok))
        o.append(div("font-size:13px;%s" % G, "Prices left out: most closes could not be confirmed (see Gaps below)."))
    else:
        o.append(div("font-size:12px;%s;margin:0 0 8px" % G, "%s close &middot; S&amp;P 500 same day %s &middot; 5 days = vs the close 5 sessions earlier &middot; %s"
                     % (e(d["price_session"]), pct(m.get("spx")), src)))
        o.append(two_col(groups[0], groups[1], 32))
        allp = d["prices"]["holdings"] + d["prices"]["watchlist"]
        pm, ah, pms, ahs = [], [], 0, 0
        for p in allp:
            v, q = quote_of(p, "premarket")
            if q is not None:
                if abs(v) >= 1.0:
                    pm.append((v, p, q))
                else:
                    pms += 1
                continue
            v, q = quote_of(p, "afterhours")
            if q is not None:
                if abs(v) >= 1.0:
                    ah.append((v, p, q))
                else:
                    ahs += 1
        pm.sort(key=lambda r: -abs(r[0]))
        ah.sort(key=lambda r: -abs(r[0]))
        tail = lambda k: ' <span style="%s">&middot; %d others within 1%%</span>' % (G, k) if k else ""
        if not late and (pm or pms):
            o.append(div("font-size:13px;color:#444444;margin:12px 0 0", '<span style="%s">Pre-market, as of %s (StockAnalysis):</span> %s%s' % (
                G, e(d.get("premarket_as_of", "")), " &middot; ".join("<b>%s</b> %s %s %s" % (e(p["ticker"]), e(p.get("currency", "USD")),
                money(q["price"]), pct(v)) for v, p, q in pm) or "none 1% or more", tail(pms))))
        if ah or ahs:
            o.append(div("font-size:13px;color:#444444;margin:4px 0 0", '<span style="%s">After-hours, %s (StockAnalysis), names with no '
                         "pre-market quote:</span> %s%s" % (G, e(d["price_session"]), " &middot; ".join("<b>%s</b> %s %s %s (%s)" % (
                             e(p["ticker"]), e(p.get("currency", "USD")), money(q["price"]), pct(v), e(q.get("time", "")))
                             for v, p, q in ah) or "none 1% or more", tail(ahs))))
    ch = data_checks(d)
    if ch:
        o.append(div("font-size:13px;margin:8px 0 0", '<span style="color:%s">Check:</span> %s' % (DOWN, e("; ".join(ch) + "."))))
    foot = ["Gaps: " + e(" ".join(gaps))] if gaps else []
    sedi = sorted(set(d.get("sedi_names") or []) & (set(d["list"]["hold"]) | set(d["list"]["watch"])))
    if sedi:
        foot.append("Canadian insider trades (SEDI) are not checked for %s; one appears here only if a news story reports it."
                    % e(", ".join(sedi[:-1]) + " and " + sedi[-1] if len(sedi) > 1 else sedi[0]))
    foot.append("Reply to change the list: &quot;bought NVDA&quot;, &quot;sold TSN&quot;, &quot;watch CRWV&quot;, &quot;target 400 on CLS&quot;. Replies are read only for list changes; anything else, tell Ryen.")
    foot.append("Facts from company releases, SEC EDGAR, StockAnalysis, US Treasury, Bank of Canada and named outlets. "
                "Research aid, verify before acting, not client material. book-monitor " + e(d.get("version", "")))
    o.append(div("border-top:1px solid %s;margin:30px 0 0;padding:12px 0 0;font-size:12px;%s;line-height:1.6" % (NAVY, G), "<br>".join(foot)))
    lb = list_block(d["list"])
    o.append(div("font-family:Menlo,Consolas,monospace;font-size:11px;color:#8a8a8a;margin:12px 0 20px;white-space:pre-wrap", e(lb)))
    o.append("</div>")
    return compact("".join(o)), "%s\n\nThis email is formatted; open it in a mail app that shows HTML.\n\n%s\n" % (d["subject"], lb)


# Size (PM proxy decision 28, 2026-11-06: check.py FAILs above 72 KB, WARNs above 60 KB; with every style inline a
# full note was about 92 KB). Cosmetic declarations move into one <style> block as short shared classes; whatever the layout depends
# on stays inline (widths, table structure, centring, spacer heights; the % colours are <font color>), so a client
# that drops <style> still shows a readable note, only plainer. Links take their colour from one rule.
INLINE = ("width", "max-width", "table-layout", "border-collapse", "text-align", "vertical-align", "white-space", "height")
STYLE_ATTR = re.compile(r' style="([^"]*)"')


def _class_name(i):
    s = ""
    while True:
        s = chr(97 + i % 26) + s
        i = i // 26 - 1
        if i < 0:
            return s


def _split(style):
    """(cosmetic declarations, inline declarations) of one style attribute."""
    decls = [x.strip() for x in style.split(";") if x.strip()]
    if any(x.startswith("height:") for x in decls):  # spacers: all of it is layout
        return "", ";".join(decls)
    keep = [x for x in decls if x.split(":", 1)[0].strip() in INLINE or (x.startswith("margin:") and "auto" in x)]
    return ";".join(x for x in decls if x not in keep), ";".join(keep)


def compact(body):
    body = body.replace(' style="color:%s;text-decoration:none"' % LINK, "").replace("&middot;", "\u00b7")
    count = {}
    for m in STYLE_ATTR.finditer(body):
        rest = _split(m.group(1))[0]
        if rest:
            count[rest] = count.get(rest, 0) + 1
    # the most used get the shortest names; ties in order of first use, so the output is stable
    classes = {r: _class_name(i) for i, r in enumerate(sorted(count, key=lambda r: -count[r]))}

    def sub(m):
        rest, keep = _split(m.group(1))
        return (' class="%s"' % classes[rest] if rest else "") + (' style="%s"' % keep if keep else "")

    body = STYLE_ATTR.sub(sub, body)
    css = "a{color:%s;text-decoration:none}" % LINK + "".join(".%s{%s}" % (c, r) for r, c in classes.items())
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            'initial-scale=1"><style>%s</style></head><body>%s</body></html>' % (css, body))


def list_block(l):
    return ("--- CURRENT LIST ---\nHOLD: %s\nWATCH: %s\nTARGETS: %s\nCIKS: %s\n--- END LIST ---"
            % (", ".join(sorted(l["hold"])), ", ".join(sorted(l["watch"])), l.get("targets") or "none", l.get("ciks") or "none"))


def render_admin(a):
    o = [WRAP, div("font-size:20px;font-weight:700", "Book admin &middot; " + e(a["date_label"])),
         div(G + ";font-size:12px;margin-top:2px", e(a["run_line"]))]
    for s in a["sections"]:
        o.append(div("font-size:11px;letter-spacing:1px;text-transform:uppercase;color:%s;border-bottom:1px solid %s;padding:22px 0 4px;margin:0 0 8px" % (MUTED, SOFT), e(s["title"])))
        if s.get("rows"):
            o.append(TB % (";font-size:14px", "".join('<tr><td style="padding:3px 12px 3px 0;color:%s;vertical-align:top;'
                     'white-space:nowrap">%s</td><td style="padding:3px 0">%s</td></tr>' % (MUTED, e(r[0]), e(r[1])) for r in s["rows"])))
        o += [div("font-size:14px;margin:0 0 6px", e(t)) for t in s.get("text", [])]
    o += [div("font-size:12px;color:%s;margin:16px 0 20px" % MUTED, "Sent log and closes for the next run are in the plain-text part of this email."), "</div>"]
    t = [a["subject"], "", "This email is formatted; open it in a mail app that shows HTML.", "", "--- SENT LOG ---"] + \
        list(a.get("log") or []) + ["--- END LOG ---", "--- CLOSES ---"] + list(a.get("closes") or []) + ["--- END CLOSES ---", ""]
    return "\n".join(o), "\n".join(t)


if __name__ == "__main__":
    if sys.argv[1:2] == ["closes"]:  # render.py closes facts_email.txt -> the CLOSES line(s) for the admin email
        cl = closes_lines(open(sys.argv[2], encoding="utf-8").read())
        if not cl:
            sys.exit("no BOOK FACTS block with a close in " + sys.argv[2])
        print("\n".join(cl))
        sys.exit(0)
    kind, src, out = sys.argv[1:4]
    data = json.load(open(src, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    h, t = (render_note if kind == "note" else render_admin)(data)
    open(os.path.join(out, kind + ".html"), "w", encoding="utf-8").write(h)
    open(os.path.join(out, kind + ".txt"), "w", encoding="utf-8").write(t)
    print("rendered %s: %d bytes html" % (kind, len(h.encode("utf-8"))))
