<script setup lang="ts">
defineProps<{
  title: string
  description?: string
  eyebrow?: string
}>()
</script>

<template>
  <header class="page-header">
    <div class="page-header__content">
      <p v-if="eyebrow" class="page-header__eyebrow label-caps">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p v-if="description" class="page-header__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.page-header__eyebrow {
  margin-bottom: 0.35rem;
  color: hsl(var(--primary));
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 0.25rem;
}

.page-header__description {
  color: hsl(var(--muted-foreground));
  font-size: 1rem;
  max-width: 42rem;
}

.page-header__actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
</style>