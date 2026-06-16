<script setup lang="ts">
import { computed } from 'vue'
import { scoreColor } from '../../types/health'

const {
  score = null,
  status,
  size = 'lg',
  loading = false,
} = defineProps<{
  score?: number | null
  status?: string
  size?: 'sm' | 'lg'
  loading?: boolean
}>()

const color = computed(() => scoreColor(score))
const displayScore = computed(() => (score == null ? '—' : score))

const ringStyle = computed(() => {
  if (score == null) {
    return { background: 'conic-gradient(hsl(var(--muted)) 0deg, hsl(var(--muted)) 360deg)' }
  }
  const pct = Math.min(100, Math.max(0, score))
  const deg = (pct / 100) * 360
  return {
    background: `conic-gradient(${color.value} 0deg ${deg}deg, hsl(var(--muted)) ${deg}deg 360deg)`,
  }
})
</script>

<template>
  <div class="health-score" :class="`health-score--${size}`">
    <div v-if="loading" class="health-score__ring skeleton"></div>
    <div v-else class="health-score__ring" :style="ringStyle">
      <div class="health-score__inner">
        <span class="health-score__value">{{ displayScore }}</span>
        <span v-if="score != null" class="health-score__max">/100</span>
      </div>
    </div>
    <p v-if="status && !loading" class="health-score__status label-caps">{{ status }}</p>
  </div>
</template>

<style scoped>
.health-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.health-score__ring {
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
}

.health-score--lg .health-score__ring {
  width: 140px;
  height: 140px;
}

.health-score--sm .health-score__ring {
  width: 56px;
  height: 56px;
  padding: 3px;
}

.health-score__inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: hsl(var(--card));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.health-score--lg .health-score__value {
  font-size: 2.25rem;
  font-weight: 700;
}

.health-score--sm .health-score__value {
  font-size: 0.95rem;
  font-weight: 700;
}

.health-score__max {
  font-size: 0.75rem;
  color: hsl(var(--muted-foreground));
  margin-top: 0.15rem;
}

.health-score--sm .health-score__max {
  display: none;
}

.health-score__status {
  color: hsl(var(--muted-foreground));
  font-size: 0.7rem;
}
</style>