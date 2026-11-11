from __future__ import annotations

DOMAIN = "luci_presence"

DEFAULT_TITLE = "Configured access points"

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

DEFAULT_SSL = False
DEFAULT_INTERFACES = ["wlan0"]
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_CONSIDER_HOME = 120

LUCIRPC_AUTH_PATH = "/cgi-bin/luci/rpc/auth"
LUCIRPC_SYS_PATH = "/cgi-bin/luci/rpc/sys"
RPC_LOGIN = "login"
RPC_WIFI_GETIWINFO = "wifi.getiwinfo"
LOGIN_RETRY_INITIAL = 15
LOGIN_RETRY_MAX = 300