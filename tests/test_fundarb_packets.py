import json

from yizhi.fundarb.packets import build_promotion_packet, write_promotion_packet


def _result(symbol, verdict, rid, net=0.0, sharpe=0.0, n_entered=20):
    return {
        "record_type": "fundarb_experiment_result",
        "result_id": rid,
        "source_coverage_id": "cov-1",
        "experiment_id": "exp-" + rid,
        "experiment": {
            "symbol": symbol,
            "min_net_bps": 5.0,
            "horizon_hours": 24.0,
            "coverage": {"overlap_points": 30},
        },
        "metrics": {
            "symbol": symbol,
            "total_realized_bps": net,
            "sharpe_like": sharpe,
            "n_entered": n_entered,
            "persistence_sign_stability": 0.7,
        },
        "judgment": {
            "verdict": verdict,
            "confidence": 0.8,
            "reasons": [verdict],
            "conclusive": verdict in {"promote", "kill"},
        },
        "status": "succeeded",
    }


def _write_results(tmp_path, rows):
    path = tmp_path / "results.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_build_packet_groups_symbol_decisions(tmp_path):
    results = _write_results(
        tmp_path,
        [
            _result("PROMO", "promote", "r1", net=120, sharpe=0.8),
            _result("PROMO", "kill", "r2", net=-5),
            _result("ITER", "iterate", "r3", net=30, sharpe=0.1),
            _result("DEAD", "kill", "r4", net=-20),
            _result("THIN", "insufficient", "r5", n_entered=3),
        ],
    )

    packet = build_promotion_packet(results, now_iso="2026-06-27T00:00:00+00:00")
    by_symbol = {decision["symbol"]: decision for decision in packet["decisions"]}

    assert packet["summary"]["results"] == 5
    assert packet["summary"]["promote"] == 1
    assert by_symbol["PROMO"]["decision"] == "promote"
    assert by_symbol["ITER"]["decision"] == "iterate"
    assert by_symbol["DEAD"]["decision"] == "kill"
    assert by_symbol["THIN"]["decision"] == "insufficient"
    assert by_symbol["PROMO"]["safety"] if "safety" in by_symbol["PROMO"] else True
    assert packet["safety"]["live_trading_authorized"] is False


def test_packet_id_is_deterministic(tmp_path):
    results = _write_results(tmp_path, [_result("A", "kill", "r1", net=-1), _result("B", "insufficient", "r2")])

    first = build_promotion_packet(results, now_iso="2026-06-27T00:00:00+00:00")
    second = build_promotion_packet(results, now_iso="2026-06-27T01:00:00+00:00")

    assert first["packet_id"] == second["packet_id"]
    output = write_promotion_packet(first, tmp_path / "packet.json")
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["packet_id"] == first["packet_id"]
