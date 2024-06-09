import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DOMAIN = "multion_iot_autogen"

def setup_platform(hass, config, add_entities, discovery_info=None):
    add_entities([MyComponentSwitch(hass)])

class MyComponentSwitch(SwitchEntity):
    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Multi-on Auto-gen"
        self._attr_unique_id = "multion_iot_autogen_switch"
        self._is_on = False

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        # Start the automation tasks
        await self._hass.services.async_call(DOMAIN, 'create_automations', {})
        await self._hass.services.async_call('automation', 'reload', {})

        await self._hass.services.async_call('persistent_notification', 'create', {
            'message': '자동화가 정상적으로 추가되었습니다.',
            'title': 'Multi-on Automation Complete'
        })

        # Automatically turn off the switch
        await self.async_turn_off()

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        await self.async_update_ha_state()

    @callback
    def async_update(self):
        self.async_write_ha_state()

