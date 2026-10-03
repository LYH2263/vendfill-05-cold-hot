<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const refill = ref<any>(null)
const savingId = ref<number | null>(null)

async function loadRefill() {
  try { refill.value = await api('/refills/run?location_id=1', { method: 'POST' }) } catch { /* */ }
}
async function loadLanes() {
  rows.value = await api('/lanes?location_id=1')
}
async function saveZone(r: any) {
  savingId.value = r.id
  try {
    await api(`/lanes/${r.id}`, { method: 'PATCH', body: JSON.stringify({ temp_zone: r.temp_zone }) })
    // 改温区后用新温区重算：货道网格与右侧小票同一套相邻判定同时刷新
    await Promise.all([loadLanes(), loadRefill()])
  } finally {
    savingId.value = null
  }
}
onMounted(async () => {
  await Promise.all([loadLanes(), loadRefill()])
})
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 温区冷热相邻互斥 · 右侧补货小票</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot" :class="{ 'vf-conflict': r.cold_hot_conflict }">
        <div class="vf-slot-head">
          <span class="vf-slot-no">{{ r.slot_no }}</span>
          <select
            class="vf-zone"
            :class="r.temp_zone === 'cold' ? 'vf-zone-cold' : 'vf-zone-hot'"
            :value="r.temp_zone"
            :disabled="savingId === r.id"
            @change="(e) => { r.temp_zone = (e.target as HTMLSelectElement).value; saveZone(r) }"
            title="登记温区：冷 / 热（未标按热兼容），重开仍保留"
          >
            <option value="hot">热</option>
            <option value="cold">冷</option>
          </select>
        </div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0 && !r.cold_hot_conflict }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }} · 补 {{ r.fill_qty }}</div>
        <div v-if="r.cold_hot_conflict" class="vf-conflict-tag">{{ r.reason }}</div>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id"
           :class="{ 'vf-receipt-conflict': l.status === 'cold_hot_conflict' }">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small v-if="l.reason" class="vf-receipt-reason">（{{ l.reason }}）</small>
        </span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 —
      </p>
    </aside>
  </div>
</template>
