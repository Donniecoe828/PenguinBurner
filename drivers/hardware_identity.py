from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_NVIDIA_VENDOR_ID = "0x10de"

_VENDOR_NAMES = {
    "0x1002": "AMD",
    "0x10de": "NVIDIA",
    "0x8086": "Intel",
}


@dataclass(frozen=True, slots=True)
class DrmGpuIdentity:
    card: str
    vendor_id: str
    vendor_name: str
    device_id: str = ""


@dataclass(frozen=True, slots=True)
class CpuIdentity:
    vendor_id: str
    vendor_name: str
    model_name: str = ""


def has_nvidia_device_nodes() -> bool:
    return Path("/dev/nvidia0").exists() or Path("/dev/nvidiactl").exists()


def discover_drm_gpu_identities() -> list[DrmGpuIdentity]:
    cards = sorted(Path("/sys/class/drm").glob("card[0-9]*"), key=lambda path: path.name)
    identities: list[DrmGpuIdentity] = []
    for card in cards:
        vendor_id = _read_text(card / "device" / "vendor").lower()
        if not vendor_id:
            continue
        identities.append(
            DrmGpuIdentity(
                card=card.name,
                vendor_id=vendor_id,
                vendor_name=_VENDOR_NAMES.get(vendor_id, f"PCI {vendor_id}"),
                device_id=_read_text(card / "device" / "device"),
            )
        )
    return identities


def detect_cpu_identity() -> CpuIdentity | None:
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    vendor_id = ""
    model_name = ""
    for line in cpuinfo.splitlines():
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key == "vendor_id" and not vendor_id:
            vendor_id = value.strip()
        elif key == "model name" and not model_name:
            model_name = value.strip()
        if vendor_id and model_name:
            break
    if not vendor_id and not model_name:
        return None
    vendor_name = _cpu_vendor_name(vendor_id, model_name)
    return CpuIdentity(
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        model_name=model_name,
    )


def _cpu_vendor_name(vendor_id: str, model_name: str) -> str:
    cleaned_vendor = str(vendor_id or "").strip()
    model = str(model_name or "").strip()
    if cleaned_vendor == "AuthenticAMD" or "amd" in model.casefold():
        return "AMD"
    if cleaned_vendor == "GenuineIntel" or "intel" in model.casefold():
        return "Intel"
    return cleaned_vendor or "Unknown"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
