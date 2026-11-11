<p align="center">
  <img src="custom_components/luci_presence/brand/icon.png" width="128" alt="LuCI AP Presence">
</p>

# LuCI AP Presence

[![GitHub release](https://img.shields.io/github/v/release/rds76/ha-openwrt-presence)](https://github.com/rds76/ha-openwrt-presence/releases/latest)
[![GitHub License](https://img.shields.io/github/license/rds76/ha-openwrt-presence)](LICENSE)
![GitHub Validate](https://img.shields.io/github/actions/workflow/status/rds76/ha-openwrt-presence/validate.yaml?label=validate)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistant&logoColor=white)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rds76&repository=ha-openwrt-presence&category=integration)
[![GitHub stars](https://img.shields.io/github/stars/rds76/ha-openwrt-presence?style=social)](https://github.com/rds76/ha-openwrt-presence/stargazers)

Wi-Fi presence detection for Home Assistant using OpenWrt access points and the LuCI RPC API.

The integration creates native `device_tracker` entities. No MQTT broker or MQTT integration is required.

## Why this project exists

This project was created to detect presence directly from the Wi-Fi association lists (`assoclist`) of OpenWrt access points.

The official Home Assistant OpenWrt (LuCI) integration uses ARP/IP-neighbor information to discover connected devices, rather than polling per-interface Wi-Fi association lists. LuCI AP Presence fills that gap by querying `wifi.getiwinfo` and checking its `assoclist`: presence is based on whether a configured MAC address is associated with a monitored Wi-Fi interface, rather than its IP-neighbor reachability.

For homes with several access points or Wi-Fi networks, the integration combines those observations into one presence result per configured track. Multiple MAC addresses can represent one person or device, and a configurable `consider_home` grace period helps avoid brief away transitions during roaming or temporary disconnections.

The LuCI communication code was originally adapted from the official integration.

## Features

- Multiple OpenWrt access points and Wi-Fi interfaces.
- Multiple MAC addresses per tracked person or device.
- Presence across all configured access points, including roaming between them.
- Global and per-track `consider_home` timeouts.
- Native Home Assistant trackers with `tracking_type: connection` and automatic `in_zones`.
- Support for Home Assistant Person entities and home-zone display on the map.
- Dedicated HTTP sessions with cookies disabled, token authentication and login retry backoff.
- YAML configuration, including `!secret` and `!include`.

## Requirements

- Compatibility target: **Home Assistant 2026.7 or newer**.
- OpenWrt access points with the LuCI RPC API enabled.
- Credentials that can log in and query Wi-Fi association lists.
- The interface names used by your access points.

The compatibility target is based on source-code review; it is not a claim that every Home Assistant release in this range has been runtime-tested.

Follow the LuCI RPC setup instructions in the [Home Assistant OpenWrt documentation](https://www.home-assistant.io/integrations/luci/) for each monitored router.

## Installation

### HACS

1. Open HACS.
2. Open **Custom repositories** from the menu.
3. Add `https://github.com/rds76/ha-openwrt-presence` with category **Integration**.
4. Download the integration.
5. Add the YAML configuration described below.
6. Restart Home Assistant.

### Manual installation

1. Copy `custom_components/luci_presence` into your Home Assistant `custom_components` directory.
2. Add the YAML configuration described below.
3. Restart Home Assistant.

The resulting directory must be:

```text
config/
  custom_components/
    luci_presence/
      __init__.py
      config_flow.py
      const.py
      coordinator.py
      device_tracker.py
      luci_api.py
      manifest.json
      brand/
      translations/
        en.json
```

If upgrading from the MQTT version, follow [Migrating from the MQTT version](#migrating-from-the-mqtt-version) before starting the replacement.

## Configuration

Configure the integration in `configuration.yaml`:

```yaml
luci_presence:
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

  scan_interval: 15
  consider_home: 120

  tracks: !include luci_presence_tracks.yaml
```

Use your routers' actual interface names. The names above are examples, not necessarily the SSID names shown to Wi-Fi clients.

Add credentials to `secrets.yaml`:

```yaml
luci_username: "your_luci_username"
luci_password: "your_luci_password"
```

Create `luci_presence_tracks.yaml`:

```yaml
dev_person_one:
  name: Person One
  icon: mdi:cellphone
  macs:
    - AA:BB:CC:DD:EE:FF
    - 11:22:33:44:55:66
  consider_home: 300

dev_person_two:
  name: Person Two
  icon: mdi:cellphone
  mac: "00:11:22:33:44:55"
```

`tracks` is a mapping. Using `!include` is optional; the same mapping can be written directly below `tracks:` in `configuration.yaml`. An existing include filename does not need to be renamed.

The integration automatically creates an internal config entry. Configuration remains in YAML; router credentials are not copied into that entry.

**Restart Home Assistant after changing the YAML configuration.** Reloading the integration alone does not reread YAML. There is no interactive setup form.

### General options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `hosts` | Yes | - | Non-empty list of OpenWrt access points. |
| `tracks` | Yes | - | Non-empty mapping of track IDs to their settings. |
| `scan_interval` | No | `15` | Polling interval in seconds; must be at least `1`. |
| `consider_home` | No | `120` | Default presence grace period in seconds; must be non-negative. |

### Host options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | Yes | - | Router hostname or IP address, without `http://` or `https://`. |
| `username` | Yes | - | LuCI username. |
| `password` | Yes | - | LuCI password. |
| `ssl` | No | `false` | Use HTTPS instead of HTTP. |
| `interfaces` | No | `["wlan0"]` | Non-empty list of Wi-Fi interfaces to query. |

### Track options

Each track ID must be a valid Home Assistant slug, using lowercase letters, digits and underscores, for example `dev_person_one`.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `mac` | One of `mac` or `macs` | - | One MAC address to track. |
| `macs` | One of `mac` or `macs` | - | List of MAC addresses to track. |
| `name` | No | Track ID | Display name of the tracker. |
| `icon` | No | Home Assistant default | Material Design icon, for example `mdi:cellphone`. |
| `consider_home` | No | Global value | Presence grace period for this track, in seconds. |

If both `mac` and `macs` are supplied, they are combined. At least one non-empty MAC address must be configured.

## How presence detection works

The integration polls routers in parallel and queries the interfaces of each router sequentially. Results from all routers and interfaces are combined.

A track is considered present when any of its configured MAC addresses is observed. After the last observation, it remains present for its `consider_home` period. It becomes away on the next poll after that period expires.

```text
OpenWrt access points
        |
        v
   LuCI RPC API
        |
        v
 Shared polling coordinator
        |
        v
 Native device_tracker entities
        |
        v
 Home Assistant persons and automations
```

### Authentication and failures

Each router uses a dedicated HTTP session with cookies disabled. Authenticated requests send the LuCI token in the `auth` query parameter. An expired token triggers at most one token refresh and request retry.

Credentials are checked before polling starts. A router that rejects them is disabled for that run, and the rejection is logged once. Correct its credentials in YAML and restart Home Assistant. Other routers continue normally. If all routers reject their credentials during startup, setup fails without adding tracker entities.

Temporary login failures use per-router retry delays of `15`, `30`, `60`, `120`, `240` and then `300` seconds. A retry occurs on the next scheduled poll after the delay expires. Repeated failures are suppressed in the log until a successful login resets the backoff and logs recovery.

**A failed router query provides no observed MAC addresses.** If the device is not observed on another router, its grace period can expire and the tracker can become away. Router communication failure is not proof that a device has left.

## Entities, persons and zones

For each configured track, the integration creates a native tracker, enabled by default:

```text
device_tracker.dev_person_one
device_tracker.dev_person_two
```

The initial entity ID is suggested from the track ID. Existing registry entries or occupied IDs may affect the final ID.

Trackers belong to the integration but are not grouped under a shared device in the Home Assistant device registry. A track may aggregate several MAC addresses, so no arbitrary single MAC is used to represent it as a physical device.

### Associated zone

Home Assistant manages the associated zone of each tracker. The default is **Home** (`zone.home`).

With that default:

| Presence | State | Zone membership |
| --- | --- | --- |
| Present, including the grace period | `home` | Includes `zone.home`. |
| Away after the grace period | `not_home` | `in_zones: []`. |

Home Assistant may also include enclosing zones in `in_zones`. To represent another location, change the associated zone in the tracker's entity settings.

The associated zone labels a positive presence result; it does not select which router to query. All configured routers still contribute to each track.

### Persons and the map

Assign the tracker to a person under **Settings > People**.

When Home Assistant selects this tracker as the person's source, the person inherits its zone membership. The map can use the associated zone's location for the person, even without GPS coordinates.

The integration does not fabricate latitude or longitude. The zone-location fallback applies to `person` entities, not directly to these coordinate-free trackers.

If a person has neither coordinates nor a usable zone, it may not appear in the map card's entity picker. It can still be listed explicitly in the card's YAML and becomes visible when a location is available:

```yaml
type: map
entities:
  - person.person_one
```

## Migrating from the MQTT version

This is a breaking replacement of `luci_presence_mqtt`, not an automatic entity-registry migration.

1. Back up your configuration and note existing tracker entity IDs and Person assignments.
2. Stop the old integration: remove its `luci_presence_mqtt:` YAML section and restart Home Assistant. Do not start the replacement yet.
3. Keep the official MQTT integration connected and clear the old retained discovery configuration for every track.
4. Verify that the old MQTT entities have been removed. Otherwise their IDs can remain reserved and new entities may get an `_2` suffix.
5. Remove `custom_components/luci_presence_mqtt` and install `custom_components/luci_presence`, including all new files.
6. Restore your configuration under `luci_presence:`, remove its `mqtt:` subsection, and keep the same hosts and track IDs.
7. Restart Home Assistant, check the new entity IDs and reassign the new trackers to their persons. Check dashboards and automations.

To clear discovery for one old track, run this in **Developer tools > Actions**:

```yaml
action: mqtt.publish
data:
  topic: homeassistant/device_tracker/dev_person_one/config
  payload: ""
  qos: 1
  retain: true
```

Replace `dev_person_one` with the old track ID. If you used another discovery prefix, replace `homeassistant` too. Repeat for every old track.

To clear retained state and attributes as well, run the same action separately for their exact topics. For example, with the old `state_prefix: house/presence`:

```text
house/presence/dev_person_one/state
house/presence/dev_person_one/attributes
```

Only clear topics owned by this integration. Do not clear an entire shared MQTT discovery prefix.

Matching `unique_id` values do not transfer registry entries from MQTT to the native integration. Keeping the same `entity_id` preserves references by that ID, but Person assignments may be removed when the old entity is deleted and must be checked.

## License

Original contributions by rds76 are licensed under the [MIT License](LICENSE).

The LuCI client contains code adapted from Home Assistant's OpenWrt (LuCI) integration. Those portions remain subject to the [Apache License, Version 2.0](LICENSE-APACHE-2.0).

See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) for attribution and licensing scope.
