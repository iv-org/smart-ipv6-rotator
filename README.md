# Smart IPv6 Rotator

Smart IPv6 Rotator is a command-line tool designed to rotate IPv6 addresses for specific subnets, enabling users to bypass restrictions on IPv6-enabled websites.

## Upgrading
If you are already running this script, please run `sudo python smart-ipv6-rotator.py clean` before upgrading it to avoid any issues.

## Requirements
- At least Python 3.9
- IPv6 on your server
- Invidious works in IPv6
- Install these two python packages:
  - pyroute2
  - requests
- Your provider need to allow you to assign any arbitrary IPv6 address, your IPv6 space must be fully routed.  
  Usually the case but some do not support it like the popular cloud providers: AWS, Google Cloud, Oracle Cloud, Azure and more.

## How to setup (very simple tutorial for Google)
Full detailed documentation: https://docs.invidious.io/ipv6-rotator/

1. Git clone the repository somewhere.
2. Find your IPv6 subnet. If you do not know it, you can use a tool like http://www.gestioip.net/cgi-bin/subnet_calculator.cgi
3. Run once the script using `sudo python smart-ipv6-rotator.py run --ipv6range=YOURIPV6SUBNET/64`
4. If everything went well then configure a cron to periodically rotate your IPv6 range.
   Twice a day (noon and midnight) is enough for YouTube servers. Also at the reboot of the server!  
   Example crontab (`crontab -e -u root`):
   ```
   @reboot sleep 30s && python smart-ipv6-rotator.py run --cron --ipv6range=YOURIPV6SUBNET/64
   0 */12 * * * python smart-ipv6-rotator.py run --cron --ipv6range=YOURIPV6SUBNET/64
   ```  
   The `sleep` command is used in case your network takes too much time time to be ready.

## Docker image
https://quay.io/repository/invidious/smart-ipv6-rotator

## How to clean the configuration done by the script
```
sudo python smart-ipv6-rotator.py clean
```

Only works if the script did not crash. But in case of a crash, in most case the system should auto rollback the changes.

## Usage

```plaintext
smart-ipv6-rotator.py [-h] {run,clean-one,clean} ...
```

### Options

- `-h, --help`: Display the help message and exit.

### Subcommands

1. `run`: Run the IPv6 rotator process.
2. `clean-one`: Clean your system for a given service / IPv6 ranges.
3. `clean`: Clean all configurations made by this script.

---

### `run` Subcommand

```plaintext
smart-ipv6-rotator.py run [-h] [--services {google}] [--external-ipv6-ranges EXTERNAL_IPV6_RANGES] [--skip-root] [--no-services] --ipv6range IPV6RANGE
```

#### Options

- `-h, --help`: Display the help message and exit.
- `--services {google}`: Define IPV6 ranges of popular services (e.g., --services google, twitter, reddit).
- `--external-ipv6-ranges EXTERNAL_IPV6_RANGES`: Manually define external IPV6 ranges to rotate for.
- `--skip-root`: Skip root check.
- `--no-services`: Completely disable the --services flag.
- `--ipv6range IPV6RANGE`: Your IPV6 range (e.g., 2407:7000:9827:4100::/64).
- `--cron`: Do not check if the IPv6 address configured will work properly. Useful for CRON and when you know that the IPv6 range is correct.
- `--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}`: Sets log level

---

### `clean` Subcommand

```plaintext
smart-ipv6-rotator.py clean [-h] [--skip-root]
```

#### Options

- `-h, --help`: Display the help message and exit.
- `--skip-root`: Skip root check.
- `--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}`: Sets log level

---

### `clean-one` Subcommand

```plaintext
smart-ipv6-rotator.py clean-one [-h] [--services {google}] [--external-ipv6-ranges EXTERNAL_IPV6_RANGES] [--skip-root] [--no-services]
```

#### Options

- `-h, --help`: Display the help message and exit.
- `--services {google}`: Define IPV6 ranges of popular services (e.g., --services google, twitter).
- `--external-ipv6-ranges EXTERNAL_IPV6_RANGES`: Manually define external IPV6 ranges to rotate for.
- `--skip-root`: Skip root check.
- `--no-services`: Completely disable the --services flag.
- `--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}`: Sets log level

---


## Why does this need root privileges?

You can only modify the network configuration of your server using root privileges.  
The attack surface of this script is very limited as it is not running in the background, it's a one shot script.

## How does this script work?
1. First it check that you have IPv6 connectivity.
2. It automatically find the default IPv6 gateway and automatically generate a random IPv6 address from the IPv6 subnet that you configured.
3. It adds the random IPv6 address to the network interface.
4. It configures route for only using that new random IPv6 address for the specific IPv6 subnets (Google ipv6 ranges by default).  
   This way your current ipv6 network configuration is untouched and any change done by the script is temporary.

## TODO (priority)
### High
- [x] Docker image for easier use.
- [x] Allow to configure your IPv6 subnets yourself. (Could be used for other projects)
- [x] Better handle in case of errors in configuring IPv6 routes. Rollback the changes automatically
- [ ] Allow to specify a specific network interface + ipv6 gateway instead of automatically discovering it.
### Medium
- [ ] Arg for spit out the IPv6 subnet of the current default ipv6 address instead of saying to use gestioip.net tool.
- [ ] In most time, adding the new random IPv6 will take precedence over the existing IPv6. This may not be the expected behavior.
### Low
- [ ] Argument for testing if the setup will work without permanently do any modification.
- [X] Allow to remove debug info
- [ ] Maybe not depend on icanhazip? Send requests in HTTPS?
