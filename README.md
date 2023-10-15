# Requirements
- IPv6 on your server
- Invidious works in IPv6
- Install these two python packages:
  - pyroute2
  - requests
- Your provider need to allow you to assign any arbitrary IPv6 address, your IPv6 space must be fully routed.
  Usually the case but some do not support it like the popular cloud providers: AWS, Google Cloud, Oracle Cloud, Azure and more.

# How to setup (very simple tutorial)

Full detailed documentation: https://docs.invidious.io/ipv6-rotator/

1. Git clone the repository somewhere.
2. Find your IPv6 subnet. If you do not know it, you can use a tool like http://www.gestioip.net/cgi-bin/subnet_calculator.cgi
3. Run once the script using `sudo python smart-ipv6-rotator.py run --ipv6range=YOURIPV6SUBNET/64`
4. If everything went well then configure a cron to periodically rotate your IPv6 range.
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
- [ ] Docker image for easier use.
- [ ] Allow to configure your IPv6 subnets yourself. (Could be used for other projects)
- [x] Better handle in case of errors in configuring IPv6 routes. Rollback the changes automatically
- [ ] Allow to specify a specific network interface + ipv6 gateway instead of automatically discovering it.
## Medium
- [ ] Arg for spit out the IPv6 subnet of the current default ipv6 address instead of saying to use gestioip.net tool.
- [ ] In most time, adding the new random IPv6 will take precedence over the existing IPv6. This may not be the expected behavior.
## Low
- [ ] Argument for testing if the setup will work without permanently do any modification.
- [ ] Allow to remove debug info
- [ ] Maybe not depend on icanhazip? Send requests in HTTPS?