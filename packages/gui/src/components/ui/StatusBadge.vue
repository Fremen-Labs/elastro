<script setup lang="ts">
import { computed } from 'vue'
import { healthColor, healthPulse, type ClusterHealth } from '../../utils/health'

const props = withDefaults(
  defineProps<{
    status: ClusterHealth
    variant?: 'solid' | 'outline'
    pulse?: boolean
  }>(),
  {
    variant: 'solid',
    pulse: undefined,
  }
)

const color = computed(() => healthColor(props.status))
const shouldPulse = computed(() => props.pulse ?? healthPulse(props.status))
</script>

<template>
  <span
    class="status-badge"
    :class="{
      'status-badge--outline': variant === 'outline',
      'status-badge--pulse': shouldPulse,
    }"
    :style="
      variant === 'outline'
        ? { borderColor: color, color }
        : { backgroundColor: color }
    "
  >
    {{ status }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  line-height: 1.2;
}

.status-badge--outline {
  background: transparent;
  border: 1.5px solid;
}

.status-badge--pulse {
  animation: pulse-health 2s infinite;
}

@keyframes pulse-health {
  0% {
    box-shadow: 0 0 0 0 hsl(var(--health-red) / 0.6);
  }
  70% {
    box-shadow: 0 0 0 10px hsl(var(--health-red) / 0);
  }
  100% {
    box-shadow: 0 0 0 0 hsl(var(--health-red) / 0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-badge--pulse {
    animation: none;
  }
}
</style>