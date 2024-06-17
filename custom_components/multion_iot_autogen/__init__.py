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
            if entity.entity_id.startswith(('switch.', 'climate.', 'button.', 'light.', 'binary_sensor.'))
        ]

        # 필터링된 엔티티를 JSON 파일로 저장
        devices_list_path = os.path.join(os.path.dirname(__file__), 'devices_list.json')
        with open(devices_list_path, 'w', encoding='utf-8') as file:
            json.dump(filtered_entities, file, ensure_ascii=False, indent=4)

        return filtered_entities
    
    def pair_devices(device_list):
        stSwitch = []
        otherDevices = []
    
        for device in device_list:
            if device["friendly_name"].lower().endswith(" st"):
                # 냉난방기 끄기 예외처리
                if "냉난방기" in device["friendly_name"] and "끄기" in device["friendly_name"]:
                    otherDevices.append(device)
                # 냉난방기 끄기 스위치를 제외한 나머지 스위치는 main entity로 분류
                else:
                    stSwitch.append(device)
            else:
                otherDevices.append(device)
        # 이름이 동일한 기기들을 묶기
        paired_devices = []
        for st in stSwitch: 
            st_name = st["friendly_name"][:-3]  # " ST"를 제거
            matched_devices = [st]
            automation_name = st_name  # " ST"가 제거된 이름을 automation_name으로 사용
            for other in otherDevices:
                other_name = other["friendly_name"].replace(" ST", "")  # " ST"를 제거
                if other_name == st_name or \
                other_name == st_name + " 끄기" or \
                other_name == st_name + " WOL" or \
                other_name == st_name + " 상태":
                    matched_devices.append(other)
            if len(matched_devices) > 1:
                paired_devices.append({
                    "automation_name": automation_name,
                    "device_list": matched_devices
                })

        with open('paired_devices.json', 'w') as json_file:
            json.dump(paired_devices, json_file, ensure_ascii=False, indent=4)
        
        return paired_devices

    def create_automations():
        init_blueprint()
        device_groups = pair_devices(get_entity())

        automations = []
        created_automations = []  # 이미 생성된 자동화 이름을 저장할 리스트
        for group in device_groups:
            if group["automation_name"] not in created_automations:
                # 1회열기 연동  
                if group["automation_name"] == "1회 열기":
                    automation = instant_door_open(group["device_list"][0]["entity_id"], group["device_list"][1]["entity_id"], group["automation_name"])
                    automations.append(automation)
                    created_automations.append(group["automation_name"]) 
                # 스위치 연동(PC는 아래 로직에서 처리)
                elif any(keyword in group["automation_name"] for keyword in ["볼공급기", "등", "상시"]) and "PC" not in group["automation_name"]:
                    automation = create_sync_switch_bp(group["device_list"][0]["entity_id"], group["device_list"][1]["entity_id"], group["automation_name"])
                    automations.append(automation)
                    created_automations.append(group["automation_name"])  
                # PC 연동(3개 타입에 맞춰 연동)
                elif any(keyword in group["automation_name"] for keyword in ["PC"]):
                    # 타입1 2개 스위치
                    if len(group["device_list"]) == 2:
                        automation = create_sync_switch_bp(group["device_list"][0]["entity_id"], group["device_list"][1]["entity_id"], group["automation_name"])
                        automations.append(automation)
                        created_automations.append(group["automation_name"])  
                    elif len(group["device_list"]) == 3:
                        wol_device = next((device for device in group["device_list"] if "WOL" in device["friendly_name"]), None)
                        status_device = next((device for device in group["device_list"] if "상태" in device["friendly_name"]), None)

                    # 타입2 SW 방식 WOL + HASS.Agent
                        if wol_device:
                            automation = create_sw_pc_switch_bp(group["device_list"][0]["entity_id"], group["device_list"][1]["entity_id"], group["device_list"][2]["entity_id"], group["automation_name"])
                            automations.append(automation)
                            created_automations.append(group["automation_name"])  
                    # 타입3 PICO 이용 방식
                        elif status_device:
                            automation = create_pico_pc_switch_bp(group["device_list"][0]["entity_id"], group["device_list"][1]["entity_id"], group["device_list"][2]["entity_id"], group["automation_name"])
                            automations.append(automation)
                            created_automations.append(group["automation_name"])
                # 냉난방기 연동
                elif any(keyword in group["automation_name"] for keyword in ["냉난방기"]):
                    automation = create_ac_bp(group["device_list"][0]["entity_id"], group["device_list"][1]["entity_id"], group["device_list"][2]["entity_id"], group["automation_name"])
                    automations.append(automation)
                    created_automations.append(group["automation_name"])

        # with open('automations.yaml', 'w') as file:
        with open('/config/automations.yaml', 'w') as file:
            yaml.dump(automations, file, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)



    def create_sw_pc_switch_bp(trigger_id, action_id, button_id, automation_name):
            return {
                "id": generate_random_id(),
                "alias": f"{automation_name} SW 타입 연동",
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
    def create_ac_bp(trigger_id, action_id, checker_id, automation_name):
            return {
                "id": generate_random_id(),
                "alias": f"{automation_name} 연동",
                "description": "ST 스위치와 냉난방기 기기 연동",
                "use_blueprint": {
                    "path": "multi-on/ac_switch.yaml",
                    "input": {
                        "main_st_switch": trigger_id,
                        "off_st_switch": action_id,
                        "climate_entity": checker_id
                    }
                }
            }

    def create_pico_pc_switch_bp(trigger_id, action_id, status_id, automation_name):
            return {
                "id": generate_random_id(),
                "alias": f"{automation_name} pico 타입 연동",
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
    def create_sync_switch_bp(trigger_id, action_id, automation_name):
            return {
                "id": generate_random_id(),
                "alias": f"{automation_name} 연동",
                "description": "ST 스위치와 실제 스위치 기기 연동",
                "use_blueprint": {
                    "path": "multi-on/sync_2_switch.yaml",
                    "input": {
                        "entity_one": trigger_id,
                        "entity_two": action_id
                    }
                }
            }

    def instant_door_open(trigger_id, action_id, automation_name):
            return {
                "id": generate_random_id(),
                "alias": f"{automation_name} 연동",
                "description": "1회열기 자동화 생성",
                "mode": "single",
                "trigger": [{
                    "platform": "state",
                    "entity_id": trigger_id,
                    "to": "on"
                }],
                "condition": [],
                "action": [
                    {"service": "switch.turn_on", "target": {"entity_id": action_id}},
                    {"service": "switch.turn_off", "target": {"entity_id": trigger_id}},
                    {"delay": {"hours": 0, "minutes": 0, "seconds": 7, "milliseconds": 0}},
                    {"service": "switch.turn_off", "target": {"entity_id": action_id}},
                    {"service": "switch.turn_off", "target": {"entity_id": trigger_id}}
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
