"""Phase 6 — snapshot narrows honestly, never fabricates (§4.3)."""

from lnos import snapshot as snap_mod


def test_without_fips_every_metric_is_narrowed_not_fabricated():
    snap = snap_mod.build_snapshot("cwmg-omaha-cia")
    assert snap.available_metrics == []
    assert snap.is_thin
    assert snap.narrowed  # plain-language reasons, one per metric
    assert all("not available" in m.display() for m in snap.metrics)


def test_metric_display_includes_value_when_available():
    from lnos.cache import SignalResult, FreshnessMeta
    ok = SignalResult(source="fred", available=True, value=3.4, unit="%",
                      meta=FreshnessMeta(source="fred", as_of="2026-04-01"))
    m = snap_mod.SnapshotMetric("County unemployment rate", ok)
    assert "3.4" in m.display() and "2026-04-01" in m.display()
