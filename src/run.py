#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrator fuer das Rotation-Dashboard.

Ablauf: Themen-ETFs + Regime-Referenzen per Yahoo laden, IBD-RS je ETF
berechnen (rs.py), staerkste Sektoren bestimmen, dazu passende Leader-Aktien
aus dem Markets-360-Export (markets360_reader.py, keine eigene Ticker-
Recherche) auswaehlen, fuer diese + eine breitere Kandidatenmenge zusaetzlich
eigene Kurse holen (r1m/r3m/Volumen/Rote-Tage-Resilienz - das liefert keine
der beiden Quellen). Schreibt data/rotation.json + .js.

Test: python3 run.py
"""

import datetime
import json
import sys

import etfs
import kursdaten
import markets360_reader
import pfade
import rs as rs_mod

TOP_SEKTOREN_N = 7
LEADER_JE_SEKTOR = 3
LEADERS_MAX = 20
RESILIENT_KANDIDATEN_N = 40
RESILIENT_MAX = 20
ROTE_TAGE_N = 5


def perf(closes, lookback):
    if not closes or len(closes) <= lookback:
        return None
    return (closes[-1] / closes[-1 - lookback] - 1.0) * 100.0


def pct_from_high(closes, fenster=252):
    if not closes:
        return None
    w = closes[-min(fenster, len(closes)):]
    hoch = max(w)
    return (closes[-1] / hoch - 1.0) * 100.0 if hoch else None


def above_ma(closes, n):
    if not closes or len(closes) < n:
        return None
    sma = sum(closes[-n:]) / n
    return closes[-1] > sma


def volumen_ratio(volumes):
    vals = [v for v in (volumes or []) if v is not None]
    if len(vals) < 51:
        return None
    basis = vals[-51:-1]
    avg = sum(basis) / len(basis)
    return round(vals[-1] / avg, 2) if avg else None


def rote_tage_resilienz(stock_closes, bench_closes):
    """rel_on_red: durchschnittliche Tages-Outperformance ggue. Benchmark an
    den (bis zu) ROTE_TAGE_N juengsten roten Tagen (Benchmark im Minus).
    stock_avg: dieselbe Outperformance-Kennzahl ueber ALLE Tage im Fenster -
    rel_on_red > stock_avg heisst: speziell an roten Tagen staerker als sonst."""
    n = min(len(stock_closes or []), len(bench_closes or []))
    if n < 15:
        return None
    sc, bc = stock_closes[-n:], bench_closes[-n:]
    tage = []
    for i in range(1, n):
        sr = sc[i] / sc[i - 1] - 1.0
        br = bc[i] / bc[i - 1] - 1.0
        tage.append((sr, br, (sr - br) * 100.0))
    if not tage:
        return None
    rote_idx = [i for i, (sr, br, ex) in enumerate(tage) if br < 0][-ROTE_TAGE_N:]
    if not rote_idx:
        return None
    rel_on_red = sum(tage[i][2] for i in rote_idx) / len(rote_idx)
    stock_avg = sum(t[2] for t in tage) / len(tage)
    green_on_red = sum(1 for i in rote_idx if tage[i][0] > 0)
    return {
        "rel_on_red": round(rel_on_red, 2),
        "stock_avg": round(stock_avg, 2),
        "green_on_red": green_on_red,
        "n_red": len(rote_idx),
    }


def regime_einschaetzung(closes_by_ticker):
    spy = closes_by_ticker.get("SPY")
    if not spy:
        return {"trend": "unbekannt", "leader": "unbekannt",
                "breadth": "unbekannt", "note": "Regime-Daten nicht verfuegbar."}
    r1m = {t: perf(closes_by_ticker.get(t), 21) for t in ("SPY", "QQQ", "DIA", "IWM", "RSP")}
    spy_1m = r1m["SPY"] or 0.0

    sma50, sma200 = above_ma(spy, 50), above_ma(spy, 200)
    if len(spy) >= 222:
        sma200_serie_steigt = sum(spy[-200:]) / 200 > sum(spy[-222:-22]) / 200
    else:
        sma200_serie_steigt = None
    if sma50 and sma200 and sma200_serie_steigt:
        trend = "Aufwaertstrend"
    elif sma50 is False and sma200 is False and sma200_serie_steigt is False:
        trend = "Abwaertstrend"
    else:
        trend = "Seitwaerts/uneinheitlich"

    diffs = {t: (r1m[t] or 0.0) - spy_1m for t in ("QQQ", "DIA", "IWM")}
    bester = max(diffs, key=diffs.get) if diffs else None
    if bester and diffs[bester] > 2.0:
        leader = {"QQQ": "Growth/Large-Cap-Tech", "DIA": "Value/Dividende (Dow)",
                  "IWM": "Small-Caps"}[bester]
    else:
        leader = "Breit (kein klarer Fuehrer)"

    spread = spy_1m - (r1m["RSP"] or spy_1m)
    if spread > 3.0:
        breadth = "eng (Mega-Caps tragen)"
    elif spread < -2.0:
        breadth = "breit (Mega-Caps hinken hinterher)"
    else:
        breadth = "ausgeglichen"

    note = f"{trend}. Marktbreite: {breadth}. Fuehrung: {leader}."
    out = {"trend": trend, "leader": leader, "breadth": breadth, "note": note}
    out.update({f"{t.lower()}_1m": (round(v, 2) if v is not None else None) for t, v in r1m.items()})
    return out


def main():
    heute = datetime.date.today().isoformat()
    cache = kursdaten.lade_cache()

    def holen(symbol):
        d = kursdaten.hole_chart_cached(symbol, cache, heute)
        return (d or {}).get("closes") or [], (d or {}).get("volumes") or []

    # 1) Regime-Referenzen + Benchmark
    regime_ticker = list(etfs.REGIME_TICKER.values())
    closes_by_ticker = {}
    volumes_by_ticker = {}
    for t in regime_ticker + [etfs.RS_BENCHMARK]:
        c, v = holen(t)
        closes_by_ticker[t] = c
        volumes_by_ticker[t] = v
    bench_closes = closes_by_ticker[etfs.RS_BENCHMARK]

    # 2) Themen-ETFs: eigene Kurse + IBD-RS ggue. Benchmark
    raw_scores = {}
    etf_kennzahlen = {}
    for ticker in etfs.THEMEN_ETFS:
        c, v = holen(ticker)
        closes_by_ticker[ticker] = c
        raw_scores[ticker] = rs_mod.raw_rs_score(c, bench_closes) if c else None
        etf_kennzahlen[ticker] = {
            "r1m": perf(c, 21), "r3m": perf(c, 63),
            "pct_from_high": pct_from_high(c),
            "above_ma50": above_ma(c, 50),
        }
    rs_ratings = rs_mod.assign_rs_ratings(raw_scores)

    sektoren = []
    for ticker, thema in etfs.THEMEN_ETFS.items():
        if ticker not in rs_ratings:
            continue
        k = etf_kennzahlen[ticker]
        sektoren.append({
            "etf": ticker, "theme": thema, "rs": rs_ratings[ticker],
            "r1m": k["r1m"], "r3m": k["r3m"],
            "pct_from_high": k["pct_from_high"], "above_ma50": k["above_ma50"],
        })
    sektoren.sort(key=lambda s: s["rs"], reverse=True)

    # 3) Leader-Aktien aus Markets 360 in den staerksten Sektoren
    aktien = markets360_reader.lade_aktien()
    top_themen = {s["etf"] for s in sektoren[:TOP_SEKTOREN_N]}
    je_thema = {}
    for a in aktien:
        if a["thema"] in top_themen:
            je_thema.setdefault(a["thema"], []).append(a)
    leader_kandidaten = []
    for thema, liste in je_thema.items():
        liste.sort(key=lambda a: a["rs"], reverse=True)
        leader_kandidaten.extend(liste[:LEADER_JE_SEKTOR])
    leader_kandidaten.sort(key=lambda a: a["rs"], reverse=True)
    leader_kandidaten = leader_kandidaten[:LEADERS_MAX]

    # 4) Breitere Kandidatenmenge fuer die Rote-Tage-Resilienz (sektorunabhaengig)
    alle_sortiert = sorted(aktien, key=lambda a: a["rs"], reverse=True)
    resilient_symbole = {a["symbol"] for a in alle_sortiert[:RESILIENT_KANDIDATEN_N]}
    resilient_symbole |= {a["symbol"] for a in leader_kandidaten}
    by_symbol = {a["symbol"]: a for a in aktien}

    # 5) Eigene Kurse fuer die ausgewaehlte Teilmenge (Leader + Resilienz-Kandidaten)
    ticker_kurse = {}
    for sym in resilient_symbole:
        c, v = holen(sym)
        ticker_kurse[sym] = (c, v)

    leaders = []
    for a in leader_kandidaten:
        c, v = ticker_kurse.get(a["symbol"], ([], []))
        if not c:
            continue
        pfh = pct_from_high(c)
        leaders.append({
            "ticker": a["symbol"], "theme": etfs.THEMEN_ETFS.get(a["thema"], a["sektor_raw"]),
            "rs": int(a["rs"]), "price": c[-1],
            "r1m": perf(c, 21), "r3m": perf(c, 63),
            "pct_from_high": pfh,
            "vol_ratio": volumen_ratio(v),
            "tt_crit": int(a["tt_pass"]) if a["tt_pass"] is not None else None,
            "near_high": (pfh is not None and pfh > -3.0),
        })

    resilient = []
    for sym in resilient_symbole:
        a = by_symbol.get(sym)
        c, _ = ticker_kurse.get(sym, ([], []))
        if not a or not c:
            continue
        res = rote_tage_resilienz(c, bench_closes)
        if not res:
            continue
        resilient.append({
            "ticker": sym, "theme": etfs.THEMEN_ETFS.get(a["thema"], a["sektor_raw"]),
            "rs": int(a["rs"]), "pct_from_high": pct_from_high(c),
            **res,
        })
    resilient.sort(key=lambda r: r["rel_on_red"], reverse=True)
    resilient = resilient[:RESILIENT_MAX]

    kursdaten.speichere_cache(cache)

    out = {
        "mode": "evening",
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "universe_size": len(aktien),
        "regime": regime_einschaetzung(closes_by_ticker),
        "sectors": sektoren,
        "leaders": leaders,
        "resilient": resilient,
        "premarket": [],
    }

    with open(pfade.ROTATION_JSON, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
    with open(pfade.ROTATION_JS, "w", encoding="utf-8") as fp:  # file://-Fallback
        fp.write("window.ROTATION_DATA = ")
        json.dump(out, fp, ensure_ascii=False)
        fp.write(";")

    print(f"Rotation-Dashboard: {len(sektoren)} Sektoren, {len(leaders)} Leader, "
          f"{len(resilient)} Resilienz-Kandidaten, Universum {len(aktien)} Aktien.")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
