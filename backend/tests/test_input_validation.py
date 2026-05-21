"""
Tests – Input Validation
=========================
Covers:
  - validate_ipv4 / validate_port / validate_protocol / validate_interface
  - WhitelistAddRequest / WhitelistRemoveRequest Pydantic models
  - POST /api/whitelist/add  (422 on bad IP / protocol)
  - POST /api/sniffer/start  (422 on injection chars in interface name,
                               422 on bad min_packets / prediction_mode)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError

VALID_KEY = "test-key-validation"


# ---------------------------------------------------------------------------
# Module-scoped TestClient
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    import sys, types
    for mod in ["scapy", "scapy.all", "scapy.layers", "scapy.layers.inet", "scapy.arch", "scapy.arch.windows"]:
        sys.modules.setdefault(mod, types.ModuleType(mod))

    from fastapi.testclient import TestClient
    from backend.config import get_settings
    from backend.api.websocket import AlertBroadcastBridge

    settings = get_settings()
    original_key = settings.api_key
    object.__setattr__(settings, "api_key", VALID_KEY)

    try:
        with patch("backend.database.connection.init_db", return_value=None):
            with patch.object(AlertBroadcastBridge, "start", new=AsyncMock(return_value=None)):
                with patch.object(AlertBroadcastBridge, "stop", new=AsyncMock(return_value=None)):
                    from backend.main import app
                    with TestClient(app, raise_server_exceptions=False) as c:
                        yield c
    finally:
        object.__setattr__(settings, "api_key", original_key)


def _auth() -> dict:
    return {"X-API-Key": VALID_KEY}


# ===========================================================================
# Unit tests for validation.py helpers
# ===========================================================================

class TestValidateIPv4:
    def test_valid_addresses(self):
        from backend.api.validation import validate_ipv4
        for ip in ["0.0.0.0", "192.168.1.1", "10.0.0.1", "255.255.255.255", "172.16.0.1"]:
            assert validate_ipv4(ip) == ip

    def test_strips_whitespace(self):
        from backend.api.validation import validate_ipv4
        assert validate_ipv4("  192.168.1.1  ") == "192.168.1.1"

    def test_rejects_hostname(self):
        from backend.api.validation import validate_ipv4
        with pytest.raises(ValueError, match="Invalid IPv4"):
            validate_ipv4("example.com")

    def test_rejects_ipv6(self):
        from backend.api.validation import validate_ipv4
        with pytest.raises(ValueError):
            validate_ipv4("::1")

    def test_rejects_out_of_range_octet(self):
        from backend.api.validation import validate_ipv4
        with pytest.raises(ValueError):
            validate_ipv4("256.0.0.1")

    def test_rejects_partial(self):
        from backend.api.validation import validate_ipv4
        with pytest.raises(ValueError):
            validate_ipv4("192.168.1")

    def test_rejects_empty(self):
        from backend.api.validation import validate_ipv4
        with pytest.raises(ValueError):
            validate_ipv4("")

    def test_rejects_injection(self):
        from backend.api.validation import validate_ipv4
        for bad in ["1.2.3.4; rm -rf /", "1.2.3.4 | cat /etc/passwd", "$(whoami)"]:
            with pytest.raises(ValueError):
                validate_ipv4(bad)


class TestValidatePort:
    def test_valid_ports(self):
        from backend.api.validation import validate_port
        for p in [1, 80, 443, 8080, 65535]:
            assert validate_port(p) == p

    def test_rejects_zero(self):
        from backend.api.validation import validate_port
        with pytest.raises(ValueError):
            validate_port(0)

    def test_rejects_above_max(self):
        from backend.api.validation import validate_port
        with pytest.raises(ValueError):
            validate_port(65536)

    def test_rejects_negative(self):
        from backend.api.validation import validate_port
        with pytest.raises(ValueError):
            validate_port(-1)


class TestValidateProtocol:
    def test_valid_protocols(self):
        from backend.api.validation import validate_protocol
        assert validate_protocol("tcp") == "tcp"
        assert validate_protocol("UDP") == "udp"
        assert validate_protocol("ICMP") == "icmp"

    def test_rejects_unknown(self):
        from backend.api.validation import validate_protocol
        for bad in ["http", "ftp", "sctp", "", "tcp; rm -rf /"]:
            with pytest.raises(ValueError):
                validate_protocol(bad)


class TestValidateInterface:
    def test_valid_names(self):
        from backend.api.validation import validate_interface
        for name in ["eth0", "Wi-Fi", "Ethernet 2", "lo", "wlan0", "en0"]:
            assert validate_interface(name) == name

    def test_rejects_semicolon(self):
        from backend.api.validation import validate_interface
        with pytest.raises(ValueError):
            validate_interface("eth0; rm -rf /")

    def test_rejects_pipe(self):
        from backend.api.validation import validate_interface
        with pytest.raises(ValueError):
            validate_interface("eth0 | cat /etc/passwd")

    def test_rejects_backtick(self):
        from backend.api.validation import validate_interface
        with pytest.raises(ValueError):
            validate_interface("`whoami`")

    def test_rejects_dollar(self):
        from backend.api.validation import validate_interface
        with pytest.raises(ValueError):
            validate_interface("$(id)")

    def test_rejects_slash(self):
        from backend.api.validation import validate_interface
        with pytest.raises(ValueError):
            validate_interface("/dev/eth0")

    def test_rejects_too_long(self):
        from backend.api.validation import validate_interface
        with pytest.raises(ValueError):
            validate_interface("a" * 65)

    def test_rejects_empty(self):
        from backend.api.validation import validate_interface
        with pytest.raises(ValueError):
            validate_interface("")


# ===========================================================================
# Pydantic model validation
# ===========================================================================

class TestWhitelistAddRequest:
    def _make(self, **kwargs):
        from backend.api.legacy_routes import WhitelistAddRequest
        return WhitelistAddRequest(**kwargs)

    def test_valid_minimal(self):
        req = self._make(ip_address="192.168.1.10")
        assert req.ip_address == "192.168.1.10"

    def test_valid_full(self):
        req = self._make(ip_address="10.0.0.1", port=443, protocol="tcp", reason="test")
        assert req.protocol == "tcp"
        assert req.port == 443

    def test_invalid_ip(self):
        with pytest.raises(ValidationError) as exc_info:
            self._make(ip_address="not-an-ip")
        assert "Invalid IPv4" in str(exc_info.value)

    def test_invalid_protocol(self):
        with pytest.raises(ValidationError):
            self._make(ip_address="10.0.0.1", protocol="http")

    def test_port_zero_rejected(self):
        with pytest.raises(ValidationError):
            self._make(ip_address="10.0.0.1", port=0)

    def test_port_above_max_rejected(self):
        with pytest.raises(ValidationError):
            self._make(ip_address="10.0.0.1", port=65536)

    def test_protocol_normalised_to_lowercase(self):
        req = self._make(ip_address="10.0.0.1", protocol="TCP")
        assert req.protocol == "tcp"


class TestWhitelistRemoveRequest:
    def _make(self, **kwargs):
        from backend.api.legacy_routes import WhitelistRemoveRequest
        return WhitelistRemoveRequest(**kwargs)

    def test_valid_by_id(self):
        req = self._make(whitelist_id=1)
        assert req.whitelist_id == 1

    def test_valid_by_ip(self):
        req = self._make(ip_address="10.0.0.5")
        assert req.ip_address == "10.0.0.5"

    def test_requires_id_or_ip(self):
        with pytest.raises(ValidationError):
            self._make()

    def test_invalid_ip_rejected(self):
        with pytest.raises(ValidationError):
            self._make(ip_address="999.999.999.999")


# ===========================================================================
# HTTP endpoint validation (via TestClient)
# ===========================================================================

class TestWhitelistEndpointValidation:
    def test_add_invalid_ip_returns_422(self, client) -> None:
        r = client.post(
            "/api/whitelist/add",
            json={"ip_address": "not-an-ip"},
            headers=_auth(),
        )
        assert r.status_code == 422

    def test_add_injection_ip_returns_422(self, client) -> None:
        r = client.post(
            "/api/whitelist/add",
            json={"ip_address": "1.2.3.4; DROP TABLE whitelist;"},
            headers=_auth(),
        )
        assert r.status_code == 422

    def test_add_invalid_protocol_returns_422(self, client) -> None:
        r = client.post(
            "/api/whitelist/add",
            json={"ip_address": "10.0.0.1", "protocol": "ftp"},
            headers=_auth(),
        )
        assert r.status_code == 422

    def test_add_port_zero_returns_422(self, client) -> None:
        r = client.post(
            "/api/whitelist/add",
            json={"ip_address": "10.0.0.1", "port": 0},
            headers=_auth(),
        )
        assert r.status_code == 422

    def test_add_port_too_high_returns_422(self, client) -> None:
        r = client.post(
            "/api/whitelist/add",
            json={"ip_address": "10.0.0.1", "port": 99999},
            headers=_auth(),
        )
        assert r.status_code == 422

    def test_remove_invalid_ip_returns_422(self, client) -> None:
        r = client.post(
            "/api/whitelist/remove",
            json={"ip_address": "bad-ip"},
            headers=_auth(),
        )
        assert r.status_code == 422

    def test_remove_no_id_or_ip_returns_422(self, client) -> None:
        r = client.post(
            "/api/whitelist/remove",
            json={},
            headers=_auth(),
        )
        assert r.status_code == 422


class TestSnifferStartValidation:
    def _start(self, client, **params):
        return client.post(
            "/api/sniffer/start",
            params=params,
            headers=_auth(),
        )

    def test_injection_interface_returns_422(self, client) -> None:
        r = self._start(client, interface="eth0; rm -rf /")
        assert r.status_code == 422

    def test_pipe_interface_returns_422(self, client) -> None:
        r = self._start(client, interface="eth0 | id")
        assert r.status_code == 422

    def test_backtick_interface_returns_422(self, client) -> None:
        r = self._start(client, interface="`whoami`")
        assert r.status_code == 422

    def test_min_packets_zero_returns_422(self, client) -> None:
        r = self._start(client, interface="eth0", min_packets=0)
        assert r.status_code == 422

    def test_min_packets_too_large_returns_422(self, client) -> None:
        r = self._start(client, interface="eth0", min_packets=99999)
        assert r.status_code == 422

    def test_invalid_prediction_mode_returns_422(self, client) -> None:
        r = self._start(client, interface="eth0", prediction_mode="invalid")
        assert r.status_code == 422

    def test_valid_interface_name_passes_safety_check(self, client) -> None:
        """Safe interface name passes validation (may still fail HW check → 400, not 422)."""
        r = self._start(client, interface="eth0")
        # 422 = validation error; 400 = HW interface not found; both are acceptable here
        # but 422 specifically means our safety check fired incorrectly
        assert r.status_code != 422, f"Safe interface name was rejected: {r.text}"
