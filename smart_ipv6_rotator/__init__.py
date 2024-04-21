import os
from ipaddress import IPv6Address, IPv6Network
from math import exp
from random import choice, getrandbits, seed
from runpy import run_path
from time import sleep
from typing import Any, Callable

import click
import requests

from smart_ipv6_rotator.const import ICANHAZIP_IPV6_ADDRESS, IP, IPROUTE
from smart_ipv6_rotator.helpers import (
    PreviousConfigs,
    SavedRanges,
    check_ipv6_connectivity,
    clean_ranges,
    root_check,
    what_ranges,
)
from smart_ipv6_rotator.ranges import RANGES

SHARED_OPTIONS = [
    click.option(
        "--service",
        type=click.types.Choice(list(RANGES.keys())),
        required=False,
        help="IPV6 ranges of popular services.",
    ),
    click.option(
        "--ipv6-ranges",
        type=click.types.STRING,
        required=False,
        help="Manually define external IPV6 ranges to rotate for.",
    ),
    click.option(
        "--skip-root",
        required=False,
        type=click.types.BOOL,
        help="Example: --skip-root for skipping root check",
        default=False,
    ),
]


def add_options(options) -> Callable[..., Any]:
    def _add_options(func) -> Any:
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


@click.group()
def main() -> None:
    """IPv6 rotator for specific subnets - unblock restrictions on IPv6 enabled websites"""
    pass


@main.command()
@click.option(
    "--my-ipv6-range",
    required=True,
    help="Your IPV6 range. Example: --my-ipv6-rang=2001:1:1::/64",
)
@add_options(SHARED_OPTIONS)
def run(
    my_ipv6_range: str,
    skip_root: bool = False,
    service: str | None = None,
    ipv6_ranges: str | None = None,
) -> None:
    """Run the IPv6 rotator process."""

    root_check(skip_root)
    check_ipv6_connectivity()

    service_ranges = what_ranges(service, ipv6_ranges)

    clean_ranges(service_ranges, skip_root)

    seed()
    ipv6_network = IPv6Network(my_ipv6_range)
    random_ipv6_address = str(
        IPv6Address(
            ipv6_network.network_address
            + getrandbits(ipv6_network.max_prefixlen - ipv6_network.prefixlen)
        )
    )

    default_interface = IPROUTE.route("get", dst=choice(service_ranges))[0]  # type: ignore
    default_interface_index = int(default_interface.get_attrs("RTA_OIF")[0])
    default_interface_gateway = str(default_interface.get_attrs("RTA_GATEWAY")[0])
    default_interface_name = IP.interfaces[default_interface_index]["ifname"]

    memory_settings = {
        "random_ipv6_address": random_ipv6_address,
        "random_ipv6_address_mask": ipv6_network.prefixlen,
        "gateway": default_interface_gateway,
        "interface_index": default_interface_index,
        "interface_name": default_interface_name,
        "ipv6_subnet": my_ipv6_range,
    }

    # Save config now, will be cleaned if errors raised.
    PreviousConfigs(service_ranges).save(
        SavedRanges(**{**memory_settings, "ranges": service_ranges})
    )

    click.echo("[DEBUG] Debug info:")
    for key, value in memory_settings.items():
        click.echo(f"{key} --> {value}")

    try:
        IPROUTE.addr(
            "add",
            default_interface_index,
            address=random_ipv6_address,
            mask=ipv6_network.prefixlen,
        )
    except Exception as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[Error] Failed to add the new random IPv6 address. The setup did not work!\n"
            "        That's unexpected! Did you correctly configured the IPv6 subnet to use?\n"
            f"       Exception:\n{error}"
        )

    sleep(2)  # Need so that the linux kernel takes into account the new ipv6 route

    try:
        IPROUTE.route(
            "add",
            dst=ICANHAZIP_IPV6_ADDRESS,
            prefsrc=random_ipv6_address,
            gateway=default_interface_gateway,
            oif=default_interface_index,
            priority=1,
        )
    except Exception as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[Error] Failed to configure the test IPv6 route. The setup did not work!\n"
            f"       Exception:\n{error}"
        )

    sleep(2)

    try:
        check_new_ipv6_address = requests.get(
            f"http://[{ICANHAZIP_IPV6_ADDRESS}]",
            headers={"host": "ipv6.icanhazip.com"},
            timeout=5,
        )
    except requests.exceptions.RequestException as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[ERROR] Failed to send the request for checking the new IPv6 address! The setup did not work!\n"
            "        Your provider probably does not allow setting any arbitrary IPv6 address.\n"
            "        Or did you correctly configured the IPv6 subnet to use?\n"
            f"       Exception:\n{error}"
        )

    response_new_ipv6_address = check_new_ipv6_address.text.strip()
    if response_new_ipv6_address == random_ipv6_address:
        click.echo("[INFO] Correctly using the new random IPv6 address, continuing.")
    else:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[ERROR] The new random IPv6 is not used! The setup did not work!\n"
            "        That is very unexpected, check if your IPv6 routes do not have too much priority."
            f"       Address used: {response_new_ipv6_address}"
        )

    try:
        for ipv6_range in service_ranges:
            IPROUTE.route(
                "add",
                dst=ipv6_range,
                prefsrc=random_ipv6_address,
                gateway=default_interface_gateway,
                oif=default_interface_index,
                priority=1,
            )
    except Exception as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            f"[Error] Failed to configure the test IPv6 route. The setup did not work!\n"
            f"        Exception:\n{error}"
        )

    click.echo(
        f"[INFO] Correctly configured the IPv6 routes for IPv6 ranges {service_ranges}.\n"
        "[INFO] Successful setup. Waiting for the propagation in the Linux kernel."
    )
    sleep(6)


@main.command()
@add_options(SHARED_OPTIONS)
def clean(
    skip_root: bool = False, service: str | None = None, ipv6_ranges: str | None = None
) -> None:
    """Clean your system for a given service / ipv6 ranges."""

    clean_ranges(what_ranges(service, ipv6_ranges), skip_root)
