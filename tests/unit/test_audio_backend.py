"""Unit tests for AudioBackend."""

from linux_game_bar.widgets.audio import AudioBackend


def test_audio_backend_initialization():
    backend = AudioBackend()
    assert hasattr(backend, "has_wpctl")
    assert hasattr(backend, "has_pactl")


def test_get_volume_real_or_fallback():
    backend = AudioBackend()
    vol, muted = backend.get_volume("@DEFAULT_AUDIO_SINK@")
    assert isinstance(vol, float)
    assert 0.0 <= vol <= 2.0
    assert isinstance(muted, bool)


def test_get_endpoints():
    backend = AudioBackend()
    sinks, sources = backend.get_endpoints()
    assert isinstance(sinks, list)
    assert isinstance(sources, list)
    # On target system with wpctl, sinks should be discovered
    if backend.has_wpctl:
        assert len(sinks) > 0
        assert any(s.is_default for s in sinks)
