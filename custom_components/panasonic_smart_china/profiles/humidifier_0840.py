"""Verified profile for Panasonic Smart China 0840 humidifier devices."""

from __future__ import annotations

from ..models import (
    ENTITY_KIND_HUMIDIFIER,
    PLATFORM_HUMIDIFIER,
    PLATFORM_SELECT,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PROTOCOL_AIRCLE_RUNNING_MODE,
    PanasonicEndpoint,
    PanasonicProfile,
)

# FE-Z16C (deviceId 9C1221D225B3_0840_Aircle-17-05) 实测结论：
#   * 云接口族后缀是 "Humi"，而不是 VXR110C；
#   * usrId / deviceId / token 必须放进请求体的 params 里（顶层会返回 -1）；
#   * 参数名来自官方 App 4.99.0 运行时内存中真实的请求 / 响应报文。
HUMIDIFIER_0840_PROFILE = PanasonicProfile(
    profile_id="humidifier_0840_aircle",
    controller_model="FE-Z16C",
    name="松下加湿器 (FE-Z16C)",
    category_ids=frozenset({"0840"}),
    model_ids=frozenset({"FE-Z16C", "Aircle-17-05"}),
    ha_platforms=(
        PLATFORM_HUMIDIFIER,
        PLATFORM_SWITCH,
        PLATFORM_SENSOR,
        PLATFORM_SELECT,
    ),
    entity_kind=ENTITY_KIND_HUMIDIFIER,
    protocol=PROTOCOL_AIRCLE_RUNNING_MODE,
    status_endpoint=PanasonicEndpoint(
        path="ADevGetStatusHumi",
        request_id=1065,
        require_results=True,
        required_result_keys=frozenset({"runSta"}),
        nested_params=True,
    ),
    set_endpoint=PanasonicEndpoint(
        path="ADevSetStatusHumi",
        request_id=2001,
        require_results=False,
        allow_non_json_response=True,
        nested_params=True,
    ),
    cookie_required=True,
)
