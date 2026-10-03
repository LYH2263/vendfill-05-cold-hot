"""Vending refill: gap = capacity - stock - in_transit; fills capped by gap; no negative fills.

同柜冷热邻道互斥：同一点位内按货道编号排序，相邻两道温区分别为冷/热时，
后登记（id 较大）的一道本轮补量强制为 0，先登记道仍按缺口正常补。
未标温区按热兼容。相邻判定只在本模块实现一次，补货单行集合、满仓集合、
汇总待补集合全部从同一份 build_fill_lines 结果派生。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from itertools import groupby

COLD = "cold"
HOT = "hot"
CONFLICT_REASON = "冷热相邻冲突"


@dataclass
class FillLine:
    lane_id: int
    slot_no: str
    sku_name: str
    capacity: int
    stock: int
    in_transit: int
    gap: int
    fill_qty: int
    status: str  # need_fill | full | overbooked
    zone: str = HOT        # effective zone: 未标温区按热兼容
    reason: str = ""       # 补量被置 0 的单独原因，不与其他原因并句


def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit


def effective_zone(zone: str | None) -> str:
    """温区归一：未标温区（None/空串）按热兼容。"""
    return COLD if zone == COLD else HOT


def is_cold_hot_adjacent(zone_a: str | None, zone_b: str | None) -> bool:
    """相邻两道是否构成冷/热互斥对。冷=冷、热=热（含未标）均不冲突。"""
    return effective_zone(zone_a) != effective_zone(zone_b)


def _later_lane_id(lane_a: dict, lane_b: dict) -> int:
    """冲突对中后登记的那一道（id 较大者）。"""
    return max(int(lane_a["id"]), int(lane_b["id"]))


def find_temperature_blocked(lanes: list[dict]) -> set[int]:
    """同一点位内按货道编号排序，返回因冷热相邻而被置 0 的货道 id 集合。

    每个冷/热相邻对中后登记（id 较大）的一道被封锁；一道可能同时与左右
    两道构成冲突对，因此以集合收集。
    """
    blocked: set[int] = set()
    ordered = sorted(lanes, key=lambda l: (l.get("location_id", 0), l["slot_no"]))
    for _loc, group in groupby(ordered, key=lambda l: l.get("location_id", 0)):
        group_lanes = list(group)
        for prev, cur in zip(group_lanes, group_lanes[1:]):
            if is_cold_hot_adjacent(prev.get("zone"), cur.get("zone")):
                blocked.add(_later_lane_id(prev, cur))
    return blocked


def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested optional desired fill per lane_id; capped by gap; never negative.

    冷/热相邻冲突对中后登记道本轮补量强制为 0，原因单独记为冷热相邻冲突。
    """
    blocked_ids = find_temperature_blocked(lanes)
    lines: list[FillLine] = []
    for lane in sorted(lanes, key=lambda l: (l.get("location_id", 0), l["slot_no"])):
        zone = effective_zone(lane.get("zone"))
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
        reason = ""
        if gap < 0:
            status = "overbooked"
            fill = 0
        elif gap == 0:
            status = "full"
            fill = 0
        else:
            status = "need_fill"
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            fill = max(0, min(desire, gap))
            if int(lane["id"]) in blocked_ids and fill > 0:
                # 后登记道在冷热相邻冲突中被置 0；先登记道不受影响。
                fill = 0
                reason = CONFLICT_REASON
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status, zone=zone, reason=reason,
        ))
    return lines


def summarize(lines: list[FillLine]) -> dict:
    pending = [l for l in lines if l.fill_qty > 0]
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == "need_fill"),
        "full_count": sum(1 for l in lines if l.status == "full"),
        "overbooked_count": sum(1 for l in lines if l.status == "overbooked"),
        "conflict_count": sum(1 for l in lines if l.reason == CONFLICT_REASON),
        # 汇总待补集合：真正出正补量的货道，冲突置 0 道不在其中
        "pending_slots": [l.slot_no for l in pending],
        "lines": [asdict(l) for l in lines],
    }
