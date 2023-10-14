from runpy import run_path
import sys
import os
from random import seed, getrandbits, choice
from ipaddress import IPv6Network, IPv6Address
from time import sleep
from runpy import run_path

def module_not_found_helper(module_name):
    sys.exit(f"""[Error] Module '{module_name}' is not installed. please install it using your package manager.
        Debian/Ubuntu: sudo apt install python3-{module_name}
        RHEL/CentOS/Fedora: sudo dnf install python-{module_name}
        Other Linux distributions (probably): sudo yourpackagemanager install python-{module_name}""")
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
        requests.get("http://ipv6.icanhazip.com")
    except requests.exceptions.RequestException:
        sys.exit("[Error] You do not have IPv6 connectivity. This script can not work.")

    print("[INFO] You have IPv6 connectivity. Continuing.")


def clean_previous_setup():
    if os.path.isfile(location_saved_config_ipv6_configured):
        settings = run_path(location_saved_config_ipv6_configured)
        iproute.route(
            "del",
            dst=icanhazip_ipv6_address,
            prefsrc=settings["random_ipv6_address"],
            gateway=settings["gateway"],
            oif=settings["interface_index"],
        )
        for ipv6_range in google_ipv6_ranges:
            iproute.route(
                "del",
                dst=ipv6_range,
                prefsrc=settings["random_ipv6_address"],
                gateway=settings["gateway"],
                oif=settings["interface_index"],
            )
        iproute.addr(
            "del",
            settings["interface_index"],
            address=settings["random_ipv6_address"],
            mask=settings["random_ipv6_address_mask"],
        )
        print("[INFO] Finished cleaning up previous setup.")
        os.remove(location_saved_config_ipv6_configured)
    else:
        print("[INFO] No cleanup of previous setup needed.")


if os.geteuid() != 0:
    sys.exit("[Error] Please run this script as root! It needs root privileges.")

if len(sys.argv) == 1:
    print("Args:\n- run: Run the script\n- clean: Clean the previous setup.\n")
    print(f"Example: python {sys.argv[0]} run")

elif sys.argv[1] == "clean":
    clean_previous_setup()

elif sys.argv[1] == "run":
    check_ipv6_connectivity()

    clean_previous_setup()

    settings = run_path("./config.py")

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

    print(default_interface_index)
    print(random_ipv6_address)
    print(default_interface_name)
    print(ipv6_network.prefixlen)
    print(default_interface_gateway)

    iproute.addr(
        "add",
        default_interface_index,
        address=random_ipv6_address,
        mask=ipv6_network.prefixlen,
    )
    # needed so that the linux kernel takes into account the new ipv6 address
    sleep(2)

    # test that the new ipv6 route works
    iproute.route(
        "add",
        dst=icanhazip_ipv6_address,
        prefsrc=random_ipv6_address,
        gateway=default_interface_gateway,
        oif=default_interface_index,
        priority=1,
    )
    # needed so that the linux kernel takes into account the new ipv6 route
    sleep(2)
    try:
        check_new_ipv6_address = requests.get(
            f"http://[{icanhazip_ipv6_address}]", headers={"host": "ipv6.icanhazip.com"}
        )
        response_new_ipv6_address = check_new_ipv6_address.text.strip()
        if response_new_ipv6_address == random_ipv6_address:
            print("[INFO] Correctly using the new random IPv6 address, continuing.")
        else:
            print(
                f"[ERROR] The new random IPv6 is not used! Address used: {response_new_ipv6_address}"
            )
    except requests.exceptions.RequestException:
        print("[ERROR] Failed to send the request for checking the new IPv6 address!")

    # configure routes for ipv6 ranges of Google
    for ipv6_range in google_ipv6_ranges:
        iproute.route(
            "add",
            dst=ipv6_range,
            prefsrc=random_ipv6_address,
            gateway=default_interface_gateway,
            oif=default_interface_index,
            priority=1,
        )

    print("[INFO] Correctly configured the IPv6 routes for Google IPv6 ranges.")

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
