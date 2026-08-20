/**
 * ADA Hub - React 19 Single Page Application
 * Modern Component-Based Architecture with Full Lifecycle Controls (Ollama, ADA, MCPs)
 */

// =============================================================================
// Markdown Parser
// =============================================================================
export function markdownToHtml(text) {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="code-block"><code class="language-${lang}">${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // Bold & Italic
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bullet lists
  html = html.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  // Line breaks
  html = html.replace(/\n/g, '<br/>');
  return html;
}

// =============================================================================
// API Service with Lifecycle Management
// =============================================================================
export const api = {
  getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  },

  async request(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    const token = this.getCookie('ada_csrf');
    if (token) {
      headers['X-ADA-Token'] = token;
    }
    const res = await fetch(path, { credentials: 'same-origin', ...options, headers });
    if (!res.ok) {
      let errText = 'Error en la petición';
      try {
        const json = await res.json();
        errText = json.message || json.error || errText;
      } catch (_) {}
      throw new Error(errText);
    }
    return res.json();
  },

  getStatus() { return this.request('/api/status'); },
  
  // Ollama Lifecycle
  getOllamaStatus() { return this.request('/api/ollama/status'); },
  startOllama() { return this.request('/api/ollama/start', { method: 'POST' }); },
  stopOllama() { return this.request('/api/ollama/stop', { method: 'POST' }); },
  restartOllama() { return this.request('/api/ollama/restart', { method: 'POST' }); },
  getOllamaModels() { return this.request('/api/ollama/models'); },
  unloadOllamaModel(model) {
    return this.request('/api/ollama/unload', { method: 'POST', body: JSON.stringify({ model }) });
  },
  deleteOllamaModel(model) {
    return this.request('/api/ollama/delete', { method: 'POST', body: JSON.stringify({ model }) });
  },

  // ADA Agent Lifecycle
  restartAgent() { return this.request('/api/agent/restart', { method: 'POST' }); },

  // Telegram Bot Lifecycle
  getTelegramStatus() { return this.request('/api/telegram/status'); },
  startTelegram() { return this.request('/api/telegram/start', { method: 'POST' }); },
  stopTelegram() { return this.request('/api/telegram/stop', { method: 'POST' }); },
  restartTelegram() { return this.request('/api/telegram/restart', { method: 'POST' }); },
  testTelegram() { return this.request('/api/telegram/test', { method: 'POST' }); },

  // Models & Policy
  getModelsCatalog() { return this.request('/api/models/catalog'); },
  getModelsPolicy() { return this.request('/api/models/policy'); },
  saveModelsPolicy(policy) {
    return this.request('/api/models/policy', { method: 'POST', body: JSON.stringify({ model_policy: policy }) });
  },
  runBenchmark(model, prompt_key) {
    return this.request('/api/models/benchmark', { method: 'POST', body: JSON.stringify({ model, prompt_key }) });
  },

  // MCPs Lifecycle
  getMCPsServers() { return this.request('/api/mcps/servers'); },
  startMCPServer(name) { return this.request(`/api/mcps/servers/${name}/start`, { method: 'POST' }); },
  stopMCPServer(name) { return this.request(`/api/mcps/servers/${name}/stop`, { method: 'POST' }); },
  restartMCPServer(name) { return this.request(`/api/mcps/servers/${name}/restart`, { method: 'POST' }); },
  restartAllMCPServers() { return this.request('/api/mcps/servers/restart-all', { method: 'POST' }); },
  pingMCPServer(name) { return this.request(`/api/mcps/servers/${name}/ping`); },
  getMCPsTools(category) {
    const query = category && category !== 'all' ? `?category=${category}` : '';
    return this.request(`/api/mcps/tools${query}`);
  },
  toggleMCPTool(name, enabled) {
    return this.request('/api/mcps/tools/toggle', { method: 'POST', body: JSON.stringify({ name, enabled }) });
  },
  runMCPTool(name, parameters = {}) {
    return this.request('/api/mcps/tools/run', { method: 'POST', body: JSON.stringify({ name, parameters }) });
  },
  addMCPServer(data) {
    return this.request('/api/mcps/servers', { method: 'POST', body: JSON.stringify(data) });
  },
  getMCPsConfig() { return this.request('/api/mcps/config'); },
  saveMCPsConfig(data) { return this.request('/api/mcps/config', { method: 'POST', body: JSON.stringify(data) }); },

  // Health Doctor & Auto-Healing
  getHealthcheck() { return this.request('/api/healthcheck'); },
  healAll() { return this.request('/api/healthcheck/heal', { method: 'POST' }); },
  fixHealthItem(actionId) { return this.request(`/api/healthcheck/fix/${actionId}`, { method: 'POST' }); },

  // Memory & Config
  getMemoryStats() { return this.request('/api/memory/stats'); },
  getAuditLog(limit = 50) { return this.request(`/api/audit?limit=${limit}`); },
  getConfig() { return this.request('/api/config'); },
  saveConfig(config) {
    return this.request('/api/config', { method: 'POST', body: JSON.stringify({ config }) });
  },
  warmup() { return this.request('/api/warmup', { method: 'POST' }); },
  getConversation() { return this.request('/api/conversation'); },
  clearConversation() { return this.request('/api/conversation', { method: 'DELETE' }); },
};

// Helper to reliably check if Ollama is online across different API payload structures
export const isOllamaAvailable = (statusData) => {
  if (!statusData) return false;
  if (statusData.ollama_health && (statusData.ollama_health.online === true || statusData.ollama_health.status === 'healthy')) {
    return true;
  }
  if (statusData.health && (statusData.health.online === true || statusData.health.status === 'healthy')) {
    return true;
  }
  if (statusData.runtime) {
    if (statusData.runtime.available === true) return true;
    if (statusData.runtime.status && statusData.runtime.status.available === true) return true;
  }
  if (statusData.available === true) return true;
  return false;
};

// React & Hooks
const { useState, useEffect, useRef, useCallback, createElement: h } = window.React || {};

// =============================================================================
// React Components
// =============================================================================

// 1. Sidebar Component
function Sidebar({ activeTab, onSelectTab, statusData, runtimeStatus }) {
  const isOnline = isOllamaAvailable(statusData) || runtimeStatus?.available === true;

  const navItems = [
    { id: 'overview', label: 'Overview', group: 'SISTEMA', icon: '📊' },
    { id: 'ollama', label: 'Ollama Hub', badge: isOnline ? 'Online' : 'Offline', badgeClass: isOnline ? 'badge-success' : 'badge-danger', group: 'SISTEMA', icon: '🦙' },
    { id: 'models', label: 'Modelos & Roles', group: 'SISTEMA', icon: '🧠' },
    { id: 'mcps', label: 'MCPs & Tools', badge: '19 tools', badgeClass: 'badge-accent', group: 'SISTEMA', icon: '🔌' },
    { id: 'chat', label: 'ADA Chat', group: 'AGENTE & OPERACIONES', icon: '💬' },
    { id: 'telegram', label: 'Telegram Bot', group: 'AGENTE & OPERACIONES', icon: '📱' },
    { id: 'memory', label: 'Memoria & Auditoría', group: 'AGENTE & OPERACIONES', icon: '🗃️' },
    { id: 'settings', label: 'Configuración', group: 'AGENTE & OPERACIONES', icon: '⚙️' },
  ];

  let currentGroup = '';

  return h('aside', { className: 'sidebar', id: 'sidebar' }, [
    h('div', { className: 'sidebar-header', key: 'header' }, [
      h('div', { className: 'brand' }, [
        h('div', { className: 'brand-orb' }, [
          h('span', { className: 'orb-glow' }),
          h('span', { className: 'orb-letter' }, 'A'),
        ]),
        h('div', { className: 'brand-info' }, [
          h('span', { className: 'brand-title' }, 'ADA HUB'),
          h('span', { className: 'brand-tag' }, 'v0.1.0 · Panel de Control'),
        ]),
      ]),
    ]),
    h('nav', { className: 'sidebar-nav', key: 'nav' }, 
      navItems.map((item) => {
        const elements = [];
        if (item.group !== currentGroup) {
          currentGroup = item.group;
          elements.push(h('div', { className: 'nav-group-title', key: `grp-${currentGroup}` }, currentGroup));
        }
        elements.push(
          h('button', {
            key: item.id,
            className: `nav-item ${activeTab === item.id ? 'active' : ''}`,
            id: `nav-${item.id}`,
            onClick: () => onSelectTab(item.id),
          }, [
            h('span', { className: 'nav-item-icon', key: 'icon' }, item.icon),
            h('span', { key: 'lbl' }, item.label),
            item.badge ? h('span', { className: `badge ${item.badgeClass || ''}`, key: 'badge' }, item.badge) : null,
          ])
        );
        return elements;
      })
    ),
    h('div', { className: 'sidebar-footer', key: 'footer' }, [
      h('div', { className: 'runtime-pill', id: 'runtime-status-pill' }, [
        h('span', { className: `status-dot ${isOnline ? 'online' : 'offline'}` }),
        h('span', { className: 'status-text' }, isOnline ? 'Ollama Online' : 'Ollama Inactivo'),
      ]),
    ]),
  ]);
}

// 2. Header Component
function Header({ title, subtitle, onWarmup, onRefresh, isRefreshing }) {
  return h('header', { className: 'top-header' }, [
    h('div', { className: 'header-left', key: 'left' }, [
      h('h1', { className: 'page-title', id: 'page-title' }, title),
      h('span', { className: 'page-subtitle', id: 'page-subtitle' }, subtitle),
    ]),
    h('div', { className: 'header-actions', key: 'actions' }, [
      h('button', { className: 'btn btn-ghost', id: 'btn-warmup', onClick: onWarmup, title: 'Precargar motor' }, [
        h('span', null, '⚡ Warmup'),
      ]),
      h('button', { className: 'btn btn-secondary', id: 'btn-refresh', onClick: onRefresh, title: 'Actualizar datos' }, [
        h('span', null, isRefreshing ? 'Actualizando...' : '🔄 Actualizar'),
      ]),
    ]),
  ]);
}

// 3. Overview Tab View (With Health Doctor & Service Control Matrix)
function OverviewView({ statusData, onSwitchTab, showToast, onRefresh }) {
  const [healthData, setHealthData] = useState(null);
  const [isHealing, setIsHealing] = useState(false);
  const [fixingAction, setFixingAction] = useState(null);

  const hardware = statusData?.hardware || {};
  const runtime = statusData?.runtime || {};
  const isOllamaRunning = isOllamaAvailable(statusData);

  const loadHealth = useCallback(async () => {
    try {
      const data = await api.getHealthcheck();
      setHealthData(data);
    } catch (_) {}
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth, statusData]);

  const handleAutoHeal = async () => {
    setIsHealing(true);
    showToast('Iniciando diagnóstico y auto-remediación del sistema...', 'info');
    try {
      const res = await api.healAll();
      showToast(`Auto-remediación completada. Score: ${res.new_score}%`, res.new_score === 100 ? 'success' : 'info');
      setHealthData(res.diagnosis);
      onRefresh();
    } catch (err) {
      showToast('Error en auto-remediación: ' + err.message, 'danger');
    } finally {
      setIsHealing(false);
    }
  };

  const handleFixItem = async (actionId) => {
    setFixingAction(actionId);
    try {
      const res = await api.fixHealthItem(actionId);
      showToast(res.message || 'Acción ejecutada correctamente', res.ok ? 'success' : 'warning');
      loadHealth();
      onRefresh();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    } finally {
      setFixingAction(null);
    }
  };

  const handleOllamaStart = async () => {
    try {
      showToast('Iniciando servicio Ollama...', 'info');
      await api.startOllama();
      showToast('Ollama iniciado correctamente', 'success');
      onRefresh();
    } catch (err) {
      showToast('Error al iniciar Ollama: ' + err.message, 'danger');
    }
  };

  const handleOllamaStop = async () => {
    try {
      showToast('Deteniendo servicio Ollama...', 'info');
      await api.stopOllama();
      showToast('Ollama detenido', 'info');
      onRefresh();
    } catch (err) {
      showToast('Error al detener Ollama: ' + err.message, 'danger');
    }
  };

  const handleOllamaRestart = async () => {
    try {
      showToast('Reiniciando servicio Ollama...', 'info');
      await api.restartOllama();
      showToast('Ollama reiniciado exitosamente', 'success');
      onRefresh();
    } catch (err) {
      showToast('Error al reiniciar Ollama: ' + err.message, 'danger');
    }
  };

  const handleAgentRestart = async () => {
    try {
      showToast('Reiniciando Agente ADA...', 'info');
      await api.restartAgent();
      showToast('Agente ADA y sesiones reiniciadas', 'success');
      onRefresh();
    } catch (err) {
      showToast('Error al reiniciar agente: ' + err.message, 'danger');
    }
  };

  const handleMCPsRestartAll = async () => {
    try {
      showToast('Reiniciando todos los servidores MCP...', 'info');
      await api.restartAllMCPServers();
      showToast('Todos los servidores MCP reiniciados', 'success');
      onRefresh();
    } catch (err) {
      showToast('Error al reiniciar MCPs: ' + err.message, 'danger');
    }
  };

  const healthScore = healthData?.score !== undefined ? healthData.score : 100;
  const overallStatus = healthData?.overall_status || (isOllamaRunning ? 'healthy' : 'degraded');
  const checkItems = healthData?.items || [];
  const hasPendingFixes = healthData?.can_auto_heal_all;

  const ITEM_ICONS = {
    ollama_daemon: '🦙',
    models_installed: '🧠',
    ada_agent: '🤖',
    mcps_subsystem: '🔌',
    sqlite_memory: '🗄️',
    hardware_resources: '💻',
  };

  return h('section', { className: 'tab-view active', id: 'tab-overview' }, [
    // Health Doctor Auto-Healing Banner
    h('div', { className: 'doctor-banner mb-6', key: 'doctor-banner' }, [
      h('div', { className: 'doctor-header' }, [
        h('div', { className: 'doctor-score-box' }, [
          h('div', { className: `doctor-score-ring ${overallStatus}` }, `${healthScore}%`),
          h('div', { className: 'doctor-title-group' }, [
            h('h3', null, [
              'Healthcheck General del Sistema',
              h('span', {
                className: `badge ${overallStatus === 'healthy' ? 'badge-success' : overallStatus === 'degraded' ? 'badge-warning' : 'badge-danger'}`
              }, overallStatus === 'healthy' ? '100% Operativo' : overallStatus === 'degraded' ? 'Degradado / Alertas' : 'Requiere Atención')
            ]),
            h('p', null, hasPendingFixes ? 'Hay componentes que no están levantados. Podés repararlos con un solo clic.' : 'Todos los subsistemas y motores están operando correctamente.'),
          ]),
        ]),
        h('div', null, [
          hasPendingFixes ? h('button', {
            className: 'btn-heal-all',
            onClick: handleAutoHeal,
            disabled: isHealing,
          }, isHealing ? 'Reparando componentes...' : '🚀 Auto-Reparar / Levantar Todo lo que Falte') : h('button', {
            className: 'btn btn-sm btn-ghost',
            onClick: loadHealth,
          }, '🔍 Re-verificar Salud'),
        ]),
      ]),

      // Diagnostic Grid Checklist
      h('div', { className: 'doctor-items-grid' },
        checkItems.map(item => {
          const isOk = item.status === 'ok';
          const isWarn = item.status === 'warning';
          const statusBadge = isOk ? 'badge-success' : isWarn ? 'badge-warning' : 'badge-danger';
          const statusLabel = isOk ? 'OK' : isWarn ? 'Alerta' : 'Error';
          const icon = ITEM_ICONS[item.id] || '⚙️';

          return h('div', { className: 'doctor-item-card', key: item.id }, [
            h('div', { className: 'doctor-item-top' }, [
              h('div', { className: 'doctor-item-name' }, [
                h('span', { className: 'text-base' }, icon),
                h('span', null, item.name),
              ]),
              h('span', { className: `badge ${statusBadge}` }, statusLabel),
            ]),
            h('p', { className: 'doctor-item-msg' }, item.message),
            item.can_auto_fix && item.status !== 'ok' ? h('div', { className: 'doctor-item-actions' }, [
              h('button', {
                className: 'btn btn-sm btn-primary',
                onClick: () => handleFixItem(item.fix_action_id),
                disabled: fixingAction === item.fix_action_id,
              }, fixingAction === item.fix_action_id ? 'Levantando...' : `⚡ ${item.fix_label || 'Levantar'}`),
            ]) : null,
          ]);
        })
      ),
    ]),

    // Top Hardware & Status Stats
    h('div', { className: 'grid grid-cols-4 gap-4 mb-6', key: 'stats-grid' }, [
      h('div', { className: 'card stat-card', key: 'ollama-card' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'Ollama Engine'),
          h('span', { className: `status-indicator ${isOllamaRunning ? 'online' : 'offline'}` }),
        ]),
        h('div', { className: 'stat-value' }, isOllamaRunning ? 'En Línea' : 'Detenido'),
        h('div', { className: 'stat-footer' }, 'http://127.0.0.1:11434'),
      ]),
      h('div', { className: 'card stat-card', key: 'ram-card' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'Memoria RAM'),
          h('span', { className: 'stat-badge' }, `${hardware.ram_gb || '--'} GB Total`),
        ]),
        h('div', { className: 'stat-value' }, `${hardware.ram_percent || 0}%`),
        h('div', { className: 'progress-bar-bg' }, [
          h('div', { className: 'progress-bar-fill', style: { width: `${hardware.ram_percent || 0}%` } }),
        ]),
      ]),
      h('div', { className: 'card stat-card', key: 'cpu-card' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'CPU Cores'),
          h('span', { className: 'stat-badge' }, hardware.platform || 'Linux'),
        ]),
        h('div', { className: 'stat-value' }, `${hardware.cpu_count || '--'} Cores`),
        h('div', { className: 'stat-footer' }, 'Procesador del sistema'),
      ]),
      h('div', { className: 'card stat-card', key: 'agent-card' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'Agente ADA Core'),
          h('span', { className: 'stat-badge badge-primary' }, 'Activo'),
        ]),
        h('div', { className: 'stat-value' }, 'Listo'),
        h('div', { className: 'stat-footer' }, 'SQLite FTS5 Habilitado'),
      ]),
    ]),

    // Central Lifecycle Services Control Matrix
    h('div', { className: 'card mb-6', key: 'control-matrix-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, 'Centro de Control de Servicios & Ciclo de Vida'),
          h('span', { className: 'badge badge-accent' }, 'Control en Tiempo Real'),
        ]),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'grid grid-cols-3 gap-4' }, [
          // Ollama Control Box
          h('div', { className: 'service-box', key: 'box-ollama' }, [
            h('div', { className: 'service-box-header' }, [
              h('div', { className: 'flex items-center gap-2' }, [
                h('span', { className: 'text-lg' }, '🦙'),
                h('span', { className: 'font-bold' }, 'Ollama Daemon'),
              ]),
              h('span', { className: `badge ${isOllamaRunning ? 'badge-success' : 'badge-danger'}` },
                isOllamaRunning ? 'Activo' : 'Inactivo'
              ),
            ]),
            h('p', { className: 'text-xs text-muted mt-1' }, 'Servicio local de inferencia de modelos LLM.'),
            h('div', { className: 'service-box-actions mt-4 flex gap-2' }, [
              !isOllamaRunning ? h('button', { className: 'btn btn-sm btn-primary', onClick: handleOllamaStart }, '▶ Iniciar') : null,
              isOllamaRunning ? h('button', { className: 'btn btn-sm btn-secondary', onClick: handleOllamaStop }, '⏹ Detener') : null,
              h('button', { className: 'btn btn-sm btn-ghost', onClick: handleOllamaRestart }, '🔄 Reiniciar'),
            ]),
          ]),

          // ADA Agent Control Box
          h('div', { className: 'service-box', key: 'box-agent' }, [
            h('div', { className: 'service-box-header' }, [
              h('div', { className: 'flex items-center gap-2' }, [
                h('span', { className: 'text-lg' }, '🧠'),
                h('span', { className: 'font-bold' }, 'ADA Agent Core'),
              ]),
              h('span', { className: 'badge badge-success' }, 'Operativo'),
            ]),
            h('p', { className: 'text-xs text-muted mt-1' }, 'Orquestador multiagente, memoria y router.'),
            h('div', { className: 'service-box-actions mt-4 flex gap-2' }, [
              h('button', { className: 'btn btn-sm btn-primary', onClick: handleAgentRestart }, '🔄 Reiniciar Agente'),
              h('button', { className: 'btn btn-sm btn-ghost', onClick: () => api.clearConversation().then(() => showToast('Memoria reiniciada', 'info')) }, '🧹 Limpiar'),
            ]),
          ]),

          // MCPs Engine Control Box
          h('div', { className: 'service-box', key: 'box-mcps' }, [
            h('div', { className: 'service-box-header' }, [
              h('div', { className: 'flex items-center gap-2' }, [
                h('span', { className: 'text-lg' }, '🔌'),
                h('span', { className: 'font-bold' }, 'MCPs Servers (5)'),
              ]),
              h('span', { className: 'badge badge-accent' }, 'Conectados'),
            ]),
            h('p', { className: 'text-xs text-muted mt-1' }, 'Servidores Model Context Protocol y herramientas.'),
            h('div', { className: 'service-box-actions mt-4 flex gap-2' }, [
              h('button', { className: 'btn btn-sm btn-secondary', onClick: handleMCPsRestartAll }, '🔄 Reiniciar Todos'),
              h('button', { className: 'btn btn-sm btn-ghost', onClick: () => onSwitchTab('mcps') }, '⚙️ Ver Servidores'),
            ]),
          ]),
        ]),
      ]),
    ]),

    // Bottom Grid: Models & Quick Actions
    h('div', { className: 'grid grid-cols-2 gap-6 mb-6', key: 'details-grid' }, [
      h('div', { className: 'card', key: 'assigned-models' }, [
        h('div', { className: 'card-header' }, [
          h('h3', { className: 'card-title' }, 'Modelos Asignados Activos'),
          h('button', { className: 'btn btn-sm btn-ghost', onClick: () => onSwitchTab('models') }, 'Gestionar'),
        ]),
        h('div', { className: 'card-body' }, [
          h('div', { className: 'model-role-row', key: 'chat-role' }, [
            h('span', { className: 'role-badge role-chat' }, 'Chat Principal'),
            h('span', { className: 'model-name-pill' }, 'llama3.2:3b'),
          ]),
          h('div', { className: 'model-role-row', key: 'vision-role' }, [
            h('span', { className: 'role-badge role-vision' }, 'Visión & OCR'),
            h('span', { className: 'model-name-pill' }, 'qwen2.5vl:3b'),
          ]),
          h('div', { className: 'model-role-row', key: 'router-role' }, [
            h('span', { className: 'role-badge role-router' }, 'Router Rápido'),
            h('span', { className: 'model-name-pill' }, 'llama3.2:3b'),
          ]),
        ]),
      ]),
      h('div', { className: 'card', key: 'quick-actions' }, [
        h('div', { className: 'card-header' }, [
          h('h3', { className: 'card-title' }, 'Acciones Rápidas'),
        ]),
        h('div', { className: 'card-body quick-actions-grid' }, [
          h('button', { className: 'quick-action-btn', onClick: () => onSwitchTab('ollama') }, [
            h('span', { className: 'qa-icon' }, '📥'),
            h('span', { className: 'qa-title' }, 'Descargar Modelo'),
            h('span', { className: 'qa-sub' }, 'Pull de nuevo LLM en Ollama'),
          ]),
          h('button', { className: 'quick-action-btn', onClick: () => onSwitchTab('models') }, [
            h('span', { className: 'qa-icon' }, '⚡'),
            h('span', { className: 'qa-title' }, 'Test de Velocidad'),
            h('span', { className: 'qa-sub' }, 'Medir tokens/segundo'),
          ]),
          h('button', { className: 'quick-action-btn', onClick: () => onSwitchTab('mcps') }, [
            h('span', { className: 'qa-icon' }, '🔌'),
            h('span', { className: 'qa-title' }, 'Ver Herramientas'),
            h('span', { className: 'qa-sub' }, 'Activar/Desactivar tools'),
          ]),
          h('button', { className: 'quick-action-btn', onClick: () => onSwitchTab('chat') }, [
            h('span', { className: 'qa-icon' }, '💬'),
            h('span', { className: 'qa-title' }, 'Abrir Chat'),
            h('span', { className: 'qa-sub' }, 'Interactuar con ADA'),
          ]),
        ]),
      ]),
    ]),
  ]);
}

// 4. Ollama Tab View (With Full Start / Stop / Restart Controls)
function OllamaView({ modelsData, statusData, onRefresh, showToast, onBenchmark }) {
  const [pullInput, setPullInput] = useState('');
  const [pulling, setPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState({ percent: 0, status: '', text: '' });

  const models = modelsData?.models || [];
  const running = modelsData?.running || [];
  const isOnline = isOllamaAvailable(statusData);

  const handleStart = async () => {
    try {
      showToast('Iniciando servicio Ollama...', 'info');
      await api.startOllama();
      showToast('Ollama iniciado correctamente', 'success');
      onRefresh();
    } catch (err) {
      showToast('Error al iniciar: ' + err.message, 'danger');
    }
  };

  const handleStop = async () => {
    try {
      showToast('Deteniendo servicio Ollama...', 'info');
      await api.stopOllama();
      showToast('Ollama detenido', 'info');
      onRefresh();
    } catch (err) {
      showToast('Error al detener: ' + err.message, 'danger');
    }
  };

  const handleRestart = async () => {
    try {
      showToast('Reiniciando servicio Ollama...', 'info');
      await api.restartOllama();
      showToast('Ollama reiniciado exitosamente', 'success');
      onRefresh();
    } catch (err) {
      showToast('Error al reiniciar: ' + err.message, 'danger');
    }
  };

  const handlePull = async () => {
    if (!pullInput.trim()) {
      showToast('Ingresá el nombre del modelo', 'warning');
      return;
    }
    const modelName = pullInput.trim();
    setPulling(true);
    setPullProgress({ percent: 0, status: `Iniciando pull de ${modelName}...`, text: '' });

    try {
      const token = api.getCookie('ada_csrf');
      const res = await fetch('/api/ollama/pull/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-ADA-Token': token },
        body: JSON.stringify({ model: modelName }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.status) {
                setPullProgress({
                  percent: data.percent || 0,
                  status: data.status,
                  text: `${data.percent || 0}% (${data.completed_formatted || ''} / ${data.total_formatted || ''})`,
                });
              }
              if (data.done) {
                showToast(`Modelo ${modelName} descargado exitosamente`, 'success');
                setPulling(false);
                onRefresh();
              }
            } catch (_) {}
          }
        }
      }
    } catch (err) {
      showToast('Error en pull: ' + err.message, 'danger');
      setPulling(false);
    }
  };

  const handleUnload = async (name) => {
    try {
      await api.unloadOllamaModel(name);
      showToast(`Modelo ${name} descargado de VRAM`, 'info');
      onRefresh();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handleDelete = async (name) => {
    if (!confirm(`¿Eliminar modelo ${name} de disco?`)) return;
    try {
      await api.deleteOllamaModel(name);
      showToast(`Modelo ${name} eliminado`, 'info');
      onRefresh();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  return h('section', { className: 'tab-view active', id: 'tab-ollama' }, [
    // Ollama Lifecycle Bar
    h('div', { className: 'card mb-6', key: 'service-control-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, 'Control del Servicio Ollama'),
          h('span', { className: `badge ${isOnline ? 'badge-success' : 'badge-danger'}` },
            isOnline ? 'En ejecución' : 'Detenido'
          ),
        ]),
        h('div', { className: 'flex items-center gap-2' }, [
          !isOnline ? h('button', { className: 'btn btn-sm btn-primary', onClick: handleStart }, '▶ Iniciar Servicio') : null,
          isOnline ? h('button', { className: 'btn btn-sm btn-secondary text-danger', onClick: handleStop }, '⏹ Detener') : null,
          h('button', { className: 'btn btn-sm btn-ghost', onClick: handleRestart }, '🔄 Reiniciar Servicio'),
        ]),
      ]),
    ]),

    // Pull Form Card
    h('div', { className: 'card mb-6', key: 'pull-card' }, [
      h('div', { className: 'card-header' }, [
        h('h3', { className: 'card-title' }, 'Descargar / Pull de Modelo Ollama'),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'pull-form' }, [
          h('input', {
            type: 'text',
            className: 'form-input flex-1',
            placeholder: 'Ej: deepseek-r1:8b, qwen2.5:7b, llama3.2:1b, nomic-embed-text',
            value: pullInput,
            onChange: (e) => setPullInput(e.target.value),
            onKeyDown: (e) => e.key === 'Enter' && handlePull(),
          }),
          h('button', { className: 'btn btn-primary', onClick: handlePull, disabled: pulling }, [
            h('span', null, pulling ? 'Descargando...' : '📥 Descargar Modelo'),
          ]),
        ]),
        pulling ? h('div', { className: 'pull-progress-container' }, [
          h('div', { className: 'pull-progress-header' }, [
            h('span', null, pullProgress.status),
            h('span', null, pullProgress.text),
          ]),
          h('div', { className: 'progress-bar-bg' }, [
            h('div', { className: 'progress-bar-fill', style: { width: `${pullProgress.percent}%` } }),
          ]),
        ]) : null,
      ]),
    ]),

    // Running VRAM Models Card
    h('div', { className: 'card mb-6', key: 'running-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, 'Modelos en Memoria / VRAM Activos (Ollama ps)'),
          h('span', { className: 'badge badge-accent' }, `${running.length} en VRAM`),
        ]),
      ]),
      h('div', { className: 'card-body' }, [
        !running.length ? h('div', { className: 'empty-state-sm' }, 'No hay modelos cargados en VRAM en este momento.')
          : h('div', { className: 'running-models-grid' }, 
              running.map(r => h('div', { className: 'model-card border-accent', key: r.name }, [
                h('div', { className: 'model-card-header' }, [
                  h('span', { className: 'model-name' }, r.name),
                  h('span', { className: 'badge badge-success' }, `VRAM: ${r.size_vram_formatted}`),
                ]),
                h('div', { className: 'flex justify-between items-center mt-2' }, [
                  h('span', { className: 'text-xs text-muted' }, 'Cargado en memoria gráfica'),
                  h('button', { className: 'btn btn-sm btn-secondary', onClick: () => handleUnload(r.name) }, 'Descargar de VRAM'),
                ]),
              ]))
            ),
      ]),
    ]),

    // Installed Models Card
    h('div', { className: 'card', key: 'installed-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, 'Modelos Instalados en Disco'),
          h('span', { className: 'badge badge-primary' }, `${models.length} modelos`),
        ]),
      ]),
      h('div', { className: 'card-body' }, [
        !models.length ? h('div', { className: 'empty-state-sm' }, 'No se encontraron modelos instalados en Ollama.')
          : h('div', { className: 'models-grid' }, 
              models.map(m => h('div', { className: 'model-card', key: m.name }, [
                h('div', { className: 'model-card-header' }, [
                  h('span', { className: 'model-name' }, m.name),
                  h('span', { className: 'badge badge-accent' }, m.size_formatted),
                ]),
                h('div', { className: 'model-meta' }, [
                  m.details?.parameter_size ? h('span', { className: 'badge', key: 'p' }, m.details.parameter_size) : null,
                  m.details?.quantization_level ? h('span', { className: 'badge', key: 'q' }, m.details.quantization_level) : null,
                  m.details?.family ? h('span', { className: 'badge', key: 'f' }, m.details.family) : null,
                ]),
                h('div', { className: 'flex justify-between items-center mt-2' }, [
                  h('button', { className: 'btn btn-sm btn-ghost', onClick: () => onBenchmark(m.name) }, '⚡ Probar'),
                  h('button', { className: 'btn btn-sm btn-secondary text-danger', onClick: () => handleDelete(m.name) }, 'Eliminar'),
                ]),
              ]))
            ),
      ]),
    ]),
  ]);
}

// 5. Models Tab View (Roles & Benchmark)
function ModelsView({ installedModels, showToast }) {
  const [chatRole, setChatRole] = useState('llama3.2:3b');
  const [visionRole, setVisionRole] = useState('qwen2.5vl:3b');
  const [routerRole, setRouterRole] = useState('llama3.2:3b');
  const [benchModel, setBenchModel] = useState('');
  const [benchPrompt, setBenchPrompt] = useState('quick');
  const [benchResult, setBenchResult] = useState(null);
  const [benchLoading, setBenchLoading] = useState(false);
  const [catalog, setCatalog] = useState([]);

  useEffect(() => {
    api.getModelsPolicy().then(data => {
      if (data.active) {
        if (data.active.chat) setChatRole(data.active.chat);
        if (data.active.vision) setVisionRole(data.active.vision);
        if (data.active.router) setRouterRole(data.active.router);
      }
    }).catch(() => {});

    api.getModelsCatalog().then(data => {
      setCatalog(data.catalog || []);
    }).catch(() => {});
  }, []);

  const handleSaveRoles = async () => {
    const policy = {
      chat: { preferred: chatRole, fallbacks: [] },
      vision: { preferred: visionRole, fallbacks: [] },
      router: { preferred: routerRole, fallbacks: [] },
    };
    try {
      await api.saveModelsPolicy(policy);
      showToast('Roles de modelos guardados exitosamente', 'success');
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handleBenchmark = async () => {
    const target = benchModel || (installedModels[0]?.name);
    if (!target) {
      showToast('Seleccioná un modelo para benchmark', 'warning');
      return;
    }
    setBenchLoading(true);
    setBenchResult(null);
    try {
      const res = await api.runBenchmark(target, benchPrompt);
      setBenchResult(res);
      if (res.ok) showToast('Benchmark finalizado', 'success');
    } catch (err) {
      setBenchResult({ ok: false, error: err.message });
    } finally {
      setBenchLoading(false);
    }
  };

  return h('section', { className: 'tab-view active', id: 'tab-models' }, [
    h('div', { className: 'grid grid-cols-2 gap-6 mb-6', key: 'top-grid' }, [
      // Role Assignment Matrix
      h('div', { className: 'card', key: 'roles-matrix' }, [
        h('div', { className: 'card-header' }, [
          h('h3', { className: 'card-title' }, 'Asignación de Roles de Modelos'),
          h('button', { className: 'btn btn-sm btn-primary', onClick: handleSaveRoles }, 'Guardar Cambios'),
        ]),
        h('div', { className: 'card-body flex flex-col gap-4' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Modelo de Chat Principal'),
            h('select', { className: 'form-select', value: chatRole, onChange: (e) => setChatRole(e.target.value) },
              installedModels.map(m => h('option', { key: m.name, value: m.name }, `${m.name} (${m.size_formatted})`))
            ),
            h('span', { className: 'form-help' }, 'Utilizado para responder dudas generales y razonamiento.'),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Modelo de Visión & OCR'),
            h('select', { className: 'form-select', value: visionRole, onChange: (e) => setVisionRole(e.target.value) },
              installedModels.map(m => h('option', { key: m.name, value: m.name }, `${m.name} (${m.size_formatted})`))
            ),
            h('span', { className: 'form-help' }, 'Utilizado cuando se envían imágenes o capturas.'),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Modelo de Router / Clasificación'),
            h('select', { className: 'form-select', value: routerRole, onChange: (e) => setRouterRole(e.target.value) },
              installedModels.map(m => h('option', { key: m.name, value: m.name }, `${m.name} (${m.size_formatted})`))
            ),
            h('span', { className: 'form-help' }, 'Modelo rápido y ligero para enrutar intenciones.'),
          ]),
        ]),
      ]),

      // Benchmark Runner
      h('div', { className: 'card', key: 'bench-card' }, [
        h('div', { className: 'card-header' }, [
          h('h3', { className: 'card-title' }, 'Benchmark & Test de Velocidad'),
        ]),
        h('div', { className: 'card-body flex flex-col gap-4' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Seleccionar Modelo'),
            h('select', { className: 'form-select', value: benchModel || installedModels[0]?.name || '', onChange: (e) => setBenchModel(e.target.value) },
              installedModels.map(m => h('option', { key: m.name, value: m.name }, m.name))
            ),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Tipo de Prueba'),
            h('select', { className: 'form-select', value: benchPrompt, onChange: (e) => setBenchPrompt(e.target.value) }, [
              h('option', { value: 'quick' }, 'Respuesta Rápida (Explicación corta)'),
              h('option', { value: 'reasoning' }, 'Razonamiento Lógico Paso a Paso'),
              h('option', { value: 'json' }, 'Estructuración en JSON'),
            ]),
          ]),
          h('button', { className: 'btn btn-secondary', onClick: handleBenchmark, disabled: benchLoading }, [
            h('span', null, benchLoading ? 'Midiendo rendimiento...' : '⚡ Iniciar Prueba de Rendimiento'),
          ]),
          benchResult ? h('div', { className: 'benchmark-results-box' }, [
            benchResult.ok ? h('div', null, [
              h('div', { className: 'bench-stats-grid' }, [
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'Velocidad'),
                  h('span', { className: 'bench-stat-val text-primary' }, `${benchResult.tokens_per_second} t/s`),
                ]),
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'Latencia TTFT'),
                  h('span', { className: 'bench-stat-val' }, benchResult.ttft_ms ? `${benchResult.ttft_ms} ms` : 'N/A'),
                ]),
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'Tiempo Total'),
                  h('span', { className: 'bench-stat-val' }, `${benchResult.total_time_s} s`),
                ]),
              ]),
              h('div', { className: 'bench-output' }, benchResult.response),
            ]) : h('div', { className: 'text-danger text-sm' }, `Error: ${benchResult.error}`),
          ]) : null,
        ]),
      ]),
    ]),

    // Catalog
    h('div', { className: 'card', key: 'catalog-card' }, [
      h('div', { className: 'card-header' }, [
        h('h3', { className: 'card-title' }, 'Catálogo de Modelos Recomendados para tu Hardware'),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'catalog-grid' },
          catalog.map(c => h('div', { className: 'model-card', key: c.name }, [
            h('div', { className: 'model-card-header' }, [
              h('span', { className: 'model-name' }, c.name),
              h('span', { className: `badge ${c.hardware_fit ? 'badge-success' : 'badge-warning'}` },
                c.hardware_fit ? 'Apto para tu RAM' : 'Requiere más RAM'
              ),
            ]),
            h('p', { className: 'text-xs text-muted' }, c.description),
            h('div', { className: 'model-meta' }, [
              h('span', { className: 'badge badge-accent' }, `Roles: ${(c.roles || []).join(', ')}`),
              h('span', { className: 'badge' }, `Mínimo: ${c.min_ram_gb} GB RAM`),
            ]),
          ]))
        ),
      ]),
    ]),
  ]);
}

// 6. MCPs & Tools Tab View (VS Code / Antigravity IDE Master-Detail Style)
function MCPsView({ showToast }) {
  const [servers, setServers] = useState([]);
  const [tools, setTools] = useState([]);
  const [selectedServerName, setSelectedServerName] = useState('filesystem');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // all, active, stopped
  const [activeSubTab, setActiveSubTab] = useState('tools'); // tools, manifest, console
  const [toolSearch, setToolSearch] = useState('');
  const [expandedSchemas, setExpandedSchemas] = useState({});
  const [testInputs, setTestInputs] = useState({});
  const [testResults, setTestResults] = useState({});
  const [runningTool, setRunningTool] = useState(null);
  const [consoleLogs, setConsoleLogs] = useState([
    { timestamp: new Date().toLocaleTimeString(), type: 'info', text: 'MCP Subsystem inicializado y conectado.' },
  ]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newServerForm, setNewServerForm] = useState({ name: '', transport: 'stdio', command: '', url: '' });

  const SERVER_ICONS = {
    filesystem: '📁',
    web_search: '🌐',
    system: '⚡',
    gmail: '📧',
    photography: '📷',
  };

  const addLog = (text, type = 'info') => {
    setConsoleLogs(prev => [
      ...prev,
      { timestamp: new Date().toLocaleTimeString(), type, text },
    ]);
  };

  const loadData = useCallback(async () => {
    try {
      const [sData, tData] = await Promise.all([
        api.getMCPsServers(),
        api.getMCPsTools(),
      ]);
      const sList = sData.servers || [];
      setServers(sList);
      setTools(tData.tools || []);
      if (!selectedServerName && sList.length > 0) {
        setSelectedServerName(sList[0].name);
      }
    } catch (_) {}
  }, [selectedServerName]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const selectedServer = servers.find(s => s.name === selectedServerName) || servers[0] || {
    name: 'filesystem',
    transport: 'built-in',
    status: 'active',
    tool_count: 4,
  };

  const serverTools = tools.filter(t => t.server === selectedServer.name);
  const filteredServerTools = serverTools.filter(t => 
    !toolSearch || t.name.toLowerCase().includes(toolSearch.toLowerCase()) || t.description.toLowerCase().includes(toolSearch.toLowerCase())
  );

  const filteredServers = servers.filter(s => {
    const matchesSearch = !searchQuery || s.name.toLowerCase().includes(searchQuery.toLowerCase());
    const isActive = s.status === 'active' || s.status === 'connected';
    if (statusFilter === 'active') return matchesSearch && isActive;
    if (statusFilter === 'stopped') return matchesSearch && !isActive;
    return matchesSearch;
  });

  const handleStartServer = async (name) => {
    try {
      addLog(`Enviando comando START para servidor '${name}'...`, 'info');
      await api.startMCPServer(name);
      showToast(`Servidor MCP ${name} iniciado`, 'success');
      addLog(`Servidor '${name}' está ONLINE (activo)`, 'success');
      loadData();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
      addLog(`Error al iniciar '${name}': ${err.message}`, 'warn');
    }
  };

  const handleStopServer = async (name) => {
    try {
      addLog(`Enviando comando STOP para servidor '${name}'...`, 'info');
      await api.stopMCPServer(name);
      showToast(`Servidor MCP ${name} detenido`, 'info');
      addLog(`Servidor '${name}' ha sido DETENIDO`, 'warn');
      loadData();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handleRestartServer = async (name) => {
    try {
      addLog(`Reiniciando servidor MCP '${name}'...`, 'info');
      await api.restartMCPServer(name);
      showToast(`Servidor MCP ${name} reiniciado`, 'success');
      addLog(`Servidor '${name}' reiniciado exitosamente`, 'success');
      loadData();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handleRestartAll = async () => {
    try {
      addLog('Iniciando reinicio global de todos los servidores MCP...', 'info');
      await api.restartAllMCPServers();
      showToast('Todos los servidores MCP reiniciados', 'success');
      addLog('Todos los servidores MCP reiniciados exitosamente', 'success');
      loadData();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handlePing = async (name) => {
    try {
      addLog(`Ejecutando ping de diagnóstico en servidor '${name}'...`, 'info');
      const res = await api.pingMCPServer(name);
      addLog(`Ping '${name}': Status=${res.status}, Latencia=${res.latency_ms !== null ? res.latency_ms + 'ms' : 'N/A'}`, 'success');
      showToast(`Ping a ${name}: OK (${res.latency_ms || 0} ms)`, 'info');
    } catch (err) {
      showToast('Error en ping: ' + err.message, 'danger');
      addLog(`Fallo de ping en '${name}': ${err.message}`, 'warn');
    }
  };

  const handleToggleTool = async (toolName, currentEnabled) => {
    try {
      await api.toggleMCPTool(toolName, !currentEnabled);
      showToast(`Herramienta ${toolName} ${!currentEnabled ? 'activada' : 'pausada'}`, 'info');
      addLog(`Tool '${toolName}' ${!currentEnabled ? 'ACTIVADA' : 'PAUSADA'}.`, 'info');
      loadData();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handleRunToolTest = async (tool) => {
    setRunningTool(tool.name);
    let params = {};
    const inputVal = testInputs[tool.name];
    if (inputVal && inputVal.trim()) {
      try {
        params = JSON.parse(inputVal);
      } catch (err) {
        showToast('JSON de parámetros inválido', 'danger');
        setRunningTool(null);
        return;
      }
    } else {
      // Default parameters based on properties
      const props = tool.parameters?.properties || {};
      for (const [key, prop] of Object.entries(props)) {
        if (key === 'path') params[key] = '.';
        else if (key === 'query') params[key] = 'ADA IA test';
        else if (key === 'command') params[key] = 'echo "test"';
        else if (key === 'limit') params[key] = 5;
        else params[key] = prop.default || '';
      }
    }

    addLog(`Ejecutando prueba interactiva de '${tool.name}' con args: ${JSON.stringify(params)}...`, 'info');

    try {
      const res = await api.runMCPTool(tool.name, params);
      setTestResults(prev => ({ ...prev, [tool.name]: res }));
      addLog(`Resultado '${tool.name}': ${JSON.stringify(res).slice(0, 120)}...`, res.ok ? 'success' : 'warn');
      showToast(`Prueba de ${tool.name} ejecutada`, res.ok ? 'success' : 'warning');
    } catch (err) {
      setTestResults(prev => ({ ...prev, [tool.name]: { ok: false, error: err.message } }));
      addLog(`Error ejecutando '${tool.name}': ${err.message}`, 'warn');
    } finally {
      setRunningTool(null);
    }
  };

  const handleAddServer = async () => {
    if (!newServerForm.name.trim()) {
      showToast('Ingresá el nombre del servidor', 'warning');
      return;
    }
    try {
      await api.addMCPServer({
        name: newServerForm.name.trim(),
        transport: newServerForm.transport,
        command: newServerForm.command ? newServerForm.command.split(' ') : null,
        url: newServerForm.url || null,
      });
      showToast(`Servidor MCP ${newServerForm.name} registrado`, 'success');
      addLog(`Nuevo servidor MCP '${newServerForm.name}' agregado.`, 'success');
      setShowAddModal(false);
      setNewServerForm({ name: '', transport: 'stdio', command: '', url: '' });
      loadData();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const isSelectedActive = selectedServer?.status === 'active' || selectedServer?.status === 'connected';

  // Server Manifest JSON representation
  const serverManifest = {
    name: selectedServer.name,
    version: '1.0.0',
    transport: selectedServer.transport,
    status: selectedServer.status,
    endpoint: selectedServer.url || 'local-stdio',
    tools_count: serverTools.length,
    tools: serverTools.map(t => ({
      name: t.name,
      description: t.description,
      risk_level: t.risk_level,
      enabled: t.enabled,
      parameters: t.parameters,
    })),
  };

  return h('section', { className: 'tab-view active', id: 'tab-mcps' }, [
    h('div', { className: 'vscode-mcp-layout' }, [
      // Left Pane: MCP Servers Explorer (VS Code Style)
      h('div', { className: 'vscode-sidebar-pane', key: 'left-pane' }, [
        h('div', { className: 'vscode-sidebar-header' }, [
          h('span', { className: 'vscode-sidebar-title' }, 'MCP SERVERS & EXTENSIONS'),
          h('div', { className: 'vscode-sidebar-actions' }, [
            h('button', { className: 'vscode-icon-btn', title: 'Reiniciar Todos', onClick: handleRestartAll }, '🔄'),
            h('button', { className: 'vscode-icon-btn', title: 'Añadir Servidor', onClick: () => setShowAddModal(true) }, '➕'),
          ]),
        ]),

        // Search Bar
        h('div', { className: 'vscode-search-box' }, [
          h('input', {
            type: 'text',
            className: 'vscode-search-input',
            placeholder: '🔍 Filtrar servidores...',
            value: searchQuery,
            onChange: (e) => setSearchQuery(e.target.value),
          }),
        ]),

        // Status Filter Tabs
        h('div', { className: 'vscode-filter-tabs' }, [
          h('button', {
            className: `vscode-filter-tab ${statusFilter === 'all' ? 'active' : ''}`,
            onClick: () => setStatusFilter('all'),
          }, `Todos (${servers.length})`),
          h('button', {
            className: `vscode-filter-tab ${statusFilter === 'active' ? 'active' : ''}`,
            onClick: () => setStatusFilter('active'),
          }, `Activos (${servers.filter(s => s.status === 'active' || s.status === 'connected').length})`),
          h('button', {
            className: `vscode-filter-tab ${statusFilter === 'stopped' ? 'active' : ''}`,
            onClick: () => setStatusFilter('stopped'),
          }, `Detenidos (${servers.filter(s => s.status === 'stopped').length})`),
        ]),

        // Servers List
        h('div', { className: 'vscode-servers-list' },
          filteredServers.map(s => {
            const isActive = s.status === 'active' || s.status === 'connected';
            const isSelected = s.name === selectedServer.name;
            const icon = SERVER_ICONS[s.name] || '🔌';

            return h('div', {
              key: s.name,
              className: `vscode-ext-item ${isSelected ? 'active' : ''}`,
              onClick: () => { setSelectedServerName(s.name); },
            }, [
              h('div', { className: 'vscode-ext-icon' }, icon),
              h('div', { className: 'vscode-ext-info' }, [
                h('div', { className: 'vscode-ext-header' }, [
                  h('span', { className: 'vscode-ext-name' }, s.name),
                  h('span', { className: `status-dot ${isActive ? 'online' : 'offline'}` }),
                ]),
                h('div', { className: 'vscode-ext-sub' }, [
                  h('span', null, `${s.tool_count} tools`),
                  h('span', null, '·'),
                  h('span', null, s.transport),
                ]),
              ]),
            ]);
          })
        ),
      ]),

      // Right Pane: MCP Inspector / Detail View
      h('div', { className: 'vscode-editor-pane', key: 'right-pane' }, [
        // Editor Header
        h('div', { className: 'vscode-editor-header' }, [
          h('div', { className: 'vscode-header-main' }, [
            h('div', { className: 'vscode-header-icon' }, SERVER_ICONS[selectedServer.name] || '🔌'),
            h('div', { className: 'vscode-header-title' }, [
              h('h2', null, [
                selectedServer.name,
                h('span', { className: `badge ${isSelectedActive ? 'badge-success' : 'badge-danger'}` },
                  isSelectedActive ? 'En Línea' : 'Detenido'
                ),
              ]),
              h('div', { className: 'vscode-header-meta' }, [
                h('span', null, `Protocolo: Model Context Protocol (MCP)`),
                h('span', null, '·'),
                h('span', null, `Transporte: ${selectedServer.transport}`),
                h('span', null, '·'),
                h('span', null, `${serverTools.length} capacidades registradas`),
              ]),
            ]),
          ]),

          // Lifecycle Actions
          h('div', { className: 'vscode-header-actions' }, [
            !isSelectedActive
              ? h('button', { className: 'btn btn-sm btn-primary', onClick: () => handleStartServer(selectedServer.name) }, '▶ Iniciar')
              : h('button', { className: 'btn btn-sm btn-secondary text-danger', onClick: () => handleStopServer(selectedServer.name) }, '⏹ Detener'),
            h('button', { className: 'btn btn-sm btn-ghost', onClick: () => handleRestartServer(selectedServer.name) }, '🔄 Reiniciar'),
            h('button', { className: 'btn btn-sm btn-ghost', onClick: () => handlePing(selectedServer.name) }, '⚡ Ping'),
          ]),
        ]),

        // Sub-Navigation Tabs
        h('div', { className: 'vscode-editor-tabs' }, [
          h('button', {
            className: `vscode-tab-btn ${activeSubTab === 'tools' ? 'active' : ''}`,
            onClick: () => setActiveSubTab('tools'),
          }, `🛠️ Herramientas / Tools (${serverTools.length})`),
          h('button', {
            className: `vscode-tab-btn ${activeSubTab === 'manifest' ? 'active' : ''}`,
            onClick: () => setActiveSubTab('manifest'),
          }, '⚙️ Manifest JSON'),
          h('button', {
            className: `vscode-tab-btn ${activeSubTab === 'console' ? 'active' : ''}`,
            onClick: () => setActiveSubTab('console'),
          }, `📜 Consola & Diagnóstico (${consoleLogs.length})`),
        ]),

        // Tab Content
        h('div', { className: 'vscode-tab-content' }, [
          // Sub-Tab 1: Tools Explorer
          activeSubTab === 'tools' ? h('div', { key: 'tab-tools' }, [
            h('div', { className: 'flex justify-between items-center mb-4' }, [
              h('input', {
                type: 'text',
                className: 'form-input form-input-sm max-w-sm',
                placeholder: 'Filtrar herramientas de este servidor...',
                value: toolSearch,
                onChange: (e) => setToolSearch(e.target.value),
              }),
              h('span', { className: 'text-xs text-muted' },
                `${filteredServerTools.length} de ${serverTools.length} herramientas mostradas`
              ),
            ]),

            !filteredServerTools.length ? h('div', { className: 'empty-state-sm' }, 'No se encontraron herramientas en este servidor.')
              : h('div', { className: 'vscode-tools-list' },
                  filteredServerTools.map(t => {
                    const isExpanded = !!expandedSchemas[t.name];
                    const riskClass = t.risk_level === 'safe' ? 'badge-success' : t.risk_level === 'confirmation' ? 'badge-warning' : 'badge-danger';
                    const riskLabel = t.risk_level === 'safe' ? 'Seguro' : t.risk_level === 'confirmation' ? 'Requiere Confirmación' : 'Elevado';
                    const properties = t.parameters?.properties || {};
                    const requiredList = t.parameters?.required || [];
                    const result = testResults[t.name];
                    const isRunning = runningTool === t.name;

                    return h('div', { className: 'vscode-tool-card', key: t.name }, [
                      h('div', { className: 'vscode-tool-header' }, [
                        h('div', { className: 'flex items-center gap-3' }, [
                          h('span', { className: 'vscode-tool-name' }, t.name),
                          h('span', { className: `badge ${riskClass}` }, riskLabel),
                        ]),
                        h('div', { className: 'flex items-center gap-3' }, [
                          h('label', { className: 'checkbox-label' }, [
                            h('input', {
                              type: 'checkbox',
                              checked: t.enabled,
                              onChange: () => handleToggleTool(t.name, t.enabled),
                            }),
                            h('span', { className: 'text-xs' }, t.enabled ? 'Habilitada' : 'Pausada'),
                          ]),
                        ]),
                      ]),

                      h('p', { className: 'vscode-tool-desc' }, t.description),

                      // Parameters Inspection Section
                      h('div', { className: 'schema-box' }, [
                        h('div', {
                          className: 'schema-title flex justify-between cursor-pointer',
                          onClick: () => setExpandedSchemas(prev => ({ ...prev, [t.name]: !isExpanded })),
                        }, [
                          h('span', null, `📋 Esquema de Parámetros (${Object.keys(properties).length} props)`),
                          h('span', { className: 'text-primary' }, isExpanded ? 'Ocultar ▲' : 'Ver Detalles ▼'),
                        ]),

                        isExpanded ? h('table', { className: 'schema-table mt-2' }, [
                          h('thead', null, [
                            h('tr', null, [
                              h('th', null, 'Parámetro'),
                              h('th', null, 'Tipo'),
                              h('th', null, 'Requerido'),
                              h('th', null, 'Descripción'),
                            ]),
                          ]),
                          h('tbody', null,
                            Object.entries(properties).map(([pName, pMeta]) => h('tr', { key: pName }, [
                              h('td', { className: 'font-mono text-primary font-bold' }, pName),
                              h('td', { className: 'font-mono text-muted' }, pMeta.type || 'string'),
                              h('td', null, requiredList.includes(pName) ? h('span', { className: 'text-danger' }, 'Sí') : 'Opcional'),
                              h('td', { className: 'text-muted' }, pMeta.description || '-'),
                            ]))
                          ),
                        ]) : null,
                      ]),

                      // Tool Test Runner Box
                      h('div', { className: 'tool-tester-box' }, [
                        h('div', { className: 'tester-title' }, [
                          h('span', null, '⚡ Probar Invocación de Herramienta'),
                          h('button', {
                            className: 'btn btn-sm btn-primary',
                            onClick: () => handleRunToolTest(t),
                            disabled: isRunning || !t.enabled || !isSelectedActive,
                          }, isRunning ? 'Ejecutando...' : 'Ejecutar Test'),
                        ]),
                        h('input', {
                          type: 'text',
                          className: 'tester-input',
                          placeholder: `Argumentos JSON (opcional), ej: {"path": "."}`,
                          value: testInputs[t.name] || '',
                          onChange: (e) => setTestInputs({ ...testInputs, [t.name]: e.target.value }),
                        }),
                        result ? h('pre', { className: 'tester-output' }, JSON.stringify(result, null, 2)) : null,
                      ]),
                    ]);
                  })
                )
          ]) : null,

          // Sub-Tab 2: Manifest JSON
          activeSubTab === 'manifest' ? h('div', { key: 'tab-manifest' }, [
            h('div', { className: 'flex justify-between items-center mb-3' }, [
              h('div', { className: 'flex items-center gap-2' }, [
                h('span', { className: 'text-sm text-muted' }, 'Archivo fuente:'),
                h('span', { className: 'badge badge-primary font-mono' }, 'mcps/config.json'),
              ]),
              h('div', { className: 'flex gap-2' }, [
                h('button', {
                  className: 'btn btn-sm btn-ghost',
                  onClick: () => {
                    navigator.clipboard.writeText(JSON.stringify(serverManifest, null, 2));
                    showToast('Configuración JSON copiada', 'info');
                  },
                }, '📋 Copiar JSON'),
              ]),
            ]),
            h('pre', { className: 'manifest-editor' }, JSON.stringify(serverManifest, null, 2)),
          ]) : null,

          // Sub-Tab 3: Output Terminal Console
          activeSubTab === 'console' ? h('div', { key: 'tab-console' }, [
            h('div', { className: 'flex justify-between items-center mb-3' }, [
              h('span', { className: 'text-sm text-muted' }, 'Salida de eventos y registro de llamadas en tiempo real:'),
              h('button', { className: 'btn btn-sm btn-ghost', onClick: () => setConsoleLogs([]) }, 'Limpiar Consola'),
            ]),
            h('div', { className: 'terminal-console' },
              consoleLogs.map((l, i) => h('div', { className: 'console-line', key: i }, [
                h('span', { className: 'console-timestamp' }, `[${l.timestamp}]`),
                h('span', { className: `console-${l.type}` }, l.text),
              ]))
            ),
          ]) : null,
        ]),
      ]),
    ]),

    // Add Custom Server Modal
    showAddModal ? h('div', { className: 'modal-overlay', key: 'modal' }, [
      h('div', { className: 'modal-card' }, [
        h('div', { className: 'modal-header' }, [
          h('h3', { className: 'font-bold text-base' }, 'Conectar Nuevo Servidor MCP'),
          h('button', { className: 'vscode-icon-btn', onClick: () => setShowAddModal(false) }, '✕'),
        ]),
        h('div', { className: 'modal-body' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Nombre del Servidor'),
            h('input', {
              type: 'text',
              className: 'form-input',
              placeholder: 'Ej: sqlite-mcp, git-mcp, puppeteer',
              value: newServerForm.name,
              onChange: (e) => setNewServerForm({ ...newServerForm, name: e.target.value }),
            }),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Transporte'),
            h('select', {
              className: 'form-select',
              value: newServerForm.transport,
              onChange: (e) => setNewServerForm({ ...newServerForm, transport: e.target.value }),
            }, [
              h('option', { value: 'stdio' }, 'stdio (Comando local / CLI)'),
              h('option', { value: 'sse' }, 'SSE (Server-Sent Events / HTTP)'),
            ]),
          ]),
          newServerForm.transport === 'stdio' ? h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Comando Ejecutable'),
            h('input', {
              type: 'text',
              className: 'form-input font-mono text-xs',
              placeholder: 'Ej: npx -y @modelcontextprotocol/server-sqlite /path/db.sqlite',
              value: newServerForm.command,
              onChange: (e) => setNewServerForm({ ...newServerForm, command: e.target.value }),
            }),
          ]) : h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'URL Endpoint'),
            h('input', {
              type: 'text',
              className: 'form-input font-mono text-xs',
              placeholder: 'http://127.0.0.1:8000/sse',
              value: newServerForm.url,
              onChange: (e) => setNewServerForm({ ...newServerForm, url: e.target.value }),
            }),
          ]),
        ]),
        h('div', { className: 'modal-footer' }, [
          h('button', { className: 'btn btn-secondary', onClick: () => setShowAddModal(false) }, 'Cancelar'),
          h('button', { className: 'btn btn-primary', onClick: handleAddServer }, 'Conectar Servidor'),
        ]),
      ]),
    ]) : null,
  ]);
}


// 7. Chat Tab View
function ChatView({ showToast }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [lang, setLang] = useState('auto');
  const [isStreaming, setIsStreaming] = useState(false);
  const chatBottomRef = useRef(null);

  useEffect(() => {
    api.getConversation().then(data => {
      if (data.messages && data.messages.length) {
        setMessages(data.messages);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userText = input.trim();
    setInput('');

    const newMessages = [...messages, { role: 'user', text: userText }];
    setMessages(newMessages);
    setIsStreaming(true);

    const assistantIdx = newMessages.length;
    setMessages([...newMessages, { role: 'assistant', text: 'Pensando...' }]);

    try {
      const token = api.getCookie('ada_csrf');
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-ADA-Token': token },
        body: JSON.stringify({ message: userText, lang }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.text) {
                setMessages(prev => {
                  const updated = [...prev];
                  updated[assistantIdx] = { role: 'assistant', text: data.text };
                  return updated;
                });
              }
            } catch (_) {}
          }
        }
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev];
        updated[assistantIdx] = { role: 'assistant', text: `Error: ${err.message}` };
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  const handleClear = async () => {
    await api.clearConversation();
    setMessages([]);
    showToast('Historial reiniciado', 'info');
  };

  const handleDownload = () => {
    let md = '# ADA - Registro de Conversación\n\n';
    messages.forEach(m => {
      const role = m.role === 'user' ? '**Usuario**' : '**ADA**';
      md += `${role}:\n${m.text}\n\n---\n\n`;
    });
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ada_chat_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
  };

  return h('section', { className: 'tab-view active', id: 'tab-chat' }, [
    h('div', { className: 'chat-wrapper' }, [
      h('div', { className: 'chat-messages', id: 'chat-messages' }, [
        !messages.length ? h('div', { className: 'empty-chat', key: 'empty' }, [
          h('div', { className: 'orb-large' }, 'A'),
          h('h2', null, '¿En qué te puedo ayudar hoy?'),
          h('p', null, 'Puedo ayudarte a organizar fotos, ejecutar tareas del sistema, buscar en internet o responder preguntas.'),
        ]) : messages.map((m, idx) => h('div', {
          key: idx,
          className: `message-bubble ${m.role}`,
          dangerouslySetInnerHTML: { __html: markdownToHtml(m.text) },
        })),
        h('div', { ref: chatBottomRef }),
      ]),
      h('div', { className: 'chat-toolbar', key: 'toolbar' }, [
        h('div', { className: 'chat-shortcuts' }, 'Enter para enviar · Shift + Enter para salto de línea'),
        h('div', { className: 'chat-options' }, [
          h('select', {
            className: 'form-select form-select-sm',
            value: lang,
            onChange: (e) => setLang(e.target.value),
          }, [
            h('option', { value: 'auto' }, 'Idioma: Auto'),
            h('option', { value: 'es' }, 'Español'),
            h('option', { value: 'en' }, 'English'),
          ]),
          h('button', { className: 'btn btn-sm btn-ghost', onClick: handleDownload }, 'Exportar .md'),
          h('button', { className: 'btn btn-sm btn-ghost', onClick: handleClear }, 'Limpiar'),
        ]),
      ]),
      h('div', { className: 'chat-composer', key: 'composer' }, [
        h('textarea', {
          className: 'chat-textarea',
          placeholder: 'Escribí tu mensaje o solicitud...',
          rows: 2,
          value: input,
          onChange: (e) => setInput(e.target.value),
          onKeyDown: (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          },
        }),
        h('button', { className: 'btn btn-primary btn-send', onClick: handleSend, disabled: isStreaming }, [
          h('span', null, isStreaming ? '...' : 'Enviar 🚀'),
        ]),
      ]),
    ]),
  ]);
}

// 8. Memory Tab View
function MemoryView() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.getMemoryStats().then(setStats).catch(() => {});
  }, []);

  const auditEntries = stats?.recent_audit || [];

  return h('section', { className: 'tab-view active', id: 'tab-memory' }, [
    h('div', { className: 'grid grid-cols-3 gap-6 mb-6', key: 'stats' }, [
      h('div', { className: 'card', key: 'db' }, [
        h('div', { className: 'card-header' }, h('h4', { className: 'card-title' }, 'Base de Datos')),
        h('div', { className: 'card-body' }, [
          h('div', { className: 'stat-value text-base' }, stats?.db_path || 'memory.db'),
          h('div', { className: 'stat-footer' }, 'SQLite FTS5 Habilitado'),
        ]),
      ]),
      h('div', { className: 'card', key: 'audit' }, [
        h('div', { className: 'card-header' }, h('h4', { className: 'card-title' }, 'Registros de Auditoría')),
        h('div', { className: 'card-body' }, [
          h('div', { className: 'stat-value' }, stats?.audit_count || 0),
          h('div', { className: 'stat-footer' }, 'Acciones registradas'),
        ]),
      ]),
      h('div', { className: 'card', key: 'sess' }, [
        h('div', { className: 'card-header' }, h('h4', { className: 'card-title' }, 'Sesiones Guardadas')),
        h('div', { className: 'card-body' }, [
          h('div', { className: 'stat-value' }, '1'),
          h('div', { className: 'stat-footer' }, 'Sesión principal activa'),
        ]),
      ]),
    ]),
    h('div', { className: 'card', key: 'table-card' }, [
      h('div', { className: 'card-header' }, [
        h('h3', { className: 'card-title' }, 'Registro de Auditoría de Acciones (Audit Log)'),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'table-container' }, [
          h('table', { className: 'data-table' }, [
            h('thead', null, [
              h('tr', null, [
                h('th', null, 'Timestamp'),
                h('th', null, 'Acción / Tool'),
                h('th', null, 'Detalles'),
                h('th', null, 'Resultado'),
              ]),
            ]),
            h('tbody', null,
              !auditEntries.length ? h('tr', null, h('td', { colSpan: 4, className: 'text-center py-4' }, 'No hay registros de auditoría aún.'))
                : auditEntries.map((e, i) => h('tr', { key: i }, [
                    h('td', { className: 'font-mono text-xs' }, e.created_at || 'Reciente'),
                    h('td', { className: 'font-semibold' }, e.action || e.tool || 'Tarea'),
                    h('td', { className: 'text-xs text-muted' }, JSON.stringify(e.payload || e.details || {})),
                    h('td', null, h('span', { className: `badge ${e.status === 'error' ? 'badge-danger' : 'badge-success'}` }, e.status || 'OK')),
                  ]))
            ),
          ]),
        ]),
      ]),
    ]),
  ]);
}

// 9. Settings Tab View
function SettingsView({ showToast }) {
  const [config, setConfig] = useState({
    name: 'ADA',
    ollama_url: 'http://127.0.0.1:11434',
    photo_root: '~/Desktop/Fotos',
    allowed_roots: ['~/Desktop'],
    confirm_risky: true,
  });

  useEffect(() => {
    api.getConfig().then(data => {
      if (data.config) setConfig(data.config);
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      await api.saveConfig(config);
      showToast('Configuración guardada exitosamente', 'success');
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  return h('section', { className: 'tab-view active', id: 'tab-settings' }, [
    h('div', { className: 'card max-w-3xl' }, [
      h('div', { className: 'card-header' }, [
        h('h3', { className: 'card-title' }, 'Configuración del Asistente'),
        h('button', { className: 'btn btn-primary', onClick: handleSave }, 'Guardar Configuración'),
      ]),
      h('div', { className: 'card-body flex flex-col gap-5' }, [
        h('div', { className: 'form-group' }, [
          h('label', { className: 'form-label' }, 'Nombre del Asistente'),
          h('input', {
            type: 'text',
            className: 'form-input',
            value: config.name || '',
            onChange: (e) => setConfig({ ...config, name: e.target.value }),
          }),
        ]),
        h('div', { className: 'form-group' }, [
          h('label', { className: 'form-label' }, 'URL de Ollama Endpoint'),
          h('input', {
            type: 'text',
            className: 'form-input',
            value: config.ollama_url || '',
            onChange: (e) => setConfig({ ...config, ollama_url: e.target.value }),
          }),
        ]),
        h('div', { className: 'form-group' }, [
          h('label', { className: 'form-label' }, 'Carpeta de Fotos (photo_root)'),
          h('input', {
            type: 'text',
            className: 'form-input',
            value: config.photo_root || '',
            onChange: (e) => setConfig({ ...config, photo_root: e.target.value }),
          }),
        ]),
        h('div', { className: 'form-group' }, [
          h('label', { className: 'form-label' }, 'Carpetas Permitidas (allowed_roots)'),
          h('input', {
            type: 'text',
            className: 'form-input',
            value: (config.allowed_roots || []).join(', '),
            onChange: (e) => setConfig({ ...config, allowed_roots: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }),
          }),
        ]),
        h('div', { className: 'form-group' }, [
          h('label', { className: 'checkbox-label' }, [
            h('input', {
              type: 'checkbox',
              checked: config.confirm_risky !== false,
              onChange: (e) => setConfig({ ...config, confirm_risky: e.target.checked }),
            }),
            h('span', null, 'Requerir confirmación para acciones riesgosas (mover/borrar archivos, scripts)'),
          ]),
        ]),
      ]),
    ]),
  ]);
}

// =============================================================================
// Telegram View Component
// =============================================================================
function TelegramView({ showToast }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getTelegramStatus();
      setStatus(data);
    } catch (err) {
      showToast('Error al obtener estado de Telegram: ' + err.message, 'danger');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 8000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleStart = async () => {
    setActionLoading(true);
    try {
      showToast('Iniciando daemon de Telegram Bot...', 'info');
      const res = await api.startTelegram();
      if (res.ok) {
        showToast(res.message || 'Bot de Telegram iniciado', 'success');
      } else {
        showToast(res.error || 'Error al iniciar bot', 'danger');
      }
      fetchStatus();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      showToast('Deteniendo bot de Telegram...', 'info');
      const res = await api.stopTelegram();
      showToast(res.message || 'Bot de Telegram detenido', 'info');
      fetchStatus();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestart = async () => {
    setActionLoading(true);
    try {
      showToast('Reiniciando bot de Telegram...', 'info');
      const res = await api.restartTelegram();
      showToast(res.message || 'Bot reiniciado', 'success');
      fetchStatus();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      showToast('Verificando token con la API de Telegram (getMe)...', 'info');
      const res = await api.testTelegram();
      if (res.ok) {
        setTestResult(res.bot);
        showToast(`Conexión exitosa con @${res.bot?.username || 'bot'}`, 'success');
      } else {
        showToast('Error de API Telegram: ' + (res.error || 'Token inválido'), 'danger');
        setTestResult({ error: res.error });
      }
    } catch (err) {
      showToast('Error al conectar con Telegram: ' + err.message, 'danger');
    } finally {
      setTesting(false);
    }
  };

  if (loading && !status) {
    return h('div', { className: 'loading-state' }, 'Cargando estado de Telegram Bot...');
  }

  const isRunning = status?.running === true;

  return h('div', { className: 'telegram-view animate-fade-in' }, [
    // Header Hero Banner
    h('div', { className: 'hero-banner mb-6' }, [
      h('div', { className: 'hero-content' }, [
        h('div', { className: 'hero-badge' }, [
          h('span', { className: `status-dot ${isRunning ? 'status-online' : 'status-offline'}` }),
          h('span', null, isRunning ? 'Daemon de Telegram en Ejecución (Long-polling)' : 'Daemon de Telegram Detenido'),
        ]),
        h('h2', { className: 'hero-title' }, '📱 Servidor & Bot de Telegram'),
        h('p', { className: 'hero-subtitle' },
          'Servicio de mensajería independiente que reenvía texto, fotos y comandos a los endpoints de razonamiento de ADA.'
        ),
      ]),
      h('div', { className: 'hero-actions' }, [
        isRunning
          ? h('button', {
              className: 'btn btn-danger',
              onClick: handleStop,
              disabled: actionLoading,
            }, '⏹️ Detener Bot')
          : h('button', {
              className: 'btn btn-primary',
              onClick: handleStart,
              disabled: actionLoading || !status?.token_set,
            }, '▶️ Iniciar Bot'),
        h('button', {
          className: 'btn btn-secondary',
          onClick: handleRestart,
          disabled: actionLoading || !isRunning,
        }, '🔄 Reiniciar'),
        h('button', {
          className: 'btn btn-outline',
          onClick: handleTestConnection,
          disabled: testing || !status?.token_set,
        }, testing ? '⌛ Probando...' : '🔍 Probar Conexión (getMe)'),
      ]),
    ]),

    // Metrics Grid
    h('div', { className: 'metrics-grid mb-6' }, [
      h('div', { className: 'metric-card' }, [
        h('div', { className: 'metric-header' }, [
          h('span', { className: 'metric-title' }, 'Estado del Servicio'),
          h('span', { className: 'metric-icon' }, '⚡'),
        ]),
        h('div', { className: 'metric-value' }, isRunning ? 'ONLINE' : 'OFFLINE'),
        h('div', { className: 'metric-subtitle' }, isRunning ? 'Polling activo cada ' + status.poll_seconds + 's' : 'Proceso detenido'),
      ]),
      h('div', { className: 'metric-card' }, [
        h('div', { className: 'metric-header' }, [
          h('span', { className: 'metric-title' }, 'Token de Bot'),
          h('span', { className: 'metric-icon' }, '🔑'),
        ]),
        h('div', { className: 'metric-value font-mono', style: { fontSize: '1.1rem' } }, status?.token_masked || 'No configurado'),
        h('div', { className: 'metric-subtitle' }, status?.token_set ? 'Token cargado en entorno' : 'Falta TELEGRAM_BOT_TOKEN'),
      ]),
      h('div', { className: 'metric-card' }, [
        h('div', { className: 'metric-header' }, [
          h('span', { className: 'metric-title' }, 'Chats Autorizados'),
          h('span', { className: 'metric-icon' }, '🛡️'),
        ]),
        h('div', { className: 'metric-value' }, (status?.allowed_chat_ids?.length || 0) > 0 ? `${status.allowed_chat_ids.length} chat(s)` : 'Todos (Público)'),
        h('div', { className: 'metric-subtitle' }, (status?.allowed_chat_ids?.length || 0) > 0 ? status.allowed_chat_ids.join(', ') : 'Sin restricción de ID'),
      ]),
      h('div', { className: 'metric-card' }, [
        h('div', { className: 'metric-header' }, [
          h('span', { className: 'metric-title' }, 'Carpeta de Descargas'),
          h('span', { className: 'metric-icon' }, '📥'),
        ]),
        h('div', { className: 'metric-value font-mono', style: { fontSize: '1rem' } }, status?.inbox || 'telegram_inbox'),
        h('div', { className: 'metric-subtitle' }, 'Almacenamiento de imágenes recibidas'),
      ]),
    ]),

    // Test API Identity Card (if available)
    testResult && !testResult.error ? h('div', { className: 'card mb-6 animate-fade-in' }, [
      h('div', { className: 'card-header' }, [
        h('h3', { className: 'card-title' }, '🤖 Identidad del Bot Verificada por Telegram'),
        h('span', { className: 'badge badge-success' }, 'Verificado'),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'grid grid-cols-2 gap-4' }, [
          h('div', null, [
            h('span', { className: 'text-muted block text-xs uppercase mb-1' }, 'Nombre del Bot'),
            h('span', { className: 'font-semibold text-lg' }, testResult.first_name || 'ADA Bot'),
          ]),
          h('div', null, [
            h('span', { className: 'text-muted block text-xs uppercase mb-1' }, 'Username'),
            h('span', { className: 'badge badge-accent' }, `@${testResult.username}`),
          ]),
          h('div', null, [
            h('span', { className: 'text-muted block text-xs uppercase mb-1' }, 'ID de Telegram'),
            h('span', { className: 'font-mono text-sm' }, testResult.id),
          ]),
          h('div', null, [
            h('span', { className: 'text-muted block text-xs uppercase mb-1' }, 'Grupos Permitidos'),
            h('span', { className: 'text-sm' }, testResult.can_join_groups ? 'Sí' : 'No'),
          ]),
        ]),
      ]),
    ]) : null,

    // Standalone CLI Execution Guide Card
    h('div', { className: 'card' }, [
      h('div', { className: 'card-header' }, [
        h('h3', { className: 'card-title' }, '💻 Ejecución como Proceso Aislado'),
        h('span', { className: 'badge badge-info' }, 'CLI & Background'),
      ]),
      h('div', { className: 'card-body' }, [
        h('p', { className: 'text-sm text-muted mb-4' },
          'Telegram está diseñado como un servidor/bot completamente independiente en la raíz `telegram/bot.py`. Podés ejecutarlo directamente en una terminal separada, en un contenedor Docker o como un servicio systemd:'
        ),
        h('pre', { className: 'code-block' },
          `# 1. Exportar el token entregado por BotFather\nexport TELEGRAM_BOT_TOKEN="tu-token-aqui"\nexport TELEGRAM_ALLOWED_CHAT_IDS="123456789" # opcional\n\n# 2. Iniciar el bot de Telegram de forma aislada\n.venv/bin/python telegram/bot.py`
        ),
        h('div', { className: 'flex justify-between items-center mt-4 text-xs text-muted' }, [
          h('span', null, '💡 Se comunicará con ADA vía REST HTTP en http://127.0.0.1:5005'),
          h('span', { className: 'badge badge-outline' }, 'Endpoints: /api/chat & /api/status'),
        ]),
      ]),
    ]),
  ]);
}

// =============================================================================
// Main App Component
// =============================================================================
export function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [statusData, setStatusData] = useState(null);
  const [ollamaData, setOllamaData] = useState({ models: [], running: [] });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toasts, setToasts] = useState([]);

  const showToast = (msg, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [status, ollama] = await Promise.all([
        api.getStatus(),
        api.getOllamaModels().catch(() => ({ models: [], running: [] })),
      ]);
      setStatusData(status);
      setOllamaData(ollama);
    } catch (_) {}
    finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(() => {
      api.getStatus().then(setStatusData).catch(() => {});
    }, 15000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const titles = {
    overview: ['Overview del Sistema', 'Panel general de recursos, motores y estado del agente'],
    ollama: ['Ollama Hub', 'Administración de modelos locales, descarga y monitoreo de VRAM'],
    models: ['Modelos & Roles', 'Asignación de roles por tarea y benchmark de velocidad'],
    mcps: ['MCPs & Herramientas', 'Servidores Model Context Protocol y catálogo de tools'],
    chat: ['ADA Chat', 'Asistente interactivo local con razonamiento paso a paso'],
    telegram: ['Telegram Bot (Daemon Independiente)', 'Servicio de mensajería y bot de asistencia vía Telegram'],
    memory: ['Memoria & Auditoría', 'Explorador de base de datos SQLite y registro de auditoría'],
    settings: ['Configuración', 'Parámetros del sistema y políticas de seguridad'],
  };

  const currentTitle = titles[activeTab] || titles.overview;

  const handleWarmup = async () => {
    try {
      await api.warmup();
      showToast('Warmup ejecutado exitosamente', 'success');
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  return h('div', { className: 'app-layout' }, [
    h(Sidebar, {
      key: 'sidebar',
      activeTab,
      onSelectTab: setActiveTab,
      statusData,
      runtimeStatus: statusData?.runtime,
    }),
    h('main', { className: 'main-wrapper', key: 'main' }, [
      h(Header, {
        key: 'header',
        title: currentTitle[0],
        subtitle: currentTitle[1],
        onWarmup: handleWarmup,
        onRefresh: refreshAll,
        isRefreshing,
      }),
      h('div', { className: 'content-container', key: 'content' }, [
        activeTab === 'overview' ? h(OverviewView, { statusData, onSwitchTab: setActiveTab, showToast, onRefresh: refreshAll }) : null,
        activeTab === 'ollama' ? h(OllamaView, { modelsData: ollamaData, statusData, onRefresh: refreshAll, showToast, onBenchmark: (m) => { setActiveTab('models'); } }) : null,
        activeTab === 'models' ? h(ModelsView, { installedModels: ollamaData.models || [], showToast }) : null,
        activeTab === 'mcps' ? h(MCPsView, { showToast }) : null,
        activeTab === 'chat' ? h(ChatView, { showToast }) : null,
        activeTab === 'telegram' ? h(TelegramView, { showToast }) : null,
        activeTab === 'memory' ? h(MemoryView, null) : null,
        activeTab === 'settings' ? h(SettingsView, { showToast }) : null,
      ]),
    ]),
    // Toast Container
    h('div', { className: 'toast-container', key: 'toasts' },
      toasts.map(t => h('div', { className: `toast toast-${t.type}`, key: t.id }, t.msg))
    ),
  ]);
}

// Auto-mount on load
if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => {
    const rootElem = document.getElementById('root');
    if (rootElem && window.ReactDOM) {
      const root = window.ReactDOM.createRoot(rootElem);
      root.render(h(App));
    }
  });
}
