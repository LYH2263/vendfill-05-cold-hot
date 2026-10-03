from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane
from app.services.fill_engine import build_fill_lines, normalize_temp_zone
router = APIRouter(prefix="/lanes", tags=["lanes"])


class ZoneUpdate(BaseModel):
    temp_zone: str  # cold | hot；空/其它按热兼容


def _lanes_with_fill(rows: list[Lane]) -> list[dict]:
    """按点位分组走同一套 fill_engine 相邻判定，回填温区/补量/冲突原因，保证各页一致。"""
    by_loc: dict[int, list[Lane]] = {}
    for r in rows:
        by_loc.setdefault(r.location_id, []).append(r)

    line_by_id: dict[int, dict] = {}
    for group in by_loc.values():
        payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                    "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit,
                    "temp_zone": l.temp_zone} for l in group]
        for line in build_fill_lines(payload):
            line_by_id[line.lane_id] = {
                "gap": line.gap, "fill_qty": line.fill_qty, "status": line.status,
                "temp_zone": line.temp_zone, "reason": line.reason,
            }

    out = []
    for r in rows:
        f = line_by_id[r.id]
        out.append({
            "id": r.id, "location_id": r.location_id, "slot_no": r.slot_no,
            "sku_name": r.sku_name, "capacity": r.capacity, "stock": r.stock,
            "in_transit": r.in_transit,
            "temp_zone": f["temp_zone"], "gap": f["gap"], "fill_qty": f["fill_qty"],
            "status": f["status"], "reason": f["reason"],
            "cold_hot_conflict": f["status"] == "cold_hot_conflict",
            "fill_pct": round(r.stock / r.capacity * 100, 1) if r.capacity else 0,
        })
    return out


@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None:
        q = q.where(Lane.location_id == location_id)
    return _lanes_with_fill(list(db.scalars(q).all()))


@router.patch("/{lane_id}")
def update_zone(lane_id: int, body: ZoneUpdate, db: Session = Depends(get_db)):
    lane = db.get(Lane, lane_id)
    if not lane:
        raise HTTPException(404, "货道不存在")
    lane.temp_zone = normalize_temp_zone(body.temp_zone)  # 冷/热落库，未标按热兼容
    db.commit()
    return {"id": lane.id, "temp_zone": lane.temp_zone}
