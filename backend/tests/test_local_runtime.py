import threading

import pytest

from pipeline import local_runtime


@pytest.fixture(autouse=True)
def _reset():
    local_runtime.reset_for_testing()
    yield
    local_runtime.reset_for_testing()


def test_hold_records_the_current_occupant():
    with local_runtime.hold("image"):
        assert local_runtime.current_occupant() == "image"
    assert local_runtime.current_occupant() == "image"


def test_switching_modality_unloads_the_previous_one(monkeypatch):
    unloaded: list[str] = []
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: unloaded.append(modality))
    with local_runtime.hold("text"):
        pass
    with local_runtime.hold("image"):
        pass
    assert unloaded == ["text"]


def test_reentrant_hold_of_same_modality_does_not_unload(monkeypatch):
    unloaded: list[str] = []
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: unloaded.append(modality))
    with local_runtime.hold("text"):
        with local_runtime.hold("text"):
            pass
    assert unloaded == []


def test_hold_serializes_across_threads(monkeypatch):
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: None)
    order: list[str] = []
    started = threading.Event()

    def worker():
        started.wait(timeout=5)
        with local_runtime.hold("image"):
            order.append("image")

    thread = threading.Thread(target=worker)
    with local_runtime.hold("text"):
        thread.start()
        started.set()
        thread.join(timeout=0.5)
        order.append("text")
    thread.join(timeout=5)
    assert order == ["text", "image"]


def test_unload_all_clears_the_occupant(monkeypatch):
    unloaded: list[str] = []
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: unloaded.append(modality))
    with local_runtime.hold("voice"):
        pass
    local_runtime.unload_all()
    assert unloaded == ["voice"]
    assert local_runtime.current_occupant() is None


def test_unload_all_is_safe_when_nothing_is_resident(monkeypatch):
    unloaded: list[str] = []
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: unloaded.append(modality))
    local_runtime.unload_all()
    assert unloaded == []


def test_unload_never_raises_when_the_daemon_is_down(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(local_runtime.httpx, "post", boom)
    local_runtime._unload("image")  # must not raise


def test_ollama_keep_alive_is_short_in_local_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    assert local_runtime.ollama_keep_alive() == "60s"
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    assert local_runtime.ollama_keep_alive() == "30m"


def test_daemon_health_reports_every_backend(monkeypatch):
    monkeypatch.setattr(local_runtime, "_probe", lambda url: "11434" in url)
    health = local_runtime.daemon_health()
    assert set(health) == {"ollama", "comfyui", "mlx-audio"}
    assert health["ollama"] is True
    assert health["comfyui"] is False


def test_daemon_url_honours_the_env_override(monkeypatch):
    monkeypatch.setenv("LOCAL_COMFYUI_URL", "http://127.0.0.1:9999/")
    assert local_runtime.daemon_url("comfyui") == "http://127.0.0.1:9999"


def test_ensure_daemon_raises_an_actionable_error(monkeypatch):
    monkeypatch.setattr(local_runtime, "_probe", lambda url: False)
    with pytest.raises(RuntimeError, match="not responding"):
        local_runtime.ensure_daemon("comfyui")


def test_ensure_daemon_passes_when_healthy(monkeypatch):
    monkeypatch.setattr(local_runtime, "_probe", lambda url: True)
    local_runtime.ensure_daemon("comfyui")
