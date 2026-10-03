<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
async function run() { data.value = await api('/refills/run?location_id=1', { method: 'POST' }) }
onMounted(run)

function statusLabel(s: string) {
  if (s === 'need_fill') return '待补'
  if (s === 'full') return '满仓'
  if (s === 'overbooked') return '超占'
  if (s === 'cold_hot_conflict') return '冷热冲突'
  return s
}
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 冷热相邻后道本轮补 0 · 收据纸样式</p>
  <button class="btn" @click="run">重新生成补货单</button>
  <div style="margin-top:1rem" v-if="data">
    <div class="vf-receipt">
      <h2>*** VendFill 补货单 ***</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div
        class="vf-receipt-line"
        v-for="l in data.lines"
        :key="l.lane_id"
        :class="{ 'vf-receipt-conflict': l.status === 'cold_hot_conflict' }"
      >
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small>({{ statusLabel(l.status) }})</small>
          <small v-if="l.reason" class="vf-receipt-reason">（{{ l.reason }}）</small>
        </span>
        <span>{{ l.fill_qty }} / 缺{{ l.gap }}</span>
      </div>
      <div v-if="data.cold_hot_conflict_count" class="vf-receipt-note">
        冷热相邻冲突 {{ data.cold_hot_conflict_count }} 道，后道本轮补量 0
      </div>
      <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">谢谢使用 · 请核对后装机</p>
    </div>
  </div>
</template>
