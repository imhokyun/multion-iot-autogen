import logging
import json
import os
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import yaml

_LOGGER = logging.getLogger(__name__)

DOMAIN = "multion_iot_autogen"

def setup(hass: HomeAssistant, config: dict):
    def get_entity():
        # Home Assistant에서 모든 엔티티 가져오기
        all_entities = hass.states.async_all()
        
        filtered_entities = [
            {
                'entity_id': entity.entity_id,
                'friendly_name': entity.attributes.get('friendly_name', entity.entity_id)
            }
            for entity in all_entities
            if entity.entity_id.startswith(('switch.', 'climate.', 'button.', 'light.'))
        ]

        with open('/config/custom_components/multion_iot_autogen/device_list.json', 'w', encoding='utf-8') as file:
            json.dump(filtered_entities, file, ensure_ascii=False, indent=4)
        _LOGGER.info("Filtered device data saved to device_list.json")

    def create_automations():
        with open('/config/custom_components/multion_iot_autogen/device_list.json', 'r') as d:
            data = json.load(d)

        st_entities, non_st_entities, friendly_names = {}, {}, {}

        for item in data:
            friendly_names[item['entity_id']] = item['friendly_name']
            if " st" in item['friendly_name'].lower():
                base_name = item['friendly_name'].lower().replace(" st", "")
                st_entities[base_name] = item['entity_id']
            else:
                non_st_entities[item['friendly_name']] = item['entity_id']

        automations = []

        for base_name, trigger_id in st_entities.items():
            friendly_name = friendly_names[trigger_id].lower().replace(" st", "")

            if "볼공급기" in base_name or "상시" in base_name:
                if base_name in non_st_entities:
                    action_id = non_st_entities[base_name]
                    automations.extend([
                        sync_switch(trigger_id, action_id, "on", friendly_name),
                        sync_switch(trigger_id, action_id, "off", friendly_name)
                    ])
            elif "1회 열기" in base_name:
                if base_name in non_st_entities:
                    action_id = non_st_entities[base_name]
                    automations.append(instant_door_open(trigger_id, action_id, friendly_name))
            elif "냉난방기" in base_name:
                if base_name in non_st_entities:
                    action_id = non_st_entities[base_name]
                    automations.extend([
                        sync_climate(trigger_id, action_id, "on", "auto", friendly_name),
                        sync_climate(trigger_id, action_id, "off", "off", friendly_name)
                    ])

        room_entities = {}
        for item in data:
            room_number = item['friendly_name'].split()[0]
            if room_number not in room_entities:
                room_entities[room_number] = {}
            if '켜기' in item['friendly_name']:
                room_entities[room_number]['switch_on'] = item['entity_id']
            elif '끄기' in item['friendly_name']:
                room_entities[room_number]['button_off'] = item['entity_id']
            elif 'st' in item['entity_id']:
                room_entities[room_number]['st'] = item['entity_id']

        for room, entities in room_entities.items():
            if all(key in entities for key in ('st', 'switch_on', 'button_off')):
                automations.extend(create_pc_automations(entities['st'], entities['switch_on'], entities['button_off'], room))


        with open('/config/custom_components/multion_iot_autogen/automations.yaml', 'w') as file:
            yaml.dump(automations, file, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)
        
        with open('/config/automations.yaml', 'w') as file:
            yaml.dump(automations, file, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)

        # automations_path = os.path.join(hass.config.path(), 'automations.yaml')
        # with open(automations_path, 'w') as file:
        #     yaml.dump(automations, file, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)

        _LOGGER.info("Automations created and saved to automations.yaml")

    def sync_switch(trigger_entity, action_entity, trigger_state, friendly_name):
        return {
            "id": generate_random_id(),
            "alias": f'{friendly_name} {trigger_state}',
            "description": "",
            "mode": "single",
            "trigger": [{
                "platform": "state",
                "entity_id": trigger_entity,
                "to": trigger_state
            }],
            "condition": [],
            "action": [{
                "service": f"switch.turn_{trigger_state}",
                "target": {
                    "entity_id": action_entity
                }
            }]
        }

    def sync_climate(trigger_entity, action_entity, trigger_state, action_state, friendly_name):
        return {
            "id": generate_random_id(),
            "alias": f'{friendly_name} {action_state}',
            "description": "",
            "mode": "single",
            "trigger": [{
                "platform": "state",
                "entity_id": trigger_entity,
                "to": trigger_state
            }],
            "condition": [],
            "action": [{
                "service": "climate.set_hvac_mode",
                "data": {
                    "hvac_mode": action_state
                },
                "target": {
                    "entity_id": action_entity
                }
            }]
        }

    def instant_door_open(trigger_entity, action_entity, friendly_name):
        return {
            "id": generate_random_id(),
            "alias": friendly_name,
            "description": "",
            "mode": "single",
            "trigger": [{
                "platform": "state",
                "entity_id": trigger_entity,
                "to": "on"
            }],
            "condition": [],
            "action": [
                {"service": "switch.turn_on", "target": {"entity_id": action_entity}},
                {"service": "switch.turn_off", "target": {"entity_id": trigger_entity}},
                {"delay": {"hours": 0, "minutes": 0, "seconds": 7, "milliseconds": 0}},
                {"service": "switch.turn_off", "target": {"entity_id": action_entity}},
                {"service": "switch.turn_off", "target": {"entity_id": trigger_entity}}
            ]
        }

    def create_pc_automations(st_entity_id, switch_on_entity_id, button_off_entity_id, friendly_name):
        return [
            {
                "id": generate_random_id(),
                "alias": f"{friendly_name} pc 켜기",
                "description": "Turns on the PC.",
                "mode": "single",
                "trigger": [{"platform": "state", "entity_id": st_entity_id, "to": "on"}],
                "action": [{"service": "switch.turn_on", "target": {"entity_id": switch_on_entity_id}}]
            },
            {
                "id": generate_random_id(),
                "alias": f"{friendly_name} pc 끄기",
                "description": "Turns off the PC.",
                "mode": "single",
                "trigger": [{"platform": "state", "entity_id": st_entity_id, "to": "off"}],
                "action": [{"service": "button.press", "target": {"entity_id": button_off_entity_id}}]
            }
        ]

    def generate_random_id(length=10):
        import random
        import string
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

        
    # Register services
    hass.services.register(DOMAIN, 'get_entities', lambda service: get_entity())
    hass.services.register(DOMAIN, 'create_automations', lambda service: create_automations())


    # Load platforms
    discovery.load_platform(hass, 'button', DOMAIN, {}, config)

    return True
