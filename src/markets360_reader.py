#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liest den Markets-360-Export (Symbol/Name/Kurs/RS/TT_Pass/Sektor je Aktie) -
NUR das, keine eigene Ticker-Recherche, keine eigene RS-Berechnung fuer
Einzelaktien (Entflechtung, siehe pfade.py-Docstring). Cloud-Lauf und
lokaler Lauf probieren dieselben zwei Pfade wie Signal-Hub/Price-Action-Hub
(EXTERN_* zuerst, dann LOKAL_* als Fallback - siehe pfade.py).

CSV ist Semikolon-getrennt mit deutschem Dezimalkomma (Apple-Numbers-Export-
Konvention, siehe globale CLAUDE.md "File Encoding"). Trend-Screener wird
hier bewusst NICHT mit eingelesen: dessen "sector"-Feld ist aktuell noch
durchgehend None (Stand 2026-07), liefert also keinen Mehrwert fuer die
Sektor-Zuordnung - kann nachgezogen werden, sobald sich das aendert.
"""

import csv
import json
import os

import pfade
from sektor_mapping import thema_fuer_sektor


def _de_float(s):
    if not s or s == "—":
        return None
    try:
        return float(s.replace(".", "").replace(",", ".").replace("€", "").replace("$", "").strip())
    except ValueError:
        return None


def _quelle_datei():
    for pfad in (pfade.EXTERN_MARKETS360, pfade.LOKAL_MARKETS360):
        if os.path.isfile(pfad):
            return pfad
    return None


def lade_aktien():
    """Liste von Dicts: symbol, name, price, rs, tt_pass, sektor_raw, thema.
    Leer, wenn die Quelldatei (noch) fehlt - kein Fehler, siehe pfade.py."""
    datei = _quelle_datei()
    if not datei:
        return []
    aktien = []
    with open(datei, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            symbol = (row.get("Symbol") or "").strip()
            rs = _de_float(row.get("RS"))
            if not symbol or rs is None:
                continue
            sektor_raw = (row.get("Sektor") or "").strip()
            aktien.append({
                "symbol": symbol,
                "name": (row.get("Name") or symbol).strip(),
                "price": _de_float(row.get("Kurs")),
                "rs": rs,
                # Achtung Spaltennamen: "TrendTemplate" ist die numerische
                # Kriterien-Anzahl (0..8), "TT_Pass" ist nur True/False (alle
                # 8 erfuellt) - nicht verwechseln.
                "tt_pass": _de_float(row.get("TrendTemplate")),
                "sektor_raw": sektor_raw,
                "thema": thema_fuer_sektor(sektor_raw),
            })
    return aktien
