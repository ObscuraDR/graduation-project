"""
Unit tests for sniffer interface validation
Tests interface discovery and validation logic without real packet sniffing
"""

import pytest
from unittest.mock import patch, MagicMock
import sys

# Mock scapy before importing packet_sniffer
sys.modules['scapy'] = MagicMock()
sys.modules['scapy.all'] = MagicMock()
sys.modules['scapy.layers.inet'] = MagicMock()
sys.modules['scapy.arch'] = MagicMock()
sys.modules['scapy.arch.windows'] = MagicMock()

from backend.capture_engine.packet_sniffer import validate_interface, get_available_interfaces


class TestInterfaceValidation:
    """Test interface validation logic"""

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_validate_interface_valid_windows(self, mock_get_windows_if_list):
        """Test validation with valid interface on Windows"""
        # Mock Windows interface list
        mock_get_windows_if_list.return_value = [
            {'name': 'Wi-Fi', 'description': 'Wireless Adapter', 'ip': '192.168.1.100', 'is_up': True},
            {'name': 'Ethernet', 'description': 'Ethernet Adapter', 'ip': '192.168.1.101', 'is_up': True}
        ]
        
        with patch('sys.platform', 'win32'):
            is_valid, error_msg, available = validate_interface('Wi-Fi')
            
            assert is_valid is True
            assert error_msg is None
            assert 'Wi-Fi' in available
            assert 'Ethernet' in available

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_validate_interface_invalid_windows(self, mock_get_windows_if_list):
        """Test validation with invalid interface on Windows"""
        mock_get_windows_if_list.return_value = [
            {'name': 'Wi-Fi', 'description': 'Wireless Adapter', 'ip': '192.168.1.100', 'is_up': True}
        ]
        
        with patch('sys.platform', 'win32'):
            is_valid, error_msg, available = validate_interface('InvalidInterface')
            
            assert is_valid is False
            assert error_msg is not None
            assert 'InvalidInterface' in error_msg
            assert 'Wi-Fi' in available

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_validate_interface_no_interfaces_windows(self, mock_get_windows_if_list):
        """Test validation when no interfaces are available on Windows"""
        mock_get_windows_if_list.return_value = []
        
        with patch('sys.platform', 'win32'):
            is_valid, error_msg, available = validate_interface('Wi-Fi')
            
            assert is_valid is False
            assert error_msg is not None
            assert 'Npcap' in error_msg
            assert available == []

    @patch('backend.capture_engine.packet_sniffer.get_if_list')
    def test_validate_interface_valid_unix(self, mock_get_if_list):
        """Test validation with valid interface on Unix-like systems"""
        mock_get_if_list.return_value = ['eth0', 'wlan0', 'lo']
        
        with patch('sys.platform', 'linux'):
            is_valid, error_msg, available = validate_interface('eth0')
            
            assert is_valid is True
            assert error_msg is None
            assert 'eth0' in available
            assert 'wlan0' in available

    @patch('backend.capture_engine.packet_sniffer.get_if_list')
    def test_validate_interface_invalid_unix(self, mock_get_if_list):
        """Test validation with invalid interface on Unix-like systems"""
        mock_get_if_list.return_value = ['eth0', 'wlan0']
        
        with patch('sys.platform', 'linux'):
            is_valid, error_msg, available = validate_interface('invalid')
            
            assert is_valid is False
            assert error_msg is not None
            assert 'invalid' in error_msg
            assert 'eth0' in available


class TestGetAvailableInterfaces:
    """Test interface discovery logic"""

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_get_available_interfaces_windows(self, mock_get_windows_if_list):
        """Test getting available interfaces on Windows"""
        mock_get_windows_if_list.return_value = [
            {'name': 'Wi-Fi', 'description': 'Wireless', 'ip': '192.168.1.100', 'is_up': True},
            {'name': 'Ethernet', 'description': 'Ethernet', 'ip': '192.168.1.101', 'is_up': False}
        ]
        
        with patch('sys.platform', 'win32'):
            interfaces = get_available_interfaces()
            
            assert len(interfaces) == 2
            assert 'Wi-Fi' in interfaces
            assert 'Ethernet' in interfaces

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_get_available_interfaces_windows_empty_name(self, mock_get_windows_if_list):
        """Test filtering interfaces with empty names on Windows"""
        mock_get_windows_if_list.return_value = [
            {'name': 'Wi-Fi', 'description': 'Wireless', 'ip': '192.168.1.100', 'is_up': True},
            {'name': '', 'description': 'Empty Name', 'ip': '192.168.1.101', 'is_up': True},
            {'name': None, 'description': 'Null Name', 'ip': '192.168.1.102', 'is_up': True}
        ]
        
        with patch('sys.platform', 'win32'):
            interfaces = get_available_interfaces()
            
            assert len(interfaces) == 1
            assert 'Wi-Fi' in interfaces

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_get_available_interfaces_windows_error(self, mock_get_windows_if_list):
        """Test error handling when getting interfaces on Windows"""
        mock_get_windows_if_list.side_effect = Exception("Scapy error")
        
        with patch('sys.platform', 'win32'):
            interfaces = get_available_interfaces()
            
            assert interfaces == []

    @patch('backend.capture_engine.packet_sniffer.get_if_list')
    def test_get_available_interfaces_unix(self, mock_get_if_list):
        """Test getting available interfaces on Unix-like systems"""
        mock_get_if_list.return_value = ['eth0', 'wlan0', 'lo']
        
        with patch('sys.platform', 'linux'):
            interfaces = get_available_interfaces()
            
            assert len(interfaces) == 3
            assert 'eth0' in interfaces
            assert 'wlan0' in interfaces
            assert 'lo' in interfaces

    @patch('backend.capture_engine.packet_sniffer.get_if_list')
    def test_get_available_interfaces_unix_error(self, mock_get_if_list):
        """Test error handling when getting interfaces on Unix-like systems"""
        mock_get_if_list.side_effect = Exception("Scapy error")
        
        with patch('sys.platform', 'linux'):
            interfaces = get_available_interfaces()
            
            assert interfaces == []


class TestInterfaceValidationEdgeCases:
    """Test edge cases for interface validation"""

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_validate_interface_case_sensitivity(self, mock_get_windows_if_list):
        """Test that interface validation is case-sensitive"""
        mock_get_windows_if_list.return_value = [
            {'name': 'Wi-Fi', 'description': 'Wireless', 'ip': '192.168.1.100', 'is_up': True}
        ]
        
        with patch('sys.platform', 'win32'):
            # Exact match should work
            is_valid, _, _ = validate_interface('Wi-Fi')
            assert is_valid is True
            
            # Different case should fail
            is_valid, _, _ = validate_interface('wi-fi')
            assert is_valid is False
            
            is_valid, _, _ = validate_interface('WI-FI')
            assert is_valid is False

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_validate_interface_special_characters(self, mock_get_windows_if_list):
        """Test validation with interface names containing special characters"""
        mock_get_windows_if_list.return_value = [
            {'name': 'Ethernet 2', 'description': 'Ethernet Adapter 2', 'ip': '192.168.1.102', 'is_up': True}
        ]
        
        with patch('sys.platform', 'win32'):
            is_valid, error_msg, available = validate_interface('Ethernet 2')
            
            assert is_valid is True
            assert 'Ethernet 2' in available

    @patch('backend.capture_engine.packet_sniffer.get_windows_if_list')
    def test_validate_interface_duplicate_names(self, mock_get_windows_if_list):
        """Test validation when multiple interfaces have the same name"""
        mock_get_windows_if_list.return_value = [
            {'name': 'Ethernet', 'description': 'Adapter 1', 'ip': '192.168.1.100', 'is_up': True},
            {'name': 'Ethernet', 'description': 'Adapter 2', 'ip': '192.168.1.101', 'is_up': True}
        ]
        
        with patch('sys.platform', 'win32'):
            is_valid, _, available = validate_interface('Ethernet')
            
            assert is_valid is True
            # Should return both instances (or deduplicated depending on implementation)
            assert 'Ethernet' in available


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
