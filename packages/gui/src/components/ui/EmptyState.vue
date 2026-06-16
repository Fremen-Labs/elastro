<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="empty-state card">
    <div v-if="$slots.icon" class="empty-state__icon">
      <slot name="icon" />
    </div>
    <h2>{{ title }}</h2>
    <p v-if="description">{{ description }}</p>
    <div v-if="$slots.actions" class="empty-state__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-state__icon {
  color: hsl(var(--muted-foreground));
  margin-bottom: 1rem;
  opacity: 0.6;
}

.empty-state h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.empty-state p {
  color: hsl(var(--muted-foreground));
  max-width: 28rem;
}

.empty-state__actions {
  margin-top: 1.25rem;
}
</style>