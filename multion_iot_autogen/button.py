import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "multion_iot_autogen"

def setup_platform(hass, config, add_entities, discovery_info=None):
    add_entities([MyComponentButton(hass)])

class MyComponentButton(ButtonEntity):
    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Multion IoT Autogen"
        self._attr_unique_id = "multion_iot_autogen"

    def press(self):
        self._hass.services.call(DOMAIN, 'get_entities')
        self._hass.services.call(DOMAIN, 'create_automations')

