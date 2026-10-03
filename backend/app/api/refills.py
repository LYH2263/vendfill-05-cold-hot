import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane, Location, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize
router = APIRouter(prefix="/refills", tags=["refills"])


def _load_lanes(db: Session, location_id: int) -> list[dict]:
    lanes = db.scalars(
        select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)
    ).all()
    return [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
             "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit,
             "temp_zone": l.temp_zone} for l in lanes]


def _with_sets(summary: dict) -> dict:
    """在引擎汇总上补充待补集合 / 冷热相邻冲突集合（同一判定结果的不同视图）。"""
    summary["pending"] = [l for l in summary["lines"] if l["status"] == "need_fill"]
    summary["conflicts"] = [l for l in summary["lines"] if l["status"] == "cold_hot_conflict"]
    return summary


@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "点位不存在")
    # 每次生成都读取当前温区重算；改温区后旧单据不会残留旧判定
    summary = _with_sets(summarize(build_fill_lines(_load_lanes(db, location_id))))
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "location_id": location_id, **summary}


@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    order = db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                       .order_by(RefillOrder.id.desc())).first()
    if not order:
        return run_refill(location_id=location_id, db=db)
    data = json.loads(order.lines_json)
    # 兼容历史单据：补齐温区视图字段
    data.setdefault("pending", [l for l in data["lines"] if l["status"] == "need_fill"])
    data.setdefault("conflicts", [l for l in data["lines"] if l["status"] == "cold_hot_conflict"])
    data.setdefault("cold_hot_conflict_count", len(data["conflicts"]))
    return {"id": order.id, "location_id": location_id, **data}


@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    return {"location_id": location_id, "lanes": [l for l in data["lines"] if l["status"] == "full"]}


@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    return {
        "location_id": location_id,
        "total_fill": data["total_fill"],
        "need_fill_count": data["need_fill_count"],
        "full_count": data["full_count"],
        "overbooked_count": data["overbooked_count"],
        "cold_hot_conflict_count": data["cold_hot_conflict_count"],
        "pending": data["pending"],
        "conflicts": data["conflicts"],
    }
