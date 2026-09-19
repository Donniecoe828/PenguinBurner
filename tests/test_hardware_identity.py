from pathlib import Path

from drivers import hardware_identity


def test_detect_cpu_identity_parses_amd_cpu(monkeypatch) -> None:
    def fake_read_text(self: Path, *args, **kwargs) -> str:
        if str(self) == "/proc/cpuinfo":
            return (
                "processor\t: 0\n"
                "vendor_id\t: AuthenticAMD\n"
                "model name\t: AMD Ryzen 7 7800X3D\n"
            )
        raise FileNotFoundError

    monkeypatch.setattr(hardware_identity.Path, "read_text", fake_read_text)
    cpu = hardware_identity.detect_cpu_identity()
    assert cpu is not None
    assert cpu.vendor_name == "AMD"
    assert cpu.vendor_id == "AuthenticAMD"
    assert cpu.model_name == "AMD Ryzen 7 7800X3D"


def test_discover_drm_gpu_identities_maps_amd_vendor(monkeypatch) -> None:
    def fake_glob(self: Path, pattern: str):
        if str(self) == "/sys/class/drm" and pattern == "card[0-9]*":
            return [Path("/sys/class/drm/card1"), Path("/sys/class/drm/card0")]
        return []

    values = {
        "/sys/class/drm/card0/device/vendor": "0x1002\n",
        "/sys/class/drm/card0/device/device": "0x744c\n",
        "/sys/class/drm/card1/device/vendor": "0x10de\n",
        "/sys/class/drm/card1/device/device": "0x2704\n",
    }

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        value = values.get(str(self))
        if value is None:
            raise FileNotFoundError
        return value

    monkeypatch.setattr(hardware_identity.Path, "glob", fake_glob)
    monkeypatch.setattr(hardware_identity.Path, "read_text", fake_read_text)

    identities = hardware_identity.discover_drm_gpu_identities()
    assert [item.card for item in identities] == ["card0", "card1"]
    assert identities[0].vendor_name == "AMD"
    assert identities[0].device_id == "0x744c"
    assert identities[1].vendor_name == "NVIDIA"


def test_has_nvidia_device_nodes_checks_expected_paths(monkeypatch) -> None:
    def fake_exists(self: Path) -> bool:
        return str(self) == "/dev/nvidiactl"

    monkeypatch.setattr(hardware_identity.Path, "exists", fake_exists)
    assert hardware_identity.has_nvidia_device_nodes() is True
