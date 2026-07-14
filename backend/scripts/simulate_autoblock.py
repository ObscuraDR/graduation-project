"""
simulate_autoblock.py
======================
Giả lập tấn công DDoS liên tiếp → kích hoạt auto-block IP trên Dashboard.

Kịch bản:
  1. Hạ alert_cooldown xuống 0 và auto_block_threshold xuống 3 (demo mode)
  2. Gửi nhiều rounds DDoS từ pool 3 IPs cố định
  3. Sau 3 alerts từ cùng IP → AlertManager tự block IP đó
  4. Dashboard hiển thị: severity HIGH/CRITICAL + IP xuất hiện trong Blacklist

Cách dùng:
    python3 backend/scripts/simulate_autoblock.py
    python3 backend/scripts/simulate_autoblock.py --rounds 4 --delay 0.3
"""

import argparse
import time
import sys
import httpx

BASE_URL = "http://localhost:8000"
API_KEY  = "changeme-set-API_KEY-in-env"


def p(msg): print(msg, flush=True)


def check_backend() -> bool:
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code == 200:
            p(f"✅ Backend OK (v{r.json().get('version','?')})")
            return True
    except Exception as e:
        p(f"❌ Backend không khả dụng: {e}")
        p("   Hãy chạy: sudo .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
    return False


def set_demo_config(cooldown: int, threshold: int, confidence: float):
    """Điều chỉnh AlertManager để phù hợp với demo."""
    try:
        r = httpx.post(
            f"{BASE_URL}/api/stats/alert-engine/config",
            params={
                "alert_cooldown": cooldown,
                "auto_block_threshold": threshold,
                "confidence_threshold": confidence,
            },
            timeout=5
        )
        if r.status_code == 200:
            changes = r.json().get("changes", {})
            p(f"✅ AlertManager config: cooldown={changes.get('alert_cooldown')}s  "
              f"auto_block={changes.get('auto_block_threshold')}  "
              f"confidence≥{changes.get('confidence_threshold')}")
            return True
    except Exception as e:
        p(f"⚠️  Không thể cấu hình AlertManager: {e}")
    return False


def restore_config():
    """Khôi phục cấu hình mặc định sau demo."""
    try:
        httpx.post(
            f"{BASE_URL}/api/stats/alert-engine/config",
            params={
                "alert_cooldown": 30,
                "auto_block_threshold": 10,
                "confidence_threshold": 0.75,
            },
            timeout=5
        )
        p("✅ AlertManager config đã được khôi phục về mặc định")
    except Exception:
        pass


def start_wave(rounds: int, delay: float) -> bool:
    """Bắt đầu 1 wave demo."""
    try:
        r = httpx.post(
            f"{BASE_URL}/api/demo/start",
            params={
                "classes": "DDoS",
                "rounds": rounds,
                "delay_sec": delay,
                "unique_src": True,   # Pool 3 IPs: .1, .2, .3
                "shuffle": False,
            },
            timeout=10
        )
        if r.status_code == 200:
            d = r.json()
            p(f"   → {d.get('samples_per_round','?')} flows × {rounds} rounds")
            return True
        p(f"   → Lỗi {r.status_code}: {r.text[:100]}")
        return False
    except Exception as e:
        p(f"   → Không kết nối: {e}")
        return False


def wait_done(timeout: int = 90) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{BASE_URL}/api/demo/status", timeout=5)
            if r.status_code == 200:
                s = r.json()
                if not s.get("running", True):
                    return s
        except Exception:
            pass
        time.sleep(1)
    return {}


def get_blacklist() -> list:
    try:
        r = httpx.get(
            f"{BASE_URL}/api/blacklist/",
            headers={"X-API-Key": API_KEY},
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("items", [])
            return [i for i in items if i.get("is_active")]
    except Exception:
        pass
    return []


def get_engine_stats() -> dict:
    try:
        r = httpx.get(f"{BASE_URL}/api/stats/alert-engine", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="Giả lập tấn công → kích hoạt auto-block IP"
    )
    parser.add_argument("--rounds",  type=int,   default=4,   help="Số rounds mỗi wave (default: 4)")
    parser.add_argument("--delay",   type=float, default=0.2, help="Delay giữa flows (giây, default: 0.2)")
    parser.add_argument("--url",     default="http://localhost:8000")
    parser.add_argument("--restore", action="store_true",
                        help="Chỉ khôi phục config mặc định rồi thoát")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.url.rstrip("/")

    if args.restore:
        restore_config()
        return

    p("\n" + "="*60)
    p("  Z-SENTINEL — Auto-Block Demo")
    p("  DDoS liên tiếp → severity leo thang → IP tự bị chặn")
    p("="*60)
    p(f"""
  Cấu hình demo:
    Pool IP tấn công : 203.0.113.1, .2, .3
    Rounds / wave    : {args.rounds} × 8 flows = {args.rounds*8} alerts/wave
    Delay            : {args.delay}s / flow
    Cooldown demo    : 0s (hạ từ 30s để demo nhanh)
    Auto-block sau   : 3 alerts / IP (hạ từ 10)

  💡 Mở Dashboard → Cảnh báo để xem alerts real-time
     Sau đó xem Firewall → Blacklist
""")

    # 1. Kiểm tra backend
    if not check_backend():
        sys.exit(1)

    # 2. Bật demo mode
    try:
        httpx.post(f"{BASE_URL}/api/demo/config", json={"enabled": True}, timeout=5)
        p("✅ Demo mode: enabled")
    except Exception:
        pass

    # 3. Hạ ngưỡng để demo nhanh
    p("\n[1/4] Cấu hình AlertManager cho demo...")
    set_demo_config(
        cooldown=0,      # Không cooldown → mỗi alert đều được ghi
        threshold=3,     # Block sau 3 alerts thay vì 10
        confidence=0.6   # Hạ threshold để bắt nhiều hơn
    )

    # 4. Wave 1 — DDoS đầu tiên
    p("\n[2/4] Wave 1 — DDoS từ 3 IPs...")
    if not start_wave(args.rounds, args.delay):
        p("❌ Không thể khởi động demo. Kiểm tra ENABLE_DEMO_REPLAY=true trong .env")
        sys.exit(1)

    # Theo dõi alerts real-time
    p("\n  Đang theo dõi alerts...\n")
    last_alerts = 0
    last_blocked = 0
    start_t = time.time()

    while True:
        time.sleep(1.5)
        elapsed = int(time.time() - start_t)

        try:
            r = httpx.get(f"{BASE_URL}/api/demo/status", timeout=3)
            if r.status_code != 200:
                continue
            s = r.json()
            alerts    = s.get("alerts_broadcast", 0)
            detected  = s.get("detected_attacks", 0)
            suppressed= s.get("suppressed", 0)
            running   = s.get("running", True)

            # Hiển thị alert mới
            if alerts > last_alerts:
                new = alerts - last_alerts
                p(f"  🔴 +{new} alert(s) → total={alerts}  detected={detected}  suppressed={suppressed}  [{elapsed}s]")
                last_alerts = alerts

                # Kiểm tra auto-block ngay
                engine = get_engine_stats()
                blocked_now = engine.get("blacklist_count", 0)
                if blocked_now > last_blocked:
                    bl = get_blacklist()
                    p(f"\n  ┌─────────────────────────────────────────┐")
                    p(f"  │  🚫 AUTO-BLOCK TRIGGERED!                │")
                    p(f"  │  {blocked_now} IP(s) đã bị chặn tự động:{'':12}│")
                    for item in bl:
                        ip     = item.get('ip_address', '?')
                        reason = item.get('reason', '')[:30]
                        p(f"  │    • {ip:20} {reason:18}│")
                    p(f"  └─────────────────────────────────────────┘\n")
                    last_blocked = blocked_now

            if not running:
                break

        except Exception:
            pass

    # 5. Wave 2 — tiếp tục nếu chưa đủ block
    engine = get_engine_stats()
    if engine.get("blacklist_count", 0) == 0:
        p("\n[3/4] Wave 2 — Tiếp tục tấn công...")
        start_wave(args.rounds, args.delay)
        stats = wait_done(60)
        last_alerts = stats.get("alerts_broadcast", 0)
    else:
        p("\n[3/4] ✅ Đã có IPs bị block — bỏ qua Wave 2")

    # 6. Khôi phục config
    p("\n[4/4] Khôi phục cấu hình AlertManager...")
    restore_config()

    # 7. Kết quả
    bl_final = get_blacklist()
    engine_final = get_engine_stats()

    p(f"\n{'='*60}")
    p(f"  ✅ Demo hoàn thành!")
    p(f"")
    p(f"  Kết quả:")
    p(f"    Tổng alerts phát hiện : {engine_final.get('total_alerts', '?')}")
    p(f"    IPs bị auto-block     : {len(bl_final)}")
    if bl_final:
        for item in bl_final:
            p(f"      🚫 {item.get('ip_address')} — {item.get('reason','')[:50]}")
    p(f"")
    p(f"  Kiểm tra trên Dashboard:")
    p(f"    Cảnh báo → xem severity HIGH/CRITICAL")
    p(f"    Firewall → Blacklist → thấy IPs bị block")
    p(f"    AI Insights → click alert để xem SHAP explanation")
    p(f"{'='*60}\n")


if __name__ == "__main__":
    main()
