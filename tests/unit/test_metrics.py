"""Unit tests for MetricsWorker telemetry logic."""

from linux_game_bar.core.metrics_service import MetricsWorker


def test_metrics_worker_data_collection(qapp):
    worker = MetricsWorker(interval_ms=500, history_len=10)
    data = worker._collect_metrics()

    assert "cpu" in data
    assert "ram" in data
    assert "gpu" in data
    assert "thermal" in data
    assert "battery" in data

    assert isinstance(data["cpu"]["percent"], (int, float))
    assert isinstance(data["ram"]["percent"], (int, float))
    assert data["ram"]["total_gb"] > 0
    assert len(data["cpu"]["history"]) == 1


def test_metrics_intel_gpu_fallback(tmp_path):
    # Pass a non-existent sysfs path to test graceful handling without crashing
    worker = MetricsWorker(interval_ms=500, history_len=10, intel_sysfs_path=str(tmp_path / "nonexistent"))
    gpu_data = worker._sample_intel_gpu()
    assert gpu_data["available"] is False
    assert gpu_data["percent"] == 0.0
