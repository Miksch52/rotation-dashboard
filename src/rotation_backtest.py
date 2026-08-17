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
from datetime import datetime, timezone

import pfade
import kursdaten

HORIZONTE = [("4W", 21), ("8W", 50), ("12W", 78)]   # Mindest-KALENDERtage je Kohorte
KATEGORIEN = ("top_rs_etf", "leader", "resilient")
RS_SCHWELLE = 80   # IBD/Minervini-Konvention: RS-Rating >= 80 gilt als fuehrend


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
    bekannt = {(e["datum"], e["ticker"], e["kategorie"]) for e in lb}
    cache = kursdaten.lade_cache()
    neu = 0

    for s in daten.get("sectors", []):
        ticker = s.get("etf")
        if not ticker or s.get("rs") is None or s["rs"] < RS_SCHWELLE:
            continue
        key = (heute, ticker, "top_rs_etf")
        if key in bekannt:
            continue
        preis = _preis(ticker, cache, heute)
        if not preis:
            continue
        lb.append({"datum": heute, "ticker": ticker, "kategorie": "top_rs_etf",
                    "theme": s.get("theme"), "rs": s.get("rs"), "preis_signal": preis})
        neu += 1

    for l in daten.get("leaders", []):
        ticker = l.get("ticker")
        if not ticker:
            continue
        key = (heute, ticker, "leader")
        if key in bekannt:
            continue
        preis = l.get("price") or _preis(ticker, cache, heute)
        if not preis:
            continue
        lb.append({"datum": heute, "ticker": ticker, "kategorie": "leader",
                    "theme": l.get("theme"), "rs": l.get("rs"), "preis_signal": preis})
        neu += 1

    for r in daten.get("resilient", []):
        ticker = r.get("ticker")
        if not ticker:
            continue
        key = (heute, ticker, "resilient")
        if key in bekannt:
            continue
        preis = _preis(ticker, cache, heute)
        if not preis:
            continue
        lb.append({"datum": heute, "ticker": ticker, "kategorie": "resilient",
                    "theme": r.get("theme"), "rs": r.get("rs"), "preis_signal": preis})
        neu += 1

    kursdaten.speichere_cache(cache)
    lb = lb[-5000:]
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
    einzelfaelle = []
    aktuell = {}
    for e in lb:
        try:
            tage = (heute_dt - datetime.strptime(e["datum"], "%Y-%m-%d").date()).days
        except Exception:
            continue
        bk = _bucket(tage)
        if not bk or e.get("kategorie") not in eimer:
            continue
        sym = e.get("ticker")
        if sym not in aktuell:
            aktuell[sym] = _preis(sym, cache, heute_str)
        kurs = aktuell[sym]
        if not kurs or not e.get("preis_signal"):
            continue
        ret = kurs / e["preis_signal"] - 1
        eimer[e["kategorie"]][bk].append(ret)
        einzelfaelle.append({
            "ticker": e["ticker"], "kategorie": e["kategorie"], "theme": e.get("theme"),
            "datum": e["datum"], "preis_signal": e["preis_signal"],
            "horizont": bk, "return_pct": round(ret * 100, 2),
        })
    kursdaten.speichere_cache(cache)
    fr = {k: {h: _stats(eimer[k][h]) for h, _ in HORIZONTE} for k in eimer}
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
    print(f"{'Kategorie':12s}{'Hor':5s}{'n':>5s}{'Win%':>7s}{'Ø%':>8s}")
    for kategorie in KATEGORIEN:
        for label, _ in HORIZONTE:
            s = fr.get(kategorie, {}).get(label) or {}
            if not s.get("n"):
                continue
            print(f"{kategorie:12s}{label:5s}{s['n']:5d}{s['win']:7.1f}{s['avg']:8.2f}")


def log_und_evaluate():
    """Bequemer Einstiegspunkt fuer run.py: loggen + auswerten + schreiben in
    einem Aufruf."""
    log_heute()
    fr, einzelfaelle = evaluate()
    out = {
        "erstellt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hinweis": ("Forward-Test: Kurs am Signaltag (top_rs_etf: RS-Rating >= 80, "
                    "leader: Leader-Aktie im staerksten Thema, resilient: Rote-Tage-"
                    "Resilienz-Kandidat) vs. aktueller Kurs, Kohorten nach Alter "
                    "(>=21/50/78 Kalendertage). Unverzerrt (Einstufung stand vor dem "
                    "Ergebnis fest). Absoluter Return, kein Index-Vergleich (siehe "
                    "Docstring in rotation_backtest.py)."),
        "forward_realisiert": fr,
        "forward_einzelfaelle": einzelfaelle,
    }
    _schreibe(out)
    if einzelfaelle:
        print(f"\n=== Rotation-Dashboard Forward-Test ({len(einzelfaelle)} gereifte Einzelfaelle) ===")
        _druck_tabelle(fr)
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
