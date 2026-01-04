#!/usr/bin/env python3
"""
MTN MF935 MiFi USSD Terminal
Interactive USSD session via command line.

Usage:
    python3 mifi_ussd.py                  # Interactive mode
    python3 mifi_ussd.py "*312*567#"      # Send specific USSD code
    python3 mifi_ussd.py --data           # Preset: data plan menu (*312*567#)
"""

import requests
import hashlib
import time
import argparse
import signal
import sys


class MiFiUSSD:
    # USSD status codes
    STATUS_PROCESSING = "15"
    STATUS_READY = "16"
    STATUS_NO_SERVICE = "1"
    STATUS_NETWORK_TERMINATED = "2"
    STATUS_TIMEOUT = ["3", "unknown"]
    STATUS_CARRIER_TIMEOUT = "4"  # Carrier timeout - may need retry or session ended
    STATUS_RETRY = "10"
    STATUS_CANCELLED = "13"
    STATUS_NOT_SUPPORTED = "41"
    STATUS_UNSUPPORTED = "99"

    def __init__(self, host="192.168.0.1", password="admin", debug=False):
        self.base_url = f"http://{host}"
        self.password = password
        self.session = requests.Session()
        self.session_active = False
        self.debug = debug

    def _get_cmd(self, cmd, extra_params=None):
        """Send a GET command to the device."""
        params = {
            "cmd": cmd,
            "_": str(int(time.time() * 1000))
        }
        if extra_params:
            params.update(extra_params)

        url = f"{self.base_url}/goform/goform_get_cmd_process"
        headers = {"Referer": f"{self.base_url}/index.html"}

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"Error: {e}")
            return None

    def _post_cmd(self, data):
        """Send a POST command to the device."""
        url = f"{self.base_url}/goform/goform_set_cmd_process"
        headers = {
            "Referer": f"{self.base_url}/index.html",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            resp = self.session.post(url, data=data, headers=headers, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_login_token(self):
        """Get the login token (LD) from device."""
        result = self._get_cmd("LD")
        if result and "LD" in result:
            return result["LD"]
        return None

    def login(self):
        """Authenticate with the device using ZTE MF935 algorithm."""
        token = self.get_login_token()

        if not token:
            print("Error: Could not get login token (LD)")
            return False

        # ZTE MF935: SHA256(SHA256(password) + LD) - uppercase hex
        sha256_password = hashlib.sha256(self.password.encode()).hexdigest().upper()
        final_password = hashlib.sha256((sha256_password + token).encode()).hexdigest().upper()

        data = {
            "isTest": "false",
            "goformId": "LOGIN",
            "password": final_password
        }

        result = self._post_cmd(data)

        if result:
            error_code = result.get("result")
            if error_code == "0":
                print("Login successful!")
                return True
            elif error_code == "3":
                print("Login failed: Wrong password")
            elif error_code == "4":
                print("Login failed: Account locked! Please reboot device.")
            else:
                print(f"Login failed: Error code {error_code}")

        return False

    def decode_ussd_response(self, hex_data):
        """Decode hex-encoded USSD response to readable text."""
        if not hex_data:
            return ""

        try:
            # USSD responses are typically hex-encoded UTF-16BE
            # Each character is 4 hex digits
            text = ""
            for i in range(0, len(hex_data), 4):
                if i + 4 <= len(hex_data):
                    char_code = int(hex_data[i:i+4], 16)
                    if char_code > 0:
                        text += chr(char_code)
            return text
        except Exception as e:
            # If decoding fails, return raw data
            return hex_data

    def send_ussd(self, code):
        """Send initial USSD code."""
        print(f"Sending USSD: {code}")

        data = {
            "isTest": "false",
            "goformId": "USSD_PROCESS",
            "USSD_operator": "ussd_send",
            "USSD_send_number": code
        }

        result = self._post_cmd(data)

        if result and result.get("result") == "success":
            self.session_active = True
            return True
        else:
            print(f"Failed to send USSD: {result}")
            return False

    def poll_response(self, timeout=30, poll_interval=0.5):
        """Poll for USSD response. Returns immediately when ready."""
        print("Waiting for response...", end="", flush=True)

        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout:
            result = self._get_cmd("ussd_write_flag")

            if not result:
                print("\nError: Failed to poll status")
                return None

            status = result.get("ussd_write_flag", "")
            
            # Debug output
            if self.debug and status != last_status:
                print(f"\n[DEBUG] ussd_write_flag={status}", end="", flush=True)
                last_status = status

            if status == self.STATUS_READY:
                print()  # New line after dots
                return "ready"

            elif status == self.STATUS_NO_SERVICE:
                print("\nError: No service")
                return "no_service"

            elif status == self.STATUS_NETWORK_TERMINATED:
                print("\nSession terminated by network")
                return "terminated"

            elif status in self.STATUS_TIMEOUT:
                print("\nTimeout waiting for response")
                return "timeout"
            
            elif status == self.STATUS_CARRIER_TIMEOUT:
                # Carrier timeout - session likely ended, try to get response
                print("\nCarrier timeout")
                return "carrier_timeout"

            elif status == self.STATUS_RETRY:
                print("\nNetwork busy, please retry")
                return "retry"

            elif status == self.STATUS_CANCELLED:
                print("\nSession cancelled")
                return "cancelled"

            elif status == self.STATUS_NOT_SUPPORTED:
                print("\nOperation not supported")
                return "not_supported"

            elif status == self.STATUS_UNSUPPORTED:
                print("\nUSSD not supported")
                return "unsupported"
            
            elif status == "0" or status == "":
                # Session may have ended - try to get response
                print()
                if self.debug:
                    print("[DEBUG] Status 0 or empty - session may have ended")
                return "ended"

            elif status == self.STATUS_PROCESSING:
                # Still processing, continue polling
                if not self.debug:
                    print(".", end="", flush=True)

            time.sleep(poll_interval)

        print("\nTimeout: No response within 30 seconds")
        return "timeout"

    def get_response(self):
        """Get and decode USSD response."""
        result = self._get_cmd("ussd_data_info")

        if not result:
            return None, None

        ussd_data = result.get("ussd_data", "")
        ussd_action = result.get("ussd_action", "0")

        decoded_text = self.decode_ussd_response(ussd_data)

        # ussd_action: "0" = session ended, "1" = session continues (expecting reply)
        session_continues = ussd_action == "1"

        return decoded_text, session_continues

    def reply(self, text):
        """Reply to USSD prompt."""
        data = {
            "isTest": "false",
            "goformId": "USSD_PROCESS",
            "USSD_operator": "ussd_reply",
            "USSD_reply_number": text
        }

        result = self._post_cmd(data)

        if result and result.get("result") == "success":
            return True
        else:
            print(f"Failed to send reply: {result}")
            return False

    def cancel(self):
        """Cancel current USSD session."""
        if not self.session_active:
            return

        print("\nCancelling USSD session...")

        data = {
            "isTest": "false",
            "goformId": "USSD_PROCESS",
            "USSD_operator": "ussd_cancel"
        }

        result = self._post_cmd(data)

        if result and result.get("result") == "success":
            # Wait for cancellation to complete
            for _ in range(10):
                status_result = self._get_cmd("ussd_write_flag")
                if status_result and status_result.get("ussd_write_flag") == self.STATUS_CANCELLED:
                    print("Session cancelled.")
                    break
                time.sleep(0.5)

        self.session_active = False


def print_response_box(text):
    """Print response in a formatted box."""
    if not text:
        print("(Empty response)")
        return

    lines = text.strip().split('\n')
    max_len = max(len(line) for line in lines) if lines else 40
    max_len = max(max_len, 40)

    print()
    print("=" * (max_len + 4))
    for line in lines:
        print(f"  {line}")
    print("=" * (max_len + 4))
    print()


def main():
    parser = argparse.ArgumentParser(
        description="MTN MF935 MiFi USSD Terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 mifi_ussd.py                  # Interactive mode
    python3 mifi_ussd.py "*312*567#"      # Send specific USSD code
    python3 mifi_ussd.py --data           # Preset: data plan menu
        """
    )
    parser.add_argument("code", nargs="?", help="USSD code to send (e.g., *312*567#)")
    parser.add_argument("--host", default="192.168.0.1", help="MiFi IP address")
    parser.add_argument("--password", default="admin", help="Admin password")
    parser.add_argument("--data", action="store_true", help="Preset: data plan menu (*312*567#)")
    parser.add_argument("--balance", action="store_true", help="Preset: airtime balance (*310#)")
    parser.add_argument("--data-balance", action="store_true", help="Preset: data balance via SMS (*323#)")
    parser.add_argument("--debug", action="store_true", help="Show debug info")

    args = parser.parse_args()

    # Determine USSD code
    ussd_code = None
    if args.data:
        ussd_code = "*312*567#"
    elif args.balance:
        ussd_code = "*310#"
    elif args.data_balance:
        ussd_code = "*323#"
    elif args.code:
        ussd_code = args.code
    else:
        # Interactive: prompt for code
        ussd_code = input("Enter USSD code (e.g., *312*567#): ").strip()
        if not ussd_code:
            print("No code entered. Exiting.")
            return

    # Initialize USSD handler
    ussd = MiFiUSSD(host=args.host, password=args.password, debug=args.debug)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        ussd.cancel()
        print("\nExiting.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Login
    if not ussd.login():
        print("Failed to login. Exiting.")
        return

    # Send initial USSD code
    if not ussd.send_ussd(ussd_code):
        return

    # Main interaction loop
    while True:
        # Poll for response
        status = ussd.poll_response(timeout=30, poll_interval=0.5)

        # Handle timeout/ended - try to get any pending response
        if status in ["ended", "timeout", "terminated", "carrier_timeout"]:
            response_text, _ = ussd.get_response()
            if response_text and response_text.strip():
                print_response_box(response_text)
            if status == "carrier_timeout":
                print("Carrier ended the session. Check SMS for confirmation.")
            else:
                print("Session ended.")
            ussd.session_active = False
            break
        elif status != "ready":
            ussd.session_active = False
            break

        # Get and display response
        response_text, session_continues = ussd.get_response()
        print_response_box(response_text)

        if not session_continues:
            print("Session ended.")
            ussd.session_active = False
            break

        # Prompt for reply
        try:
            user_input = input("Enter reply (or 'q' to cancel): ").strip()
        except EOFError:
            ussd.cancel()
            break

        if user_input.lower() == 'q':
            ussd.cancel()
            break

        if not user_input:
            print("No input. Use 'q' to cancel or enter a reply.")
            continue

        # Send reply
        if not ussd.reply(user_input):
            print("Failed to send reply.")
            break


if __name__ == "__main__":
    main()
