# MiFi SMS Manager

A Python tool to manage SMS messages on ZTE MF935 MiFi devices (MTN 4G).

## Problem

The ZTE MF935 MiFi has a bug where the web interface hangs or fails to load when the SMS inbox is full. The only workaround is usually a factory reset, which is inconvenient.

## Solution

This script connects to your MiFi's API and deletes SMS messages programmatically, bypassing the buggy web interface.

## Features

- List all SMS messages (device + SIM storage)
- Delete all SMS messages
- Run diagnostics to discover API endpoints
- Works without login for most operations
- Supports both device memory and SIM card storage

## Requirements

- Python 3.6+
- `requests` library

```bash
pip install requests
```

## Usage

```bash
# Delete all SMS messages
python3 mifi_sms_manager.py --action delete

# List all SMS messages
python3 mifi_sms_manager.py --action list

# Run diagnostics
python3 mifi_sms_manager.py --action diagnose
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `192.168.0.1` | MiFi IP address |
| `--password` | `admin` | Admin password |
| `--action` | `diagnose` | Action: `delete`, `list`, `diagnose` |

### Examples

```bash
# Delete SMS on a MiFi with custom IP
python3 mifi_sms_manager.py --host 192.168.1.1 --action delete

# List SMS with custom password
python3 mifi_sms_manager.py --password mypassword --action list
```

## Automation

To prevent inbox overflow, schedule automatic deletion using cron:

```bash
# Edit crontab
crontab -e

# Add this line to run every 6 hours
0 */6 * * * /usr/bin/python3 /path/to/mifi_sms_manager.py --action delete >> /var/log/mifi-sms.log 2>&1
```

## Tested Devices

- ZTE MF935 (MTN 4G MiFi)

May also work with other ZTE MiFi devices:
- ZTE MF920
- ZTE MF927U
- ZTE MF90+

## API Reference

The script uses the following ZTE API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/goform/goform_get_cmd_process?cmd=sms_capacity_info` | GET | Get SMS storage capacity |
| `/goform/goform_get_cmd_process?cmd=sms_data_total` | GET | List SMS messages |
| `/goform/goform_set_cmd_process` | POST | Delete SMS (goformId=DELETE_SMS) |

## Troubleshooting

### "Login failed" messages
This is normal - most SMS operations work without authentication.

### No messages found
Try running `--action diagnose` to discover your device's specific API format.

### Connection refused
Make sure you're connected to the MiFi's WiFi network.

## License

MIT License - Use at your own risk.

## Contributing

Found a bug or want to add support for another device? PRs welcome!
