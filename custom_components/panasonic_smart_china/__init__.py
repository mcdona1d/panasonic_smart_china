import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import PanasonicApiClient
from .const import CONF_SSID, CONF_USR_ID, CONF_USERNAME, DOMAIN
from .profiles import supported_platforms

_LOGGER = logging.getLogger(__name__)

PLATFORMS = list(supported_platforms())


def _async_create_hub_device(hass: HomeAssistant, entry: ConfigEntry):
    """Create the account-level hub device referenced by child via_device."""
    usr_id = entry.data.get(CONF_USR_ID)
    if not usr_id:
        _LOGGER.warning("No usrId in entry data; cannot create hub device")
        return
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, usr_id)},
        name=f"Panasonic Smart China ({entry.data.get(CONF_USERNAME, usr_id)})",
        manufacturer="Panasonic",
        model="Smart China",
    )


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": PanasonicApiClient(hass, entry.data.get(CONF_SSID)),
    }

    # Create the hub device BEFORE platforms are loaded so that child
    # entities' via_device reference resolves to an existing device.
    _async_create_hub_device(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
