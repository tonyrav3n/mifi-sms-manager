# MiFi SMS Manager & USSD Terminal

Python tools to manage SMS messages and run USSD commands on ZTE MF935 MiFi devices (MTN/Airtel 4G).

## Tools

| Tool | Description |
|------|-------------|
| `mifi_sms_manager.py` | Manage SMS messages (list, delete) |
| `mifi_ussd.py` | Interactive USSD terminal (buy data, check balance) |

## Problem

The ZTE MF935 MiFi has a bug where the web interface hangs or fails to load when the SMS inbox is full. The only workaround is usually a factory reset, which is inconvenient.

## Solution

These scripts connect to your MiFi's API and:
- Delete SMS messages programmatically, bypassing the buggy web interface
- Run USSD commands interactively to buy data plans, check balance, etc.

## Requirements

- Python 3.6+
- `requests` library

```bash
pip install requests
```

---

## SMS Manager

### Features

- List all SMS messages (device + SIM storage)
- Delete all SMS messages
- Run diagnostics to discover API endpoints
- Supports both device memory and SIM card storage

### Usage

```bash
# Delete all SMS messages
python3 mifi_sms_manager.py --action delete

# List all SMS messages
python3 mifi_sms_manager.py --action list

# Run diagnostics
python3 mifi_sms_manager.py --action diagnose

# Skip login (if account is locked)
python3 mifi_sms_manager.py --action delete --skip-login
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `192.168.0.1` | MiFi IP address |
| `--password` | `admin` | Admin password |
| `--action` | `diagnose` | Action: `delete`, `list`, `diagnose` |
| `--skip-login` | false | Skip login attempt |

---

## USSD Terminal

### Features

- Send USSD codes interactively
- Navigate multi-step USSD menus
- Preset shortcuts for common operations
- Debug mode to see raw status codes
- Graceful Ctrl+C handling

### Usage

```bash
# Interactive mode (prompts for USSD code)
python3 mifi_ussd.py

# Send specific USSD code
python3 mifi_ussd.py "*312*567#"

# Preset: Data plan menu
python3 mifi_ussd.py --data

# Preset: Check airtime balance
python3 mifi_ussd.py --balance

# Preset: Check data balance (sends SMS)
python3 mifi_ussd.py --data-balance

# Debug mode (show raw status codes)
python3 mifi_ussd.py --debug --data
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `192.168.0.1` | MiFi IP address |
| `--password` | `admin` | Admin password |
| `--data` | - | Preset: send `*312*567#` (data plan menu) |
| `--balance` | - | Preset: send `*310#` (airtime balance) |
| `--data-balance` | - | Preset: send `*323#` (data balance via SMS) |
| `--debug` | false | Show debug info |

### Example Session

```
$ python3 mifi_ussd.py --data
Login successful!
Sending USSD: *312*567#
Waiting for response........

============================================
  1 My Area
  2 Data Plans
  3 10GB @N3000
  4 5GB @N1500
  5 3GB @N750
  ...
============================================

Enter reply (or 'q' to cancel): 1
Waiting for response.....

============================================
  MY AREA OFFER
  1 500MB @N100(1day)
  2 1.25GB @N200(7days)
  3 2GB @N300(7days)
  4 3.2GB @N500(30days)
============================================

Enter reply (or 'q' to cancel): 2
...
```

---

## Automation

To prevent inbox overflow, schedule automatic SMS deletion using cron:

```bash
# Edit crontab
crontab -e

# Add this line to run every 6 hours
0 */6 * * * /usr/bin/python3 /path/to/mifi_sms_manager.py --action delete >> /var/log/mifi-sms.log 2>&1
```

## Tested Devices

- ZTE MF935 (MTN/Airtel 4G MiFi)

May also work with other ZTE MiFi devices:
- ZTE MF920
- ZTE MF927U
- ZTE MF90+

## API Reference

The scripts use the following ZTE API endpoints:

### SMS Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/goform/goform_get_cmd_process?cmd=sms_capacity_info` | GET | Get SMS storage capacity |
| `/goform/goform_get_cmd_process?cmd=sms_data_total` | GET | List SMS messages |
| `/goform/goform_set_cmd_process` | POST | Delete SMS (goformId=DELETE_SMS) |

### USSD Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/goform/goform_set_cmd_process` | POST | Send USSD (goformId=USSD_PROCESS) |
| `/goform/goform_get_cmd_process?cmd=ussd_write_flag` | GET | Poll USSD status |
| `/goform/goform_get_cmd_process?cmd=ussd_data_info` | GET | Get USSD response |

### Authentication

The ZTE MF935 uses a token-based login with SHA256 hashing:
```
password = SHA256(SHA256(password) + LD_token)  # uppercase hex
```

## Troubleshooting

### "Login failed: Wrong password"
- Ensure the password is correct (default: `admin`)
- If the browser is logged in, logout first or use `--skip-login`

### "Account locked"
- Reboot the MiFi device and wait for it to reconnect

### "Carrier timeout" during USSD
- This usually means the carrier ended the session
- Check SMS for confirmation or error messages

### No messages found
Try running `--action diagnose` to discover your device's specific API format.

### Connection refused
Make sure you're connected to the MiFi's WiFi network.

## License

MIT License - Use at your own risk.

## Contributing

Found a bug or want to add support for another device? PRs welcome!
