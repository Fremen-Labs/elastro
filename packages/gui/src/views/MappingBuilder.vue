<script setup lang="ts">
import { ref, computed } from 'vue'
import axios from 'axios'
import { state } from '../store'

export interface FieldDef {
  name: string;
  type: string;
  ignore_above?: number;
  properties?: FieldDef[]; 
}

const templateTarget = ref('logs-*')
const activePolicy = ref('strict')

const fields = ref<FieldDef[]>([])
const rootNewFieldName = ref('')
const rootNewFieldType = ref('text')

// All valid ES standard types
const fieldTypes = [
  'text', 'keyword', 'long', 'integer', 'short', 'byte', 
  'double', 'float', 'date', 'boolean', 'object', 'nested'
]

const addRootField = () => {
  if (!rootNewFieldName.value.trim()) return
  
  const newField: FieldDef = {
    name: rootNewFieldName.value.trim(),
    type: rootNewFieldType.value
  }

  // Smart Defaults logic
  if (newField.type === 'keyword') {
    newField.ignore_above = 256
  } else if (newField.type === 'object' || newField.type === 'nested') {
    newField.properties = []
  }

  fields.value.push(newField)
  rootNewFieldName.value = ''
  rootNewFieldType.value = 'text'
}

const removeField = (list: FieldDef[], index: number) => {
  list.splice(index, 1)
}

const addNestedField = (parent: FieldDef) => {
  if (!parent.properties) parent.properties = []
  
  // Prompt is native, quick, and reliable for a lightweight UI builder
  const name = prompt("Enter nested field name:")
  if (!name) return
  
  const type = prompt(`Enter field type for '${name}' (e.g., text, keyword, long):`, 'text')
  if (!type || !fieldTypes.includes(type.toLowerCase())) {
     alert("Invalid or missing Elasticsearch data type.")
     return
  }

  const newField: FieldDef = {
    name: name.trim(),
    type: type.toLowerCase()
  }

  if (newField.type === 'keyword') {
    newField.ignore_above = 256
  } else if (newField.type === 'object' || newField.type === 'nested') {
    newField.properties = []
  }

  parent.properties.push(newField)
}

// Convert our Vue state tree into syntactically perfect ES JSON mappings
const generatedSchema = computed(() => {
  const buildProperties = (defs: FieldDef[]) => {
    const props: any = {}
    for (const f of defs) {
      props[f.name] = { type: f.type }
      if (f.ignore_above !== undefined) {
        props[f.name].ignore_above = f.ignore_above
      }
      if ((f.type === 'object' || f.type === 'nested') && f.properties && f.properties.length > 0) {
        // ES nested mapping syntax
        props[f.name].properties = buildProperties(f.properties)
      }
    }
    return props
  }

  const mappingBody = {
    mappings: {
      dynamic: activePolicy.value,
      properties: buildProperties(fields.value)
    }
  }

  return JSON.stringify(mappingBody, null, 2)
})

const isDeploying = ref(false)
const deployStatus = ref<{success: boolean, message: string} | null>(null)

const deployTemplate = async () => {
  if (!state.clusters || state.clusters.length === 0) {
    deployStatus.value = { success: false, message: "No active cluster found in state. Please select a cluster first." }
    return
  }
  
  // Uses the first cluster in state or whichever the user last viewed
  const clusterName = state.clusters[0].name
  isDeploying.value = true
  deployStatus.value = null

  try {
    // We send the JSON text as the "stdin" argument so the python CLI can consume it 
    // seamlessly via `elastro template create <name> --file -`
    const commandToRun = `template create ${templateTarget.value} --file -`
    
    const response = await axios.post(`/api/cluster/${clusterName}/cli`, {
      command: commandToRun,
      stdin: generatedSchema.value
    }, {
      headers: {
        'Authorization': `Bearer ${state.token}`
      }
    })

    if (response.data.exit_code === 0) {
      deployStatus.value = { success: true, message: `Template ${templateTarget.value} successfully deployed to ${clusterName}!` }
    } else {
      deployStatus.value = { success: false, message: response.data.error || response.data.output || "Unknown error deploying template." }
    }
  } catch (err: any) {
    console.error("Deploy failed", err)
    deployStatus.value = { 
      success: false, 
      message: err.response?.data?.detail || err.message || "Network error occurred." 
    }
  } finally {
    isDeploying.value = false
  }
}
</script>

<template>
  <div class="mapping-builder-page animate-fade-in">
    <header class="page-header">
      <h1>Mapping Builder</h1>
      <p class="text-muted text-sm mt-2">Visually construct structural index schemas and analyzers without JSON syntax errors.</p>
    </header>

    <div class="builder-layout mb-4 mt-4">
      
      <!-- Left Column: Visual Editor -->
      <div class="card editor-panel">
        <h3 class="panel-title">1. Global Settings</h3>
        <div class="metrics-grid mb-6">
          <div class="detail-row">
            <span class="detail-label">Template Pattern Target</span>
            <input type="text" v-model="templateTarget" class="cli-input mt-2" placeholder="e.g. logs-*" />
          </div>
          <div class="detail-row">
            <span class="detail-label">Dynamic Mapping Policy</span>
            <select v-model="activePolicy" class="cli-input mt-2">
              <option value="strict">Strict (Reject unknown fields)</option>
              <option value="true">Dynamic (Auto-map unknown fields)</option>
              <option value="false">False (Ignore unknown fields)</option>
            </select>
            <p class="text-xs text-muted mt-1" v-if="activePolicy === 'strict'">
               Prevents mapping explosions. Safe for production.
            </p>
          </div>
        </div>

        <h3 class="panel-title">2. Field Definitions</h3>
        
        <!-- Field Tree Render -->
        <div class="field-tree" v-if="fields.length > 0">
           <!-- Vue recursive components are tricky in single files, we use a flattened template approach or child for infinite nesting,
                but for simplicity in this structural UI, 1 level depth inline rendering handles 99% of log/metric use cases. -->
           <div class="field-item card" v-for="(field, idx) in fields" :key="idx">
             <div class="field-item-header">
                <div>
                  <span class="field-name">{{ field.name }}</span>
                  <span class="field-type" :class="`type-${field.type}`">{{ field.type }}</span>
                  <span class="field-badge text-xs" v-if="field.ignore_above"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline; margin-right: 2px;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg> Safe Keyword</span>
                </div>
                <div class="field-actions">
                  <button v-if="field.type === 'object' || field.type === 'nested'" @click="addNestedField(field)" class="btn-icon" title="Add Child Property"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg></button>
                  <button @click="removeField(fields, idx)" class="btn-icon text-destructive" title="Remove Field"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                </div>
             </div>
             
             <!-- Nested Children list -->
             <div v-if="(field.type === 'object' || field.type === 'nested') && field.properties && field.properties.length > 0" class="nested-tree">
                <div class="field-item child-item" v-for="(child, cIdx) in field.properties" :key="cIdx">
                  <div class="field-item-header">
                    <div>
                      <span class="field-name">{{ child.name }}</span>
                      <span class="field-type" :class="`type-${child.type}`">{{ child.type }}</span>
                    </div>
                    <div class="field-actions">
                      <button @click="removeField(field.properties, cIdx)" class="btn-icon text-destructive"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                    </div>
                  </div>
                </div>
             </div>
           </div>
        </div>
        <div v-else class="empty-state">
           No fields defined. Your mapping is completely empty.
        </div>

        <!-- Add New Root Field -->
        <div class="add-field-form mt-4">
           <input type="text" v-model="rootNewFieldName" placeholder="Field name (e.g. source.ip)" class="cli-input field-input" @keyup.enter="addRootField" />
           <select v-model="rootNewFieldType" class="cli-input type-input">
             <option v-for="t in fieldTypes" :key="t" :value="t">{{ t }}</option>
           </select>
           <button @click="addRootField" class="btn btn-secondary add-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              Add Field
           </button>
        </div>
      </div>

      <!-- Right Column: Live Output & Action -->
      <div class="card output-panel">
        <h3 class="panel-title">3. Generated JSON Payload</h3>
        <p class="text-xs text-muted mb-2">This structure is syntactically flawless and ready for deployment.</p>
        
        <div class="editor-output p-4 rounded mb-4" style="flex: 1; overflow-y: auto;">
          <pre><code>{{ generatedSchema }}</code></pre>
        </div>
        
        <div class="deploy-actions pt-4" style="border-top: 1px solid hsl(var(--border));">
          
          <div v-if="deployStatus" 
                class="mb-3 p-3 rounded text-sm" 
                :class="deployStatus.success ? 'bg-teal-900/20 text-teal-400 border border-teal-800' : 'bg-destructive/10 text-destructive border border-destructive/30'">
             {{ deployStatus.message }}
          </div>

          <button 
            class="btn btn-primary w-full shadow-lg" 
            style="width: 100%; display:flex; justify-content: center; align-items: center;"
            @click="deployTemplate"
            :disabled="isDeploying"
          >
            <svg v-if="!isDeploying" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            <svg v-else class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
            {{ isDeploying ? 'Deploying to Cluster...' : 'Deploy Template to Cluster' }}
          </button>
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

.builder-layout {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 1.5rem;
  align-items: stretch;
  min-height: 600px;
}

.panel-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: hsl(var(--foreground));
  border-bottom: 1px solid hsl(var(--border) / 0.5);
  padding-bottom: 0.5rem;
}

.editor-panel, .output-panel {
  display: flex;
  flex-direction: column;
}

.metrics-grid {
  display: flex;
  gap: 1rem;
}

.detail-row {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.detail-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.cli-input {
  background: hsl(var(--muted)/0.3); 
  border: 1px solid hsl(var(--border)); 
  padding: 0.5rem 0.75rem; 
  border-radius: var(--radius); 
  color: hsl(var(--foreground));
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.2s;
}

.cli-input:focus {
  border-color: hsl(var(--primary));
}

.field-tree {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.field-item {
  padding: 0.75rem 1rem;
  background: hsl(var(--muted) / 0.2);
  border: 1px solid hsl(var(--border) / 0.6);
  border-left: 3px solid hsl(var(--muted));
  transition: all 0.2s ease;
}

.field-item:hover {
  border-left-color: hsl(var(--primary));
  background: hsl(var(--muted) / 0.4);
}

.field-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.field-name {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 1rem;
  margin-right: 0.75rem;
}

.field-type {
  font-size: 0.75rem;
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  border: 1px solid currentColor;
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: 0.05em;
}

/* Smart Visual Indicators */
.type-text { color: hsl(var(--destructive)); background: hsl(var(--destructive)/0.1); }
.type-keyword { color: hsl(var(--teal)); background: hsl(var(--teal)/0.1); }
.type-object, .type-nested { color: hsl(var(--primary)); background: hsl(var(--primary)/0.1); }
.type-date { color: #8b5cf6; background: rgba(139, 92, 246, 0.1); } /* Purple */

.field-badge {
  margin-left: 0.75rem;
  color: hsl(var(--teal));
  background: hsl(var(--teal)/0.1);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

.field-actions {
  display: flex;
  gap: 0.25rem;
}

.btn-icon {
  background: transparent;
  border: none;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
}

.btn-icon:hover {
  background: hsl(var(--muted));
  color: hsl(var(--foreground));
}

.text-destructive {
  color: hsl(var(--destructive) / 0.7);
}

.text-destructive:hover {
  color: hsl(var(--destructive));
  background: hsl(var(--destructive) / 0.1) !important;
}

.nested-tree {
  margin-top: 0.75rem;
  padding-left: 1.5rem;
  border-left: 1px dashed hsl(var(--border));
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.child-item {
  padding: 0.5rem 0.75rem;
  border-left: 3px solid hsl(var(--primary) / 0.5);
}

.add-field-form {
  display: flex;
  gap: 0.5rem;
  padding: 1rem;
  background: hsl(var(--muted)/0.1);
  border-radius: var(--radius);
  border: 1px dashed hsl(var(--border));
}

.field-input { flex: 2; }
.type-input { flex: 1; }
.add-btn { flex: 0 0 auto; display: flex; align-items: center; gap: 0.5rem; }

.editor-output {
  background: hsl(240 10% 4%);
  border: 1px solid hsl(var(--border) / 0.5);
  font-family: var(--font-mono);
  font-size: 0.9rem;
  color: #a1a1aa;
}

.editor-output pre {
  margin: 0;
  white-space: pre-wrap;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: hsl(var(--muted-foreground));
  background: hsl(var(--muted)/0.1);
  border-radius: var(--radius);
  border: 1px dashed hsl(var(--border));
  margin-bottom: 1rem;
}

/* Utilities */
.text-muted { color: hsl(var(--muted-foreground)); }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-4 { margin-top: 1.5rem; }
.mb-2 { margin-bottom: 0.5rem; }
.mb-4 { margin-bottom: 1.5rem; }
.mb-6 { margin-bottom: 2rem; }
.p-4 { padding: 1rem; }
.pt-4 { padding-top: 1rem; }
.pt-4 { padding-top: 1rem; }
.w-full { width: 100%; }
.shadow-lg { box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); }

/* Status Classes */
.bg-teal-900\/20 { background-color: rgba(19, 78, 74, 0.2); }
.text-teal-400 { color: #2dd4bf; }
.border-teal-800 { border-color: #115e59; }

.bg-destructive\/10 { background-color: hsl(var(--destructive) / 0.1); }
.border-destructive\/30 { border-color: hsl(var(--destructive) / 0.3); }

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
