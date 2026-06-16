<script setup lang="ts">
import type { FindingDetailSections, HealthFinding } from '../../types/health'

const props = defineProps<{
  finding: HealthFinding
}>()

const sections = (): FindingDetailSections | null => {
  const raw = props.finding.metadata?.detail_sections
  return raw && typeof raw === 'object' ? (raw as FindingDetailSections) : null
}
</script>

<template>
  <div class="finding-detail-panel">
    <template v-if="sections()">
      <section v-if="sections()?.why" class="detail-block">
        <h5>Why this matters</h5>
        <p>{{ sections()?.why }}</p>
      </section>

      <section v-if="sections()?.implications?.length" class="detail-block">
        <h5>Performance implications</h5>
        <ul>
          <li v-for="(item, idx) in sections()?.implications" :key="idx">{{ item }}</li>
        </ul>
      </section>

      <section v-if="sections()?.top_indices?.length" class="detail-block">
        <h5>Most affected indices</h5>
        <ul class="index-list">
          <li v-for="item in sections()?.top_indices" :key="item.index">
            <code>{{ item.index }}</code>
            — {{ item.oversharded_shard_count }} oversharded shard(s), smallest
            {{ item.smallest_human }}
          </li>
        </ul>
      </section>

      <section v-if="sections()?.resolution?.length" class="detail-block">
        <h5>How to resolve</h5>
        <div
          v-for="(step, idx) in sections()?.resolution"
          :key="`${step.title}-${idx}`"
          class="resolution-step"
        >
          <strong>{{ idx + 1 }}. {{ step.title }}</strong>
          <p>{{ step.body }}</p>
          <pre
            v-for="(command, cmdIdx) in step.commands || []"
            :key="`${command}-${cmdIdx}`"
            class="command-snippet"
          >{{ command }}</pre>
        </div>
      </section>

      <section v-if="sections()?.cautions?.length" class="detail-block">
        <h5>Before you change production indices</h5>
        <ul>
          <li v-for="(item, idx) in sections()?.cautions" :key="idx">{{ item }}</li>
        </ul>
      </section>

      <section v-if="sections()?.references?.length" class="detail-block references">
        <h5>References</h5>
        <ul>
          <li v-for="(url, idx) in sections()?.references" :key="idx">
            <a :href="url" target="_blank" rel="noopener noreferrer">{{ url }}</a>
          </li>
        </ul>
      </section>
    </template>

    <pre v-else-if="finding.detail" class="detail-fallback">{{ finding.detail }}</pre>
    <p v-else class="text-muted">No expanded guidance available for this finding.</p>
  </div>
</template>

<style scoped>
.finding-detail-panel {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid hsl(var(--border) / 0.6);
  font-size: 0.82rem;
  line-height: 1.5;
}

.detail-block + .detail-block {
  margin-top: 0.85rem;
}

.detail-block h5 {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: hsl(var(--muted-foreground));
  margin: 0 0 0.35rem;
}

.detail-block p {
  margin: 0;
}

.detail-block ul {
  margin: 0.25rem 0 0;
  padding-left: 1.1rem;
}

.index-list code {
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.resolution-step {
  margin-top: 0.5rem;
}

.resolution-step p {
  margin: 0.25rem 0 0.35rem;
}

.command-snippet {
  margin: 0.25rem 0 0;
  padding: 0.5rem 0.65rem;
  border-radius: var(--radius);
  background: hsl(var(--muted) / 0.45);
  border: 1px solid hsl(var(--border));
  font-family: var(--font-mono);
  font-size: 0.75rem;
  white-space: pre-wrap;
  overflow-x: auto;
}

.detail-fallback {
  margin: 0;
  white-space: pre-wrap;
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.references a {
  color: hsl(var(--primary));
  word-break: break-all;
}
</style>