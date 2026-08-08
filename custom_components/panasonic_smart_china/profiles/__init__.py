"""Device profile registry."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import PanasonicProfile
from .aircon_common_0900 import AIRCON_COMMON_0900_PROFILE
from .bathroom_heater_0820_fv_rb20vl1 import (
    BATHROOM_HEATER_0820_FV_RB20VL1_PROFILE,
)
from .ducted_ac_0900 import DUCTED_AC_0900_PROFILE

SUPPORTED_PROFILES = {
    AIRCON_COMMON_0900_PROFILE.profile_id: AIRCON_COMMON_0900_PROFILE,
    DUCTED_AC_0900_PROFILE.profile_id: DUCTED_AC_0900_PROFILE,
    BATHROOM_HEATER_0820_FV_RB20VL1_PROFILE.profile_id: (
        BATHROOM_HEATER_0820_FV_RB20VL1_PROFILE
    ),
}

SUPPORTED_CONTROLLERS = {
    profile.controller_model: profile
    for profile in SUPPORTED_PROFILES.values()
}


def iter_supported_profiles() -> Iterable[PanasonicProfile]:
    """Iterate over all registered verified profiles."""
    return SUPPORTED_PROFILES.values()


def supported_platforms() -> tuple[str, ...]:
    """Return Home Assistant platforms needed by registered profiles."""
    platforms = {
        platform
        for profile in SUPPORTED_PROFILES.values()
        for platform in profile.ha_platforms
    }
    return tuple(sorted(platforms))


def find_profile(profile_id: str | None) -> PanasonicProfile | None:
    """Find a profile by profile id."""
    if not profile_id:
        return None
    return SUPPORTED_PROFILES.get(profile_id)


def find_profile_for_controller(controller_model: str | None) -> PanasonicProfile | None:
    """Find a profile by controller/model key stored in config entries."""
    if not controller_model:
        return None
    return SUPPORTED_CONTROLLERS.get(controller_model)


def find_profiles_for_category(category_id: str | None) -> dict[str, PanasonicProfile]:
    """Find verified profiles for a Panasonic category id."""
    if not category_id:
        return {}
    return {
        key: profile
        for key, profile in SUPPORTED_PROFILES.items()
        if profile.matches_category(category_id)
    }


def find_profiles_for_device(
    category_id: str | None,
    model_values: set[str] | frozenset[str] | None = None,
) -> dict[str, PanasonicProfile]:
    """Find verified profiles for a concrete Panasonic cloud device."""
    if not category_id:
        return {}
    model_specific_matches = {
        key: profile
        for key, profile in SUPPORTED_PROFILES.items()
        if profile.model_ids and profile.matches_device(category_id, model_values)
    }
    if model_specific_matches:
        return model_specific_matches

    return {
        key: profile
        for key, profile in SUPPORTED_PROFILES.items()
        if not profile.model_ids and profile.matches_device(category_id, model_values)
    }


def find_profile_for_device_config(
    *,
    profile_id: str | None = None,
    controller_model: str | None = None,
    category_id: str | None = None,
) -> PanasonicProfile | None:
    """Resolve a configured device to a profile with tolerant fallbacks."""
    profile = find_profile(profile_id)
    if profile:
        return profile

    profile = find_profile_for_controller(controller_model)
    if profile:
        return profile

    category_matches = {
        key: candidate
        for key, candidate in find_profiles_for_category(category_id).items()
        if not candidate.model_ids
    }
    if len(category_matches) == 1:
        return next(iter(category_matches.values()))

    return None
