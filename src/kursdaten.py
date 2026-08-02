#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eigenstaendiger Kursdaten-Abruf fuer das Rotation-Dashboard.

Adaptiert aus Price-Action-Hub/src/kursdaten.py (selbst aus
Signal-Hub/src/scorer.py::yahoo_chart() abgeleitet) - bewusst dupliziert,
kein Import ueber die Ordnergrenze (Entflechtung, siehe pfade.py-Docstring).
Direkter Yahoo-Chart-API-Aufruf statt yfinance-Paket, damit die Pipeline
keine zusaetzliche Abhaengigkeit braucht (identisches Lastprofil wie die
beiden Schwester-Apps).
"""

import concurrent.futures
import json
import ssl
import time
import urllib.parse
import urllib.request

import pfade

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"}


def _http_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as r:
        return json.load(r)


def yahoo_chart(symbol, range_="2y"):
    """Close/Volumen (kein OHLC noetig - reine RS-/Resilienz-Berechnung).
    2y statt 1y: die 252-Handelstage-RS-Komponente (~12 Monate) braucht
    STRIKT MEHR als 252 Balken, ein reiner 1y-Range liegt oft genau an
    dieser Grenze und wuerde die 12-Monats-Komponente regelmaessig leer
    lassen. None bei Fehler/zu wenig Historie."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?range={range_}&interval=1d")
    d = _http_json(url)
    res = d.get("chart", {}).get("result")
    if not res:
        return None
    r = res[0]
    q = r.get("indicators", {}).get("quote", [{}])[0]
    co, vo = q.get("close") or [], q.get("volume") or []
    closes, volumes = [], []
    for i in range(len(co)):
        c = co[i]
        if c is None:
            continue
        closes.append(c)
        volumes.append(vo[i] if i < len(vo) and vo[i] is not None else None)
    if len(closes) < 60:
        return None
    return {"closes": closes, "volumes": volumes}


def lade_cache():
    try:
        with open(pfade.YAHOO_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def speichere_cache(cache):
    with open(pfade.YAHOO_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def hole_chart_cached(symbol, cache, heute):
    """Tages-Cache-Wrapper, faengt Netzwerkfehler pro Ticker einzeln ab.
    Performance-Review 2026-08-02: Exceptions werden NICHT gecacht (sonst
    sperrt ein einmaliger Timeout den Ticker fuer den Rest des Tages,
    ununterscheidbar von "wirklich keine Daten")."""
    key = f"{symbol}@{heute}"
    if key in cache:
        return cache[key]
    try:
        d = yahoo_chart(symbol)
    except Exception:
        time.sleep(0.25)
        return None
    time.sleep(0.25)
    cache[key] = d
    return d


def prefetch_charts_parallel(symbols, cache, heute, max_workers=5):
    """Holt alle noch nicht gecachten Charts parallel statt seriell mit
    time.sleep() dazwischen (Performance-Review 2026-08-02, analog Signal-Hub/
    Price-Action-Hub). Schreibt in `cache` im selben Format wie
    hole_chart_cached() - jeder Aufruf davon im bestehenden Loop wird danach
    ein reiner Cache-Hit."""
    fehlend, gesehen = [], set()
    for symbol in symbols:
        if not symbol or symbol in gesehen:
            continue
        gesehen.add(symbol)
        if f"{symbol}@{heute}" not in cache:
            fehlend.append(symbol)
    if not fehlend:
        return
    def _fetch(symbol):
        try:
            d = yahoo_chart(symbol)
            fehler = False
        except Exception:
            d, fehler = None, True
        time.sleep(0.2)
        return symbol, d, fehler
    print(f"  Praefetch: {len(fehlend)} neue Charts ({max_workers} parallel) ...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for symbol, d, fehler in ex.map(_fetch, fehlend):
            if not fehler:
                cache[f"{symbol}@{heute}"] = d
