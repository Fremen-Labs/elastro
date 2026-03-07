<script setup lang="ts">
import { ref } from 'vue'

const templateTarget = ref('logs-*')
const activePolicy = ref('Strict Override')

const mockSchema = `{
  "properties": {
    "@timestamp": { "type": "date" },
    "status": { "type": "keyword" }
  }
}`
</script>

<template>
  <div class="mapping-builder-page animate-fade-in">
    <header class="page-header">
      <h1>Mapping Builder</h1>
      <p class="text-muted text-sm mt-2">Visually construct structural index schemas and analyzers.</p>
    </header>

    <div class="card mb-4 mt-4">
      <div class="form-container">
        <p class="mb-4 text-muted">Use this builder to scaffold mappings visually before pushing them to your clusters.</p>
        
        <div class="metrics-grid mb-4" style="gap: 1rem; margin-bottom: 2rem;">
          <div class="detail-row card">
            <span class="detail-label">Template Pattern Target</span>
            <input type="text" v-model="templateTarget" class="cli-input mt-2" style="background: hsl(var(--muted)/0.3); border: 1px solid hsl(var(--border)); padding: 0.5rem; border-radius: 4px; color: white;" />
          </div>
          <div class="detail-row card">
            <span class="detail-label">Dynamic Mapping Policy</span>
            <select v-model="activePolicy" class="cli-input mt-2" style="background: hsl(var(--muted)/0.3); border: 1px solid hsl(var(--border)); padding: 0.5rem; border-radius: 4px; color: white;">
              <option value="Strict Override">Strict Override</option>
              <option value="Dynamic">Dynamic</option>
              <option value="False">False (Runtime only)</option>
            </select>
          </div>
        </div>

        <h3 class="mb-2" style="font-size: 1.1rem; font-weight: 600;">Generated Schema</h3>
        <div class="editor-mockup p-4 bg-black rounded mb-4" style="font-family: var(--font-mono); font-size: 0.9rem; color: #a1a1aa; border: 1px solid hsl(var(--border)); background: hsl(240 10% 4%); white-space: pre;">{{ mockSchema }}</div>
        
        <div style="display: flex; gap: 1rem; margin-top: 1.5rem;">
          <button class="btn btn-primary">Save Template</button>
          <button class="btn btn-secondary">Load Existing Pattern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid hsl(var(--border) / 0.3);
}

.page-header h1 {
  font-size: 2.5rem;
  font-weight: 700;
  letter-spacing: -0.025em;
  color: hsl(var(--foreground));
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 2rem;
}

.text-muted {
  color: hsl(var(--muted-foreground));
}

.text-sm {
  font-size: 0.875rem;
}

.detail-row {
  display: flex;
  flex-direction: column;
}

.detail-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-value {
  font-size: 1rem;
  font-weight: 500;
}
</style>
