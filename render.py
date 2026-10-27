#!/usr/bin/env python3
# book-monitor v0.9 renderer, layout B (desktop briefing; Oct 27: target gaps admin only): render.py note|admin data.json out_dir
import json, sys, os, html
SANS = "Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
INK, NAVY, MUTED, RULE, SOFT, BOX = "#1a1a1a", "#14243a", "#5f5f5f", "#ececec", "#e3e3e3", "#c9d2de"
UP, DOWN, GREY, LINK = "#137333", "#b3261e", "#5f5f5f", "#1f4e8c"
WRAP = ('<div style="max-width:760px;margin:0 auto;padding:16px 8px;font-family:%s;font-size:14px;line-height:1.5;color:%s">'
        % (SANS, INK))
TARGET_GAP = 0.60
G = "color:%s" % MUTED
TB = '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse%s">%s</table>'


def e(s):
    return html.escape(str(s), quote=True)


def pct_val(c, p):
    if c in (None, "") or p in (None, "") or float(p) == 0:
        return None
    return (float(c) / float(p) - 1) * 100


def pct(v):
    if v is None:
        return '<span style="color:%s">n/a</span>' % GREY
    r = round(v, 1)
    return '<span style="color:%s">%s%%</span>' % ((UP, "+%.1f" % r) if r > 0 else (DOWN, "%.1f" % r) if r < 0 else (GREY, "0.0"))


def money(x):
    return "n/a" if x is None else "{:,.2f}".format(float(x))


def link(l):
    return '<a href="%s" style="color:%s;text-decoration:none">%s</a>' % (e(l["url"]), LINK, e(l["name"]))


def links(ls):
    return " &middot; ".join(link(l) for l in (ls or []))


def div(style, body):
    return '<div style="%s">%s</div>' % (style, body)


def td(style, body, extra=""):
    return '<td%s style="%s">%s</td>' % (extra, style, body)


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
        h = "padding:3px 4px;border-bottom:1px solid #d9d9d9;text-align:right;color:%s;font-size:11px" % MUTED
        rows = ['<tr>%s%s%s%s</tr>' % (td("padding:3px 0;border-bottom:1px solid #d9d9d9", ""), td(h, "Actual"),
                                        td(h, e(tb["est_header"])), td(h, "Yr ago"))]
        c = "padding:4px;border-bottom:1px solid #f0f0f0;text-align:right"
        for r in tb["rows"]:
            rows.append('<tr>%s%s%s%s</tr>' % (td("padding:4px 0;border-bottom:1px solid #f0f0f0", e(r["label"])),
                                                td(c + ";font-weight:700", e(r["actual"])), td(c, e(r.get("est", "n/a"))),
                                                td(c, e(r.get("yr_ago", "n/a")))))
        o.append(TB % (";width:100%;font-size:13px", "".join(rows)))
        if tb.get("note"):
            o.append(div("font-size:11px;%s;margin:4px 0 0" % G, e(tb["note"])))
    for pa in eb.get("paragraphs", []):
        o.append(div("margin:8px 0 0;font-size:13px", '<span style="font-size:11px;letter-spacing:1px;text-transform:uppercase;%s">%s</span><br>%s%s'
                     % (G, e(pa["label"]), e(pa["text"]), (" " + links(pa["links"])) if pa.get("links") else "")))
    if eb.get("doc_links"):
        o.append(div("font-size:12px;margin:8px 0 0", links(eb["doc_links"])))
    return "".join(o)


def item_rows(name_cell, items, top_rule):
    rows = []
    for i, it in enumerate(items):
        rule = top_rule if i == 0 else "1px solid #ffffff"
        rows.append('<tr>%s%s%s</tr>' % (
            td("width:130px;padding:7px 10px 7px 0;vertical-align:top;border-top:%s" % rule, name_cell if i == 0 else ""),
            td("width:84px;padding:7px 10px 7px 0;vertical-align:top;border-top:1px solid %s;font-size:12px;%s" % (RULE, G),
               "%s<br>%s" % (e(it["date"]), e(it["category"]))),
            td("padding:7px 0;vertical-align:top;border-top:1px solid %s" % RULE, "%s %s" % (e(it["text"]), links(it.get("links"))))))
    return "".join(rows)


def price_table(title, lst):
    h = "padding:0 6px 4px;text-align:right;color:%s;font-size:11px" % MUTED
    rows = ['<tr>%s%s%s%s%s</tr>' % (td("padding:0 0 4px;color:%s;font-size:11px;font-weight:700;letter-spacing:1.5px" % MUTED, title),
                                      td(h, "Close"), td(h, "1 day"), td(h, "5 days"), td(h.replace("0 6px 4px", "0 0 4px 6px"), "vs 52w high"))]
    c = "padding:3px 6px;border-top:1px solid %s;text-align:right" % RULE
    for p in lst:
        cl = p.get("close")
        rows.append('<tr>%s%s%s%s%s</tr>' % (td("padding:3px 0;border-top:1px solid %s;font-weight:700" % RULE, e(p["ticker"])),
                                              td(c, money(cl)), td(c, pct(pct_val(cl, p.get("prev_close")))),
                                              td(c, pct(pct_val(cl, p.get("close_5d_ago")))),
                                              td(c.replace("3px 6px", "3px 0 3px 6px"), pct(pct_val(cl, p.get("high52")) if p.get("high52") else None))))
    return TB % (";width:100%;font-size:13px", "".join(rows))


def render_note(d):
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
        left.append(TB % (";width:100%", "".join('<tr>%s%s%s</tr>' % (
            td("width:56px;padding:7px 8px 7px 0;border-top:1px solid %s;font-weight:700;vertical-align:top" % SOFT, e(r["ticker"])),
            td("padding:7px 8px 7px 0;border-top:1px solid %s;vertical-align:top" % SOFT, e(r["headline"])),
            td("padding:7px 0;border-top:1px solid %s;font-size:12px;%s;text-align:right;vertical-align:top;white-space:nowrap" % (SOFT, G), e(r["status"])))
            for r in d["top"])))
    else:
        left.append(div("padding:7px 0;border-top:1px solid %s" % SOFT, "Nothing material on your names."))

    def num(x, f):
        return '<span style="color:%s">n/a</span>' % GREY if x is None else f.format(x)
    bp = "" if m.get("us10y_bp") is None else ", %+d bp" % m["us10y_bp"]
    mrows = [("S&amp;P 500", pct(m.get("spx"))), ("Nasdaq 100", pct(m.get("ndx"))), ("S&amp;P/TSX", pct(m.get("tsx"))),
             ("US 10Y", num(m.get("us10y"), "{:.2f}%") + bp), ("USD/CAD", num(m.get("usdcad"), "{:.4f}"))]
    box = [div("margin:0 0 6px", small_caps("%s close" % e(m["day"]))),
           TB % (";width:100%;font-size:14px", "".join('<tr>%s%s</tr>' % (
               td("padding:3px 0;border-bottom:1px solid #eef1f5;color:#444444", l),
               td("padding:3px 0;border-bottom:1px solid #eef1f5;text-align:right;font-weight:700", v)) for l, v in mrows))]
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
        for t in d[sec]:
            p = prices.get(t["ticker"], {})
            c = p.get("close")
            sub = ("%s %s %s" % (e(p.get("currency", "USD")), money(c), pct(pct_val(c, p.get("prev_close"))))) if c is not None else "close not confirmed"
            v, q = quote_of(p, "premarket")
            if not late and q is not None and abs(v) >= 1.0:
                sub += "<br>pre-mkt %s %s" % (pct(v), e(q.get("time", "")))
            cell = '<b style="font-size:14px">%s</b><br><span style="font-size:12px;%s">%s</span><br><span style="font-size:12px">%s</span>' % (
                e(t["ticker"]), G, e(t["company"]), sub)
            rows.append(item_rows(cell, t["items"], "1px solid #b9c3d0"))
        o.append(TB % (";width:100%;font-size:13.5px", "".join(rows)))
    if d.get("no_source_moves"):
        o.append(div("font-size:13px;color:#444444;margin:10px 0 0", '<span style="%s">Moves with no news found:</span> ' % G +
                     ", ".join("<b>%s</b> (%s) %s vs S&amp;P 500" % (e(x["ticker"]), e(x.get("status", "")), pct(x["pct"])) for x in d["no_source_moves"])))

    if d.get("peers"):
        o.append(serif_head("Peers"))
        o.append(TB % (";width:100%;font-size:13.5px", "".join('<tr>%s%s</tr>' % (
            td("width:84px;padding:7px 10px 7px 0;vertical-align:top;border-top:1px solid %s;font-size:12px;%s" % (RULE, G),
               "%s<br>%s" % (e(it["date"]), e(it["category"]))),
            td("padding:7px 0;vertical-align:top;border-top:1px solid %s" % RULE, "%s %s" % (e(it["text"]), links(it.get("links")))))
            for it in d["peers"])))

    if d.get("ai"):
        rows = []
        for it in d["ai"]:
            rows.append('<tr>%s%s%s</tr>' % (
                td("width:130px;padding:7px 10px 7px 0;vertical-align:top;border-top:1px solid #e3e8ef",
                   '<b>%s</b><br><span style="font-size:12px;%s">%s</span>' % (e(it["name"]), G, e(it.get("company", "")))),
                td("width:84px;padding:7px 10px 7px 0;vertical-align:top;border-top:1px solid #e3e8ef;font-size:12px;%s" % G,
                   "%s<br>%s" % (e(it["date"]), e(it["category"]))),
                td("padding:7px 0;vertical-align:top;border-top:1px solid #e3e8ef", "%s %s" % (e(it["text"]), links(it.get("links"))))))
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
            left.append(TB % (";width:100%;font-size:13px", "".join('<tr>%s%s</tr>' % (
                td("width:84px;padding:4px 8px 4px 0;border-top:1px solid %s;vertical-align:top;%s" % (RULE, G), e(c["date"])),
                td("padding:4px 0;border-top:1px solid %s;vertical-align:top" % RULE, "<b>%s</b> %s %s" % (e(c["who"]), e(c["text"]), links(c.get("links")))))
                for c in d["coming_up"])))
        if d.get("next_earnings"):
            left.append(div("font-size:12px;color:#444444;margin:10px 0 0;line-height:1.5",
                            '<span style="%s">Next earnings, 30 days (* company-confirmed):</span> ' % G +
                            " &middot; ".join("%s %s" % (e(g["date"]), e(", ".join(g["names"]))) for g in d["next_earnings"])))
    if d.get("also_today"):
        right.append(serif_head("Also today", 20, 0))
        right.append(TB % (";width:100%;font-size:13px;color:#333333", "".join('<tr>%s%s</tr>' % (
            td("width:52px;padding:4px 8px 4px 0;border-top:1px solid %s;vertical-align:top;font-weight:700;color:%s" % (RULE, INK), e(a["ticker"])),
            td("padding:4px 0;border-top:1px solid %s;vertical-align:top" % RULE, "%s %s" % (e(a["text"]), links(a.get("links")))))
            for a in d["also_today"])))
    if left or right:
        o.append(div("height:32px;line-height:32px;font-size:1px", "&nbsp;"))
        o.append(two_col("".join(left), "".join(right)))

    o.append(serif_head("Prices"))
    ok = n = 0
    groups = []
    for g, label in (("holdings", "HOLDINGS"), ("watchlist", "WATCHLIST")):
        lst = sorted(d["prices"][g], key=lambda p: (pct_val(p.get("close"), p.get("prev_close")) is None,
                                                    -(pct_val(p.get("close"), p.get("prev_close")) or 0)))
        n += len(lst)
        ok += sum(1 for p in lst if pct_val(p.get("close"), p.get("prev_close")) is not None)
        curs = "/".join(sorted(set(p.get("currency", "USD") for p in lst)) or ["USD"])
        groups.append(price_table("%s (%s)" % (label, curs), lst))
    gaps = list(d.get("gaps") or [])
    if n and ok * 2 < n:
        gaps.insert(0, "Prices: 1-day %% missing for %d names." % (n - ok))
        o.append(div("font-size:13px;%s" % G, "Prices left out: most closes could not be confirmed (see Gaps below)."))
    else:
        o.append(div("font-size:12px;%s;margin:0 0 8px" % G, "%s close &middot; S&amp;P 500 same day %s &middot; 5 days = vs the close 5 sessions earlier &middot; %s"
                     % (e(d["price_session"]), pct(m.get("spx")), link(d["prices"]["source"]))))
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
    return "\n".join(o), "%s\n\nThis email is formatted; open it in a mail app that shows HTML.\n\n%s\n" % (d["subject"], lb)


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
    kind, src, out = sys.argv[1:4]
    data = json.load(open(src, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    h, t = (render_note if kind == "note" else render_admin)(data)
    open(os.path.join(out, kind + ".html"), "w", encoding="utf-8").write(h)
    open(os.path.join(out, kind + ".txt"), "w", encoding="utf-8").write(t)
    print("rendered %s: %d bytes html" % (kind, len(h.encode("utf-8"))))
