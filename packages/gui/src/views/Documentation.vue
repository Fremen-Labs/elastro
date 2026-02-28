<script setup lang="ts">
import { ref } from 'vue';
import CLIDocs from '../components/docs/CLIDocs.vue';
import APIDocs from '../components/docs/APIDocs.vue';

const activeTab = ref('cli');
</script>

<template>
  <div class="docs-wrapper animate-fade-in relative z-10 w-full h-full">
    <!-- Background Glow Effects -->
    <div class="bg-glow bg-glow-primary"></div>
    <div class="bg-glow bg-glow-accent"></div>
    
    <div class="tabs-container relative z-20">
      <div class="tabs-list">
        <button 
          :class="['tab-trigger', { active: activeTab === 'cli' }]" 
          @click="activeTab = 'cli'"
        >
          Elastro CLI
        </button>
        <button 
          :class="['tab-trigger', { active: activeTab === 'api' }]" 
          @click="activeTab = 'api'"
        >
          Python API
        </button>
      </div>

      <div class="tabs-content">
        <CLIDocs v-if="activeTab === 'cli'" />
        <APIDocs v-if="activeTab === 'api'" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.docs-wrapper {
  position: relative;
  min-height: 100%;
}

.bg-glow {
  position: absolute;
  width: 50vw;
  height: 50vh;
  border-radius: 50%;
  filter: blur(140px);
  z-index: 1;
  pointer-events: none;
  opacity: 0.25;
}

.bg-glow-primary {
  top: -10%;
  right: -10%;
  background: radial-gradient(circle, hsl(var(--primary)) 0%, transparent 70%);
}

.bg-glow-accent {
  bottom: -20%;
  left: -20%;
  background: radial-gradient(circle, hsl(var(--teal)) 0%, transparent 70%);
}

.tabs-container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.tabs-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  width: 100%;
  max-width: 400px;
  margin: 0 auto 2rem auto;
  background: hsl(var(--muted) / 0.5);
  padding: 0.375rem;
  border-radius: 0.75rem;
  border: 1px solid hsl(var(--border) / 0.5);
  gap: 0.25rem;
}

.tab-trigger {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  border: none;
  background: transparent;
  color: hsl(var(--muted-foreground));
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-trigger:hover {
  color: hsl(var(--foreground));
}

.tab-trigger.active {
  background: hsl(var(--card));
  color: hsl(var(--foreground));
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.tabs-content {
  width: 100%;
}
</style>
