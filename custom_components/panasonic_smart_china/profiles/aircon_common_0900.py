"""Panasonic Smart China AirconCommon 2024 new-protocol profile."""

from __future__ import annotations

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACMode,
)

from ..models import (
    ENTITY_KIND_DUCTED_AC,
    PLATFORM_CLIMATE,
    PROTOCOL_AC_STATUS,
    PanasonicEndpoint,
    PanasonicProfile,
)
from .ducted_ac_0900 import FAN_MAX, FAN_MIN, SAFE_STATUS_KEYS


AIRCON_COMMON_0900_PROFILE = PanasonicProfile(
    profile_id="aircon_common_0900",
    controller_model="AirconCommon-2024-01",
    name="Panasonic AirconCommon 2024 new protocol",
    category_ids=frozenset({"0900"}),
    model_ids=frozenset({"AirconCommon-2024-01"}),
    ha_platforms=(PLATFORM_CLIMATE,),
    entity_kind=ENTITY_KIND_DUCTED_AC,
    protocol=PROTOCOL_AC_STATUS,
    status_endpoint=PanasonicEndpoint(
        path="ACDevGetStatusInfoAW",
        request_id=100,
        require_results=True,
        required_result_keys=frozenset({"runStatus"}),
    ),
    set_endpoint=PanasonicEndpoint(
        path="ACDevSetStatusNewProtocol",
        request_id=200,
        require_results=False,
    ),
    temp_scale=1,
    power_on_value=48,
    power_off_value=49,
    default_hvac_mode=HVACMode.COOL,
    hvac_mapping={
        HVACMode.COOL: 66,
        HVACMode.HEAT: 67,
        HVACMode.DRY: 68,
        HVACMode.AUTO: 66,
    },
    fan_mapping={
        FAN_AUTO: 65,
        FAN_MIN: 49,
        FAN_LOW: 50,
        FAN_MEDIUM: 52,
        FAN_HIGH: 54,
        FAN_MAX: 55,
    },
    safe_status_keys=SAFE_STATUS_KEYS,
)
