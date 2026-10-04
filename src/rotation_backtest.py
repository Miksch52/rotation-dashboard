#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Forward-Test für die drei Rotation-Dashboard-Setup-Kategorien.

Gleiches Grundprinzip wie Price-Action-Hub/src/hebel_backtest.py
(unverzerrtes Forward-Logbuch, kein Retro-Modus - alle drei Kategorien
kombinieren bereits mehrere fremde Quellen, eine rückwirkende Rekonstruktion
lohnt sich für einen ersten Baustein nicht). Drei Kohorten:

  top_rs_etf   - Themen-ETF mit RS-Rating >= 80 (IBD/Minervini-Konvention:
                 RS >= 80 gilt als "führend"). Testet, ob das eigene, echte
                 IBD-Rating (rs.py) tatsächlich Momentum-Persistenz hat.
  leader       - Aktien, die als Leader in einem der stärksten Themen
                 geführt werden (aus dem Markets-360-Export übernommen).
  resilient    - Aktien mit auffälliger Rote-Tage-Resilienz.

Bewusst ABSOLUTER Forward-Return (kein Index-Edge wie bei Signal-Hubs
score_backtest.py) - erster Baustein, Index-Vergleich kann später ergänzt
werden, falls die absolute Auswertung zu leicht vom Marktregime verzerrt
wirkt.

  python3 src/rotation_backtest.py --log       # haengt die heutigen Treffer
        je Kategorie mit Datum+Kurs ans Forward-Logbuch.
  python3 src/rotation_backtest.py --evaluate  # bewertet gereifte Picks
        (>=21/50/78 Kalendertage) gegen aktuelle Yahoo-Kurse.

run.py ruft log_und_evaluate() bei jedem Lauf auf.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import index_vergleich
import pfade
import kursdaten

HORIZONTE = [("4W", 21), ("8W", 50), ("12W", 78)]   # Mindest-KALENDERtage je Kohorte
KATEGORIEN = ("top_rs_etf", "leader", "resilient")
RS_SCHWELLE = 80   # IBD/Minervini-Konvention: RS-Rating >= 80 gilt als fuehrend
DUBLETTEN = 0      # vom letzten evaluate() herausgefilterte Dubletten (seit 2026-10-04)


def _stats(rets):
    if not rets:
        return {"n": 0, "win": None, "avg": None, "median": None}
    rets = sorted(rets)
    n = len(rets)
    win = sum(1 for r in rets if r > 0) / n
    avg = sum(rets) / n
    median = rets[n // 2] if n % 2 else (rets[n // 2 - 1] + rets[n // 2]) / 2
    return {"n": n, "win": round(win * 100, 1),
            "avg": round(avg * 100, 2), "median": round(median * 100, 2)}


def _bucket(elapsed_tage):
    """Kalendertage -> reifster Horizont (oder None, wenn noch zu jung)."""
    if elapsed_tage >= 78:
        return "12W"
    if elapsed_tage >= 50:
        return "8W"
    if elapsed_tage >= 21:
        return "4W"
    return None


def _preis(symbol, cache, heute_str):
    d = kursdaten.hole_chart_cached(symbol, cache, heute_str)
    return d.get("closes")[-1] if d and d.get("closes") else None


# ---------------------------------------------------------------------------
def _logbuch_load():
    if os.path.exists(pfade.ROTATION_LOGBUCH):
        try:
            return json.load(open(pfade.ROTATION_LOGBUCH, encoding="utf-8"))
        except Exception:
            return []
    return []


def _logbuch_save(lb):
    with open(pfade.ROTATION_LOGBUCH, "w", encoding="utf-8") as f:
        json.dump(lb, f, ensure_ascii=False, indent=2)


def log_heute():
    if not os.path.exists(pfade.ROTATION_JSON):
        print("Keine rotation.json -> nichts zu loggen.")
        return
    daten = json.load(open(pfade.ROTATION_JSON, encoding="utf-8"))
    heute = datetime.now().strftime("%Y-%m-%d")
    lb = _logbuch_load()
    # Doppel-Pruefung ueber den belegten Handelstag statt das Schreibdatum
    # (seit 2026-10-04, siehe index_vergleich.logbuch_schluessel): Sa-, So- und
    # Mo-Lauf sehen dieselben Freitagskurse und legen damit nur EINEN Eintrag an.
    bekannt = {index_vergleich.logbuch_schluessel(e, "ticker", "kategorie") for e in lb}
    cache = kursdaten.lade_cache()
    idx_charts = index_vergleich.lade_index_charts(kursdaten.hole_chart_cached, cache, heute)
    neu = 0

    def anhaengen(ticker, kategorie, preis, quelle):
        nonlocal neu
        eintrag = {"datum": heute, "ticker": ticker, "kategorie": kategorie}
        ht = index_vergleich.handelstag_fuer(idx_charts, None, ticker)
        if ht:
            eintrag["handelstag"] = ht
        key = index_vergleich.logbuch_schluessel(eintrag, "ticker", "kategorie")
        if key in bekannt:
            return
        preis = preis() if callable(preis) else preis
        if not preis:
            return
        eintrag.update({"theme": quelle.get("theme"), "rs": quelle.get("rs"),
                        "preis_signal": preis})
        lb.append(eintrag)
        bekannt.add(key)
        neu += 1

    for s in daten.get("sectors", []):
        ticker = s.get("etf")
        if not ticker or s.get("rs") is None or s["rs"] < RS_SCHWELLE:
            continue
        anhaengen(ticker, "top_rs_etf", lambda t=ticker: _preis(t, cache, heute), s)

    for l in daten.get("leaders", []):
        ticker = l.get("ticker")
        if not ticker:
            continue
        anhaengen(ticker, "leader",
                  lambda t=ticker, l=l: l.get("price") or _preis(t, cache, heute), l)

    for r in daten.get("resilient", []):
        ticker = r.get("ticker")
        if not ticker:
            continue
        anhaengen(ticker, "resilient", lambda t=ticker: _preis(t, cache, heute), r)

    kursdaten.speichere_cache(cache)
    # Aufbewahrung nach ALTER statt nach Eintragszahl (seit 2026-09-13). Die
    # fruehere Kappe "lb[-N:]" skalierte mit der Treffermenge: bei ~417
    # Hebel- bzw. ~172 Pivot-Eintraegen je Tag behielt sie in der Cloud nur
    # 12 bzw. 29 Tage und loeschte Episoden, bevor sie 4W/8W/12W erreichen
    # konnten (Hebel-Backtest dauerhaft n=0, Pivot nie 8W/12W; Pivot-
    # Episoden 02.07.-15.08.2026 dadurch unwiederbringlich verloren).
    # 120 Tage = laengster Horizont (78 Kalendertage) plus Puffer.
    aufbewahrung_tage = 120
    grenze = (datetime.now().date() - timedelta(days=aufbewahrung_tage)).isoformat()
    lb = [e for e in lb if (e.get("datum") or "") >= grenze]
    _logbuch_save(lb)
    print(f"Rotation-Forward-Logbuch: {neu} neue Picks ergaenzt (gesamt {len(lb)}).")


# ---------------------------------------------------------------------------
def evaluate():
    lb = _logbuch_load()
    if not lb:
        print("Rotation-Logbuch leer -> erst --log sammeln lassen.")
        return {}, []
    cache = kursdaten.lade_cache()
    heute_dt = datetime.now().date()
    heute_str = heute_dt.isoformat()
    eimer = {k: {h: [] for h, _ in HORIZONTE} for k in KATEGORIEN}
    # Index-Vergleich (seit 2026-09-12, Systempruefung Punkt 5): bis dahin
    # meldete diese Datei bewusst nur absolute Returns - "Leader-Aktie
    # 91,7 % Trefferquote" war damit genauso wenig belegt wie eine schwache
    # Kohorte, nur in die andere Richtung. Das Rotations-Logbuch fuehrt
    # keinen Markt; seit 2026-09-13 leitet index_vergleich.markt_fuer ihn aus
    # dem Boersensuffix ab (unter den Leadern/Resilienz-Kandidaten stehen auch
    # europaeische Werte wie SHEL.L oder ASML.AS - vorher alle gegen ^GSPC).
    eimer_edge = {k: {h: [] for h, _ in HORIZONTE} for k in KATEGORIEN}
    idx_charts = index_vergleich.lade_index_charts(
        kursdaten.hole_chart_cached, cache, heute_str)
    einzelfaelle = []
    charts = {}
    # Dubletten-Filter (seit 2026-10-04, siehe index_vergleich.ist_dublette):
    # eine Episode je (Ticker, Kategorie, Startbar) - Sa/So/Mo bzw. Feiertag +
    # Folgetag zaehlten vorher mehrfach mit identischem Ergebnis.
    global DUBLETTEN
    DUBLETTEN = 0
    gesehen = set()
    for e in lb:
        try:
            tage = (heute_dt - datetime.strptime(e["datum"], "%Y-%m-%d").date()).days
        except Exception:
            continue
        if e.get("kategorie") not in eimer:
            continue
        sym = e.get("ticker")
        if sym not in charts:
            charts[sym] = kursdaten.hole_chart_cached(sym, cache, heute_str) or {}
        # Feste Fenster (seit 2026-09-13, Systempruefung Punkt 2), siehe
        # index_vergleich.fenster_returns: Signalkurs gegen den Schlusskurs genau
        # 21/50/78 Kalendertage spaeter. Die Episode zaehlt in jedem erreichten
        # Horizont; bk/ret meinen den laengsten davon (Einzelfall-Liste).
        start = index_vergleich.start_datum(e)
        rets = index_vergleich.fenster_returns(charts[sym], start, e.get("preis_signal"))
        bk, ret = index_vergleich.laengster_horizont(rets)
        if bk is None:
            continue
        if index_vergleich.ist_dublette(gesehen, charts[sym], start, sym, e["kategorie"]):
            DUBLETTEN += 1
            continue
        edges = index_vergleich.fenster_edges(idx_charts, e.get("markt"), start, rets,
                                              pick_chart=charts[sym], ticker=sym)
        for h, r in rets.items():
            if r is None:
                continue
            eimer[e["kategorie"]][h].append(r)
            if edges[h] is not None:
                eimer_edge[e["kategorie"]][h].append(edges[h])
        edge = edges[bk]
        einzelfaelle.append({
            "ticker": e["ticker"], "kategorie": e["kategorie"], "theme": e.get("theme"),
            "datum": e["datum"], "handelstag": e.get("handelstag"),
            "preis_signal": e["preis_signal"],
            "horizont": bk, "return_pct": round(ret * 100, 2),
            "edge_idx_pct": round(edge * 100, 2) if edge is not None else None,
            "fenster": {h: round(r * 100, 2) for h, r in rets.items() if r is not None},
        })
    kursdaten.speichere_cache(cache)
    fr = {k: {h: index_vergleich.ergaenze_edge(_stats(eimer[k][h]), eimer_edge[k][h])
              for h, _ in HORIZONTE} for k in eimer}
    return fr, einzelfaelle


# ---------------------------------------------------------------------------
def _schreibe(out):
    with open(pfade.ROTATION_BACKTEST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(pfade.ROTATION_BACKTEST_JS, "w", encoding="utf-8") as f:
        f.write("window.ROTATION_BACKTEST_DATA = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";")


def _druck_tabelle(fr):
    print(f"{'Kategorie':12s}{'Hor':5s}{'n':>5s}{'Win%':>7s}{'Ø%':>8s}{'ØvsIdx':>9s}{'>Idx%':>7s}")
    for kategorie in KATEGORIEN:
        for label, _ in HORIZONTE:
            s = fr.get(kategorie, {}).get(label) or {}
            if not s.get("n"):
                continue
            # Index-Spalten (seit 2026-09-12): erst der Vorsprung sagt, ob die
            # Kohorte etwas kann - der Absolutwert sagt nur, wie der Markt lief.
            e_avg = s.get("edge_idx_avg")
            e_win = s.get("edge_idx_win")
            print(f"{kategorie:12s}{label:5s}{s['n']:5d}{s['win']:7.1f}{s['avg']:8.2f}"
                  f"{(e_avg if e_avg is not None else 0):+9.2f}"
                  f"{(e_win if e_win is not None else 0):7.1f}")


def log_und_evaluate():
    """Bequemer Einstiegspunkt fuer run.py: loggen + auswerten + schreiben in
    einem Aufruf."""
    log_heute()
    fr, einzelfaelle = evaluate()
    out = {
        "erstellt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hinweis": ("Forward-Test mit festen Fenstern (seit 2026-09-13): Kurs am Signaltag "
                    "(top_rs_etf: RS-Rating >= 80, leader: Leader-Aktie im staerksten Thema, "
                    "resilient: Rote-Tage-Resilienz-Kandidat) vs. Schlusskurs genau 21/50/78 "
                    "Kalendertage spaeter; eine Episode zaehlt in jedem erreichten Horizont, "
                    "ihr Wert bleibt danach fest. Unverzerrt (Einstufung stand vor dem "
                    "Ergebnis fest). Mit Index-Vergleich gegen ^GSPC ueber dasselbe Fenster "
                    "(seit 2026-09-12). Je Ticker, Kategorie und Starttag zaehlt nur eine "
                    "Episode (seit 2026-10-04: Sa/So/Mo bzw. Feiertag + Folgetag waren "
                    "vorher Dubletten)."),
        "forward_realisiert": fr,
        "forward_einzelfaelle": einzelfaelle,
        "dubletten_gefiltert": DUBLETTEN,
    }
    _schreibe(out)
    if einzelfaelle:
        print(f"\n=== Rotation-Dashboard Forward-Test ({len(einzelfaelle)} gereifte Einzelfaelle) ===")
        _druck_tabelle(fr)
    if DUBLETTEN:
        print(f"Dubletten herausgefiltert (gleicher Starttag): {DUBLETTEN}")
    print(f"Gespeichert: {pfade.ROTATION_BACKTEST}")
    return fr, einzelfaelle


def main():
    args = sys.argv[1:]
    if "--log" in args:
        log_heute()
        return
    if "--evaluate" in args:
        log_und_evaluate()
        return
    print("Nutzung: rotation_backtest.py --log | --evaluate")


if __name__ == "__main__":
    main()
