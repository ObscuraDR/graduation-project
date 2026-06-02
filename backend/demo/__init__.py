"""
Demo utilities for thesis defense.

This package contains a reproducible "live attack" demonstration that streams
REAL labelled CICIDS2017 attack flows through the SAME model + alert manager +
WebSocket broadcast path used by the live sniffer pipeline. It requires no
packet-capture privileges (Npcap / admin) and no external attack tools, so the
demo is deterministic and safe to run on any machine during a defense.
"""

from backend.demo.attack_replay import AttackReplayDemo, get_attack_replay_demo

__all__ = ["AttackReplayDemo", "get_attack_replay_demo"]
