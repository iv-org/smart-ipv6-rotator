import logging

from pyroute2 import IPDB, IPRoute

ICANHAZIP_IPV6_ADDRESS = "2606:4700::6812:7261"

JSON_CONFIG_FILE = "/tmp/smart-ipv6-rotator.json"

LEGACY_CONFIG_FILE = "/tmp/smart-ipv6-rotator.py"

LOGGER = logging.getLogger(__name__)
LOG_LEVELS_NAMES = list(logging._nameToLevel.keys())

IP = IPDB()
IPROUTE = IPRoute()

__all__: list[str] = ["ICANHAZIP_IPV6_ADDRESS", "IP", "IPROUTE"]
