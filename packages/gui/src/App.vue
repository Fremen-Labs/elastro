<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { LayoutDashboard, BookOpen, FileCode2, Settings, AlertTriangle } from 'lucide-vue-next'
import { state } from './store'

const router = useRouter()
const route = useRoute()

onMounted(() => {
  let token = new URLSearchParams(window.location.search).get('token') || ''
  if (!token) {
    const hashMatches = window.location.hash.match(/[?&]token=([^&]+)/)
    if (hashMatches && hashMatches[1]) {
      token = hashMatches[1]
    }
  }

  if (token) {
    state.token = token
  }
})

const navigate = (path: string) => {
  router.push(path)
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/docs', label: 'Documentation', icon: BookOpen },
  { path: '/mapping-builder', label: 'Mapping Builder', icon: FileCode2 },
  { path: '/settings', label: 'Settings', icon: Settings },
]
</script>

<template>
  <div class="layout">
    <aside class="sidebar glass-panel">
      <div class="sidebar-header">
        <div class="logo-mark" aria-hidden="true">E</div>
        <div class="brand-text">
          <h2>Elastro</h2>
          <span class="brand-sub label-caps">Cluster Ops</span>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="Main navigation">
        <button
          v-for="item in navItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: route.path === item.path }"
          @click="navigate(item.path)"
        >
          <component :is="item.icon" :size="20" class="nav-icon" />
          {{ item.label }}
        </button>
      </nav>

      <div v-if="!state.token" class="token-warning animate-fade-in" role="status">
        <AlertTriangle :size="16" />
        <span>No security token found. Launch via <code>elastro gui</code>.</span>
      </div>
    </aside>

    <main class="main-content">
      <div class="page-wrapper">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>

      <footer class="app-footer">
        <p>Elastro &copy; {{ new Date().getFullYear() }} Fremen Labs</p>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  width: 100%;
  height: 100%;
}

.sidebar {
  width: 260px;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 1.5rem 1rem;
  border-right: 1px solid hsl(var(--border));
  z-index: 10;
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  margin-bottom: 2rem;
  padding: 0 0.5rem;
}

.logo-mark {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--gradient-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.25rem;
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
}

.brand-text h2 {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  color: hsl(var(--foreground));
}

.brand-sub {
  color: hsl(var(--muted-foreground));
  font-size: 0.65rem;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.7rem 0.875rem;
  border-radius: var(--radius);
  background: transparent;
  border: none;
  border-left: 3px solid transparent;
  color: hsl(var(--muted-foreground));
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  text-align: left;
  font-family: inherit;
}

.nav-item:hover {
  background: hsl(var(--muted));
  color: hsl(var(--foreground));
}

.nav-item:focus-visible {
  outline: 2px solid hsl(var(--ring));
  outline-offset: 2px;
}

.nav-item.active {
  background: hsl(var(--nav-active-bg));
  border-left-color: hsl(var(--primary));
  color: hsl(var(--foreground));
  font-weight: 600;
}

.nav-icon {
  flex-shrink: 0;
  opacity: 0.85;
}

.nav-item.active .nav-icon {
  color: hsl(var(--primary));
  opacity: 1;
}

.token-warning {
  margin-top: auto;
  padding: 0.875rem;
  border-radius: var(--radius);
  background: hsl(var(--destructive) / 0.1);
  color: hsl(var(--destructive));
  font-size: 0.8rem;
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  line-height: 1.4;
  border: 1px solid hsl(var(--destructive) / 0.2);
}

.token-warning code {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: hsl(var(--destructive) / 0.15);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
}

.main-content {
  flex: 1;
  height: 100%;
  overflow-y: auto;
  padding: 2.5rem 2.5rem 0;
  background-color: hsl(var(--background));
  background-image: var(--gradient-hero);
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.page-wrapper {
  flex: 1 0 auto;
}

.app-footer {
  margin-top: auto;
  padding: 2rem 0;
  border-top: 1px solid hsl(var(--border) / 0.5);
  color: hsl(var(--muted-foreground));
  font-size: 0.8rem;
  text-align: center;
  flex-shrink: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active {
    transition: opacity 0.1s ease;
  }

  .fade-enter-from,
  .fade-leave-to {
    transform: none;
  }
}
</style>