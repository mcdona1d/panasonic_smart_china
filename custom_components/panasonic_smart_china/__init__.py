import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]

async def async_setup(hass: HomeAssistant, config: dict):
    # 初始化全局数据存储，用于缓存 Session
    hass.data.setdefault(DOMAIN, {
        "session": None  # 结构: {'usrId': ..., 'ssid': ..., 'devices': ...}
    })
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # 确保存储存在
    hass.data.setdefault(DOMAIN, {"session": None})
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok