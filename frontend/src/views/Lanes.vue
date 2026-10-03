<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const refill = ref<any>(null)
const saving = ref<number | null>(null)

async function run() {
  // 改温区后重新生成：冲突对按最新温区重算
  refill.value = await api('/refills/run?location_id=1', { method: 'POST' })
}

onMounted(async () => {
  rows.value = await api('/lanes')
  await run()
})

async function changeZone(r: any, zone: string) {
  saving.value = r.id
  try {
    // 空串 = 未标温区，后端按热兼容
    const updated = await api(`/lanes/${r.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ zone: zone || null }),
    })
    const i = rows.value.findIndex((x: any) => x.id === r.id)
    if (i >= 0) rows.value[i] = updated
    await run() // 持久化后立即重算，不沿用旧温区
  } finally {
    saving.value = null
  }
}

function zoneLabel(l: any) {
  return l.effective_zone === 'cold' ? '冷' : '热'
}
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 温区可登记（冷/热）· 右侧补货小票</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot" :class="{ 'vf-zone-cold': r.effective_zone === 'cold' }">
        <div class="vf-slot-head">
          <span class="vf-slot-no">{{ r.slot_no }}</span>
          <span class="vf-zone-tag" :class="r.effective_zone === 'cold' ? 'vf-zone-cold-tag' : 'vf-zone-hot-tag'">
            {{ zoneLabel(r) }}<template v-if="!r.zone">·兼容</template>
          </span>
        </div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0 }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }}</div>
        <label class="vf-zone-edit">
          温区
          <select :value="r.zone ?? ''" :disabled="saving === r.id"
                  @change="changeZone(r, ($event.target as HTMLSelectElement).value)">
            <option value="">未标（按热）</option>
            <option value="cold">冷</option>
            <option value="hot">热</option>
          </select>
        </label>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}</span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <div v-for="l in refill.lines.filter((x: any) => x.reason)" :key="'r' + l.lane_id"
           class="vf-receipt-reason">
        {{ l.slot_no }} 补量 0 · {{ l.reason }}
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 —
      </p>
    </aside>
  </div>
</template>
