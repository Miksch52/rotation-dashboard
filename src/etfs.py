#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Feste Themen-ETF-Liste (Ticker + Anzeigename), 1:1 aus der Konzept-Vorlage
uebernommen. Reihenfolge irrelevant - run.py sortiert nach RS-Rating."""

THEMEN_ETFS = {
    "XLI": "Industrials",
    "XME": "Metalle/Mining",
    "XLK": "Tech (breit)",
    "XLV": "Healthcare",
    "XLC": "Internet/Comm",
    "XLP": "Cons. Staples",
    "BOTZ": "KI-Robotik",
    "XLY": "Cons. Disc.",
    "ITA": "Defense/Aero",
    "CIBR": "Cyber",
    "XLE": "Energie",
    "URA": "Uran/Nuklear",
    "XBI": "Biotech",
    "XOP": "Oil&Gas E&P",
    "XLF": "Financials",
    "XLU": "Utilities",
    "IGV": "Software",
    "GDX": "Gold-Miner",
    "SMH": "Halbleiter",
    "TAN": "Solar",
    "KRE": "Regional Banks",
}

# Regime-Referenzen fuer die Kachel oben (Leadership/Breadth), nicht Teil der
# RS-Rangliste selbst.
REGIME_TICKER = {
    "spy": "SPY",
    "qqq": "QQQ",
    "dia": "DIA",
    "iwm": "IWM",
    "rsp": "RSP",
}

# Benchmark fuer die RS-Berechnung selbst - identisch zum Trend-Screener
# (Lokaler-Trend-Screener/config.py::BENCHMARK), fuer konsistente RS-Werte
# systemweit.
RS_BENCHMARK = "^GSPC"
