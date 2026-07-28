#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IBD-aehnliches Relative-Strength-Rating fuer die Themen-ETFs.

Formel 1:1 aus dem externen Trend-Screener-Projekt uebernommen
(Lokaler-Trend-Screener/screener.py::raw_rs_score/assign_rs_ratings) - fuer
Einzelaktien liefern Markets 360 und der Trend-Screener ihr RS-Rating bereits
selbst mit (siehe markets360_reader.py), diese Kopie brauchen wir nur fuer
die Themen-ETFs, die sonst niemand bewertet. Bewusst dupliziert statt
importiert, da die Repos getrennt bleiben (Entflechtung). Reine Python-Listen
statt pandas, damit die Pipeline ohne zusaetzliche Abhaengigkeit auskommt
(gleiches Prinzip wie Price-Action-Hub).
"""

# Gewichtete Outperformance ggue. Benchmark ueber 3/6/9/12 Monate (Handelstage),
# juengstes Quartal am staerksten gewichtet - IBDs Price-Change%-Methodik.
RS_PERIODS = [63, 126, 189, 252]
RS_WEIGHTS = [0.40, 0.20, 0.20, 0.20]


def _perf(closes, lookback):
    if len(closes) <= lookback:
        return None
    return closes[-1] / closes[-1 - lookback] - 1.0


def raw_rs_score(closes, bench_closes):
    """Gewichtete Outperformance ggue. Benchmark; None wenn zu wenig Daten."""
    score = 0.0
    used = 0.0
    for lb, w in zip(RS_PERIODS, RS_WEIGHTS):
        s, b = _perf(closes, lb), _perf(bench_closes, lb)
        if s is None or b is None:
            continue
        score += w * (s - b)
        used += w
    if used == 0:
        return None
    return score / used


def assign_rs_ratings(raw_scores: dict):
    """Wandelt {key: raw_rs_score} in {key: RS-Rating 1..99} (Perzentil-Rang
    innerhalb der uebergebenen Gruppe, hier: die Themen-ETFs untereinander)."""
    items = sorted(((k, v) for k, v in raw_scores.items() if v is not None),
                    key=lambda kv: kv[1])
    n = len(items)
    if n == 0:
        return {}
    return {k: int(round(1 + ((i + 1) / n) * 98)) for i, (k, v) in enumerate(items)}
