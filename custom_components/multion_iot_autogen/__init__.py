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
        source_path = os.path.join(
            module_path, "blueprints/automation/multi-on")
        target_path = hass.config.path("blueprints/automation/multi-on")

        # 타겟 디렉토리 확인 및 생성
        if not os.path.exists(target_path):
            os.makedirs(target_path)

        # 파일 목록 확인 및 복사
        blueprint_files = ['pico_pc_switch.yaml',
                           'switch_action.yaml', 'sw_pc_switch.yaml', 'sync_2_switch.yaml']
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
        devices_list_path = os.path.join(
            os.path.dirname(__file__), 'devices_list.json')
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
                # 냉난방기 끄기 스위치를 제외한 나머지 스위치는 ST entity로 분류
                else:
                    stSwitch.append(device)
            else:
                otherDevices.append(device)
        # 이름이 동일한 기기들을 묶기
        paired_devices = []
        for st in stSwitch:
            st_name = st["friendly_name"][:-3]  # " ST"를 제거
            matched_devices = {
                "st_switch": [st],
                "real_device": []
            }
            automation_name = st_name  # " ST"가 제거된 이름을 automation_name으로 사용
            for other in otherDevices:
                other_name = other["friendly_name"].replace(
                    " ST", "")  # " ST"를 제거
                if other_name == st_name or \
                        other_name == st_name + " 끄기" or \
                        other_name == st_name + " WOL" or \
                        other_name == st_name + " 상태":
                    matched_devices["real_device"].append(other)
            if len(matched_devices["real_device"]) > 0:
                paired_devices.append({
                    "automation_name": automation_name,
                    "device_list": matched_devices
                })

        paired_devices_path = os.path.join(
            os.path.dirname(__file__), 'paired_devices.json')
        with open(paired_devices_path, 'w', encoding='utf-8') as json_file:
            json.dump(paired_devices, json_file, ensure_ascii=False, indent=4)

        return paired_devices

    def create_automations():
        init_blueprint()
        device_groups = pair_devices(get_entity())
        ac_variables = create_ac_variables()

        automations = []
        created_automations = []  # 이미 생성된 자동화 이름을 저장할 리스트
        for group in device_groups:
            if group["automation_name"] not in created_automations:

                # 1회열기 연동
                if "1회" in group["automation_name"]:
                    automation = instant_door_open(
                        group["device_list"]["st_switch"][0]["entity_id"], group["device_list"]["real_device"][0]["entity_id"], group["automation_name"])
                    automations.append(automation)
                    created_automations.append(group["automation_name"])

                # 스위치 연동(PC는 아래 로직에서 처리)
                elif any(keyword in group["automation_name"] for keyword in ["볼공급기", "등", "상시"]) and "PC" not in group["automation_name"]:
                    automation = create_sync_switch_bp(
                        group["device_list"]["st_switch"][0]["entity_id"], group["device_list"]["real_device"][0]["entity_id"], group["automation_name"])
                    automations.append(automation)
                    created_automations.append(group["automation_name"])

                # PC 연동(3개 타입에 맞춰 연동)
                elif any(keyword in group["automation_name"] for keyword in ["PC"]):
                    # 타입1 2개 스위치
                    if len(group["device_list"]["real_device"]) == 1:
                        automation = create_sync_switch_bp(
                            group["device_list"]["st_switch"][0]["entity_id"], group["device_list"]["real_device"][0]["entity_id"], group["automation_name"])
                        automations.append(automation)
                        created_automations.append(group["automation_name"])
                    elif len(group["device_list"]["real_device"]) == 2:
                        wol_device = next(
                            (device for device in group["device_list"]["real_device"] if "WOL" in device["friendly_name"]), None)
                        status_device = next(
                            (device for device in group["device_list"]["real_device"] if "상태" in device["friendly_name"]), None)

                    # 타입2 SW 방식 WOL + HASS.Agent
                        if wol_device:
                            automation = create_sw_pc_switch_bp(
                                group["device_list"]["st_switch"][0]["entity_id"], group["device_list"]["real_device"][0]["entity_id"], group["device_list"]["real_device"][1]["entity_id"], group["automation_name"])
                            automations.append(automation)
                            created_automations.append(
                                group["automation_name"])
                            automation_off = create_sw_pc_switch_sync(
                                group["device_list"]["real_device"][1]["entity_id"], group["device_list"]["st_switch"][0]["entity_id"], group["automation_name"])
                            automations.append(automation_off)
                            created_automations.append(
                                f"{group['automation_name']} 끄기")
                    # 타입3 PICO 이용 방식
                        elif status_device:
                            automation = create_pico_pc_switch_bp(
                                group["device_list"]["st_switch"][0]["entity_id"], group["device_list"]["real_device"][1]["entity_id"], group["device_list"]["real_device"][0]["entity_id"], group["automation_name"])
                            automations.append(automation)
                            created_automations.append(
                                group["automation_name"])
                # 냉난방기 연동
                elif any(keyword in group["automation_name"] for keyword in ["냉난방기"]):
                    automation_init = init_ac_config_when_restart_ha(generate_random_id(
                    ), group["device_list"]["real_device"][0]["entity_id"], ac_variables["entity_id"][0], ac_variables["entity_id"][1], ac_variables["entity_id"][2], group["automation_name"])
                    automations.append(automation_init)
                    created_automations.append(group["automation_name"])

                    automation_on = ac_on(generate_random_id(), group["device_list"]["st_switch"][0]["entity_id"], group["device_list"]["real_device"][0]
                                          ["entity_id"], ac_variables["entity_id"][0], ac_variables["entity_id"][1], ac_variables["entity_id"][2], f"{group['automation_name']} 켜기")
                    automations.append(automation_on)
                    created_automations.append(
                        f"{group['automation_name']} 켜기")

                    automation_off = ac_off(generate_random_id(
                    ), group["device_list"]["st_switch"][0]["entity_id"], group["device_list"]["real_device"][0]["entity_id"], f"{group['automation_name']} 끄기")
                    automations.append(automation_off)
                    created_automations.append(
                        f"{group['automation_name']} 끄기")

                    automation_make_sure_off = instant_ac_off(
                        group["device_list"]["real_device"][1]["entity_id"], group["device_list"]["real_device"][0]["entity_id"], f"{group['automation_name']} 한번 더 끄기")
                    automations.append(automation_make_sure_off)
                    created_automations.append(
                        f"{group['automation_name']} 한번 더 끄기")

                    # automation = create_ac_bp(group["device_list"]["st_switch"][0]["entity_id"],
                    #                           group["device_list"]["real_device"][0]["entity_id"], group["automation_name"])
                    # automations.append(automation)
                    # created_automations.append(group["automation_name"])

                    # instant_ac_off 자동화 추가
                    # automation_off = instant_ac_off(group["device_list"]["real_device"][1]["entity_id"], group["device_list"]
                    #                                 ["real_device"][0]["entity_id"], group["automation_name"])
                    # automations.append(automation_off)
                    # created_automations.append(f"{group['automation_name']} 끄기")

        # with open('automations.yaml', 'w') as file:
        with open('/config/automations.yaml', 'w') as file:
            yaml.dump(automations, file, default_flow_style=False,
                      sort_keys=False, allow_unicode=True, indent=2)

    def create_sw_pc_switch_bp(trigger_id, action_id, button_id, automation_name):
        return {
            "id": generate_random_id(),
            "alias": f"{automation_name} SW 타입",
            "description": "ST 스위치와 SW타입 PC연동",
            "use_blueprint": {
                "path": "multi-on/sw_pc_switch.yaml",
                "input": {
                    "pc_st_switch": trigger_id,
                    "wol_switch": action_id,
                    "pc_off_button": button_id
                }
            }
        }

    def create_sw_pc_switch_sync(trigger_id, action_id, automation_name):
        return {
            "id": generate_random_id(),
            "alias": f"{automation_name} SW 타입 끄기",
            "description": "ST 스위치와 SW타입 PC 끄기",
            "mode": "single",
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": trigger_id,
                    "to": "unavailable"
                }
            ],
            "condition": [],
            "action": [
                {"service": "switch.turn_off", "target": {"entity_id": action_id}}
            ]
        }

    # def create_ac_bp(trigger_id, action_id, automation_name):
    #     return {
    #         "id": generate_random_id(),
    #         "alias": f"{automation_name}",
    #         "description": "ST 스위치와 냉난방기 기기 연동",
    #         "use_blueprint": {
    #             "path": "multi-on/ac_switch.yaml",
    #             "input": {
    #                 "main_st_switch": trigger_id,
    #                 "climate_entity": action_id
    #             }
    #         }
    #     }

    def create_pico_pc_switch_bp(trigger_id, action_id, status_id, automation_name):
        return {
            "id": generate_random_id(),
            "alias": f"{automation_name} pico 타입",
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
            "alias": f"{automation_name}",
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
            "alias": f"{automation_name}",
            "description": "1회열기 자동화",
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
                {"delay": {"hours": 0, "minutes": 0, "seconds": 5, "milliseconds": 0}},
                {"service": "switch.turn_off", "target": {"entity_id": action_id}},
                {"service": "switch.turn_off", "target": {"entity_id": trigger_id}}
            ]
        }

    def instant_ac_off(trigger_id, action_id, automation_name):
        return {
            "id": generate_random_id(),
            "alias": f"{automation_name} 끄기",
            "description": "냉난방기 끄기 자동화",
            "mode": "single",
            "trigger": [{
                "platform": "state",
                "entity_id": trigger_id,
                "to": "off"
            }],
            "condition": [],
            "action": [
                {"delay": {"hours": 0, "minutes": 0, "seconds": 1, "milliseconds": 0}},
                {"service": "climate.set_hvac_mode", "target": {
                    "entity_id": action_id}, "data": {"hvac_mode": "off"}},
                {"service": "switch.turn_on", "target": {"entity_id": trigger_id}}
            ]
        }

    def generate_random_id(length=10):
        import random
        import string
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    hass.services.register(DOMAIN, 'create_automations',
                           lambda service: create_automations())

    # Load platforms
    discovery.load_platform(hass, 'switch', DOMAIN, {}, config)

    return True

# -----------------------냉난방기 기능 추가 2024 07 11---------------------------


def create_ac_variables():
    # devices_list.json 파일 읽기
    base_dir = os.path.dirname(__file__)
    devices_list_path = os.path.join(base_dir, 'devices_list.json')
    with open(devices_list_path, 'r', encoding='utf-8') as file:
        devices = json.load(file)

    # hvac_settings 폴더 생성
    hvac_settings_folder = os.path.join(base_dir, 'hvac_settings')
    if not os.path.exists(hvac_settings_folder):
        os.makedirs(hvac_settings_folder)

    # hvac_input_number.yaml 파일 생성 및 작성
    ac_variables = {}
    hvac_input_number_content = {}
    hvac_input_select_content = {}

    for device in devices:
        if device['entity_id'].startswith('climate.'):
            entity_suffix = device['entity_id'].split('climate.')[1]
            hvac_input_number_content[f"{entity_suffix}_temperature"] = {
                "name": f"{device['friendly_name']} Temperature",
                "initial": 20,
                "min": 16,
                "max": 30,
                "step": 1
            }
            hvac_input_select_content[f"{entity_suffix}_fan_mode"] = {
                "name": f"{device['friendly_name']} Fan Mode",
                "options": ["low", "medium", "high", "auto"],
                "initial": "auto"
            }
            hvac_input_select_content[f"{entity_suffix}_hvac_mode"] = {
                "name": f"{device['friendly_name']} HVAC Mode",
                "options": ["cool", "heat", "auto", "off"],
                "initial": "auto"
            }
            ac_variables[device['entity_id']] = [f"{entity_suffix}_temperature", f"{
                entity_suffix}_fan_mode", f"{entity_suffix}_hvac_mode"]

    print(ac_variables)

    hvac_input_number_path = os.path.join(
        hvac_settings_folder, 'hvac_input_number.yaml')
    with open(hvac_input_number_path, 'w', encoding='utf-8') as file:
        yaml.dump(hvac_input_number_content, file,
                  allow_unicode=True, line_break=True)

    hvac_input_select_path = os.path.join(
        hvac_settings_folder, 'hvac_input_select.yaml')
    with open(hvac_input_select_path, 'w', encoding='utf-8') as file:
        yaml.dump(hvac_input_select_content, file,
                  allow_unicode=True, line_break=True)

    # hvac_settings폴더와 폴더 내의 파일을 복사하여 /config 폴더로 이동
    config_hvac_settings_path = os.path.join(
        base_dir, 'config', 'hvac_settings')
    if os.path.exists(config_hvac_settings_path):
        shutil.rmtree(config_hvac_settings_path)
    shutil.copytree(hvac_settings_folder, config_hvac_settings_path)

    return ac_variables


def init_ac_config_when_restart_ha(random_id, ac_entity, temperature_var, fan_mode_var, hvac_mode_var, automation_name):
    return {
        {
            "id": random_id,
            "alias": f"{automation_name}냉난방기 초기값 설정",
            "description": "HA 재부팅 시 냉난방기 설정값 초기화",
            "trigger": [
                {
                    "platform": "homeassistant",
                    "event": "start"
                }
            ],
            "condition": [],
            "action": [
                {
                    "delay": "00:00:10"
                },
                {
                    "service": "input_number.set_value",
                    "data_template": {
                        "entity_id": f"input_number.{temperature_var}",
                        "value": f"{{ state_attr('climate.{ac_entity}', 'temperature') }}"
                    }
                },
                {
                    "service": "input_select.select_option",
                    "data_template": {
                        "entity_id": f"input_select.{hvac_mode_var}",
                        "option": "{% if state_attr('climate." + ac_entity + "', 'hvac_mode') is none %}auto{% else %}{{ state_attr('climate." + ac_entity + "', 'hvac_mode') }}{% endif %}"
                    }
                },
                {
                    "service": "input_select.select_option",
                    "data_template": {
                        "entity_id": f"input_select.{fan_mode_var}",
                        "option": f"{{ state_attr('climate.{ac_entity}', 'fan_mode') }}"
                    }
                }
            ],
            "mode": "single"
        }
    }


def ac_on(random_id, trigger_id, action_id, temperature_var, fan_mode_var, hvac_mode_var, automation_name):
    return {
        {
            "id": random_id,
            "alias": f"{automation_name}템플릿 냉난방기",
            "description": "냉난방기 지정한 값으로 켜기",
            "trigger": [{
                "platform": "state",
                "entity_id": trigger_id,
                "to": "on"
            }],
            "condition": [],
            "action": [
                {
                    "service": "climate.set_temperature",
                    "entity_id": action_id,
                    "data_template": {
                        "temperature": f"{{ states('{temperature_var}') | float }}"
                    }
                },
                {
                    "delay": {
                        "milliseconds": 500
                    }
                },
                {
                    "service": "climate.set_fan_mode",
                    "entity_id": action_id,
                    "data_template": {
                        "fan_mode": f"{{ states('{fan_mode_var}') }}"
                    }
                },
                {
                    "delay": {
                        "milliseconds": 500
                    }
                },
                {
                    "service": "climate.set_hvac_mode",
                    "entity_id": action_id,
                    "data_template": {
                        "hvac_mode": f"{{ states('{hvac_mode_var}') }}"
                    }
                }
            ],
            "mode": "single"
        }

    }


def ac_off(random_id, trigger_id, action_id, automation_name):
    return {
        "id": random_id,
        "alias": f"{automation_name}냉난방기 끄기",
        "description": "냉난방기 끄기",
        "trigger": [{
            "platform": "state",
            "entity_id": trigger_id,
            "to": "off"
        }],
        "action": [
            {"service": "climate.set_hvac_mode", "target": {
                "entity_id": action_id}, "data": {"hvac_mode": "off"}},
        ]
    }
