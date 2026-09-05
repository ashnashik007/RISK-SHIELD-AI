import asyncio
import json
import random

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..database import SessionLocal
from ..engine import generator

router = APIRouter(prefix="/api/stream", tags=["stream"])


def _generate_one() -> dict:
    db = SessionLocal()
    try:
        tx, investigation = generator.generate_and_process(db)
        return {
            "id": tx.id,
            "customer_name": tx.customer.name if tx.customer else None,
            "location": tx.location,
            "device": tx.device,
            "amount": tx.amount,
            "risk_score": tx.risk_score,
            "risk_level": tx.risk_level,
            "status": tx.status,
            "investigation_opened": bool(investigation),
        }
    finally:
        db.close()


@router.get("")
async def live_stream(request: Request):
    async def event_generator():
        yield "retry: 3000\n\n"
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(random.uniform(6, 11))
            try:
                payload = await asyncio.to_thread(_generate_one)
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as exc:  # keep the stream alive even if one tick fails
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
