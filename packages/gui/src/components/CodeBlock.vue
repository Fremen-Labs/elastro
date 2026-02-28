<script setup lang="ts">
import { ref, computed } from 'vue';
import { Copy, Check, Terminal } from 'lucide-vue-next';

const props = defineProps({
  code: {
    type: String,
    required: true
  },
  language: {
    type: String,
    default: 'python'
  },
  showLineNumbers: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  }
});

const copied = ref(false);

const handleCopy = async () => {
  await navigator.clipboard.writeText(props.code);
  copied.value = true;
  setTimeout(() => { copied.value = false; }, 2000);
};

const lines = computed(() => props.code.split('\n'));

// Highlighting Logic
const pythonKeywords = /\b(from|import|def|class|return|if|else|elif|for|while|try|except|with|as|in|and|or|not|True|False|None|print|async|await)\b/;
const pythonStrings = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/;
const pythonComments = /(#.*)/;
const pythonFunctions = /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()/;
const pythonDecorators = /(@[a-zA-Z_][a-zA-Z0-9_]*)/;
const pythonNumbers = /\b(\d+)\b/;

const bashComments = /(#.*)/;
const bashStrings = /(".*?"|'.*?')/;
const bashFlags = /(--?[\w-]+)/;
const bashVars = /(\$[a-zA-Z_][a-zA-Z0-9_]*)/;

const escapeHtml = (unsafe: string) => {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
};

const highlightPython = (line: string): string => {
  const masterRegex = new RegExp([
    pythonStrings.source,
    pythonComments.source,
    pythonKeywords.source,
    pythonFunctions.source,
    pythonDecorators.source,
    pythonNumbers.source
  ].join('|'), 'g');

  return line.replace(masterRegex, (match, str, comment, kw, func, dec, num) => {
    if (str) return `<span class="hl-str">${escapeHtml(str || '')}</span>`;
    if (comment) return `<span class="hl-comment">${escapeHtml(comment || '')}</span>`;
    if (kw) return `<span class="hl-kw">${escapeHtml(kw || '')}</span>`;
    if (func) return `<span class="hl-func">${escapeHtml(func || '')}</span>`;
    if (dec) return `<span class="hl-dec">${escapeHtml(dec || '')}</span>`;
    if (num) return `<span class="hl-num">${escapeHtml(num || '')}</span>`;
    return escapeHtml(match);
  });
};

const highlightBash = (line: string): string => {
  let prefix = '';
  const commandMatch = line.match(/^(\s*)([\w.-]+)(.*)/);
  let remainder = line;

  if (commandMatch) {
    if (line.trim().startsWith('#')) {
      return `<span class="hl-comment">${escapeHtml(line)}</span>`;
    }
    const [, indent, cmd, rest] = commandMatch;
    prefix = (indent || '') + `<span class="hl-cmd">${escapeHtml(cmd || '')}</span>`;
    remainder = rest || '';
  } else {
    if (line.trim().startsWith('#')) {
      return `<span class="hl-comment">${escapeHtml(line)}</span>`;
    }
  }

  const masterRegex = new RegExp([
    bashStrings.source,
    bashComments.source,
    bashFlags.source,
    bashVars.source
  ].join('|'), 'g');

  const highlightedRest = remainder.replace(masterRegex, (match, str, comment, flag, variable) => {
    if (str) return `<span class="hl-str2">${escapeHtml(str || '')}</span>`;
    if (comment) return `<span class="hl-comment">${escapeHtml(comment || '')}</span>`;
    if (flag) return `<span class="hl-flag">${escapeHtml(flag || '')}</span>`;
    if (variable) return `<span class="hl-var">${escapeHtml(variable || '')}</span>`;
    return escapeHtml(match);
  });

  return prefix + highlightedRest;
};

const getHighlightedLine = (line: string) => {
  return props.language === 'bash' ? highlightBash(line) : highlightPython(line) || '&nbsp;';
};
</script>

<template>
  <div class="code-block">
    <!-- Header -->
    <div class="code-header">
      <div class="code-dots">
        <div class="dot dot-red"></div>
        <div class="dot dot-yellow"></div>
        <div class="dot dot-green"></div>
      </div>
      <div v-if="title" class="code-title">
        <Terminal class="icon-small" />
        {{ title }}
      </div>
      <button class="copy-btn" @click="handleCopy">
        <template v-if="copied">
          <Check class="icon-small text-green border-none" />
          <span>Copied!</span>
        </template>
        <template v-else>
          <Copy class="icon-small" />
          <span>Copy</span>
        </template>
      </button>
    </div>

    <!-- Code Content -->
    <div class="code-content">
      <pre>
        <code>
          <div v-for="(line, index) in lines" :key="index" class="code-line">
            <span v-if="showLineNumbers" class="line-number">{{ index + 1 }}</span>
            <span class="line-text" v-html="getHighlightedLine(line)"></span>
          </div>
        </code>
      </pre>
    </div>
  </div>
</template>

<style scoped>
.code-block {
  overflow: hidden;
  border-radius: 0.75rem;
  border: 1px solid hsl(var(--border) / 0.5);
  background: hsl(var(--card) / 0.4);
  backdrop-filter: blur(4px);
  width: 100%;
  margin-bottom: 2rem;
  font-family: 'JetBrains Mono', monospace;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid hsl(var(--border) / 0.3);
  background: hsl(var(--card) / 0.5);
}

.code-dots {
  display: flex;
  gap: 0.375rem;
}

.dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
}
.dot-red { background: rgba(239, 68, 68, 0.8); }
.dot-yellow { background: rgba(234, 179, 8, 0.8); }
.dot-green { background: rgba(34, 197, 94, 0.8); }

.code-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: hsl(var(--muted-foreground));
  margin-right: auto;
  margin-left: 1rem;
}

.icon-small {
  width: 1rem;
  height: 1rem;
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  background: transparent;
  border: none;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  transition: all 0.2s;
}
.copy-btn:hover {
  color: hsl(var(--foreground));
  background: hsl(var(--muted) / 0.5);
}

.code-content {
  padding: 1rem;
  overflow-x: auto;
}

pre {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.6;
}

code {
  display: block;
}

.code-line {
  display: flex;
  min-width: 0;
}

.line-number {
  user-select: none;
  color: hsl(var(--muted-foreground) / 0.3);
  width: 2rem;
  text-align: right;
  padding-right: 1rem;
  flex-shrink: 0;
}

.line-text {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Syntax Highlighting Tokens */
:deep(.hl-str) { color: #2dd4bf; } /* teal-400 */
:deep(.hl-comment) { color: hsl(var(--muted-foreground)); opacity: 0.6; font-style: italic; }
:deep(.hl-kw) { color: #f472b6; font-weight: 500; } /* pink-400 */
:deep(.hl-func) { color: #60a5fa; } /* blue-400 */
:deep(.hl-dec) { color: #facc15; } /* yellow-400 */
:deep(.hl-num) { color: #fb923c; } /* orange-400 */

:deep(.hl-cmd) { color: #d946ef; font-weight: 700; } /* fuchsia-500 */
:deep(.hl-str2) { color: #4ade80; } /* green-400 */
:deep(.hl-flag) { color: #22d3ee; opacity: 0.9; } /* cyan-400 */
:deep(.hl-var) { color: #facc15; } /* yellow-400 */
</style>
