"""Device token helpers for Panasonic Smart China.

deviceId format is MAC_CATEGORY_SUFFIX. Only the MAC and category segments may be
upper-cased; the suffix must keep its original case, otherwise devices whose suffix
contains letters (e.g. a fridge suffix "Fridge-55") produce an invalid control token.
"""

from __future__ import annotations

import hashlib


class DeviceTokenError(ValueError):
    """Raised when a Panasonic device token cannot be generated."""


def generate_device_token(device_id: str) -> str:
    """Generate the device control token from a Panasonic device id.

    deviceId 格式: MAC_CATEGORY_SUFFIX
    stoken = MAC后6位 _ CATEGORY _ MAC前6位
    token  = sha512( sha512(stoken) _ SUFFIX )
    其中 SUFFIX 使用原始大小写。
    """
    parts = device_id.split("_", 2)
    if len(parts) < 3:
        raise DeviceTokenError(
            f"Invalid deviceId format: {device_id} (expected MAC_CATEGORY_SUFFIX)"
        )

    mac_part_raw, category_raw, suffix = parts
    mac_part = mac_part_raw.upper()
    category = category_raw.upper()

    if len(mac_part) < 6:
        raise DeviceTokenError(f"Invalid MAC part in deviceId: {device_id}")

    stoken = f"{mac_part[6:]}_{category}_{mac_part[:6]}"
    inner = hashlib.sha512(stoken.encode()).hexdigest()
    return hashlib.sha512(f"{inner}_{suffix}".encode()).hexdigest()
