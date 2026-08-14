"""Device token helpers for Panasonic Smart China."""

from __future__ import annotations

import hashlib


class DeviceTokenError(ValueError):
    """Raised when a Panasonic device token cannot be generated."""


def generate_device_token(device_id: str) -> str:
    """Generate the device control token from a Panasonic device id.

    NOTE: the suffix (equipType, e.g. "Aircle-05-02") is CASE-SENSITIVE and
    must keep its original case. The server computes the expected token from
    the exact deviceId casing (see official web app js/common/common.js:
    equipType = deviceId.split('_0820_')[1] — no upper() applied).
    Uppercasing the suffix produces "token校验错误" (error 400).
    """
    parts = device_id.split("_", 2)
    if len(parts) < 3:
        raise DeviceTokenError(
            f"Invalid deviceId format: {device_id} (expected MAC_CATEGORY_SUFFIX)"
        )

    mac_part, category, suffix = parts
    mac_part = mac_part.upper()
    category = category.upper()
    # suffix intentionally keeps its original case

    if len(mac_part) < 6:
        raise DeviceTokenError(f"Invalid MAC part in deviceId: {device_id}")

    stoken = f"{mac_part[6:]}_{category}_{mac_part[:6]}"
    inner = hashlib.sha512(stoken.encode()).hexdigest()
    return hashlib.sha512(f"{inner}_{suffix}".encode()).hexdigest()
