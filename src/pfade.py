#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zentrale Pfade fuer das Rotation-Dashboard.

Trennt bewusst:
  DATA  = Rotation-Dashboard/data  -> Dashboard-Ausgabe (rotation.json/js).
          Liegt in iCloud; wird pro Lauf 1x geschrieben.
  LOKAL = ~/Library/Application Support/RotationDashboard
          -> Yahoo-Cache fuer die ETF-/Leader-Kurse. NICHT in iCloud
          (Sync-Konflikte/Eviction bei haeufigem Schreiben) und ein EIGENER
          Cache-Ordner, getrennt von Signal-Hub/Price-Action-Hub.

Liest Sektor/RS/Preis je Einzelaktie NUR aus den Ausgaben von Markets 360
und dem Trend-Screener (keine eigene Ticker-Recherche, keine doppelte
RS-Berechnung fuer Einzelaktien - Entflechtung, CLAUDE.md: "Apps nicht
mergen"). Zwei Datenpfade parallel, exakt wie in Signal-Hub/src/pfade.py:
lokal liest es die Original-Exporte direkt, der Cloud-Lauf den per rclone
aus R2 gezogenen _magazine/-Ordner (der bei Signal-Hub/pipeline.yml bereits
VOR diesem Schritt existiert, siehe Signal-Hub/.github/workflows/pipeline.yml).
"""

import os

HIER = os.path.dirname(os.path.abspath(__file__))        # .../Rotation-Dashboard/src
PROJEKT = os.path.dirname(HIER)                            # .../Rotation-Dashboard
REPO_ROOT = os.path.dirname(PROJEKT)                        # Geschwister-Ordner-Ebene

DATA = os.path.join(PROJEKT, "data")
os.makedirs(DATA, exist_ok=True)

ROTATION_JSON = os.path.join(DATA, "rotation.json")
ROTATION_JS = os.path.join(DATA, "rotation.js")
ROTATION_BACKTEST = os.path.join(DATA, "rotation_backtest.json")  # Forward-Test der drei Setup-Kategorien
ROTATION_BACKTEST_JS = os.path.join(DATA, "rotation_backtest.js")  # file://-Fallback

# Cloud-Lauf: von Signal-Hubs eigenem rclone-Schritt VOR diesem Schritt schon
# nach Signal-Hub/_magazine/ gezogen (working-directory: Signal-Hub dort).
EXTERN_MARKETS360 = os.path.join(REPO_ROOT, "Signal-Hub", "_magazine", "markets360", "markets360_latest.csv")
EXTERN_TRENDSCREENER = os.path.join(REPO_ROOT, "Signal-Hub", "_magazine", "trendscreener", "signals.json")

# Lokaler Lauf auf dem Mac mini: _magazine/ existiert dort nicht - Markets 360
# und der Trend-Screener schreiben ihre Nachtscan-Ergebnisse als eigene
# LaunchAgents auf derselben Maschine direkt an diese Original-Pfade (exakt
# dieselben Konstanten wie Signal-Hub/src/pfade.py::LOKAL_MARKETS360/
# LOKAL_TRENDSCREENER - bewusst dupliziert statt importiert, da die Repos
# getrennt bleiben muessen).
_ICLOUD = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")
LOKAL_MARKETS360 = os.path.join(
    _ICLOUD, "Trading-System", "Mein Minervini Trading-Journal-System",
    "MinerviniMarkets360", "exports", "markets360_latest.csv")
LOKAL_TRENDSCREENER = os.path.expanduser(
    "~/Library/Application Support/LokalerTrendScreener/output/signals.json")

LOKAL = os.path.expanduser("~/Library/Application Support/RotationDashboard")
os.makedirs(LOKAL, exist_ok=True)
YAHOO_CACHE = os.path.join(LOKAL, "yahoo_cache.json")
# Forward-Log der drei Setup-Kategorien (top_rs_etf/leader/resilient) - Basis
# fuer rotation_backtest.py. Wie bei Price-Action-Hub (hebel_logbuch.json)
# gibt es hier KEINEN lokalen Mac-mini-Dauerlauf, der als Ausweichquelle
# einspringen koennte - R2-Sicherung (in Signal-Hubs pipeline.yml) ist von
# Anfang an die einzige Persistenz.
ROTATION_LOGBUCH = os.path.join(LOKAL, "rotation_logbuch.json")
