#!/usr/bin/env python3
"""
MTN MF935 MiFi SMS Manager
Deletes all SMS messages to prevent inbox overflow issues.
"""

import requests
import hashlib
import time
import json
import argparse

class MiFiSMSManager:
    def __init__(self, host="192.168.0.1", password="admin"):
        self.base_url = f"http://{host}"
        self.password = password
        self.session = requests.Session()
        self.token = None
    
    def _get_cmd(self, cmd, extra_params=None):
        """Send a GET command to the device."""
        params = {
            "isTest": "false",
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
        
        # Try alternative token commands
        for cmd in ["RD", "wa_inner_version", "cr_version"]:
            result = self._get_cmd(cmd)
            if result:
                print(f"Device info ({cmd}): {result}")
        return None

    def login(self):
        """Authenticate with the device."""
        # Get token for password hashing
        token = self.get_login_token()
        
        # Try different password hashing methods used by ZTE
        password_variants = [
            self.password,  # Plain password
            hashlib.sha256(self.password.encode()).hexdigest(),  # SHA256
            hashlib.md5(self.password.encode()).hexdigest(),  # MD5
        ]
        
        if token:
            # Hash with token
            password_variants.append(
                hashlib.sha256((self.password + token).encode()).hexdigest()
            )
            password_variants.append(
                hashlib.md5((self.password + token).encode()).hexdigest()
            )
        
        for pwd in password_variants:
            data = {
                "isTest": "false",
                "goformId": "LOGIN",
                "password": pwd
            }
            result = self._post_cmd(data)
            if result and result.get("result") == "0":
                print("Login successful!")
                return True
            elif result:
                print(f"Login attempt result: {result}")
        
        print("Note: Login may not be required for SMS operations")
        return False

    def get_sms_capacity(self):
        """Get SMS storage capacity info."""
        result = self._get_cmd("sms_capacity_info")
        if result:
            print("\n=== SMS Capacity ===")
            print(f"Device storage: {result.get('sms_nv_rev_total', '?')}/{result.get('sms_nv_total', '?')} received")
            print(f"SIM storage: {result.get('sms_sim_rev_total', '?')}/{result.get('sms_sim_total', '?')} received")
        return result

    def get_sms_list(self, page=0, per_page=20, mem_store=1):
        """Get list of SMS messages."""
        # Try different parameter combinations
        param_sets = [
            # Standard ZTE format
            {
                "page": str(page),
                "data_per_page": str(per_page),
                "mem_store": str(mem_store),
                "tags": "10",
                "order_by": "order by id desc"
            },
            # Alternative format
            {
                "page": str(page),
                "data_per_page": str(per_page),
                "mem_store": str(mem_store),
                "tags": "1"
            },
            # Minimal format
            {
                "page": str(page),
                "data_per_page": str(per_page)
            },
            # Box-based format
            {
                "box_type": "1",
                "page": str(page),
                "data_per_page": str(per_page)
            }
        ]
        
        for params in param_sets:
            for cmd in ["sms_data_total", "sms_page_data", "sms_list"]:
                result = self._get_cmd(cmd, params)
                if result and result.get("messages"):
                    print(f"Found SMS using cmd={cmd}")
                    return result
        
        return {"messages": []}

    def delete_sms(self, msg_ids):
        """Delete specific SMS messages by ID."""
        if isinstance(msg_ids, list):
            msg_ids = ";".join(str(id) for id in msg_ids)
        
        # Try different delete methods
        delete_methods = [
            {"goformId": "DELETE_SMS", "msg_id": msg_ids, "isTest": "false"},
            {"goformId": "DELETE_SMS", "msg_id": msg_ids, "notCallback": "true"},
            {"goformId": "delete_sms", "msg_id": msg_ids, "isTest": "false"},
        ]
        
        for data in delete_methods:
            result = self._post_cmd(data)
            if result and result.get("result") == "success":
                print(f"Successfully deleted SMS: {msg_ids}")
                return True
            elif result:
                print(f"Delete attempt result: {result}")
        
        return False

    def delete_all_sms(self):
        """Delete all SMS messages from device and SIM."""
        print("\n=== Deleting All SMS ===")
        
        # First try to get the list and delete individually
        for mem_store in [1, 2]:  # 1=device, 2=SIM
            store_name = "device" if mem_store == 1 else "SIM"
            print(f"\nChecking {store_name} storage...")
            
            result = self.get_sms_list(mem_store=mem_store, per_page=100)
            messages = result.get("messages", [])
            
            if messages:
                msg_ids = [msg.get("id") for msg in messages if msg.get("id")]
                if msg_ids:
                    print(f"Found {len(msg_ids)} messages in {store_name}")
                    self.delete_sms(msg_ids)
        
        # Also try bulk delete commands
        bulk_delete_attempts = [
            {"goformId": "DELETE_SMS", "msg_id": "-1", "isTest": "false"},
            {"goformId": "DELETE_SMS", "msg_id": "del_all", "isTest": "false"},
            {"goformId": "DELETE_ALL_SMS", "isTest": "false"},
            {"goformId": "delete_all_sms", "isTest": "false"},
        ]
        
        print("\nTrying bulk delete methods...")
        for data in bulk_delete_attempts:
            result = self._post_cmd(data)
            if result:
                print(f"Bulk delete ({data['goformId']}): {result}")

    def run_diagnostics(self):
        """Run diagnostics to discover API endpoints."""
        print("\n=== Running Diagnostics ===")
        
        # Test various SMS-related commands
        test_cmds = [
            "sms_capacity_info",
            "sms_data_total", 
            "sms_page_data",
            "sms_cmd",
            "sms_received_flag",
            "sms_unread_num",
            "sms_parameter_info",
            "pbm_init_flag",
        ]
        
        print("\nTesting GET commands:")
        for cmd in test_cmds:
            result = self._get_cmd(cmd)
            if result and result != {}:
                print(f"  {cmd}: {json.dumps(result)[:100]}")
        
        print("\nTesting SMS list with various parameters:")
        self.get_sms_list()


def main():
    parser = argparse.ArgumentParser(description="MTN MF935 MiFi SMS Manager")
    parser.add_argument("--host", default="192.168.0.1", help="MiFi IP address")
    parser.add_argument("--password", default="admin", help="Admin password")
    parser.add_argument("--action", choices=["delete", "list", "diagnose"], 
                        default="diagnose", help="Action to perform")
    
    args = parser.parse_args()
    
    manager = MiFiSMSManager(host=args.host, password=args.password)
    
    # Try to login first
    manager.login()
    
    # Show capacity
    manager.get_sms_capacity()
    
    if args.action == "diagnose":
        manager.run_diagnostics()
    elif args.action == "list":
        result = manager.get_sms_list(per_page=100)
        print(f"\nMessages: {json.dumps(result, indent=2)}")
    elif args.action == "delete":
        manager.delete_all_sms()
        print("\n=== After deletion ===")
        manager.get_sms_capacity()


if __name__ == "__main__":
    main()
