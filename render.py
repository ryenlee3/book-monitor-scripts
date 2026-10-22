#!/usr/bin/env python3
# book-monitor v0.9 renderer: render.py note|admin data.json out_dir
import json, sys, os, html
WRAP = ("<div style=\"max-width:600px;margin:0 auto;padding:0 4px;font-family:-apple-system,'Segoe UI',"
        "Helvetica,Arial,sans-serif;font-size:15px;line-height:1.45;color:#1a1a1a\">")
UP, DOWN, GREY, LINK = "#137333", "#b3261e", "#888", "#0b57d0"
TARGET_GAP = 0.60
G = "color:#888"
TB = '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse%s">%s</table>'


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


def heading(t):
    return div("font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#777;border-bottom:1px solid #e3e3e3;"
               "padding:22px 0 4px;margin:0 0 8px", e(t))


def labelled(margin, label, body):
    return div("margin:" + margin, '<span style="%s;font-size:12px">%s</span><br>%s' % (G, label, body))


def item_block(it, last):
    return labelled("0 0 14px" if last else "0 0 8px", "%s &middot; %s" % (e(it["date"]), e(it["category"])),
                    "%s %s" % (e(it["text"]), links(it.get("links"))))


def quote_of(p, k):
    q = p.get(k)
    if q and q.get("price") is not None and p.get("close") is not None:
        return pct_val(q["price"], p["close"]), q
    return None, None


def name_head(tk, sub):
    return div("margin:0 0 4px", '<b style="font-size:16px">%s</b> <span style="%s;font-size:13px">%s</span>' % (e(tk), G, sub))


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
            tg = p.get("avg_target")
            if tg is not None and float(c) > 0 and abs(float(tg) / float(c) - 1) > TARGET_GAP:
                out.append("%s average analyst target %s %s is %+d%% from the %s close; possible stale price or data error"
                           % (t, p.get("currency", "USD"), money(tg), round((float(tg) / float(c) - 1) * 100), money(c)))
    return out


def render_note(d):
    late, m = bool(d.get("late_run")), d["market"]
    prices = {p["ticker"]: p for g in ("holdings", "watchlist") for p in d["prices"][g]}
    o = [WRAP, div("font-size:20px;font-weight:700", "Book update &middot; " + e(d["date_label"])),
         div(G + ";font-size:12px;margin-top:2px", "News %s ET &middot; Prices: %s close" % (e(d["window"]), e(d["price_session"])))]
    if late:
        o.append(div("font-size:13px;margin-top:6px", "Late run: prices are the %s close, not live; pre-market quotes left out." % e(d["price_session"])))
    if d.get("header_note"):
        o.append(div("font-size:13px;margin-top:6px", e(d["header_note"])))
    if d.get("summary"):
        o.append(div("font-size:15px;margin-top:10px", "<b>%s</b>" % e(d["summary"])))
    o.append(heading("Top"))
    if d.get("top"):
        o.append(TB % ("", "".join('<tr><td style="padding:3px 12px 3px 0;vertical-align:top;font-weight:700">%s</td>'
                                   '<td style="padding:3px 0">%s <span style="%s;font-size:12px">%s</span></td></tr>'
                                   % (e(r["ticker"]), e(r["headline"]), G, e(r["status"])) for r in d["top"])))
    else:
        o.append("<div>Nothing material on your names.</div>")

    def num(x, f):
        return '<span style="color:#888">n/a</span>' if x is None else f.format(x)
    bp = "" if m.get("us10y_bp") is None else " (%+d bp)" % m["us10y_bp"]
    o.append('<div style="border:1px solid #e3e3e3;padding:10px 12px;margin:16px 0 0;font-size:14px">' +
             "<div><b>%s close</b> &nbsp;S&amp;P 500 %s &middot; Nasdaq 100 %s &middot; TSX %s &middot; US 10Y %s%s &middot; USD/CAD %s</div>"
             % (e(m["day"]), pct(m.get("spx")), pct(m.get("ndx")), pct(m.get("tsx")), num(m.get("us10y"), "{:.2f}%"), bp,
                num(m.get("usdcad"), "{:.4f}")))
    if m.get("notes"):
        o.append(div("font-size:13px;color:#444;margin-top:4px", " ".join(e(n) for n in m["notes"])))
    o.append(div("font-size:12px;margin-top:4px", links(m.get("links"))) + "</div>")

    if d.get("earnings"):
        o.append(heading("Earnings"))
        for eb in d["earnings"]:
            o.append(name_head(eb["ticker"], "%s &middot; %s" % (e(eb["status"]), e(eb["label"]))))
            tb = eb.get("table")
            if tb:
                h = "padding:3px %s;border-bottom:1px solid #e3e3e3;text-align:right"
                rows = ['<tr style="color:#888;font-size:12px"><td style="padding:3px 8px 3px 0;border-bottom:1px solid #e3e3e3"></td>'
                        '<td style="%s">Actual</td><td style="%s">%s</td><td style="%s">Yr ago</td></tr>'
                        % (h % "8px", h % "8px", e(tb["est_header"]), h % "0 3px 8px")]
                c = "padding:4px 8px;text-align:right"
                for r in tb["rows"]:
                    rows.append('<tr><td style="padding:4px 8px 4px 0">%s</td><td style="%s"><b>%s</b></td><td style="%s">%s</td>'
                                '<td style="padding:4px 0 4px 8px;text-align:right">%s</td></tr>'
                                % (e(r["label"]), c, e(r["actual"]), c, e(r.get("est", "n/a")), e(r.get("yr_ago", "n/a"))))
                o.append(TB % (";font-size:14px;width:100%;max-width:520px;margin:4px 0 8px", "".join(rows)))
                if tb.get("note"):
                    o.append(div("font-size:12px;color:#888;margin:0 0 6px", e(tb["note"])))
            for pa in eb.get("paragraphs", []):
                o.append(labelled("0 0 6px", e(pa["label"]), e(pa["text"]) + (" " + links(pa["links"]) if pa.get("links") else "")))
            if eb.get("doc_links"):
                o.append(div("font-size:13px;margin:0 0 14px", links(eb["doc_links"])))

    for sec, title in (("holdings", "Holdings"), ("watchlist", "Watchlist")):
        if not d.get(sec):
            continue
        o.append(heading(title))
        for t in d[sec]:
            p = prices.get(t["ticker"], {})
            c = p.get("close")
            sub = "%s &middot; %s %s" % (e(t["company"]), "%s %s" % (p.get("currency", "USD"), money(c)) if c is not None
                                          else "close not confirmed", pct(pct_val(c, p.get("prev_close"))))
            v, q = quote_of(p, "premarket")
            if not late and q is not None and abs(v) >= 1.0:
                sub += " &middot; pre-mkt %s %s" % (pct(v), e(q.get("time", "")))
            o.append(name_head(t["ticker"], sub))
            for i, it in enumerate(t["items"]):
                o.append(item_block(it, i == len(t["items"]) - 1))
    if d.get("no_source_moves"):
        o.append(div("font-size:13px;margin:8px 0 0", '<span style="color:#888">Moves with no news found:</span> ' +
                     ", ".join("%s (%s) %s vs S&amp;P 500" % (e(x["ticker"]), e(x.get("status", "")), pct(x["pct"])) for x in d["no_source_moves"])))
    if d.get("peers"):
        o.append(heading("Peers"))
        o += [item_block(it, i == len(d["peers"]) - 1) for i, it in enumerate(d["peers"])]
    if d.get("ai"):
        o.append(heading("AI · market-wide"))
        o.append(div("font-size:12px;color:#888;margin:0 0 8px", "Companies not on your list. AI news on your own names stays under the ticker above."))
        for i, it in enumerate(d["ai"]):
            o.append(labelled("0 0 14px" if i == len(d["ai"]) - 1 else "0 0 10px", "%s &middot; %s" % (e(it["date"]), e(it["category"])),
                              '<b>%s</b> <span style="%s;font-size:13px">%s</span> %s %s'
                              % (e(it["name"]), G, e(it.get("company", "")), e(it["text"]), links(it.get("links")))))
    if d.get("also_today"):
        o.append(heading("Also today"))
        o.append(TB % (";font-size:13px;color:#444", "".join(
            '<tr><td style="padding:2px 10px 2px 0;font-weight:700;vertical-align:top;color:#1a1a1a">%s</td>'
            '<td style="padding:2px 0">%s %s</td></tr>' % (e(a["ticker"]), e(a["text"]), links(a.get("links"))) for a in d["also_today"])))
    if d.get("coming_up") or d.get("next_earnings"):
        o.append(heading("Coming up"))
        if d.get("coming_up"):
            o.append(TB % (";font-size:14px", "".join(
                '<tr><td style="padding:3px 10px 3px 0;color:#888;white-space:nowrap;vertical-align:top">%s</td>'
                '<td style="padding:3px 0"><b>%s</b> %s %s</td></tr>' % (e(c["date"]), e(c["who"]), e(c["text"]), links(c.get("links")))
                for c in d["coming_up"])))
        if d.get("next_earnings"):
            o.append(div("font-size:13px;color:#444;margin:10px 0 0", '<span style="color:#888;font-size:12px">Next earnings, 30 days '
                         "(* company-confirmed)</span><br>" + " &middot; ".join("%s %s" % (e(g["date"]), e(", ".join(g["names"])))
                                                                                for g in d["next_earnings"])))

    o.append(heading("Prices · %s close" % d["price_session"]))
    th = 'style="padding:2px 6px;text-align:right;font-weight:400"'
    td = '<td style="padding:2px 6px;text-align:right">%s</td>'
    rows, ok, n = [], 0, 0
    for g, label in (("holdings", "HOLDINGS"), ("watchlist", "WATCHLIST")):
        lst = sorted(d["prices"][g], key=lambda p: (pct_val(p.get("close"), p.get("prev_close")) is None,
                                                    -(pct_val(p.get("close"), p.get("prev_close")) or 0)))
        n += len(lst)
        ok += sum(1 for p in lst if pct_val(p.get("close"), p.get("prev_close")) is not None)
        rows.append('<tr style="color:#888;font-size:11px"><td style="padding:%s">%s (%s)</td><td %s>Close</td><td %s>1 day</td>'
                    '<td %s>5 days</td><td %s>vs 52w high</td></tr>' % ("0 0 4px" if g == "holdings" else "12px 0 4px", label,
                    "/".join(sorted(set(p.get("currency", "USD") for p in lst)) or ["USD"]), th, th, th, th))
        for p in lst:
            c = p.get("close")
            rows.append('<tr><td style="padding:2px 6px 2px 0"><b>%s</b></td>' % e(p["ticker"]) + td % money(c) +
                        td % pct(pct_val(c, p.get("prev_close"))) + td % pct(pct_val(c, p.get("close_5d_ago"))) +
                        '<td style="padding:2px 0 2px 6px;text-align:right">%s</td></tr>' % pct(pct_val(c, p.get("high52")) if p.get("high52") else None))
    gaps = list(d.get("gaps") or [])
    if n and ok * 2 < n:
        gaps.insert(0, "Prices: 1-day %% missing for %d names." % (n - ok))
    else:
        o.append(TB % (";font-size:13px;width:100%;max-width:520px", "".join(rows)))
        o.append(div("font-size:12px;margin:6px 0 0", '%s <span style="color:#888">&middot; S&amp;P 500 same day %s &middot; '
                     "5 days = vs the close 5 sessions earlier</span>" % (link(d["prices"]["source"]), pct(m.get("spx")))))
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
        tail = lambda k: ' <span style="color:#888">&middot; %d others within 1%%</span>' % k if k else ""
        if not late and (pm or pms):
            o.append(div("font-size:13px;margin:8px 0 0", '<span style="color:#888">Pre-market, as of %s (StockAnalysis):</span> %s%s' % (
                e(d.get("premarket_as_of", "")), " &middot; ".join("<b>%s</b> %s %s %s" % (e(p["ticker"]), e(p.get("currency", "USD")),
                money(q["price"]), pct(v)) for v, p, q in pm) or "none 1% or more", tail(pms))))
        if ah or ahs:
            o.append(div("font-size:13px;margin:4px 0 0", '<span style="color:#888">After-hours, %s (StockAnalysis), names with no '
                         "pre-market quote:</span> %s%s" % (e(d["price_session"]), " &middot; ".join("<b>%s</b> %s %s %s (%s)" % (
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
    o.append(div("border-top:1px solid #e3e3e3;margin:24px 0 0;padding:10px 0 0;font-size:12px;color:#888;line-height:1.5", "<br>".join(foot)))
    lb = list_block(d["list"])
    o.append(div("font-family:Menlo,Consolas,monospace;font-size:11px;color:#999;margin:12px 0 20px;white-space:pre-wrap", e(lb)))
    o.append("</div>")
    return "\n".join(o), "%s\n\nThis email is formatted; open it in a mail app that shows HTML.\n\n%s\n" % (d["subject"], lb)


def list_block(l):
    return ("--- CURRENT LIST ---\nHOLD: %s\nWATCH: %s\nTARGETS: %s\nCIKS: %s\n--- END LIST ---"
            % (", ".join(sorted(l["hold"])), ", ".join(sorted(l["watch"])), l.get("targets") or "none", l.get("ciks") or "none"))


def render_admin(a):
    o = [WRAP, div("font-size:20px;font-weight:700", "Book admin &middot; " + e(a["date_label"])),
         div(G + ";font-size:12px;margin-top:2px", e(a["run_line"]))]
    for s in a["sections"]:
        o.append(heading(s["title"]))
        if s.get("rows"):
            o.append(TB % (";font-size:14px", "".join('<tr><td style="padding:3px 12px 3px 0;color:#888;vertical-align:top;'
                     'white-space:nowrap">%s</td><td style="padding:3px 0">%s</td></tr>' % (e(r[0]), e(r[1])) for r in s["rows"])))
        o += [div("font-size:14px;margin:0 0 6px", e(t)) for t in s.get("text", [])]
    o += [div("font-size:12px;color:#888;margin:16px 0 20px", "Sent log and closes for the next run are in the plain-text part of this email."), "</div>"]
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
