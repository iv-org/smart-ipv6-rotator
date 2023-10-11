from config import *
import requests
import sys
from random import seed, getrandbits, choice
from ipaddress import IPv6Network, IPv6Address
from pyroute2 import IPDB
from pyroute2 import IPRoute

# https://md5calc.com/google/ip
google_ipv6_ranges = [
    "2001:4860:4000::/36",
    "2404:6800:4000::/36",
    "2607:f8b0:4000::/36",
    "2800:3f0:4000::/36",
    "2a00:1450:4000::/36",
    "2c0f:fb50:4000::/36",
]

ip = IPDB()
iproute = IPRoute()

# checking if IPv6 connectivity

try:
    requests.get("http://ipv6.icanhazip.com")
except requests.exceptions.RequestException:
    sys.exit("[Error] You do not have IPv6 connectivity. This script can not work.")

print("[OK] You have IPv6 connectivity. Continuing.")

# TODO: check if there is existing ipv6 routes already configured

# calculate random IPv6 from the configured subnet

seed()
ipv6_network = IPv6Network(ipv6_subnet)
print(ipv6_network.prefixlen)
random_ipv6_address = IPv6Address(ipv6_network.network_address + getrandbits(ipv6_network.max_prefixlen - ipv6_network.prefixlen))

# get default network interface for IPv6

default_interface_index = iproute.route('get', dst=choice(google_ipv6_ranges))[0].get_attrs('RTA_OIF')[0]
default_interface_name = ip.interfaces[default_interface_index]['ifname']

print(random_ipv6_address)

print(default_interface_name)

iproute.addr('add', default_interface_index, address=random_ipv6_address, mask=ipv6_network.prefixlen)

#file = open('/tmp/smart-ipv6-rotator-picked-ipv6.txt', "w")
#file.write("Python Guide")
#file.close()