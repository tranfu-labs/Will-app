import json

from yizhi.fundarb.dataset import build_coverage_report, ingest_cache, write_coverage_report


def _write_cache(tmp_path):
    ts0, step = 1700000000000, 28800000

    def series(rate, n=3):
        return {str(ts0 + i * step): str(rate) for i in range(n)}

    cache = {
        "venues": ["binance", "bybit"],
        "symbols": {
            "EDGEY": {
                "interval_hours": 8,
                "snapshot_diff": 0.0009,
                "binance": series("0.001"),
                "bybit": series("0.0001"),
            },
            "ONE_SIDED": {
                "interval_hours": 8,
                "snapshot_diff": 0.0,
                "binance": series("0.0002", n=2),
                "bybit": {},
            },
        },
    }
    path = tmp_path / "funding_cache.json"
    path.write_text(json.dumps(cache), encoding="utf-8")
    return path


def test_ingest_cache_appends_observations_once(tmp_path):
    cache = _write_cache(tmp_path)
    ledger = tmp_path / "ledger.jsonl"

    first = ingest_cache(cache, ledger, now_iso="2026-06-27T00:00:00+00:00")
    second = ingest_cache(cache, ledger, now_iso="2026-06-27T01:00:00+00:00")

    assert first.records_seen == 8
    assert first.records_added == 8
    assert first.records_existing == 0
    assert second.records_seen == 8
    assert second.records_added == 0
    assert second.records_existing == 8

    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 8
    assert {row["record_type"] for row in rows} == {"funding_rate"}
    assert len({row["record_id"] for row in rows}) == 8
    assert {row["source_snapshot_id"] for row in rows} == {first.source_snapshot_id}


def test_coverage_report_counts_overlap_and_readiness(tmp_path):
    cache = _write_cache(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    ingest_cache(cache, ledger, now_iso="2026-06-27T00:00:00+00:00")

    report = build_coverage_report(ledger, min_periods=3)

    assert report["records"] == 8
    assert report["symbols"] == 2
    assert report["backtest_ready_symbols"] == 1
    assert report["insufficient_symbols"] == 1
    assert report["symbol_coverage"]["EDGEY"]["overlap_points"] == 3
    assert report["symbol_coverage"]["EDGEY"]["backtest_ready"] is True
    assert report["symbol_coverage"]["ONE_SIDED"]["overlap_points"] == 0
    assert report["symbol_coverage"]["ONE_SIDED"]["backtest_ready"] is False

    output = write_coverage_report(report, tmp_path / "coverage.json")
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["symbol_coverage"]["EDGEY"]["venues"]["binance"]["points"] == 3


def test_coverage_write_preserves_generated_at_when_stable(tmp_path):
    cache = _write_cache(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    ingest_cache(cache, ledger, now_iso="2026-06-27T00:00:00+00:00")
    output = tmp_path / "coverage.json"
    first = build_coverage_report(ledger, min_periods=3)
    first["generated_at"] = "first"
    write_coverage_report(first, output)

    second = build_coverage_report(ledger, min_periods=3)
    second["generated_at"] = "second"
    write_coverage_report(second, output)
    saved = json.loads(output.read_text(encoding="utf-8"))

    assert saved["generated_at"] == "first"

    changed = build_coverage_report(ledger, min_periods=4)
    changed["generated_at"] = "third"
    write_coverage_report(changed, output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["generated_at"] == "third"
