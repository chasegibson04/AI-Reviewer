from ai_reviewer.platform import detect_platform, PlatformInfo


def test_detect_platform_mac_arm(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("platform.machine", lambda: "arm64")
    info = detect_platform()
    assert isinstance(info, PlatformInfo)
    assert info.is_macos is True
    assert info.is_mac_arm is True


def test_detect_platform_non_mac(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    info = detect_platform()
    assert info.is_macos is False
    assert info.is_mac_arm is False
