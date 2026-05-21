"""
Network Interface Discovery Tool
Lists all available sniffable interfaces using Scapy
"""

import sys
import logging
from typing import List, Dict, Optional

try:
    from scapy.all import get_if_list, get_if_addr, conf
    from scapy.arch.windows import get_windows_if_list
except ImportError:
    print("ERROR: Scapy is required. Install with: pip install scapy")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_interfaces() -> List[Dict[str, str]]:
    """
    Get list of available network interfaces
    
    Returns:
        List of interface dictionaries with name, description, IP, etc.
    """
    interfaces = []
    
    try:
        # Windows-specific interface listing
        if sys.platform == 'win32':
            win_ifaces = get_windows_if_list()
            for iface in win_ifaces:
                interfaces.append({
                    'name': iface.get('name', 'Unknown'),
                    'description': iface.get('description', 'No description'),
                    'guid': iface.get('guid', ''),
                    'ip': iface.get('ip', 'N/A'),
                    'is_up': iface.get('is_up', False)
                })
        else:
            # Unix-like systems
            if_names = get_if_list()
            for name in if_names:
                try:
                    ip = get_if_addr(name)
                except:
                    ip = 'N/A'
                
                interfaces.append({
                    'name': name,
                    'description': name,
                    'guid': '',
                    'ip': ip,
                    'is_up': True  # Assume up if in list
                })
    except Exception as e:
        logger.error(f"Error getting interfaces: {e}")
        # Fallback to basic Scapy method
        try:
            if_names = get_if_list()
            for name in if_names:
                interfaces.append({
                    'name': name,
                    'description': name,
                    'guid': '',
                    'ip': 'N/A',
                    'is_up': True
                })
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
    
    return interfaces


def recommend_interface(interfaces: List[Dict[str, str]]) -> Optional[str]:
    """
    Recommend the most likely active interface
    
    Args:
        interfaces: List of interface dictionaries
    
    Returns:
        Recommended interface name or None
    """
    if not interfaces:
        return None
    
    # Prioritize interfaces that are up and have an IP
    active_ifaces = [i for i in interfaces if i.get('is_up') and i.get('ip') != 'N/A']
    
    if active_ifaces:
        # Prefer Wi-Fi or Ethernet on Windows
        for iface in active_ifaces:
            name_lower = iface['name'].lower()
            if 'wi-fi' in name_lower or 'wlan' in name_lower:
                return iface['name']
            if 'ethernet' in name_lower or 'eth' in name_lower:
                return iface['name']
        
        # Return first active interface
        return active_ifaces[0]['name']
    
    # Fallback to first interface
    return interfaces[0]['name']


def print_interfaces(interfaces: List[Dict[str, str]], recommended: Optional[str] = None):
    """
    Print interfaces in a user-friendly format
    
    Args:
        interfaces: List of interface dictionaries
        recommended: Recommended interface name
    """
    print("=" * 80)
    print("Available Network Interfaces for Packet Sniffing")
    print("=" * 80)
    print()
    
    if not interfaces:
        print("No interfaces found. This may indicate:")
        print("  - Npcap/WinPcap is not installed")
        print("  - Npcap is not installed in WinPcap-compatible mode")
        print("  - Insufficient permissions")
        print()
        print("On Windows, install Npcap from: https://npcap.com/")
        print("  IMPORTANT: Select 'Install Npcap in WinPcap API-compatible Mode'")
        print()
        return
    
    print(f"Found {len(interfaces)} interface(s):\n")
    
    for idx, iface in enumerate(interfaces, 1):
        print(f"[{idx}] {iface['name']}")
        print(f"    Description: {iface['description']}")
        print(f"    IP Address:  {iface['ip']}")
        print(f"    Status:      {'UP' if iface['is_up'] else 'DOWN'}")
        
        if recommended and iface['name'] == recommended:
            print(f"    *** RECOMMENDED (likely active) ***")
        
        print()
    
    print("=" * 80)
    print("Instructions:")
    print("=" * 80)
    print()
    print("To start packet sniffing, use one of the interface names above:")
    print()
    
    if recommended:
        print(f"  Recommended: {recommended}")
        print(f"  Example API call:")
        print(f'    POST /api/sniffer/start')
        print(f'    {{"interface": "{recommended}"}}')
        print()
    
    print("  Or use the PowerShell script:")
    print(f"    .\\scripts\\start_sniffer.ps1 -Interface <interface_name>")
    print()
    print("Common Windows interface names:")
    print("  - 'Wi-Fi' (wireless adapter)")
    print("  - 'Ethernet' (wired adapter)")
    print("  - 'Local Area Connection'")
    print()
    print("If you see 'No interfaces found', ensure Npcap is installed correctly.")
    print()


def main():
    """Main entry point"""
    print()
    print("Network Interface Discovery Tool")
    print("=" * 80)
    print()
    
    try:
        interfaces = get_interfaces()
        recommended = recommend_interface(interfaces)
        print_interfaces(interfaces, recommended)
        
        if recommended:
            print(f"Recommended interface for sniffing: {recommended}")
            return 0
        elif interfaces:
            print("No clear recommendation found. Choose from the list above.")
            return 0
        else:
            print("ERROR: No interfaces found. Check Npcap installation.")
            return 1
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
