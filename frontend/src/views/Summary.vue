<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>({})
onMounted(async () => { s.value = await api('/refills/summary?location_id=1') })
</script>
<template>
  <h1>汇总</h1>
  <p class="sub">本点位补货建议合计 · 待补集合与补货单、货道页同一套冷热相邻判定</p>
  <div class="card grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
    <div><div class="muted">建议补货总量</div><div class="stat">{{ s.total_fill }}</div></div>
    <div><div class="muted">待补货道</div><div class="stat">{{ s.need_fill_count }}</div></div>
    <div><div class="muted">满仓货道</div><div class="stat">{{ s.full_count }}</div></div>
    <div><div class="muted">超占货道</div><div class="stat">{{ s.overbooked_count }}</div></div>
    <div><div class="muted">冷热相邻冲突</div><div class="stat">{{ s.conflict_count }}</div></div>
  </div>
  <div class="card" style="margin-top:1rem">
    <div class="muted">本轮待补集合（出正补量，冲突置 0 道不在内）</div>
    <div class="vf-pending">
      <span v-for="slot in (s.pending_slots || [])" :key="slot" class="badge badge-ok">{{ slot }}</span>
      <span v-if="!(s.pending_slots || []).length" class="muted">无</span>
    </div>
  </div>
</template>
