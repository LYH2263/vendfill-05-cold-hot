"""Vending refill: gap = capacity - stock - in_transit; fills capped by gap; no negative fills.

同柜冷热邻道互斥（唯一一套相邻判定，货道页 / 补货单行集合 / 汇总待补集合共用）：
- 货道登记温区为「冷(cold)」或「热(hot)」，未标温区按热兼容（normalize_temp_zone）。
- 同一点位内按货道编号自然排序后，相邻两道温区一冷一热即构成冷热相邻冲突对。
- 冲突对中后登记（排序靠后）的一道本轮补量强制为 0，先道仍按缺口正常补；两边不会都出正补量。
- 被置 0 的道 reason 只写「冷热相邻冲突」，不与封锁、整机上限等其他原因并句。
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

# 原因独立成句，禁止与其它原因并句（如「冷热相邻冲突,封锁」）
COLD_HOT_REASON = "冷热相邻冲突"

# 温区取值
_ZONE_COLD = "cold"
_ZONE_HOT = "hot"


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
    status: str  # need_fill | full | overbooked | cold_hot_conflict
    temp_zone: str = _ZONE_HOT  # cold | hot，未标温区按热兼容
    reason: str = ""  # 仅冷热相邻置 0 时写「冷热相邻冲突」，独立成句


def normalize_temp_zone(zone: object) -> str:
    """冷/热/空 -> 'cold'/'hot'；未标温区（None/空串）按热兼容，未识别值也按热兼容。"""
    if zone is None:
        return _ZONE_HOT
    z = str(zone).strip().lower()
    if z in ("cold", "c", "冷"):
        return _ZONE_COLD
    return _ZONE_HOT


def _natural_key(slot_no: str) -> list:
    """按编号排序的自然序：A2 在 A10 前；数字段按数值、非数字段按文本交替比较。"""
    out: list = []
    for t in re.findall(r"\d+|\D+", str(slot_no)):
        if t.isdigit():
            out.append((0, int(t)))
        else:
            out.append((1, t.lower()))
    return out


def _conflict_later_ids(ordered: list[dict]) -> set[int]:
    """同柜按编号排序后，相邻两道一冷一热 -> 返回「后登记那道」(排序靠后) 的 id 集合。

    纯函数：调用方负责按点位分组；入参必须已按 slot_no 自然序排列。
    每个相邻对只置后道为 0，先道不受影响，因此一对冲突绝不会两边都出正补量。
    """
    blocked: set[int] = set()
    zones = [normalize_temp_zone(o.get("temp_zone")) for o in ordered]
    for i in range(len(ordered) - 1):
        if zones[i] != zones[i + 1]:  # 一冷一热
            blocked.add(ordered[i + 1]["id"])
    return blocked


def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit


def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested 可选期望补量；受缺口与冷热邻道互斥约束，绝不返回负补量或冲突双正补量。"""
    # 统一的排序与相邻判定（货道页 / 补货单行集合 / 汇总待补集合共用此入口）
    ordered = sorted(lanes, key=lambda l: _natural_key(str(l["slot_no"])))
    blocked = _conflict_later_ids(ordered)

    lines: list[FillLine] = []
    for lane in ordered:
        zone = normalize_temp_zone(lane.get("temp_zone"))
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
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
        reason = ""
        if lane["id"] in blocked and fill > 0:
            # 后道本会出正补量 -> 因冷热相邻强制本轮补 0；原因独立成句。
            # 后道本身满仓/超占（补量本就为 0）时保留其原状态，不重复归因。
            fill = 0
            status = "cold_hot_conflict"
            reason = COLD_HOT_REASON
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status,
            temp_zone=zone, reason=reason,
        ))
    return lines


def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == "need_fill"),
        "full_count": sum(1 for l in lines if l.status == "full"),
        "overbooked_count": sum(1 for l in lines if l.status == "overbooked"),
        "cold_hot_conflict_count": sum(1 for l in lines if l.status == "cold_hot_conflict"),
        "lines": [asdict(l) for l in lines],
    }
