<p align="center">
  <img src="custom_components/luci_presence_mqtt/brand/icon.png" width="128" alt="LUCI">
</p>

# LuCI AP Presence to MQTT

[![GitHub release](https://img.shields.io/github/v/release/rds76/ha-openwrt-presence)](https://github.com/rds76/ha-openwrt-presence/releases/latest)
[![GitHub License](https://img.shields.io/github/license/rds76/ha-openwrt-presence)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/rds76/ha-openwrt-presence?style=social)](https://github.com/rds76/ha-openwrt-presence/stargazers)
<!--
[![Support via Revolut](https://img.shields.io/badge/Revolut-Support-blue)](https://revolut.me/radimm5hv)
-->

MQTT-based presence detection for Home Assistant using OpenWRT access points, the LuCI RPC API and MQTT Discovery.

Supports multiple OpenWRT access points, multiple SSIDs and multiple MAC addresses per tracked person.

This project was created to provide reliable Wi-Fi presence detection for Home Assistant using OpenWRT access points. Presence information is collected through the LuCI RPC API and published using MQTT Discovery, allowing automatic creation of Home Assistant entities for automations and person tracking.

The project was originally derived from the official Home Assistant OpenWRT integration and extends its LuCI RPC communication to retrieve associated Wi‑Fi client lists required for presence detection.

## Installation

### HACS

1. Open HACS.
2. Navigate to **Integrations**.
3. Click **Custom repositories**.
4. Add the repository URL and select **Integration** as the category.
5. Install **LuCI AP Presence to MQTT**.
6. Restart Home Assistant.

### Manual Installation

1. Copy the `custom_components/luci_presence_mqtt` directory to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration

The integration is configured through `configuration.yaml`.

See the examples below for a complete configuration.

## Features

- Presence detection using OpenWRT access points
- Support for multiple access points (APs)
- Support for multiple Wi-Fi interfaces (SSIDs) per access point
- Support for multiple MAC addresses per tracked person
- Individual `consider_home` timeout per tracked person
- Automatic MQTT Discovery
- Home Assistant ready

## Requirements

### OpenWRT LuCI RPC API

This project requires the LuCI RPC API to be configured on all monitored OpenWRT devices.

Please follow the same LuCI RPC API setup instructions as described in the official Home Assistant OpenWRT integration documentation:

https://www.home-assistant.io/integrations/luci/


### MQTT Integration

The Home Assistant MQTT integration must be configured and connected to a working MQTT broker before using this integration.

## How It Works

The application periodically queries configured OpenWRT access points using the LuCI RPC API and retrieves the list of associated Wi-Fi clients from one or more configured wireless interfaces.

Presence is determined across all configured access points and SSIDs. A tracked person can be associated with multiple MAC addresses and is considered present if at least one configured device is connected.

Presence information is then published via MQTT and automatically discovered by Home Assistant.

```text
OpenWRT APs
      │
      ▼
 LuCI RPC API
      │
      ▼
 LuCI AP Presence to MQTT
      │
      ▼
 MQTT Discovery
      │
      ▼
 Home Assistant
```

## Generated Entities

For each tracked device, the integration creates a Home Assistant MQTT device tracker entity.

Example:

```text
device_tracker.dev_person_one
device_tracker.dev_person_two
```

These entities can be used directly in automations and Home Assistant Person entities.

## Why This Project Exists

Many households use multiple OpenWRT access points and multiple SSIDs to provide seamless Wi‑Fi coverage.

Traditional presence detection solutions are often designed around a single access point and may struggle when devices roam between access points or move across different wireless networks.

This project was created to provide reliable Wi‑Fi presence detection across multiple OpenWRT access points and multiple SSIDs while supporting multiple MAC addresses per tracked person or device.

Presence information is retrieved directly from associated Wi‑Fi client lists exposed through the LuCI RPC API and published to Home Assistant using MQTT Discovery.

The result is a lightweight and reliable presence detection solution for Home Assistant environments built on OpenWRT infrastructure.

## Configuration Options

| Option | Type | Description |
|----------|----------|----------|
| `hosts` | list | List of OpenWRT access points to monitor. |
| `host` | string | OpenWRT hostname or IP address. |
| `username` | string | LuCI username. |
| `password` | string | LuCI password. |
| `interfaces` | list | Wi-Fi interfaces (SSIDs) that should be monitored on the access point. |
| `scan_interval` | integer | Polling interval in seconds. Default: `30`. |
| `consider_home` | integer | Default time in seconds a device remains present after disappearing from Wi-Fi. Default: `180`. |
| `mqtt.discovery_prefix` | string | MQTT Discovery prefix. Default: `homeassistant`. |
| `mqtt.state_prefix` | string | MQTT topic prefix used for publishing presence states. |
| `tracks` | string | Path to a YAML file containing tracked devices and MAC addresses. |

## Tracked Devices Options

| Option | Type | Description |
|----------|----------|----------|
| `name` | string | Friendly name of the tracked device or person. |
| `icon` | string | Optional Home Assistant Material Design icon. |
| `macs` | list | One or more MAC addresses associated with the device or person. |
| `consider_home` | integer | Optional override of the global `consider_home` value. |

## Example Configuration

```yaml
luci_presence_mqtt:
  hosts:
    - host: wifiap1.local
      username: !secret luci_username
      password: !secret luci_password
      interfaces:
        - wifi-5g
        - wifi

    - host: wifiap2.local
      username: !secret luci_username
      password: !secret luci_password
      interfaces:
        - wifi-5g
        - wifi

    - host: wifiap3.local
      username: !secret luci_username
      password: !secret luci_password
      interfaces:
        - wifi-guest

  scan_interval: 30
  consider_home: 180

  mqtt:
    discovery_prefix: homeassistant
    state_prefix: house/presence

  tracks: !include luci_presence_mqtt_tracks.yaml
```

### Example Tracked Devices

```yaml
# luci_presence_mqtt_tracks.yaml.example
person-one:
  name: Person One
  icon: mdi:cellphone
  macs:
    - AA:BB:CC:DD:EE:FF
    - 11:22:33:44:55:66
  consider_home: 300

person-two:
  name: Person Two
  icon: mdi:cellphone
  macs:
    - 00:11:22:33:44:55
```

The top-level key is used to generate the Home Assistant entity identifier.

### Tracked Devices

Tracked devices are stored in a separate file referenced by the `tracks` option.

This keeps the main configuration clean and allows MAC addresses and personal device information to be excluded from version control.

## License

MIT License