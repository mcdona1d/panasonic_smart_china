"""Shared device model definitions for Panasonic Smart China."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PLATFORM_CLIMATE = "climate"
PLATFORM_HUMIDIFIER = "humidifier"
PLATFORM_SWITCH = "switch"
PLATFORM_SENSOR = "sensor"
PLATFORM_SELECT = "select"

ENTITY_KIND_DUCTED_AC = "ducted_ac"
ENTITY_KIND_BATHROOM_HEATER = "bathroom_heater"
ENTITY_KIND_HUMIDIFIER = "humidifier"
ENTITY_KIND_HUMIDIFIER_SWITCH = "humidifier_switch"
ENTITY_KIND_HUMIDIFIER_SENSOR = "humidifier_sensor"
ENTITY_KIND_HUMIDIFIER_SELECT = "humidifier_select"

PROTOCOL_AC_STATUS = "ac_status"
PROTOCOL_BATHROOM_HEATER = "bathroom_heater"
PROTOCOL_AIRCLE_RUNNING_MODE = "aircle_running_mode"

TOKEN_STRATEGY_DEVICE_ID_SHA512 = "device_id_sha512"


@dataclass(frozen=True)
class PanasonicEndpoint:
    """Description of a Panasonic cloud control endpoint."""

    path: str
    request_id: int
    require_results: bool
    required_result_keys: frozenset[str] = frozenset()
    allow_non_json_response: bool = False
    # 部分设备族（如 Humi 系列）要求 usrId/deviceId/token 全部放在 params 里
    nested_params: bool = False


@dataclass(frozen=True)
class PanasonicProfile:
    """Capability and protocol description for a supported device family."""

    profile_id: str
    controller_model: str
    name: str
    category_ids: frozenset[str]
    ha_platforms: tuple[str, ...]
    entity_kind: str
    protocol: str
    status_endpoint: PanasonicEndpoint
    set_endpoint: PanasonicEndpoint
    model_ids: frozenset[str] = frozenset()
    token_strategy: str = TOKEN_STRATEGY_DEVICE_ID_SHA512
    temp_scale: int = 1
    default_hvac_mode: Any | None = None
    hvac_mapping: dict[Any, int] = field(default_factory=dict)
    fan_mapping: dict[str, int] = field(default_factory=dict)
    fan_payload_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    safe_status_keys: frozenset[str] = frozenset()
    cookie_required: bool = False
    referer_template: str | None = None
    extra_control_headers: dict[str, str] = field(default_factory=dict)

    def matches_category(self, category_id: str | None) -> bool:
        """Return whether this profile supports a Panasonic category id."""
        return bool(category_id and category_id in self.category_ids)

    def matches_device(
        self,
        category_id: str | None,
        model_values: set[str] | frozenset[str] | None = None,
    ) -> bool:
        """Return whether this profile supports a concrete cloud device."""
        if not self.matches_category(category_id):
            return False
        if not self.model_ids:
            return True
        normalized_models = {
            value.strip().upper()
            for value in (model_values or set())
            if value and value.strip()
        }
        supported_models = {value.upper() for value in self.model_ids}
        return bool(normalized_models & supported_models)
