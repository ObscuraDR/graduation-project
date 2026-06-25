"""
Packet Sniffer
Real-time packet capture from network interfaces using Scapy
"""

import sys
import threading
import queue
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, List, Dict
import time

try:
    from scapy.all import sniff, Packet, get_if_list
    from scapy.layers.inet import IP, TCP, UDP, ICMP
    if sys.platform == 'win32':
        from scapy.arch.windows import get_windows_if_list
except ImportError:
    raise ImportError("Scapy is required. Install with: pip install scapy")

logger = logging.getLogger(__name__)


def get_available_interfaces() -> List[str]:
    """
    Get list of available network interface names
    
    Returns:
        List of interface names
    """
    try:
        if sys.platform == 'win32':
            win_ifaces = get_windows_if_list()
            return [iface.get('name', '') for iface in win_ifaces if iface.get('name')]
        else:
            return get_if_list()
    except Exception as e:
        logger.error(f"Error getting interfaces: {e}")
        return []


def validate_interface(interface: str) -> tuple[bool, Optional[str], List[str]]:
    """
    Validate that an interface exists and is available for sniffing
    
    Args:
        interface: Interface name to validate
    
    Returns:
        Tuple of (is_valid, error_message, available_interfaces)
    """
    available = get_available_interfaces()
    
    if not available:
        return False, "No interfaces found. Npcap may not be installed correctly on Windows.", []
    
    if interface not in available:
        return False, f"Interface '{interface}' not found. Available interfaces: {available}", available
    
    return True, None, available


class PacketSniffer:
    """Real-time packet sniffer for network traffic monitoring"""
    
    def __init__(
        self,
        interface: str = "eth0",
        packet_queue: Optional[queue.Queue] = None,
        callback: Optional[Callable] = None,
        filter_expr: Optional[str] = None,
        dry_run: bool = False,
        dry_run_duration: float = 3.0
    ):
        """
        Initialize packet sniffer
        
        Args:
            interface: Network interface to capture from (eth0, wlan0, etc.)
            packet_queue: Queue to store captured packets
            callback: Callback function for each captured packet
            filter_expr: BPF filter expression (e.g., "tcp", "port 80")
            dry_run: If True, capture for dry_run_duration seconds then stop
            dry_run_duration: Duration in seconds for dry run mode
        """
        self.interface = interface
        self.packet_queue = packet_queue or queue.Queue(maxsize=10000)
        self.callback = callback
        self.filter_expr = filter_expr or "ip"
        self.dry_run = dry_run
        self.dry_run_duration = dry_run_duration
        self.is_running = False
        self.sniffer_thread = None
        self.packets_captured = 0
        self.start_time = None
        self.dry_run_complete = False
        
    def _packet_handler(self, packet: Packet):
        """Handle captured packet"""
        try:
            # Extract relevant packet information
            packet_info = self._extract_packet_info(packet)
            
            # Put in queue
            if not self.packet_queue.full():
                self.packet_queue.put(packet_info)
            else:
                logger.warning("Packet queue full, dropping packet")
            
            # Call callback if provided
            if self.callback:
                self.callback(packet_info)
            
            self.packets_captured += 1
            
            # Log every 1000 packets
            if self.packets_captured % 1000 == 0:
                elapsed = time.time() - self.start_time if self.start_time else 0
                rate = self.packets_captured / elapsed if elapsed > 0 else 0
                logger.info(f"Captured {self.packets_captured} packets ({rate:.2f} pps)")
                
        except Exception as e:
            logger.error(f"Error handling packet: {e}")
    
    def _extract_packet_info(self, packet: Packet) -> dict:
        """
        Extract relevant information from packet
        
        Args:
            packet: Scapy packet object
        
        Returns:
            Dictionary with packet information
        """
        packet_info = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'length': len(packet),
            'protocol': None,
            'src_ip': None,
            'dst_ip': None,
            'src_port': None,
            'dst_port': None,
            'tcp_flags': None,
            'payload_size': 0
        }
        
        # Extract IP layer
        if IP in packet:
            packet_info['src_ip'] = packet[IP].src
            packet_info['dst_ip'] = packet[IP].dst
            packet_info['protocol'] = packet[IP].proto
        
        # Extract TCP layer
        if TCP in packet:
            packet_info['src_port'] = packet[TCP].sport
            packet_info['dst_port'] = packet[TCP].dport
            packet_info['protocol'] = 'tcp'
            packet_info['tcp_flags'] = {
                'FIN': packet[TCP].flags.F,
                'SYN': packet[TCP].flags.S,
                'RST': packet[TCP].flags.R,
                'PSH': packet[TCP].flags.P,
                'ACK': packet[TCP].flags.A,
                'URG': packet[TCP].flags.U
            }
            packet_info['payload_size'] = len(packet[TCP].payload)
        
        # Extract UDP layer
        elif UDP in packet:
            packet_info['src_port'] = packet[UDP].sport
            packet_info['dst_port'] = packet[UDP].dport
            packet_info['protocol'] = 'udp'
            packet_info['payload_size'] = len(packet[UDP].payload)
        
        # Extract ICMP layer
        elif ICMP in packet:
            packet_info['protocol'] = 'icmp'
            packet_info['payload_size'] = len(packet[ICMP].payload)
        
        return packet_info
    
    def start(self):
        """Start packet capture in background thread"""
        if self.is_running:
            logger.warning("Sniffer already running")
            return
        
        self.is_running = True
        self.start_time = time.time()
        self.packets_captured = 0
        
        logger.info(f"Starting packet sniffer on interface {self.interface}")
        logger.info(f"Filter: {self.filter_expr}")
        
        self.sniffer_thread = threading.Thread(
            target=self._run_sniffer,
            daemon=True
        )
        self.sniffer_thread.start()
    
    def _run_sniffer(self):
        """Run scapy sniff in thread"""
        try:
            if self.dry_run:
                # Dry run mode: capture for specified duration then stop
                logger.info(f"Dry run mode: capturing for {self.dry_run_duration} seconds")
                sniff(
                    iface=self.interface,
                    prn=self._packet_handler,
                    filter=self.filter_expr,
                    store=False,
                    timeout=self.dry_run_duration
                )
                self.dry_run_complete = True
                self.is_running = False
                logger.info(f"Dry run complete. Captured {self.packets_captured} packets")
            else:
                # Normal mode: continuous capture
                sniff(
                    iface=self.interface,
                    prn=self._packet_handler,
                    filter=self.filter_expr,
                    store=False
                )
        except PermissionError as e:
            error_msg = str(e).lower()
            if 'npcap' in error_msg or 'permission' in error_msg or 'access' in error_msg:
                logger.error("Npcap is required on Windows. Install Npcap in WinPcap-compatible mode.")
                raise PermissionError(
                    "Npcap is required on Windows. Install Npcap in WinPcap-compatible mode. "
                    "Download from: https://npcap.com/"
                )
            raise
        except Exception as e:
            logger.error(f"Sniffer error: {e}")
            self.is_running = False
    
    def stop(self):
        """Stop packet capture"""
        if not self.is_running:
            return
        
        logger.info("Stopping packet sniffer...")
        self.is_running = False
        
        if self.sniffer_thread:
            self.sniffer_thread.join(timeout=5)
        
        elapsed = time.time() - self.start_time if self.start_time else 0
        rate = self.packets_captured / elapsed if elapsed > 0 else 0
        logger.info(f"Sniffer stopped. Captured {self.packets_captured} packets in {elapsed:.2f}s ({rate:.2f} pps)")
    
    def get_packet(self, timeout: float = 1.0) -> Optional[dict]:
        """
        Get next packet from queue
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            Packet info dictionary or None
        """
        try:
            return self.packet_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_stats(self) -> dict:
        """Get sniffer statistics"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        rate = self.packets_captured / elapsed if elapsed > 0 else 0
        
        return {
            'is_running': self.is_running,
            'interface': self.interface,
            'packets_captured': self.packets_captured,
            'queue_size': self.packet_queue.qsize(),
            'elapsed_seconds': elapsed,
            'packets_per_second': rate,
            'start_time': datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat() if self.start_time else None
        }


# Singleton instance
_sniffer_instance: Optional[PacketSniffer] = None


def get_sniffer(
    interface: str = "eth0",
    packet_queue: Optional[queue.Queue] = None,
    callback: Optional[Callable] = None,
    filter_expr: Optional[str] = None,
    dry_run: bool = False,
    dry_run_duration: float = 3.0
) -> PacketSniffer:
    """
    Get or create packet sniffer instance
    
    Args:
        interface: Network interface
        packet_queue: Packet queue
        callback: Callback function
        filter_expr: BPF filter expression
        dry_run: If True, capture for dry_run_duration seconds then stop
        dry_run_duration: Duration in seconds for dry run mode
    
    Returns:
        PacketSniffer instance
    """
    global _sniffer_instance

    # Nếu đã có instance đang chạy → trả về nó (không cho đổi config khi đang capture)
    if _sniffer_instance is not None and _sniffer_instance.is_running:
        logger.warning(
            "Sniffer đang chạy trên interface '%s'; bỏ qua request đổi config",
            _sniffer_instance.interface,
        )
        return _sniffer_instance

    # Nếu chưa có instance HOẶC instance cũ đã dừng → tạo mới với params hiện tại.
    # Điều này fix bug singleton reuse: trước đây start lần 2 với interface khác
    # vẫn dùng config cũ (interface + dry_run của lần đầu).
    _sniffer_instance = PacketSniffer(
        interface=interface,
        packet_queue=packet_queue,
        callback=callback,
        filter_expr=filter_expr,
        dry_run=dry_run,
        dry_run_duration=dry_run_duration,
    )

    return _sniffer_instance
