<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { state } from '../store'
import { useMappingSchema, type FieldDef } from '../composables/useMappingSchema'

// 1. Core Logic imported from our elite Composable
const { 
  fields, 
  activePolicy, 
  templateTarget, 
  fieldTypes, 
  addRootField, 
  removeField, 
  addNestedField, 
  generatedSchema 
} = useMappingSchema()

// 2. Local Interactive State 
const rootNewFieldName = ref('')
const rootNewFieldType = ref('text')

const handleAddRoot = () => {
  addRootField(rootNewFieldName.value, rootNewFieldType.value)
  rootNewFieldName.value = ''
  rootNewFieldType.value = 'text'
}

// 3. Dialog State Management (Replacing window.prompt/alert)
const showDialog = ref(false)
const dialogTargetParent = ref<FieldDef | null>(null)
const nestedNewName = ref('')
const nestedNewType = ref('text')

const openNestedDialog = (parent: FieldDef) => {
  dialogTargetParent.value = parent
  nestedNewName.value = ''
  nestedNewType.value = 'text'
  showDialog.value = true
}

const confirmNestedField = () => {
  if (dialogTargetParent.value && nestedNewName.value.trim() && fieldTypes.includes(nestedNewType.value)) {
    addNestedField(dialogTargetParent.value, nestedNewName.value, nestedNewType.value)
  }
  showDialog.value = false
  dialogTargetParent.value = null
}

const cancelNestedField = () => {
  showDialog.value = false
  dialogTargetParent.value = null
}

// 4. API Submission State
const isDeploying = ref(false)
const deployStatus = ref<{success: boolean, message: string} | null>(null)

const deployTemplate = async () => {
  if (!state.clusters || state.clusters.length === 0) {
    deployStatus.value = { success: false, message: "No active cluster found in state. Please select a cluster first." }
    return
  }
  
  const clusterName = state.clusters[0].name
  isDeploying.value = true
  deployStatus.value = null

  try {
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
      deployStatus.value = { success: true, message: `Template successfully deployed to ${clusterName}!` }
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
  <div class="mapping-builder-page animate-fade-in relative flex flex-col min-h-screen">
    <header class="page-header px-6 pt-6 pb-4 glass-header">
      <h1 class="text-3xl font-bold tracking-tight text-foreground">Mapping Builder</h1>
      <p class="text-muted-foreground text-sm mt-1">Visually construct structural index schemas and analyzers effortlessly.</p>
    </header>

    <div class="px-6 py-4 flex-1">
      <div class="builder-layout mb-8">
        <!-- Left Column: Visual Editor -->
        <div class="card editor-panel glass-panel">
          <h3 class="panel-title flex items-center">
            <svg class="mr-2" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Global Parameters
          </h3>
          <div class="metrics-grid mb-8">
            <div class="detail-row">
              <span class="detail-label">Template Pattern Target</span>
              <input type="text" v-model="templateTarget" class="cli-input mt-2 transition-all" placeholder="e.g. logs-*" />
            </div>
            <div class="detail-row">
              <span class="detail-label">Dynamic Mapping Policy</span>
              <select v-model="activePolicy" class="cli-input mt-2 transition-all">
                <option value="strict">Strict (Reject unknown fields)</option>
                <option value="true">Dynamic (Auto-map unknown fields)</option>
                <option value="false">False (Ignore unknown fields)</option>
              </select>
              <p class="text-xs text-muted-foreground mt-2" v-if="activePolicy === 'strict'">
                 Safeguards against unvalidated mapping explosions.
              </p>
            </div>
          </div>

          <h3 class="panel-title flex items-center mb-4">
            <svg class="mr-2" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
            Structure Definitions
          </h3>
          
          <!-- Field Tree Render -->
          <div class="field-tree" v-if="fields.length > 0">
             <div class="field-item card fluid-hover" v-for="(field, idx) in fields" :key="idx" v-memo="[field.name, field.type, field.properties?.length]">
               <div class="field-item-header">
                  <div class="flex items-center">
                    <span class="field-name font-mono">{{ field.name }}</span>
                    <span class="field-type" :class="`type-${field.type}`">{{ field.type }}</span>
                    <span class="field-badge text-xs flex items-center" v-if="field.ignore_above">
                       <svg class="mr-1" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg> 
                       Robustness
                    </span>
                  </div>
                  <div class="field-actions">
                    <button v-if="field.type === 'object' || field.type === 'nested'" @click="openNestedDialog(field)" class="btn-icon tactile-btn" title="Add Child Property"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg></button>
                    <button @click="removeField(fields, idx)" class="btn-icon text-destructive tactile-btn-danger" title="Remove Field"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                  </div>
               </div>
               
               <!-- Nested Children -> v-memo for reactivity bypass on deep lists -->
               <div v-if="(field.type === 'object' || field.type === 'nested') && field.properties && field.properties.length > 0" class="nested-tree mt-3 pl-4 border-l-2 border-border/50">
                  <div class="field-item child-item fluid-hover mb-2" v-for="(child, cIdx) in field.properties" :key="cIdx" v-memo="[child.name, child.type]">
                    <div class="field-item-header">
                      <div class="flex items-center">
                        <span class="field-name font-mono opacity-90">{{ child.name }}</span>
                        <span class="field-type" :class="`type-${child.type}`">{{ child.type }}</span>
                      </div>
                      <div class="field-actions">
                        <button @click="removeField(field.properties, cIdx)" class="btn-icon text-destructive tactile-btn-danger"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                      </div>
                    </div>
                  </div>
               </div>
             </div>
          </div>
          <div v-else class="empty-state p-8 text-center text-muted-foreground border border-dashed border-border/60 rounded-lg bg-muted/5">
             <svg class="mx-auto mb-3 opacity-50" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
             <p>No fields defined. Start building your mapping below.</p>
          </div>

          <!-- Add New Root Field -->
          <div class="add-field-form mt-6 flex gap-3 p-4 bg-muted/20 border border-border/40 rounded-xl">
             <input type="text" v-model="rootNewFieldName" placeholder="Enter root field name..." class="cli-input flex-1" @keyup.enter="handleAddRoot" />
             <select v-model="rootNewFieldType" class="cli-input w-32">
               <option v-for="t in fieldTypes" :key="t" :value="t">{{ t }}</option>
             </select>
             <button @click="handleAddRoot" class="btn btn-secondary tactile-btn min-w-[120px]">
                <svg class="mr-2" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                Append
             </button>
          </div>
        </div>

        <!-- Right Column: Live Output & Action -->
        <div class="card output-panel glass-panel">
          <h3 class="panel-title flex items-center mb-4">
            <svg class="mr-2 text-primary" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
            Generated Payload
          </h3>
          <p class="text-xs text-muted-foreground mb-4">Rendered instantaneously via Vue composable computed states without layout blocking.</p>
          
          <div class="editor-output p-4 rounded-xl mb-6 shadow-inner bg-black/40 border border-white/5" style="flex: 1; overflow-y: auto;">
            <pre><code class="text-sm font-mono text-teal-300/90">{{ generatedSchema }}</code></pre>
          </div>
          
          <div class="deploy-actions pt-4 border-t border-border/40">
            <div v-if="deployStatus" 
                  class="mb-4 p-4 rounded-xl text-sm flex items-start animate-fade-in" 
                  :class="deployStatus.success ? 'bg-teal-900/20 text-teal-400 border border-teal-800/50' : 'bg-destructive/10 text-destructive border border-destructive/30'">
               <svg v-if="deployStatus.success" class="mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
               <svg v-else class="mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
               {{ deployStatus.message }}
            </div>

            <button 
              class="btn btn-primary w-full shadow-xl tactile-btn py-3 text-base flex justify-center items-center font-medium" 
              @click="deployTemplate"
              :disabled="isDeploying"
            >
              <svg v-if="!isDeploying" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
              <svg v-else class="animate-spin mr-2" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
              {{ isDeploying ? 'Deploying Payload...' : 'Push Mapping to Active Cluster' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal Dialog (Replaces native prompt) -->
    <div v-if="showDialog" class="modal-overlay">
      <div class="modal-content card glass-panel animate-fade-in shadow-2xl border border-white/10" style="max-width: 400px; width: 100%;">
        <h3 class="text-lg font-bold mb-4 text-foreground flex items-center">
          <svg class="mr-2 text-primary" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          Add Nested Property
        </h3>
        <p class="text-sm text-muted-foreground mb-4">Injecting a property into: <span class="font-mono text-primary">{{ dialogTargetParent?.name }}</span></p>
        
        <div class="mb-4">
          <label class="detail-label block mb-2">Property Name</label>
          <input type="text" v-model="nestedNewName" class="cli-input w-full transition-all focus:ring-2 ring-primary/30" placeholder="e.g. host.name" @keyup.enter="confirmNestedField" autofocus />
        </div>
        
        <div class="mb-6">
          <label class="detail-label block mb-2">Property Type</label>
          <select v-model="nestedNewType" class="cli-input w-full transition-all focus:ring-2 ring-primary/30">
            <option v-for="t in fieldTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        
        <div class="flex justify-end gap-3 pt-4 border-t border-border/40">
          <button @click="cancelNestedField" class="btn btn-secondary tactile-btn px-6 text-muted-foreground hover:text-foreground">Cancel</button>
          <button @click="confirmNestedField" :disabled="!nestedNewName.trim()" class="btn btn-primary tactile-btn px-6">Confirm</button>
        </div>
      </div>
    </div>
  </div>
</template>
<style scoped>
/* Typography & Layout Overrides */
.page-header h1 {
  background: linear-gradient(to right, hsl(var(--primary)), hsl(var(--teal)));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.builder-layout {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 1.5rem;
  align-items: flex-start;
}

.panel-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: hsl(var(--foreground));
  border-bottom: 2px solid hsl(var(--border) / 0.4);
  padding-bottom: 0.75rem;
  margin-bottom: 1.25rem;
}

/* Glassmorphism Panels */
.glass-panel {
  background: hsl(var(--card) / 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid hsl(var(--border) / 0.5);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
}

.detail-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.cli-input {
  background: hsl(var(--background) / 0.8); 
  border: 1px solid hsl(var(--border)); 
  padding: 0.6rem 0.85rem; 
  border-radius: var(--radius); 
  color: hsl(var(--foreground));
  font-size: 0.95rem;
  outline: none;
}

.cli-input:focus {
  border-color: hsl(var(--primary));
  box-shadow: 0 0 0 2px hsl(var(--primary) / 0.2);
}

/* Fluid List Items */
.field-tree {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field-item {
  padding: 0.85rem 1.25rem;
  background: hsl(var(--muted) / 0.15);
  border: 1px solid hsl(var(--border) / 0.4);
  border-left: 4px solid hsl(var(--muted));
  border-radius: var(--radius);
}

.fluid-hover {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.fluid-hover:hover {
  border-left-color: hsl(var(--primary));
  background: hsl(var(--muted) / 0.3);
  transform: translateX(4px);
  box-shadow: -4px 4px 12px rgba(0,0,0,0.1);
}

/* Type Badges */
.field-type {
  font-size: 0.7rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  border: 1px solid currentColor;
  text-transform: uppercase;
  font-weight: 800;
  letter-spacing: 0.05em;
  margin-left: 0.5rem;
}

.type-text { color: hsl(var(--destructive)); background: hsl(var(--destructive)/0.05); }
.type-keyword { color: hsl(var(--teal)); background: hsl(var(--teal)/0.05); }
.type-object, .type-nested { color: hsl(var(--primary)); background: hsl(var(--primary)/0.05); }
.type-date { color: #8b5cf6; background: rgba(139, 92, 246, 0.05); }
.type-long, .type-integer, .type-float, .type-double { color: #eab308; background: rgba(234, 179, 8, 0.05); }

/* Blizzard Tactile Buttons */
.tactile-btn {
  transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 14px 0 rgba(0, 0, 0, 0.2);
}

.tactile-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(var(--primary), 0.23);
}

.tactile-btn:active:not(:disabled) {
  transform: translateY(1px) scale(0.97);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.btn-icon {
  background: transparent;
  border: none;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  padding: 0.35rem;
  border-radius: var(--radius);
  transition: all 0.2s;
}

.btn-icon:hover {
  background: hsl(var(--muted));
  color: hsl(var(--foreground));
}

.tactile-btn-danger:hover {
  color: hsl(var(--destructive));
  background: hsl(var(--destructive) / 0.15);
  box-shadow: 0 0 12px hsl(var(--destructive) / 0.3);
}

/* Modal Overlay */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
</style>
