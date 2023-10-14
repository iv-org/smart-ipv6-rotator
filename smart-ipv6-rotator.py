from runpy import run_path
import sys
import os
from random import seed, getrandbits, choice
from ipaddress import IPv6Network, IPv6Address
from time import sleep
from runpy import run_path


def module_not_found_helper(module_name):
    sys.exit(
        f"""[Error] Module '{module_name}' is not installed. please install it using your package manager.
        Debian/Ubuntu: sudo apt install python3-{module_name}
        RHEL/CentOS/Fedora: sudo dnf install python-{module_name}
        Other Linux distributions (probably): sudo yourpackagemanager install python-{module_name}"""
    )


try:
    from pyroute2 import IPDB
    from pyroute2 import IPRoute
except ModuleNotFoundError:
    module_not_found_helper("pyroute2")
try:
    import requests
except ModuleNotFoundError:
    module_not_found_helper("requests")

ip = IPDB()
iproute = IPRoute()

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


def check_ipv6_connectivity():
    try:
        requests.get("http://ipv6.icanhazip.com", timeout=5)
    except requests.exceptions.RequestException:
        sys.exit("[Error] You do not have IPv6 connectivity. This script can not work.")

    print("[INFO] You have IPv6 connectivity. Continuing.")


def clean_previous_setup(existing_settings):
    if (
        os.path.isfile(location_saved_config_ipv6_configured)
        or len(existing_settings) > 0
    ):
        settings = existing_settings
        if len(existing_settings) == 0:
            settings = run_path(location_saved_config_ipv6_configured)
        try:
            iproute.route(
                "del",
                dst=icanhazip_ipv6_address,
                prefsrc=settings["random_ipv6_address"],
                gateway=settings["gateway"],
                oif=settings["interface_index"],
            )
        except:
            print(
                "[Error] Failed to remove the test IPv6 subnet.\n"
                "        May be expected if the route were not yet configured and that was a cleanup due to an error."
            )

        try:
            for ipv6_range in google_ipv6_ranges:
                iproute.route(
                    "del",
                    dst=ipv6_range,
                    prefsrc=settings["random_ipv6_address"],
                    gateway=settings["gateway"],
                    oif=settings["interface_index"],
                )
        except:
            print(
                "[Error] Failed to remove the configured (Google) IPv6 subnets.\n"
                "        May be expected if the route were not yet configured and that was a cleanup due to an error."
            )

        try:
            iproute.addr(
                "del",
                settings["interface_index"],
                address=settings["random_ipv6_address"],
                mask=settings["random_ipv6_address_mask"],
            )
        except:
            print("[Error] Failed to remove the random IPv6 address, very unexpected!")

        print("[INFO] Finished cleaning up previous setup.")
        if len(existing_settings) == 0:
            os.remove(location_saved_config_ipv6_configured)

        print("[INFO] Waiting for the propagation in the Linux kernel.")
        sleep(6)
    else:
        print("[INFO] No cleanup of previous setup needed.")


if os.geteuid() != 0:
    sys.exit("[Error] Please run this script as root! It needs root privileges.")

if len(sys.argv) == 1:
    print("Args:\n- run: Run the script\n- clean: Clean the previous setup.\n")
    print(f"Example: python {sys.argv[0]} run")

elif sys.argv[1] == "clean":
    clean_previous_setup({})

elif sys.argv[1] == "run":
    check_ipv6_connectivity()

    clean_previous_setup({})

    try:
        settings = run_path("./config.py")
    except:
        sys.exit(
            "[ERROR] Unable to load the config file. Did you copy the config.py.example file?"
        )

    # calculate random IPv6 from the configured subnet

    seed()
    ipv6_network = IPv6Network(settings["ipv6_subnet"])
    print(ipv6_network.prefixlen)
    random_ipv6_address = str(
        IPv6Address(
            ipv6_network.network_address
            + getrandbits(ipv6_network.max_prefixlen - ipv6_network.prefixlen)
        )
    )

    # get default network interface for IPv6

    default_interface = iproute.route("get", dst=choice(google_ipv6_ranges))[0]
    default_interface_index = int(default_interface.get_attrs("RTA_OIF")[0])
    default_interface_gateway = str(default_interface.get_attrs("RTA_GATEWAY")[0])
    default_interface_name = ip.interfaces[default_interface_index]["ifname"]

    memory_settings = {
        "random_ipv6_address": random_ipv6_address,
        "random_ipv6_address_mask": ipv6_network.prefixlen,
        "gateway": default_interface_gateway,
        "interface_index": default_interface_index,
    }

    print(default_interface_index)
    print(random_ipv6_address)
    print(default_interface_name)
    print(ipv6_network.prefixlen)
    print(default_interface_gateway)

    try:
        iproute.addr(
            "add",
            default_interface_index,
            address=random_ipv6_address,
            mask=ipv6_network.prefixlen,
        )
    except Exception as e:
        clean_previous_setup(memory_settings)
        sys.exit(
            "[Error] Failed to add the new random IPv6 address. The setup did not work!\n"
            "         That's unexpected! Did you correctly configured the IPv6 subnet to use?\n"
            f"Exception:\n{e}"
        )
    # needed so that the linux kernel takes into account the new ipv6 address
    sleep(2)

    # test that the new ipv6 route works
    try:
        iproute.route(
            "add",
            dst=icanhazip_ipv6_address,
            prefsrc=random_ipv6_address,
            gateway=default_interface_gateway,
            oif=default_interface_index,
            priority=1,
        )
    except Exception as e:
        clean_previous_setup(memory_settings)
        sys.exit(
            "[Error] Failed to configure the test IPv6 route. The setup did not work!\n"
            f"Exception:\n{e}"
        )
    # needed so that the linux kernel takes into account the new ipv6 route
    sleep(2)
    try:
        check_new_ipv6_address = requests.get(
            f"http://[{icanhazip_ipv6_address}]",
            headers={"host": "ipv6.icanhazip.com"},
            timeout=5,
        )
        response_new_ipv6_address = check_new_ipv6_address.text.strip()
        if response_new_ipv6_address == random_ipv6_address:
            print("[INFO] Correctly using the new random IPv6 address, continuing.")
        else:
            clean_previous_setup(memory_settings)
            sys.exit(
                "[ERROR] The new random IPv6 is not used! The setup did not work!\n"
                "        That is very unexpected, check if your IPv6 routes do not have too much priority."
                f"Address used: {response_new_ipv6_address}"
            )
    except requests.exceptions.RequestException as e:
        clean_previous_setup(memory_settings)
        sys.exit(
            "[ERROR] Failed to send the request for checking the new IPv6 address! The setup did not work!\n"
            "        Your provider probably does not allow setting any arbitrary IPv6 address.\n"
            "        Or did you correctly configured the IPv6 subnet to use?\n"
            f"Exception:\n{e}"
        )

    # configure routes for ipv6 ranges of Google
    try:
        for ipv6_range in google_ipv6_ranges:
            iproute.route(
                "add",
                dst=ipv6_range,
                prefsrc=random_ipv6_address,
                gateway=default_interface_gateway,
                oif=default_interface_index,
                priority=1,
            )
    except Exception as e:
        clean_previous_setup(memory_settings)
        sys.exit(
            f"[Error] Failed to configure the test IPv6 route. The setup did not work!\n"
            f"Exception:\n{e}"
        )

    print("[INFO] Correctly configured the IPv6 routes for Google IPv6 ranges. Waiting for the propagation in the Linux kernel.")
    sleep(6)

    # saving configuration to a file for future cleanup
    file = open(location_saved_config_ipv6_configured, "w")
    file.write(
        'random_ipv6_address="%s"\nrandom_ipv6_address_mask=%s\ngateway="%s"\ninterface_index=%s'
        % (
            random_ipv6_address,
            ipv6_network.prefixlen,
            default_interface_gateway,
            default_interface_index,
        )
    )
    file.close()
