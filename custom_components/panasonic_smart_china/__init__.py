import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN, CONF_USR_ID, CONF_DEVICE_ID, CONF_TOKEN, 
    CONF_SSID, CONF_SENSOR_ID, CONF_CONTROLLER_MODEL,
    CONF_FAMILY_ID, CONF_REAL_FAMILY_ID, CONF_DEVICES,
    CONF_USERNAME
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Panasonic Smart China from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store configuration for reference
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old version 1 config entries to account-based version 2."""
    _LOGGER.debug("Migrating configuration from version %s", config_entry.version)

    if config_entry.version == 1:
        usr_id = config_entry.data.get(CONF_USR_ID)
        if not usr_id:
            return False

        # Find all v1 entries for this user
        all_entries = hass.config_entries.async_entries(DOMAIN)
        same_user_entries = [e for e in all_entries if e.data.get(CONF_USR_ID) == usr_id and e.version == 1]
        
        if not same_user_entries:
            return False

        # If this is not the first entry of this user, it will be deleted by the migration of the first entry
        if config_entry.entry_id != same_user_entries[0].entry_id:
            return True

        merged_devices = {}
        base_data = None

        for e in same_user_entries:
            did = e.data.get(CONF_DEVICE_ID)
            if not did: continue
            
            merged_devices[did] = {
                "deviceName": e.title if e.title else "Panasonic Device",
                CONF_CONTROLLER_MODEL: e.data.get(CONF_CONTROLLER_MODEL, "CZ-RD501DW2"),
                CONF_SENSOR_ID: e.data.get(CONF_SENSOR_ID),
                CONF_TOKEN: e.data.get(CONF_TOKEN)
            }
            if not base_data:
                base_data = {
                    CONF_USERNAME: e.data.get(CONF_USERNAME, ""),
                    CONF_USR_ID: usr_id,
                    CONF_SSID: e.data.get(CONF_SSID),
                    CONF_FAMILY_ID: e.data.get(CONF_FAMILY_ID),
                    CONF_REAL_FAMILY_ID: e.data.get(CONF_REAL_FAMILY_ID),
                }
        
        if not base_data:
             return False

        new_data = {**base_data, CONF_DEVICES: merged_devices}
        
        # Update first entry and migrate it to version 2
        hass.config_entries.async_update_entry(
            config_entry, 
            title=f"Panasonic Account ({usr_id})", 
            data=new_data, 
            version=2
        )

        # Remove other entries (async to avoid modifying list during iteration)
        for e in same_user_entries:
            if e.entry_id != config_entry.entry_id:
                _LOGGER.info("Removing redundant entry %s for user %s during migration", e.entry_id, usr_id)
                hass.async_create_task(hass.config_entries.async_remove(e.entry_id))

        _LOGGER.info("Successfully migrated Panasonic integrated account %s with %s devices", usr_id, len(merged_devices))
        return True

    return True