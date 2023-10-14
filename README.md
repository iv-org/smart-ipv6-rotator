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
5. If everything went well then configure a cron for periodically rotate your IPv6 range.
   Twice a day (noon and midnight) is enough for YouTube servers. Also at the reboot of the server!

# How to clean the configuration done by the script
```
sudo python smart-ipv6-rotator.py clean
```

Only works if the script did not crash. But in case of a crash, in most case the system should auto rollback the changes.

# Why does this need root privileges?

You can only modify the network configuration of your server using root privileges.  
The attack surface of this script is very limited as it is not running in the background, it's a one shot script.

# How does this script work?
1. First it check that you have IPv6 connectivity.
2. It automatically find the default IPv6 gateway and automatically generate a random IPv6 address from the IPv6 subnet that you configured.
3. It adds the random IPv6 address to the network interface.
4. It configures route for only using that new random IPv6 address for the specific IPv6 subnets (Google ipv6 ranges by default).
   This way you current ipv6 network configuration is untouched.

# TODO (priority)
## High
- [ ] Allow to configure your IPv6 subnets yourself. (Could be used for other projects)
- [x] Better handle in case of errors in configuring IPv6 routes. Rollback the changes automatically
- [ ] Allow to specify a specific network interface + ipv6 gateway instead of automatically discovering it.
## Medium
- [ ] Arg for spit out the IPv6 subnet of the current default ipv6 address instead of saying to use gestioip.net tool.
## Low
- [ ] Argument for testing if the setup will work without permanently do any modification.
- [ ] Allow to remove debug info
- [ ] Maybe not depend on icanhazip? Send requests in HTTPS?