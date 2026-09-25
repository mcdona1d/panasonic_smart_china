import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import PanasonicApiClient
from .const import CONF_SSID, CONF_USR_ID, DOMAIN
from .profiles import supported_platforms

_LOGGER = logging.getLogger(__name__)

PLATFORMS = list(supported_platforms())


def _async_create_account_device(
    hass: HomeAssistant, entry: ConfigEntry
) -> str | None:
    """Create the account service device and return its registry id."""
    account_id = entry.unique_id or entry.data.get(CONF_USR_ID)
    if not account_id:
        _LOGGER.warning("No account id available; account device was not created")
        return None

    account_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(account_id))},
        name=entry.title,
        manufacturer="Panasonic",
        model="Smart China",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    return account_device.id


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    # Register the account before forwarding platforms so every appliance can
    # reference an existing parent by its device-registry id.
    account_device_id = _async_create_account_device(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = {
        "client": PanasonicApiClient(hass, entry.data.get(CONF_SSID)),
        "account_device_id": account_device_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
