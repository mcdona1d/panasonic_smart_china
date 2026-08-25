"""Verified profile for Panasonic FV-RB20VL1 bathroom heater devices."""

from __future__ import annotations

from homeassistant.components.climate.const import HVACMode

from ..models import (
    ENTITY_KIND_BATHROOM_HEATER,
    PLATFORM_CLIMATE,
    PROTOCOL_BATHROOM_HEATER,
    PanasonicEndpoint,
    PanasonicProfile,
)

HVAC_MAPPING = {
    HVACMode.OFF: 32,
    HVACMode.HEAT: 37,
    HVACMode.FAN_ONLY: 38,
    HVACMode.COOL: 40,
    HVACMode.DRY: 42,
}

BATHROOM_HEATER_0820_FV_RB20VL1_PROFILE = PanasonicProfile(
    profile_id="bathroom_heater_0820_fv_rb20vl1",
    controller_model="FV-RB20VL1",
    name="松下风暖浴霸 (FV-RB20VL1)",
    category_ids=frozenset({"0820"}),
    model_ids=frozenset({"FV-RB20VL1", "Aircle-05-02"}),
    ha_platforms=(PLATFORM_CLIMATE,),
    entity_kind=ENTITY_KIND_BATHROOM_HEATER,
    protocol=PROTOCOL_BATHROOM_HEATER,
    status_endpoint=PanasonicEndpoint(
        path="ADevGetStatusInfoFV54BA1C",
        request_id=100,
        require_results=True,
        required_result_keys=frozenset({"runningMode"}),
    ),
    set_endpoint=PanasonicEndpoint(
        path="ADevSetStatusInfoFV54BA1C",
        request_id=52,
        require_results=False,
        allow_non_json_response=True,
    ),
    default_hvac_mode=HVACMode.FAN_ONLY,
    hvac_mapping=HVAC_MAPPING,
    cookie_required=True,
    referer_template=(
        "https://app.psmartcloud.com/ca/cn/0820/RB20VL1/index.html"
        "?deviceId={device_id}&devType=FV-RB20VL1"
    ),
)
