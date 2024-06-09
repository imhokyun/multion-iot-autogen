# My Component

This is a custom component for Home Assistant.

## Installation

1. Add this repository to HACS.
2. Install the component.
3. Add the configuration to `configuration.yaml`.

## Configuration

```yaml
homeassistant:
  custom_components:
    - my_component

button:
  - platform: my_component
