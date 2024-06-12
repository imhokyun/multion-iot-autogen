# My Component

어시스턴트에 Multi-on 에서 연동방식을 자동화하는 custom component 입니다.

## Installation

1. HACS에서 custom repository 추가(integration).(https://github.com/imhokyun/multion-iot-autogen.git)
2. component 설치 
3. configuration.yaml 에 아래 코드 추가

## Configuration

```yaml
multion_iot_autogen:

## 이용방법
SmartThings 스위치와 실제 기기 스위치, 등, 에어컨, PC 등 모두를 이름 규칙에 따라 설치 완료 후 
Multi-on Auto-gen "로봇" 모양 버튼을 눌러 자동화를 생성
생성 완료 후, 개발자도구 > 자동화 yaml 불러오기 버튼 체크
