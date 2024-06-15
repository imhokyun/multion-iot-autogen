import logging
import json
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import yaml
import os
import shutil

_LOGGER = logging.getLogger(__name__)

DOMAIN = "multion_iot_autogen"

async def setup(hass: HomeAssistant, config: dict):
    async def init_blueprint():
        try:
            module_path = os.path.dirname(__file__)
            source_path = os.path.join(module_path, "blueprints/automation/multi-on")
            target_path = hass.config.path("blueprints/automation/multi-on")

            if not os.path.exists(target_path):
                os.makedirs(target_path)

            blueprint_files = ['ac_switch.yaml', 'pico_pc_switch.yaml', 'sw_pc_switch.yaml', 'sync_2_switch.yaml']
            for file_name in blueprint_files:
                source_file = os.path.join(source_path, file_name)
                target_file = os.path.join(target_path, file_name)

                if os.path.exists(source_file):
                    shutil.copy2(source_file, target_file)
                    _LOGGER.info(f"{file_name} copied to {target_path}")
                else:
                    _LOGGER.warning(f"{file_name} not found in {source_path}")
        except Exception as e:
            _LOGGER.error(f"Error initializing blueprints: {e}")

    async def get_entities():
        all_entities = hass.states.async_all()
        return [
            {
                'entity_id': entity.entity_id,
                'friendly_name': entity.attributes.get('friendly_name', entity.entity_id)
            }
            for entity in all_entities
            if entity.entity_id.startswith(('switch.', 'climate.', 'button.', 'light.'))
        ]

    async def create_automations():
        await init_blueprint()
        entities = await get_entities()

        st_entities = {}
        non_st_entities = {}
        friendly_names = {}
        checker_ids = {}

        for entity in entities:
            entity_id = entity['entity_id']
            friendly_name = entity['friendly_name'].lower()
            friendly_names[entity_id] = friendly_name

            if " st" in friendly_name:
                base_name = friendly_name.replace(" st", "")
                st_entities[base_name] = entity_id
            elif "상태확인" in friendly_name:
                checker_base_name = friendly_name.replace(" 상태확인 st", "")
                checker_ids[checker_base_name] = entity_id
            else:
                non_st_entities[friendly_name] = entity_id

        automations = []

        for base_name, st_entity in st_entities.items():
            action_entity = non_st_entities.get(base_name)
            checker_entity = checker_ids.get(base_name)

            if any(keyword in base_name for keyword in ["볼공급기", "상시", "등"]):
                if action_entity:
                    automations.append(create_sync_switch_bp(st_entity, action_entity))
            elif "1회 열기" in base_name:
                if action_entity:
                    automations.append(instant_door_open(st_entity, action_entity, friendly_names[st_entity]))
            elif "냉난방기" in base_name:
                if action_entity and checker_entity:
                    automations.append(create_sync_climate_bp(st_entity, action_entity, checker_entity))
            elif "PC" in base_name:
                pc_entities = [st_entity] + [eid for name, eid in non_st_entities.items() if base_name in name]
                if len(pc_entities) == 3:
                    automations.append(create_sw_pc_switch_bp(*pc_entities))
                elif len(pc_entities) == 2:
                    if checker_entity:
                        automations.append(create_pico_pc_switch_bp(st_entity, pc_entities[1], checker_entity))
                    else:
                        automations.append(create_sync_switch_bp(st_entity, pc_entities[1]))

        try:
            with open('/config/automations.yaml', 'w') as file:
                yaml.dump(automations, file, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)
            _LOGGER.info("Automations created and saved to automations.yaml")
        except Exception as e:
            _LOGGER.error(f"Failed to write automations.yaml: {e}")

    def create_sync_switch_bp(trigger_id, action_id):
        return create_blueprint("sync_2_switch.yaml", trigger_id, action_id)

    def create_sync_climate_bp(trigger_id, action_id, checker_id):
        return create_blueprint("ac_switch.yaml", trigger_id, action_id, checker_id)

    def create_sw_pc_switch_bp(trigger_id, action_id, button_id):
        return create_blueprint("sw_pc_switch.yaml", trigger_id, action_id, button_id)

    def create_pico_pc_switch_bp(trigger_id, action_id, status_id):
        return create_blueprint("pico_pc_switch.yaml", trigger_id, action_id, status_id)

    def create_blueprint(path, *args):
        inputs = ["entity_one", "entity_two", "entity_three"]
        input_data = {key: arg for key, arg in zip(inputs, args)}
        return {
            "id": generate_random_id(),
            "alias": f"{args[-1]} 연동",
            "description": "ST 스위치와 기기 연동",
            "use_blueprint": {
                "path": f"multi-on/{path}",
                "input": input_data
            }
        }
        
    def instant_door_open(trigger_entity, action_entity, friendly_name):
        return {
            "id": generate_random_id(),
            "alias": friendly_name,
            "description": "1회열기 자동화 생성",
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

    def generate_random_id(length=10):
        import random
        import string
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    hass.services.register(DOMAIN, 'create_automations', lambda service: hass.async_add_job(create_automations))

    discovery.load_platform(hass, 'switch', DOMAIN, {}, config)

    return True

