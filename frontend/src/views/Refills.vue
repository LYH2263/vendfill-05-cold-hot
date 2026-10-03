<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
async function run() {
  // 每次生成按当前已登记温区实时重算冷热相邻冲突
  data.value = await api('/refills/run?location_id=1', { method: 'POST' })
}
onMounted(run)
function statusText(l: any) {
  if (l.reason) return l.reason
  return l.status === 'need_fill' ? '待补' : l.status === 'full' ? '满仓' : '超占'
}
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 冷热邻道后登记道补量置 0 · 收据纸样式</p>
  <button class="btn" @click="run">生成补货单</button>
  <div style="margin-top:1rem" v-if="data">
    <div class="vf-receipt">
      <h2>*** VendFill 补货单 ***</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div class="vf-receipt-line" v-for="l in data.lines" :key="l.lane_id"
           :class="{ 'vf-line-conflict': l.reason }">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small class="vf-zone-mini">[{{ l.zone === 'cold' ? '冷' : '热' }}]</small>
          <small :class="l.reason ? 'vf-reason-tag' : ''">({{ statusText(l) }})</small>
        </span>
        <span>{{ l.fill_qty }} / 缺{{ l.gap }}</span>
      </div>
      <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">谢谢使用 · 请核对后装机</p>
    </div>
  </div>
</template>
