import argparse
import logging
import sys
from dataclasses import asdict
from ipaddress import IPv6Address, IPv6Network
from os import path
from random import choice, getrandbits, seed
from time import sleep
from typing import Any, Callable

import requests

from smart_ipv6_rotator.const import (
    ICANHAZIP_IPV6_ADDRESS,
    IP,
    IPROUTE,
    LEGACY_CONFIG_FILE,
    LOG_LEVELS_NAMES,
    LOGGER,
)
from smart_ipv6_rotator.helpers import (
    PreviousConfig,
    SavedRanges,
    check_ipv6_connectivity,
    clean_ipv6_check,
    clean_ranges,
    previous_configs,
    root_check,
    what_ranges,
)
from smart_ipv6_rotator.ranges import RANGES

SHARED_OPTIONS = [
    (
        "--services",
        {
            "type": str,
            "choices": list(RANGES.keys()),
            "default": "google",
            "help": "IPV6 ranges of popular services. Example: --services google,twitter,reddit",
        },
    ),
    (
        "--external-ipv6-ranges",
        {
            "type": str,
            "help": "Manually define external IPV6 ranges to rotate for.",
        },
    ),
    (
        "--skip-root",
        {
            "action": "store_true",
            "help": "Example: --skip-root for skipping root check",
        },
    ),
    (
        "--no-services",
        {
            "action": "store_true",
            "help": "Completely disables the --services flag.",
        },
    ),
    (
        "--log-level",
        {
            "type": str,
            "choices": LOG_LEVELS_NAMES
            + [log_level.lower() for log_level in LOG_LEVELS_NAMES],
            "default": "DEBUG",
            "help": f"Sets log level, can be {','.join(LOG_LEVELS_NAMES)}",
        },
    ),
]

logging.basicConfig(format="%(levelname)s:%(name)s:%(message)s")


def parse_args(func: Callable) -> Callable[..., Any]:
    def _parse_args(namespace: argparse.Namespace) -> Any:
        params = dict(namespace.__dict__)
        params.pop("subcommand")
        params.pop("func")

        if "log_level" in params:
            LOGGER.setLevel(params["log_level"].upper())
            params.pop("log_level")

        return func(**params)

    return _parse_args


@parse_args
def run(
    ipv6range: str,
    skip_root: bool = False,
    services: str | None = None,
    external_ipv6_ranges: str | None = None,
    no_services: bool = False,
    cron: bool = False,
) -> None:
    """Run the IPv6 rotator process."""

    if path.exists(LEGACY_CONFIG_FILE):
        LOGGER.error(
            "Legacy database format detected! Please run `python smart-ipv6-rotator.py clean` using the old version of this script.\nhttps://github.com/iv-org/smart-ipv6-rotator"
        )
        sys.exit()

    if cron is True:
        LOGGER.info(
            "Running without checking if the IPv6 address configured will work properly."
        )

    root_check(skip_root)
    check_ipv6_connectivity()

    service_ranges = what_ranges(services, external_ipv6_ranges, no_services)

    clean_ranges(service_ranges, skip_root)

    seed()
    ipv6_network = IPv6Network(ipv6range)
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

    saved_ranges = SavedRanges(
        random_ipv6_address=random_ipv6_address,
        random_ipv6_address_mask=ipv6_network.prefixlen,
        gateway=default_interface_gateway,
        interface_index=default_interface_index,
        interface_name=default_interface_name,
        ipv6_subnet=ipv6range,
        ranges=service_ranges,
    )

    # Save config now, will be cleaned if errors raised.
    PreviousConfig(service_ranges).save(saved_ranges)

    LOGGER.debug("Debug info:")
    for key, value in asdict(saved_ranges).items():
        LOGGER.debug(f"{key} --> {value}")

    try:
        IPROUTE.addr(
            "add",
            default_interface_index,
            address=random_ipv6_address,
            mask=ipv6_network.prefixlen,
        )
    except Exception as error:
        clean_ranges(service_ranges, skip_root)
        LOGGER.error(
            "Failed to add the new random IPv6 address. The setup did not work!\n"
            "That's unexpected! Did you correctly configure the IPv6 subnet to use?\n"
            f"Exception:\n{error}"
        )
        sys.exit()

    sleep(2)  # Need so that the linux kernel takes into account the new ipv6 route

    if cron is False:

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
            LOGGER.error(
                "Failed to configure the test IPv6 route. The setup did not work!\n"
                f"       Exception:\n{error}"
            )
            sys.exit()

        sleep(4)

        try:
            check_new_ipv6_address = requests.get(
                f"http://[{ICANHAZIP_IPV6_ADDRESS}]",
                headers={"host": "ipv6.icanhazip.com"},
                timeout=5,
            )
        except requests.exceptions.RequestException as error:
            clean_ranges(service_ranges, skip_root)
            LOGGER.error(
                "Failed to send the request for checking the new IPv6 address! The setup did not work!\n"
                "Your provider probably does not allow setting any arbitrary IPv6 address.\n"
                "Or did you correctly configure the IPv6 subnet to use?\n"
                f"Exception:\n{error}"
            )
            sys.exit()

        try:
            check_new_ipv6_address.raise_for_status()
        except requests.HTTPError:
            clean_ranges(service_ranges, skip_root)
            LOGGER.error(
                "icanhazip didn't return the expected status, possibly they are down right now."
            )
            sys.exit()

        response_new_ipv6_address = check_new_ipv6_address.text.strip()
        if response_new_ipv6_address == random_ipv6_address:
            LOGGER.info("Correctly using the new random IPv6 address, continuing.")
        else:
            clean_ranges(service_ranges, skip_root)
            LOGGER.error(
                "The new random IPv6 is not used! The setup did not work!\n"
                "That is very unexpected, check if your IPv6 routes do not have too much priority."
                f"Address used: {response_new_ipv6_address}"
            )
            sys.exit()

        clean_ipv6_check(saved_ranges)

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
        LOGGER.error(
            f"Failed to configure the service IPv6 route. The setup did not work!\n"
            f"Exception:\n{error}"
        )
        sys.exit()

    LOGGER.info(
        f"Correctly configured the IPv6 routes for IPv6 ranges {service_ranges}.\n"
        "Successful setup. Waiting for the propagation in the Linux kernel."
    )

    sleep(6)


@parse_args
def clean_one(
    skip_root: bool = False,
    services: str | None = None,
    external_ipv6_ranges: str | None = None,
    no_services: bool = False,
) -> None:
    """Clean your system for a given service / ipv6 ranges."""

    clean_ranges(what_ranges(services, external_ipv6_ranges, no_services), skip_root)


@parse_args
def clean(
    skip_root: bool = False,
) -> None:
    """Clean all configurations made by this script."""

    for config in previous_configs():
        clean_ranges(config.ranges, skip_root)


def main() -> None:
    """IPv6 rotator for specific subnets - unblock restrictions on IPv6 enabled websites"""
    parser = argparse.ArgumentParser(
        description="IPv6 rotator for specific subnets - unblock restrictions on IPv6 enabled websites"
    )
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand")

    run_parser = subparsers.add_parser("run", help="Run the IPv6 rotator process.")
    for flag, config in SHARED_OPTIONS:
        run_parser.add_argument(flag, **config)

    run_parser.add_argument(
        "--ipv6range",
        help="Your IPV6 range. Example: 2407:7000:9827:4100::/64",
        required=True,
    )
    run_parser.add_argument(
        "--cron",
        action="store_true",
        help="Disable checks for IPV6 address configured. Useful when being instantiated by CRON and the IPv6 range configured is correct.",
        required=False,
    )
    run_parser.set_defaults(func=run)

    clean_one_parser = subparsers.add_parser(
        "clean-one", help="Clean your system for a given service / ipv6 ranges."
    )
    for flag, config in SHARED_OPTIONS:
        clean_one_parser.add_argument(flag, **config)

    clean_one_parser.set_defaults(func=clean_one)

    clean_parser = subparsers.add_parser(
        "clean", help="Clean all configurations made by this script."
    )
    clean_parser.add_argument("--skip-root", action="store_true")
    clean_parser.set_defaults(func=clean)

    # Check if a command is being ran, otherwise print help.
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
