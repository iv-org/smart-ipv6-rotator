from pyroute2 import IPDB, IPRoute

ICANHAZIP_IPV6_ADDRESS = "2606:4700::6812:7261"

JSON_CONFIG_FILE = "/tmp/smart-ipv6-rotator.json"

IP = IPDB()
IPROUTE = IPRoute()

__all__: list[str] = ["ICANHAZIP_IPV6_ADDRESS", "IP", "IPROUTE"]
