<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>({})
onMounted(async () => { s.value = await api('/refills/summary?location_id=1') })
</script>
<template>
  <h1>汇总</h1>
  <p class="sub">本点位补货建议合计 · 待补集合与冷热相邻判定同货道页、补货单一致</p>
  <div class="card grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
    <div><div class="muted">建议补货总量</div><div class="stat">{{ s.total_fill }}</div></div>
    <div><div class="muted">待补货道</div><div class="stat">{{ s.need_fill_count }}</div></div>
    <div><div class="muted">满仓货道</div><div class="stat">{{ s.full_count }}</div></div>
    <div><div class="muted">超占货道</div><div class="stat">{{ s.overbooked_count }}</div></div>
    <div><div class="muted">冷热相邻置0</div><div class="stat vf-stat-conflict">{{ s.cold_hot_conflict_count }}</div></div>
  </div>

  <div class="card">
    <div class="muted" style="margin-bottom:0.4rem">待补集合（{{ (s.pending || []).length }}）</div>
    <div v-if="!(s.pending && s.pending.length)" class="muted">本轮无待补货道</div>
    <div class="vf-chip-row">
      <span v-for="l in s.pending" :key="l.lane_id" class="vf-chip vf-chip-need">
        {{ l.slot_no }} {{ l.sku_name }} · 补{{ l.fill_qty }}
      </span>
    </div>
  </div>

  <div class="card">
    <div class="muted" style="margin-bottom:0.4rem">冷热相邻冲突 · 后道本轮补 0（{{ (s.conflicts || []).length }}）</div>
    <div v-if="!(s.conflicts && s.conflicts.length)" class="muted">无冷热相邻冲突</div>
    <div class="vf-chip-row">
      <span v-for="l in s.conflicts" :key="l.lane_id" class="vf-chip vf-chip-conflict">
        {{ l.slot_no }} {{ l.sku_name }} · 缺{{ l.gap }} 补0 · {{ l.reason }}
      </span>
    </div>
  </div>
</template>
