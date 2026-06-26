#!/usr/bin/env python3
"""Fetch real funding data via the Tokyo VPS (geo-block node) into a local cache.

The local machine is geo-blocked from most exchanges; the Tokyo VPS is the project's
egress node. See docs/data-via-vps.md. The exchange fetch (ccxt) runs ON THE VPS via
ssh; this script captures the result and writes `data/funding_cache.json` locally.
yizhi's ArbBot backtest probe then reads that cache and runs ArbBot's PURE backtest
locally — yizhi's loop never SSHes (deterministic, offline-testable, fast).

Run periodically/on demand to refresh the universe:
    python scripts/fetch_funding_via_vps.py

Depth/breadth are env-tunable so yizhi's A6 frontier-widening can request MORE data
on exhaustion (more history per symbol resolves the judge's INSUFFICIENT verdicts):
    YIZHI_FETCH_HIST_LIMIT=500 YIZHI_FETCH_N_LONGTAIL=24 python scripts/fetch_funding_via_vps.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

VPS = "ubuntu@13.158.71.214"
PEM = pathlib.Path.home() / "Downloads" / "ArbBot.pem"
CACHE = pathlib.Path(__file__).resolve().parent.parent / "data" / "funding_cache.json"
MARKER = "@@@JSON@@@"

# Runs ON THE VPS: snapshot Binance+Bybit funding, rank by cross-venue diff, pick a
# universe (mainstream baseline + top long-tail), pull aligned history per symbol.
VPS_FETCH = r'''
import ccxt, json, statistics
N_LONGTAIL = 12
HIST_LIMIT = 200
def snap(exid):
    ex = getattr(ccxt, exid)({"options": {"defaultType": "swap"}, "timeout": 20000, "enableRateLimit": True})
    out = {}
    for sym, r in ex.fetch_funding_rates().items():
        fr = r.get("fundingRate")
        if fr is not None and sym.endswith("/USDT:USDT"):
            out[sym.split("/")[0]] = float(fr)
    return out
def hist(exid, base):
    ex = getattr(ccxt, exid)({"options": {"defaultType": "swap"}, "timeout": 20000, "enableRateLimit": True})
    try:
        h = ex.fetch_funding_rate_history(f"{base}/USDT:USDT", limit=HIST_LIMIT)
        return {str(int(x["timestamp"])): str(x["fundingRate"]) for x in h if x.get("fundingRate") is not None}
    except Exception:
        return {}
bn, bb = snap("binance"), snap("bybit")
diffs = sorted(((s, bn[s] - bb[s]) for s in set(bn) & set(bb)), key=lambda x: abs(x[1]), reverse=True)
sd = dict(diffs)
universe = ["BTC", "ETH"] + [s for s, _ in diffs[:N_LONGTAIL] if s not in ("BTC", "ETH")]
out = {}
for s in universe:
    hbn, hbb = hist("binance", s), hist("bybit", s)
    ts = sorted(set(int(k) for k in hbn) & set(int(k) for k in hbb))
    if len(ts) < 10:
        continue
    gaps = [(ts[i + 1] - ts[i]) / 3600000 for i in range(len(ts) - 1)]
    out[s] = {
        "interval_hours": round(statistics.median(gaps)),
        "snapshot_diff": sd.get(s, 0.0),
        "binance": {str(t): hbn[str(t)] for t in ts},
        "bybit": {str(t): hbb[str(t)] for t in ts},
    }
print("@@@JSON@@@" + json.dumps({"venues": ["binance", "bybit"], "symbols": out}))
'''


def main() -> int:
    if not PEM.exists():
        print(f"VPS key not found at {PEM}; see docs/data-via-vps.md", file=sys.stderr)
        return 1
    # Depth/breadth are env-tunable (A6 frontier-widening requests more on exhaustion).
    hist_limit = int(os.environ.get("YIZHI_FETCH_HIST_LIMIT", "200"))
    n_longtail = int(os.environ.get("YIZHI_FETCH_N_LONGTAIL", "12"))
    script = VPS_FETCH.replace("N_LONGTAIL = 12", f"N_LONGTAIL = {n_longtail}").replace(
        "HIST_LIMIT = 200", f"HIST_LIMIT = {hist_limit}"
    )
    proc = subprocess.run(
        ["ssh", "-i", str(PEM), "-o", "ConnectTimeout=20", VPS, "cd ~/arbbot && .venv/bin/python -"],
        input=script, capture_output=True, text=True, timeout=420,
    )
    if MARKER not in proc.stdout:
        print("VPS fetch failed:\n" + (proc.stderr[-1000:] or proc.stdout[-1000:]), file=sys.stderr)
        return 1
    data = json.loads(proc.stdout.split(MARKER, 1)[1].strip())
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=2))
    syms = data["symbols"]
    print(f"wrote {CACHE} — {len(syms)} symbols ({', '.join(syms)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
