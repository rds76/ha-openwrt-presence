from __future__ import annotations

DOMAIN = "luci_presence_mqtt"

CONF_HOSTS = "hosts"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SSL = "ssl"
CONF_INTERFACES = "interfaces"

CONF_TRACKS = "tracks"
CONF_TRACK_MAC = "mac"
CONF_TRACK_MACS = "macs"
CONF_TRACK_NAME = "name"
CONF_TRACK_CONSIDER_HOME = "consider_home"
CONF_TRACK_ICON = "icon"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_CONSIDER_HOME = "consider_home"

CONF_MQTT = "mqtt"
CONF_MQTT_DISCOVERY_PREFIX = "discovery_prefix"
CONF_MQTT_STATE_PREFIX = "state_prefix"

DEFAULT_SSL = False
DEFAULT_INTERFACES = ["wlan0"]
DEFAULT_SCAN_INTERVAL = 15  # seconds
DEFAULT_CONSIDER_HOME = 120  # seconds

DEFAULT_DISCOVERY_PREFIX = "homeassistant"
DEFAULT_STATE_PREFIX = "presence"

LUCIRPC_AUTH_PATH = "/cgi-bin/luci/rpc/auth"
LUCIRPC_SYS_PATH = "/cgi-bin/luci/rpc/sys"

RPC_LOGIN = "login"
RPC_WIFI_GETIWINFO = "wifi.getiwinfo"

MQTT_DEVICE_BLOCK = {
    "identifiers": ["luci_presence_mqtt_bridge"],
    "name": "LuCI Presence",
    "manufacturer": "OpenWrt",
    "model": "LuCI RPC WiFi assoclist",
}