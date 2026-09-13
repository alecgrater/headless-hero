from pipeline import voiceover


def test_cloud_mode_selects_elevenlabs(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    from integrations import elevenlabs_client

    assert voiceover.active_speech_client() is elevenlabs_client.generate_speech


def test_local_mode_selects_local_client(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    from integrations import local_tts_client

    assert voiceover.active_speech_client() is local_tts_client.generate_speech


def test_voice_pinned_cloud_overrides_master_switch(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_VOICE_MODE", "cloud")
    from integrations import elevenlabs_client

    assert voiceover.active_speech_client() is elevenlabs_client.generate_speech


def test_voice_pinned_local_with_master_switch_off(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.setenv("LOCAL_VOICE_MODE", "local")
    from integrations import local_tts_client

    assert voiceover.active_speech_client() is local_tts_client.generate_speech


def test_generate_scene_audio_uses_the_local_client(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setattr(voiceover, "DATA_DIR", tmp_path)

    calls: list[str] = []

    def fake(text, voice_id, model_id=None, voice_settings=None, script_id=None):
        calls.append(text)
        return b"ID3FAKE", [{"word": "hi", "start_ms": 0, "end_ms": 500}]

    monkeypatch.setattr(voiceover, "active_speech_client", lambda: fake)

    web_path, duration, words, phrases = voiceover.generate_scene_audio(
        scene_id="s1", narration="hi", voice_id="narrator", script_id="proj1",
    )
    assert calls == ["hi"]
    assert duration == 0.5
    assert web_path == "/static/projects/proj1/audio/s1.mp3"
    assert (tmp_path / "projects" / "proj1" / "audio" / "s1.mp3").read_bytes() == b"ID3FAKE"
    assert words[0]["word"] == "hi"
    assert phrases


def test_generate_scene_audio_still_uses_elevenlabs_in_cloud_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setattr(voiceover, "DATA_DIR", tmp_path)

    seen: list[str] = []

    def fake(text, voice_id, model_id=None, voice_settings=None, script_id=None):
        seen.append("cloud")
        return b"ID3CLOUD", [{"word": "hi", "start_ms": 0, "end_ms": 250}]

    monkeypatch.setattr(voiceover, "_elevenlabs_generate_speech", fake)

    _, duration, _, _ = voiceover.generate_scene_audio(
        scene_id="s2", narration="hi", voice_id="narrator", script_id="proj2",
    )
    assert seen == ["cloud"]
    assert duration == 0.25
