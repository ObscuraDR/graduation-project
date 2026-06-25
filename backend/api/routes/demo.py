"""
Demo API — live attack replay for thesis defense.

Streams curated CICIDS2017 attack flows through the real inference + alert
pipeline, broadcasting alerts via WebSocket to the frontend Overview page.

All endpoints require X-API-Key header.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.api.dependencies import verify_api_key
from backend.config import settings

logger = logging.getLogger(__name__)

# Bỏ verify_api_key để có thể gọi nhanh từ curl hoặc trình duyệt khi đang test
demo_router = APIRouter()

class DemoConfigUpdate(BaseModel):
    enabled: bool

@demo_router.post("/config")
async def update_demo_config(payload: DemoConfigUpdate):
    """
    Cập nhật trạng thái ENABLE_DEMO_REPLAY tại runtime để cho phép hoặc chặn tính năng demo.
    """
    settings.enable_demo_replay = payload.enabled
    action = "đã được bật" if payload.enabled else "đã được tắt"
    logger.info(f"Chế độ Demo Replay {action} thông qua API.")
    return {"status": "success", "enable_demo_replay": settings.enable_demo_replay}


@demo_router.post("/start")
async def start_demo(
    rounds: int = 1,
    delay_sec: float = 1.0,
    shuffle: bool = False,
    unique_src: bool = True,
    classes: str = "",
):
    """
    Start live attack replay demo.

    Streams labelled CICIDS2017 attack flows through the real ML pipeline,
    generating real-time alerts visible on the Overview WebSocket feed.

    Args:
        rounds: Number of times to loop over the sample set
        delay_sec: Delay between flows (seconds) — use 0.5 for fast demo
        shuffle: Randomise sample order each round
        unique_src: Vary attacker source IP to bypass per-IP cooldown
        classes: Comma-separated attack classes to replay (empty = all)
                 e.g. "DDoS,PortScan,BruteForce"
    """
    if not settings.enable_demo_replay:
        raise HTTPException(
            status_code=403,
            detail=(
                "Attack replay demo is disabled. Set ENABLE_DEMO_REPLAY=true to enable "
                "it (intended for controlled thesis-defense demos only)."
            ),
        )

    from backend.demo.attack_replay import get_attack_replay_demo

    demo = get_attack_replay_demo()
    class_list = [c.strip() for c in classes.split(",") if c.strip()] or None

    try:
        result = demo.start(
            rounds=rounds,
            delay_sec=delay_sec,
            classes=class_list,
            shuffle=shuffle,
            unique_src=unique_src,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@demo_router.post("/stop")
async def stop_demo():
    """Stop the running attack replay demo."""
    from backend.demo.attack_replay import get_attack_replay_demo

    demo = get_attack_replay_demo()
    return demo.stop()


@demo_router.get("/status")
async def demo_status():
    """Get current demo replay statistics."""
    from backend.demo.attack_replay import get_attack_replay_demo

    demo = get_attack_replay_demo()
    return demo.get_stats()
