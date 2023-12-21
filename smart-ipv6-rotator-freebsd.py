#!/usr/bin/env python

import re
import subprocess
import sys
import os
import argparse
from random import seed, getrandbits, choice
from ipaddress import IPv6Network, IPv6Address
from time import sleep
from runpy import run_path

def module_not_found_helper(module_name):
    sys.exit(f"[Error] Module '{module_name}' is not installed. please install it using: pkg install py39-{module_name}")

try:
    import requests
except ModuleNotFoundError:
    module_not_found_helper("requests")

class SmartIPv6Rotator(object):
    def __init__(self):
        parser = argparse.ArgumentParser(
            description="IPv6 rotator",
            usage="""smart-ipv6-rotator.py <command> [<args>]

The available args are:
   run      Run the IPv6 rotator process.
""",
        )
        parser.add_argument("command", help="Subcommand to run")
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print("Unrecognized command")
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()

    # https://md5calc.com/google/ip
    google_ipv6_ranges = [
        "2001:4860:4000::/36",
        "2404:6800:4000::/36",
        "2607:f8b0:4000::/36",
        "2800:3f0:4000::/36",
        "2a00:1450:4000::/36",
        "2c0f:fb50:4000::/36",
    ]
    location_saved_config_ipv6_configured = "/tmp/smart-ipv6-rotator.py"
    icanhazip_ipv6_address = "2606:4700::6812:7261"

    def check_ipv6_connectivity(self):
        try:
            requests.get("http://ipv6.icanhazip.com", timeout=5)
        except requests.exceptions.RequestException:
            sys.exit(
                "[Error] You do not have IPv6 connectivity. This script can not work."
            )

        print("[INFO] You have IPv6 connectivity. Continuing.")

    def get_route_freebsd(self):
        result = subprocess.run(['netstat', '-rn', '-f', 'inet6'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.startswith('default'):
                parts = line.split()
                return {'gateway': parts[1], 'interface_name': parts[3]}
        return None

    def get_ipv6_addresses_freebsd(self, interface_name):
        result = subprocess.run(['ifconfig', interface_name], capture_output=True, text=True)
        ipv6_regex = re.compile(r'inet6 ([a-f0-9:]+) prefixlen (\d+)')
        return ipv6_regex.findall(result.stdout)

    def get_current_ipv6_routes_freebsd(self):
        result = subprocess.run(['netstat', '-rn', '-f', 'inet6'], capture_output=True, text=True)
        routes = []
        for line in result.stdout.splitlines():
            if line.startswith('default') or ':' in line:
                parts = line.split()
                if len(parts) > 2:
                    routes.append((parts[0], parts[1]))
        return routes

    def add_ipv6_address_freebsd(self, interface_name, gateway, ipv6_address, mask):
        full_address = f"{ipv6_address}/{mask}"
        subprocess.run(['ifconfig', interface_name, 'inet6', full_address, 'alias'], check=True)
        for ipv6_range in self.google_ipv6_ranges:
            subprocess.run(['route', '-6', 'add', ipv6_range, gateway], check=True)

    def is_global_unicast_ipv6(self, address):
        first_hextet = int(address.split(':')[0], 16)
        return (first_hextet & 0xE000) == 0x2000

    def delete_previous_alias_freebsd(self, interface_name, gateway):
        ipv6_addresses = self.get_ipv6_addresses_freebsd(interface_name)
        global_unicast_addresses = [addr for addr, _ in ipv6_addresses if self.is_global_unicast_ipv6(addr)]

        if len(global_unicast_addresses) >= 2:
            second_ipv6_address = global_unicast_addresses[1]
            second_ipv6_prefixlen = next(prefixlen for addr, prefixlen in ipv6_addresses if addr == second_ipv6_address)

            try:
                self.delete_ipv6_address_freebsd(interface_name, gateway, second_ipv6_address, second_ipv6_prefixlen)
            except Exception as e:
                print(f"Failed to delete IPv6 address {second_ipv6_address} on interface {interface_name}: {e}")
        else:
            print("Less than two global unicast IPv6 addresses found; no address deleted.")


    def delete_ipv6_address_freebsd(self, interface_name, gateway, ipv6_address, mask):
        full_address = f"{ipv6_address}/{mask}"
        subprocess.run(['ifconfig', interface_name, 'inet6', full_address, '-alias'], check=True)
        for ipv6_range in self.google_ipv6_ranges:
            current_routes = self.get_current_ipv6_routes_freebsd()
            if (ipv6_range, gateway) in current_routes:
                subprocess.run(['route', '-6', 'delete', ipv6_range, gateway], check=True)
            else:
                print(f"Route for {ipv6_range} via {gateway} does not exist, skipping deletion.")

    def run(self):
        parser = argparse.ArgumentParser(description="Run the IPv6 rotator.")
        parser.add_argument(
            "-r",
            "--ipv6range",
            required=True,
            help="Example: --ipv6range=2001:1:1::/64",
        )
        parser.add_argument(
            "--skip-root",
            required=False,
            dest='skip_root_check',
            action=argparse.BooleanOptionalAction,
            help="Example: --skip-root for skipping root check",
        )
        args = parser.parse_args(sys.argv[2:])

        if os.geteuid() != 0 and not args.skip_root_check:
            sys.exit(
                "[Error] Please run this script as root! It needs root privileges."
            )

        self.check_ipv6_connectivity()

        # calculate random IPv6 from the configured subnet

        seed()
        ipv6_network = IPv6Network(args.ipv6range)
        random_ipv6_address = str(
            IPv6Address(
                ipv6_network.network_address
                + getrandbits(ipv6_network.max_prefixlen - ipv6_network.prefixlen)
            )
        )

        # get default network interface for IPv6

        try:
            route_info = self.get_route_freebsd()
            if route_info is None:
                sys.exit("[Error] No default IPv6 route found.")
            default_interface_gateway = route_info['gateway']
            default_interface_name = route_info['interface_name']
            try:
                self.delete_previous_alias_freebsd(default_interface_name, default_interface_gateway)
                self.add_ipv6_address_freebsd(default_interface_name, default_interface_gateway, random_ipv6_address, ipv6_network.prefixlen)
            except Exception as e:
                sys.exit(f"[Error] Failed to add the new random IPv6 address: {e}")
        except Exception as e:
            sys.exit(f"[Error] fail: {e}")


if __name__ == "__main__":
    SmartIPv6Rotator()
