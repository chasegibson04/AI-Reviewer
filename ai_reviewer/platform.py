from __future__ import annotations

from dataclasses import dataclass
import platform


@dataclass(frozen=True)
class PlatformInfo:
    os_name: str
    arch: str
    is_macos: bool
    is_windows: bool
    is_linux: bool
    is_mac_arm: bool


def detect_platform() -> PlatformInfo:
    os_name = platform.system()
    arch = platform.machine().lower()
    is_macos = os_name == "Darwin"
    is_windows = os_name == "Windows"
    is_linux = os_name == "Linux"
    is_mac_arm = is_macos and arch in {"arm64", "aarch64"}
    return PlatformInfo(
        os_name=os_name,
        arch=arch,
        is_macos=is_macos,
        is_windows=is_windows,
        is_linux=is_linux,
        is_mac_arm=is_mac_arm,
    )
