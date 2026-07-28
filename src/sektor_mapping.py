#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ordnet den "Sektor"-Wert aus dem Markets-360-Export (gemischte GICS-/
TradingView-Taxonomie, je nach Datenquelle unterschiedlich benannt - siehe
MinerviniMarkets360/config.yaml datasources.order: tradingview > yahoo) einem
der Themen-ETFs aus etfs.py zu, damit "Leader in den staerksten Themen"
befuellt werden kann.

Bekannte, bewusst in Kauf genommene Einschraenkung: die "Sektor"-Spalte ist
eine grobe Branchenklassifizierung, keine thematische Nische. Fuer
uebergreifende Themen-ETFs, die quer durch mehrere GICS-Sektoren gehen
(Defense/Aero=ITA, Cyber=CIBR, Uran/Nuklear=URA, Biotech=XBI, KI-Robotik=BOTZ,
Gold-Miner=GDX, Solar=TAN, Regional Banks=KRE) liefert diese Zuordnung daher
selten Treffer - deren ETF-RS wird trotzdem korrekt direkt aus den ETF-Kursen
berechnet (unabhaengig von dieser Tabelle), nur die Leader-Aktien-Liste bleibt
fuer diese Nischen-Themen ggf. leer. Kein Versuch, das ueber eine
Ticker-Einzelfall-Liste zu "reparieren" - waere Pflegeaufwand ohne
verlaessliche Datengrundlage.
"""

SEKTOR_ZU_THEMA = {
    "Basic Materials": "XME",
    "Commercial Services": "XLI",
    "Communication Services": "XLC",
    "Communications": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Durables": "XLY",
    "Consumer Non-Durables": "XLP",
    "Consumer Services": "XLY",
    "Distribution Services": "XLI",
    "Electronic Technology": "XLK",
    "Energy": "XLE",
    "Energy Minerals": "XOP",
    "Finance": "XLF",
    "Financial Services": "XLF",
    "Health Services": "XLV",
    "Health Technology": "XLV",
    "Healthcare": "XLV",
    "Industrial Services": "XLI",
    "Industrials": "XLI",
    "Non-Energy Minerals": "XME",
    "Process Industries": "XLI",
    "Producer Manufacturing": "XLI",
    "Retail Trade": "XLY",
    "Technology": "XLK",
    "Technology Services": "IGV",
    "Transportation": "XLI",
    "Utilities": "XLU",
}


def thema_fuer_sektor(sektor):
    return SEKTOR_ZU_THEMA.get((sektor or "").strip())
