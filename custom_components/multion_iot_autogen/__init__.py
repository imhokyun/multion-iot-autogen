import logging
import json
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import yaml
import os
import shutil


_LOGGER = logging.getLogger(__name__)

DOMAIN = "multion_iot_autogen"

def setup(hass: HomeAssistant, config: dict):
    def init_blueprint():
        module_path = os.path.dirname(__file__)  # 현재 모듈의 디렉토리 경로
        source_path = os.path.join(module_path, "blueprints/automation/multi-on")
        target_path = hass.config.path("blueprints/automation/multi-on")

        # 타겟 디렉토리 확인 및 생성
        if not os.path.exists(target_path):
            os.makedirs(target_path)

        # 파일 목록 확인 및 복사
        blueprint_files = ['ac_switch.yaml', 'pico_pc_switch.yaml', 'sw_pc_switch.yaml', 'sync_2_switch.yaml']
        for file_name in blueprint_files:
            source_file = os.path.join(source_path, file_name)
            target_file = os.path.join(target_path, file_name)

            if os.path.exists(source_file):
                # 파일을 타겟 경로로 복사
                shutil.copy2(source_file, target_file)  
            else:
                print(f"Warning: {file_name} not found in {source_path}")
    
    def get_entity():
        # Home Assistant에서 모든 엔티티 가져오기
        all_entities = hass.states.async_all()
        
        # 필터링된 엔티티 리스트 생성
        filtered_entities = [
            {
                'entity_id': entity.entity_id,
                'friendly_name': entity.attributes.get('friendly_name', entity.entity_id)
            }
            for entity in all_entities
            if entity.entity_id.startswith(('switch.', 'climate.', 'button.', 'light.'))
        ]

        return filtered_entities

    def create_automations():
        init_blueprint()
        data = get_entity()

        st_entities, non_st_entities, friendly_names, checker_ids = {}, {}, {}, {}

        for item in data:
            friendly_names[item['entity_id']] = item['friendly_name']
            if " st" in item['friendly_name'].lower():
                base_name = item['friendly_name'].lower().replace(" st", "")
                st_entities[base_name] = item['entity_id']
            elif "상태확인" in item['friendly_name'].lower():
                checker_base_name = item['friendly_name'].lower().replace(" 상태확인 st", "")
                checker_ids[checker_base_name] = item['entity_id']
            else:
                non_st_entities[item['friendly_name']] = item['entity_id']
        
        automations = []

        for base_name, st_entity in st_entities.items():
            friendly_name = friendly_names[st_entity].lower().replace(" st", "")
            action_entity = non_st_entities.get(base_name)
            checker_entity = checker_ids.get(base_name)

            if "볼공급기" in base_name or "상시" in base_name or "등" in base_name:
                if action_entity:
                    automations.append(create_sync_switch_bp(st_entity, action_entity))
                    
            elif "1회 열기" in base_name:
                if action_entity:
                    automations.append(instant_door_open(st_entity, action_entity, friendly_name))

            elif "냉난방기" in base_name:
                if action_entity and checker_entity:
                    automations.append(create_sync_climate_bp(st_entity, action_entity, checker_entity))

            elif "PC" in base_name:
                # Assumption: There's some distinguishing feature or naming convention in friendly names
                if "PC" in friendly_name:
                    pc_entities = [st_entity] + [eid for name, eid in non_st_entities.items() if base_name in name]
                    if len(pc_entities) == 3:
                        # Assuming first is ST, second is WOL, third is Off Button
                            # PC control type 2 : ex) "룸1 PC ST" 스위치, "룸1 PC 켜기" 스위치, "룸1 PC 끄기" 버튼 => create_sw_pc_switch_bp 이용
                        automations.append(create_sw_pc_switch_bp(*pc_entities))
                    elif len(pc_entities) == 2:
                        # Assuming first is ST, second is button or sensor based on availability
                        if checker_entity:
                            # PC control type 3 : ex) "룸1 PC ST" 스위치, "룸1 PC 버튼" 버튼, "룸1 PC 상태" binary_sensor => create_pico_pc_switch_bp 이용
                            automations.append(create_pico_pc_switch_bp(st_entity, pc_entities[1], checker_entity))
                        else:
                            # PC control type 1 : ex) "룸1 PC ST", "룸1 PC" 2개 스위치 => create_sync_switch_bp 이용
                            automations.append(create_sync_switch_bp(st_entity, pc_entities[1]))

        with open('/config/automations.yaml', 'w') as file:
            yaml.dump(automations, file, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)

        _LOGGER.info("Automations created and saved to automations.yaml")
    
    def create_sync_switch_bp(trigger_id, action_id):
        return {
            "id": generate_random_id(),
            "alias": f"{action_id} 연동",
            "description": "ST 스위치와 실제 스위치 기기 연동",
            "use_blueprint": {
                "path": "multi-on/sync_2_switch.yaml",
                "input": {
                    "entity_one": trigger_id,
                    "entity_two": action_id
                }
            }
        }
    
    def create_sync_climate_bp(trigger_id, action_id, checker_id):
        return {
            "id": generate_random_id(),
            "alias": f"{action_id} 연동",
            "description": "ST 스위치와 냉난방기 제어 기기 연동",
            "use_blueprint": {
                "path": "multi-on/ac_switch.yaml",
                "input": {
                    "main_st_switch": trigger_id,
                    "status_check_st_switch": action_id,
                    "climate_entity": checker_id
                }
            }
        }
    
    def create_sw_pc_switch_bp(trigger_id, action_id, button_id):
        return {
            "id": generate_random_id(),
            "alias": f"{action_id} 연동",
            "description": "ST 스위치와 SW타입 PC연동",
            "use_blueprint": {
                "path": "multi-on/sw_pc_switch.yaml",
                "input": {
                    "pc_st_switch:": trigger_id,
                    "wol_switch": action_id,
                    "pc_off_button": button_id
                }
            }
        }
    
    def create_pico_pc_switch_bp(trigger_id, action_id, status_id):
        return {
            "id": generate_random_id(),
            "alias": f"{action_id} 연동",
            "description": "ST 스위치와 SW타입 PC연동",
            "use_blueprint": {
                "path": "multi-on/sw_pc_switch.yaml",
                "input": {
                    "pc_st_switch:": trigger_id,
                    "pc_status_sensor": status_id,
                    "pc_button": action_id
                }
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

    hass.services.register(DOMAIN, 'create_automations', lambda service: create_automations())


    # Load platforms
    discovery.load_platform(hass, 'switch', DOMAIN, {}, config)

    return True
