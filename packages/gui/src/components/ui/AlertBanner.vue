<script setup lang="ts">
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-vue-next'
import { computed } from 'vue'

const props = defineProps<{
  variant: 'error' | 'warning' | 'success' | 'info'
}>()

const icon = computed(() => {
  switch (props.variant) {
    case 'error':
      return AlertCircle
    case 'warning':
      return AlertTriangle
    case 'success':
      return CheckCircle2
    default:
      return Info
  }
})
</script>

<template>
  <div class="alert-banner" :class="`alert-banner--${variant}`" role="alert">
    <component :is="icon" :size="20" class="alert-banner__icon" />
    <div class="alert-banner__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.alert-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border-radius: var(--radius);
  margin-bottom: 1.5rem;
  font-weight: 500;
  font-size: 0.9rem;
  border: 1px solid transparent;
}

.alert-banner__icon {
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.alert-banner__body {
  flex: 1;
  line-height: 1.5;
}

.alert-banner--error {
  background: hsl(var(--destructive) / 0.12);
  color: hsl(var(--destructive));
  border-color: hsl(var(--destructive) / 0.25);
}

.alert-banner--warning {
  background: hsl(var(--warning) / 0.12);
  color: hsl(var(--warning));
  border-color: hsl(var(--warning) / 0.25);
}

.alert-banner--success {
  background: hsl(var(--success) / 0.12);
  color: hsl(var(--success));
  border-color: hsl(var(--success) / 0.25);
}

.alert-banner--info {
  background: hsl(var(--info) / 0.12);
  color: hsl(var(--info));
  border-color: hsl(var(--info) / 0.25);
}
</style>