"""Shared device model definitions for Panasonic Smart China."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PLATFORM_CLIMATE = "climate"
PLATFORM_SENSOR = "sensor"
PLATFORM_SWITCH = "switch"
PLATFORM_NUMBER = "number"
PLATFORM_SELECT = "select"

ENTITY_KIND_DUCTED_AC = "ducted_ac"
ENTITY_KIND_BATHROOM_HEATER = "bathroom_heater"
ENTITY_KIND_WASHER = "washer"
ENTITY_KIND_DRYER = "dryer"
ENTITY_KIND_FRIDGE = "fridge"
ENTITY_KIND_KNOB = "knob"

PROTOCOL_AC_STATUS = "ac_status"
PROTOCOL_BATHROOM_HEATER = "bathroom_heater"
PROTOCOL_GENERIC_STATUS = "generic_status"

TOKEN_STRATEGY_DEVICE_ID_SHA512 = "device_id_sha512"


@dataclass(frozen=True)
class PanasonicEndpoint:
    """Description of a Panasonic cloud control endpoint."""

    path: str
    request_id: int
    require_results: bool
    required_result_keys: frozenset[str] = frozenset()
    allow_non_json_response: bool = False


@dataclass(frozen=True)
class PanasonicSensorDescription:
    """描述一个要暴露成 HA sensor 的状态字段。"""

    key: str
    source_key: str
    name: str
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    value_map: dict = field(default_factory=dict)
    scale: float | None = None


@dataclass(frozen=True)
class PanasonicSwitchDescription:
    """描述一个 HA switch（洗衣机电源/开始暂停、冰箱布尔开关、旋钮找一找）。"""

    key: str
    name: str
    state_key: str
    state_on: frozenset = frozenset({1})
    on_change: dict = field(default_factory=dict)
    off_change: dict = field(default_factory=dict)
    require_door_closed: bool = False


@dataclass(frozen=True)
class PanasonicNumberDescription:
    """描述一个 HA number（如冰箱各温区目标温度）。"""

    key: str
    source_key: str
    name: str
    min_value: float = 0
    max_value: float = 100
    step: float = 1
    unit: str | None = None
    device_class: str | None = None


@dataclass(frozen=True)
class PanasonicSelectDescription:
    """描述一个 HA select（如洗衣机/烘干机程序选择）。"""

    key: str
    source_key: str
    name: str
    options: dict = field(default_factory=dict)


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
    sensor_descriptions: tuple[PanasonicSensorDescription, ...] = ()
    control_switches: tuple[PanasonicSwitchDescription, ...] = ()
    control_numbers: tuple[PanasonicNumberDescription, ...] = ()
    control_selects: tuple[PanasonicSelectDescription, ...] = ()

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
