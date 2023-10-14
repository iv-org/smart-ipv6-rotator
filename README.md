# Requirements
- IPv6 on your server
- Invidious works in IPv6
- Install these two python packages:
  - pyroute2
  - requests

# How to setup (very simple tutorial for the moment)
1. Git clone the repository somewhere
2. Copy the file `config.py.example` to `config.py`.
3. Change the `ipv6_subnet` to your IPv6 subnet. If you do not know it, you can use a tool like http://www.gestioip.net/cgi-bin/subnet_calculator.cgi
4. Run once the script using `sudo python smart-ipv6-rotator.py run`
5. If everything went well then configure a cron for periodically rotate your IPv6 range. Once per day is enough for YouTube servers.

# TODO
- Allow to configure your IPv6 subnets yourself. (Could be used for other projects)
- Better handle in case of errors in configuring IPv6 routes. Rollback the changes automatically
- Argument for testing if the setup will work without permanently do any modification.
- Allow to specify a specific network interface + ipv6 gateway instead of automatically discovering it.
- Arg for spit out the IPv6 subnet of the current default ipv6 address instead of saying to use gestioip.net tool.