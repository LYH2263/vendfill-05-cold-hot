from app.services.fill_engine import (
    COLD_HOT_REASON,
    build_fill_lines,
    compute_gap,
    normalize_temp_zone,
    summarize,
)


def _lane(id, slot, zone, cap=20, stock=5, transit=0):
    return {"id": id, "slot_no": slot, "sku_name": slot, "capacity": cap,
            "stock": stock, "in_transit": transit, "temp_zone": zone}


def _by_id(lines):
    return {l.slot_no: l for l in lines}


def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5


def test_no_negative_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 12, "in_transit": 0}]
    lines = build_fill_lines(lanes)
    assert lines[0].fill_qty == 0
    assert lines[0].status == "overbooked"


def test_cap_by_gap():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0}]
    lines = build_fill_lines(lanes, requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15


def test_full_zero_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 8, "in_transit": 2}]
    s = summarize(build_fill_lines(lanes))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0


# ---------- 冷热邻道互斥 ----------

def test_seed_a1_cold_a2_hot_later_zero():
    """种子情形：A1 冷、A2 热；按编号 A1 正常补，A2 补量 0 且原因独立成句。"""
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot")]
    m = _by_id(build_fill_lines(lanes))
    assert m["A1"].fill_qty == 15 and m["A1"].status == "need_fill"
    assert m["A2"].fill_qty == 0
    assert m["A2"].status == "cold_hot_conflict"
    assert m["A2"].reason == COLD_HOT_REASON == "冷热相邻冲突"
    # 绝不两边都出正补量
    assert not (m["A1"].fill_qty > 0 and m["A2"].fill_qty > 0)


def test_reason_is_standalone_sentence():
    """原因只写冷热相邻冲突，不与封锁、整机上限等并句。"""
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot")]
    reason = _by_id(build_fill_lines(lanes))["A2"].reason
    assert reason == "冷热相邻冲突"
    for token in ("封锁", "整机", "上限", ",", "，", ";", "；"):
        assert token not in reason


def test_unmarked_zone_defaults_hot_compatible():
    """未标温区按热兼容：冷道在前 + 未标道在后 -> 后道被置 0。"""
    lanes = [
        {"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5,
         "in_transit": 0, "temp_zone": "cold"},
        {"id": 2, "slot_no": "A2", "sku_name": "可乐", "capacity": 18, "stock": 10,
         "in_transit": 0},  # 未标
    ]
    m = _by_id(build_fill_lines(lanes))
    assert m["A2"].temp_zone == "hot"
    assert m["A2"].fill_qty == 0 and m["A2"].status == "cold_hot_conflict"
    assert m["A1"].fill_qty > 0


def test_same_zone_pair_not_conflicted():
    """冷冷、热热相邻不互斥，两道都正常出补量。"""
    colds = _by_id(build_fill_lines([_lane(1, "A1", "cold"), _lane(2, "A2", "cold")]))
    hots = _by_id(build_fill_lines([_lane(3, "B1", "hot"), _lane(4, "B2", None)]))
    assert colds["A1"].fill_qty > 0 and colds["A2"].fill_qty > 0
    assert colds["A2"].reason == ""
    assert hots["B1"].fill_qty > 0 and hots["B2"].fill_qty > 0


def test_rezone_recomputes_conflict():
    """改温区后重算：A2 由热改冷 -> 冲突消失，A2 恢复正补量，不得仍按旧温区出双正补量逻辑。"""
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot")]
    before = _by_id(build_fill_lines(lanes))
    assert before["A2"].fill_qty == 0
    # 用户在货道页把 A2 改成冷（落库后重新生成等价于传入新温区）
    lanes[1]["temp_zone"] = "cold"
    after = _by_id(build_fill_lines(lanes))
    assert after["A1"].fill_qty > 0 and after["A2"].fill_qty > 0
    assert after["A2"].status == "need_fill" and after["A2"].reason == ""
    # 两道都改成热同样消除冲突
    lanes[0]["temp_zone"] = "hot"
    lanes[1]["temp_zone"] = "hot"
    both_hot = _by_id(build_fill_lines(lanes))
    assert both_hot["A1"].fill_qty > 0 and both_hot["A2"].fill_qty > 0


def test_rezone_creates_new_conflict():
    """原本同温区不冲突，把先道改冷后应立即产生冲突并置后道为 0。"""
    lanes = [_lane(1, "A1", "hot"), _lane(2, "A2", "hot")]
    assert _by_id(build_fill_lines(lanes))["A2"].fill_qty > 0
    lanes[0]["temp_zone"] = "cold"
    m = _by_id(build_fill_lines(lanes))
    assert m["A1"].fill_qty > 0 and m["A2"].fill_qty == 0
    assert m["A2"].reason == "冷热相邻冲突"


def test_order_independent_input_and_natural_sort():
    """乱序传入仍按编号自然序判定（A2 在 A10 前），后道置 0。"""
    lanes = [_lane(10, "A10", "cold"), _lane(2, "A2", "hot"), _lane(1, "A1", "cold")]
    lines = build_fill_lines(lanes)
    slots = [l.slot_no for l in lines]
    assert slots == ["A1", "A2", "A10"]
    m = _by_id(lines)
    assert m["A1"].fill_qty > 0
    assert m["A2"].fill_qty == 0  # A1(冷) -> A2(热) 后道
    assert m["A10"].fill_qty == 0  # A2(热) -> A10(冷) 相邻且一冷一热，A10 为后道


def test_chain_never_double_positive():
    """冷-热-冷链：每个冷热相邻对都不得双正；中间与末道作为后道被置 0。"""
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot"), _lane(3, "A3", "cold")]
    m = _by_id(build_fill_lines(lanes))
    assert m["A1"].fill_qty > 0
    assert m["A2"].fill_qty == 0 and m["A3"].fill_qty == 0


def test_blocked_lane_with_no_gap_keeps_full():
    """后道本就满仓（补量本为 0）时保留满仓状态，不重复归因。"""
    lanes = [_lane(1, "A1", "cold"),
             _lane(2, "A2", "hot", cap=18, stock=18, transit=0)]
    m = _by_id(build_fill_lines(lanes))
    assert m["A2"].fill_qty == 0 and m["A2"].status == "full" and m["A2"].reason == ""


def test_summary_conflict_count():
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot"),
             _lane(3, "B1", "hot"), _lane(4, "B2", "hot")]
    s = summarize(build_fill_lines(lanes))
    assert s["cold_hot_conflict_count"] == 1
    assert s["total_fill"] == 15 + 15 + 15  # A1 + B1 + B2，A2 被置 0


def test_normalize_temp_zone_aliases():
    assert normalize_temp_zone("cold") == "cold"
    assert normalize_temp_zone("冷") == "cold"
    assert normalize_temp_zone("HOT") == "hot"
    assert normalize_temp_zone("热") == "hot"
    assert normalize_temp_zone("") == "hot"
    assert normalize_temp_zone(None) == "hot"
    assert normalize_temp_zone("weird") == "hot"
