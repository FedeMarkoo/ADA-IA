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
  getDebug() { return this.request('/api/debug'); },
  setDebug(enabled) { return this.request('/api/debug', { method: 'POST', body: JSON.stringify({ enabled }) }); },
  
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
  stopAgent() { return this.request('/api/agent/stop', { method: 'POST' }); },
  startAgent() { return this.request('/api/agent/start', { method: 'POST' }); },

  // Telegram Bot Lifecycle
  getTelegramStatus() { return this.request('/api/telegram/status'); },
  startTelegram() { return this.request('/api/telegram/start', { method: 'POST' }); },
  stopTelegram() { return this.request('/api/telegram/stop', { method: 'POST' }); },
  restartTelegram() { return this.request('/api/telegram/restart', { method: 'POST' }); },
  testTelegram(body = {}) { return this.request('/api/telegram/test', { method: 'POST', body: JSON.stringify(body) }); },
  getTelegramHistory() { return this.request('/api/telegram/history'); },
  saveTelegramConfig(data) { return this.request('/api/telegram/config', { method: 'POST', body: JSON.stringify(data) }); },

  // Encrypted Vault (vault.db)
  getVaultKeys() { return this.request('/api/vault/keys'); },
  setVaultSecret(name, value, meta = {}) {
    return this.request('/api/vault/set', { method: 'POST', body: JSON.stringify({ name, value, meta }) });
  },
  deleteVaultSecret(name) {
    return this.request('/api/vault/' + encodeURIComponent(name), { method: 'DELETE' });
  },

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
  stopAllMCPServers() { return this.request('/api/mcps/servers/stop-all', { method: 'POST' }); },
  startAllMCPServers() { return this.request('/api/mcps/servers/start-all', { method: 'POST' }); },
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
  restartAll() { return this.request('/api/restart-all', { method: 'POST' }); },
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
function Header({ title, subtitle, onWarmup, onRefresh, onRestartAll, isRefreshing, isRestarting, identity, debugEnabled, onToggleDebug }) {
  return h('header', { className: 'top-header' }, [
    h('div', { className: 'header-left', key: 'left' }, [
      h('h1', { className: 'page-title', id: 'page-title' }, title),
      h('span', { className: 'page-subtitle', id: 'page-subtitle' }, `${subtitle} · ADA v${identity?.version || '—'} · inicio ${identity?.started_at ? new Date(identity.started_at).toLocaleString() : '—'}`),
    ]),
    h('div', { className: 'header-actions', key: 'actions' }, [
      h('button', { className: 'btn btn-ghost', id: 'btn-warmup', onClick: onWarmup, title: 'Precargar motor' }, [
        h('span', null, '⚡ Warmup'),
      ]),
      h('button', { className: `btn ${debugEnabled ? 'btn-danger' : 'btn-ghost'}`, onClick: onToggleDebug, title: 'Guardar log técnico detallado' }, debugEnabled ? '🐞 Debug ON' : '🐞 Debug'),
      h('button', { className: 'btn btn-secondary', id: 'btn-refresh', onClick: onRefresh, title: 'Actualizar datos' }, [
        h('span', null, isRefreshing ? 'Actualizando...' : '🔄 Actualizar'),
      ]),
      h('button', { className: 'btn btn-danger', id: 'btn-restart-all', onClick: onRestartAll, disabled: isRestarting, title: 'Reiniciar servicios de ADA' }, [
        h('span', null, isRestarting ? 'Reiniciando...' : '↻ Reiniciar todo'),
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
  const isAgentRunning = statusData?.agent_enabled !== false;
  const mcpServers = statusData?.mcp_servers || [];
  const areMCPsRunning = mcpServers.some(server => server.status === 'active');

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
          const effectiveStatus = item.id === 'ada_agent' && statusData?.agent_enabled === false
            ? 'stopped'
            : item.id === 'mcps_subsystem' && statusData?.mcp_servers?.length && statusData.mcp_servers.every(server => server.status !== 'active')
              ? 'stopped'
              : item.status;
          const isOk = effectiveStatus === 'ok';
          const isWarn = effectiveStatus === 'warning';
          const statusBadge = isOk ? 'badge-success' : isWarn ? 'badge-warning' : 'badge-danger';
          const statusLabel = isOk ? 'OK' : isWarn ? 'Alerta' : effectiveStatus === 'stopped' ? 'Apagado' : 'Error';
          const icon = ITEM_ICONS[item.id] || '⚙️';

          return h('div', { className: 'doctor-item-card', key: item.id }, [
            h('div', { className: 'doctor-item-top' }, [
              h('div', { className: 'doctor-item-name' }, [
                h('span', { className: 'text-base' }, icon),
                h('span', null, item.name),
              ]),
              h('span', { className: `badge ${statusBadge}` }, statusLabel),
            ]),
            h('p', { className: 'doctor-item-msg' }, effectiveStatus === 'stopped' ? (item.id === 'ada_agent' ? 'ADA Agent Core está apagado.' : 'Todos los servidores MCP están apagados.') : item.message),
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
          h('span', { className: `stat-badge ${statusData?.agent_enabled === false ? 'badge-danger' : 'badge-primary'}` }, statusData?.agent_enabled === false ? 'Apagado' : 'Activo'),
        ]),
        h('div', { className: 'stat-value' }, statusData?.agent_enabled === false ? 'Detenido' : 'Listo'),
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
              h('span', { className: `badge ${isAgentRunning ? 'badge-success' : 'badge-danger'}` }, isAgentRunning ? 'Operativo' : 'Apagado'),
            ]),
            h('p', { className: 'text-xs text-muted mt-1' }, 'Orquestador multiagente, memoria y router.'),
            h('div', { className: 'service-box-actions mt-4 flex gap-2' }, [
              !isAgentRunning ? h('button', { className: 'btn btn-sm btn-primary', onClick: async () => { await api.startAgent(); onRefresh(); } }, '▶ Iniciar') : h('button', { className: 'btn btn-sm btn-secondary', onClick: async () => { await api.stopAgent(); onRefresh(); } }, '⏹ Apagar'),
              h('button', { className: 'btn btn-sm btn-ghost', onClick: handleAgentRestart }, '🔄 Reiniciar'),
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
              h('span', { className: `badge ${areMCPsRunning ? 'badge-accent' : 'badge-danger'}` }, areMCPsRunning ? 'Conectados' : 'Apagados'),
            ]),
            h('p', { className: 'text-xs text-muted mt-1' }, 'Servidores Model Context Protocol y herramientas.'),
            h('div', { className: 'service-box-actions mt-4 flex gap-2' }, [
              areMCPsRunning ? h('button', { className: 'btn btn-sm btn-secondary', onClick: async () => { await api.stopAllMCPServers(); onRefresh(); } }, '⏹ Apagar Todos') : h('button', { className: 'btn btn-sm btn-primary', onClick: async () => { await api.startAllMCPServers(); onRefresh(); } }, '▶ Iniciar Todos'),
              h('button', { className: 'btn btn-sm btn-ghost', onClick: handleMCPsRestartAll }, '🔄 Reiniciar Todos'),
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
  const sendingRef = useRef(false);

  useEffect(() => {
    api.getConversation().then(data => {
      if (data.messages && data.messages.length) {
        setMessages(data.messages.filter(m => m.kind !== 'status'));
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming || sendingRef.current) return;
    sendingRef.current = true;
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
      let eventName = 'message';
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split(/\n\n/);
        buffer = events.pop() || '';
        for (const eventBlock of events) {
          const lines = eventBlock.split(/\n/);
          let payloadLine = null;
          for (const line of lines) {
            if (line.startsWith('event: ')) eventName = line.slice(7).trim();
            if (line.startsWith('data: ')) payloadLine = line.slice(6);
          }
          if (payloadLine) {
            try {
              const data = JSON.parse(payloadLine);
              if (data.text && (eventName === 'status' || eventName === 'reply' || eventName === 'error' || eventName === 'message')) {
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
      if (buffer.trim()) {
        const dataLine = buffer.split(/\n/).find(line => line.startsWith('data: '));
        if (dataLine) {
          const data = JSON.parse(dataLine.slice(6));
          if (data.text) setMessages(prev => { const updated = [...prev]; updated[assistantIdx] = { role: 'assistant', text: data.text }; return updated; });
        }
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev];
        updated[assistantIdx] = { role: 'assistant', text: `Error: ${err.message}` };
        return updated;
      });
    } finally {
      sendingRef.current = false;
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

  // Vault State
  const [vaultKeys, setVaultKeys] = useState([]);
  const [vaultLoading, setVaultLoading] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('telegram_bot_token');
  const [customKeyName, setCustomKeyName] = useState('');
  const [secretValue, setSecretValue] = useState('');
  const [secretDescription, setSecretDescription] = useState('');
  const [savingSecret, setSavingSecret] = useState(false);

  const fetchVaultKeys = useCallback(async () => {
    try {
      setVaultLoading(true);
      const res = await api.getVaultKeys();
      if (res.ok) {
        setVaultKeys(res.keys || []);
      }
    } catch (err) {
      console.warn('Error fetching vault keys:', err);
    } finally {
      setVaultLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVaultKeys();
  }, [fetchVaultKeys]);

  const handleSaveSecret = async (e) => {
    e.preventDefault();
    const finalKey = selectedPreset === 'custom' ? customKeyName.trim() : selectedPreset;
    if (!finalKey) {
      showToast('Ingresá el nombre del secreto', 'warning');
      return;
    }
    if (!secretValue.trim()) {
      showToast('El valor del secreto no puede estar vacío', 'warning');
      return;
    }
    setSavingSecret(true);
    try {
      showToast('Cifrando y guardando en vault.db...', 'info');
      const res = await api.setVaultSecret(finalKey, secretValue.trim(), {
        description: secretDescription.trim() || `Clave para ${finalKey}`,
      });
      showToast(res.message || 'Secreto cifrado guardado', 'success');
      setSecretValue('');
      setSecretDescription('');
      if (selectedPreset === 'custom') setCustomKeyName('');
      fetchVaultKeys();
    } catch (err) {
      showToast('Error al guardar secreto: ' + err.message, 'danger');
    } finally {
      setSavingSecret(false);
    }
  };

  const handleDeleteSecret = async (name) => {
    if (!confirm(`¿Estás seguro de eliminar el secreto cifrado '${name}' de la bóveda?`)) return;
    try {
      const res = await api.deleteVaultSecret(name);
      showToast(res.message || 'Secreto eliminado', 'info');
      fetchVaultKeys();
    } catch (err) {
      showToast('Error al eliminar: ' + err.message, 'danger');
    }
  };

  return h('section', { className: 'tab-view active flex flex-col gap-6', id: 'tab-settings' }, [
    // 1. General Config Card
    h('div', { className: 'card max-w-4xl' }, [
      h('div', { className: 'card-header' }, [
        h('h3', { className: 'card-title' }, '⚙️ Configuración del Asistente'),
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

    // 2. Encrypted Vault (vault.db) Card
    h('div', { className: 'card max-w-4xl', key: 'vault-settings-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('span', { className: 'text-xl' }, '🔐'),
          h('div', null, [
            h('h3', { className: 'card-title' }, 'Bóveda Cifrada de Credenciales & Tokens (vault.db)'),
            h('p', { className: 'text-xs text-muted' }, 'Base de datos SQLite aislada (~/Desktop/ADA_Data/vault.db) cifrada con AES-256 (Fernet) y protegida por el SO.'),
          ]),
        ]),
        h('span', { className: 'badge badge-success' }, 'AES-256 Cifrado en Reposo'),
      ]),
      h('div', { className: 'card-body flex flex-col gap-6' }, [
        // List of Stored Secrets
        h('div', null, [
          h('h4', { className: 'text-sm font-semibold text-white mb-3' }, 'Secretos Almacenados Cifrados:'),
          vaultKeys.length === 0
            ? h('p', { className: 'text-xs text-muted p-3 bg-surface-elevated rounded-lg' }, 'No hay credenciales almacenadas en la bóveda aún.')
            : h('div', { className: 'flex flex-col gap-2' },
                vaultKeys.map(k =>
                  h('div', {
                    key: k.name,
                    className: 'p-3 bg-surface-elevated rounded-lg flex items-center justify-between border border-subtle'
                  }, [
                    h('div', { className: 'flex items-center gap-3' }, [
                      h('span', { className: 'badge badge-accent font-mono' }, k.name),
                      h('span', { className: 'text-xs text-muted' }, k.meta?.description || 'Credencial cifrada'),
                      h('span', { className: 'text-xs text-muted' }, `(Actualizado: ${k.updated_at})`),
                    ]),
                    h('button', {
                      className: 'btn btn-sm btn-ghost text-danger',
                      onClick: () => handleDeleteSecret(k.name),
                      title: 'Eliminar secreto de la bóveda'
                    }, '🗑️ Eliminar')
                  ])
                )
              )
        ]),

        // Add / Update Secret Form
        h('form', { onSubmit: handleSaveSecret, className: 'p-4 bg-surface-elevated rounded-lg border border-subtle flex flex-col gap-4' }, [
          h('h4', { className: 'text-sm font-semibold text-white' }, '➕ Agregar o Actualizar Secreto Cifrado:'),
          h('div', { className: 'grid grid-cols-2 gap-4' }, [
            h('div', { className: 'form-group' }, [
              h('label', { className: 'form-label text-xs' }, 'Tipo de Secreto / Servicio'),
              h('select', {
                className: 'form-select font-mono text-sm',
                value: selectedPreset,
                onChange: (e) => setSelectedPreset(e.target.value),
              }, [
                h('option', { value: 'telegram_bot_token' }, '📱 Telegram Bot Token (telegram_bot_token)'),
                h('option', { value: 'openai_api_key' }, '🤖 OpenAI API Key (openai_api_key)'),
                h('option', { value: 'anthropic_api_key' }, '🧠 Anthropic API Key (anthropic_api_key)'),
                h('option', { value: 'openrouter_api_key' }, '🌐 OpenRouter API Key (openrouter_api_key)'),
                h('option', { value: 'groq_api_key' }, '⚡ Groq API Key (groq_api_key)'),
                h('option', { value: 'gmail_oauth' }, '📧 Gmail OAuth Token (gmail_oauth)'),
                h('option', { value: 'instagram_access_token' }, '📸 Instagram Access Token (instagram_access_token)'),
                h('option', { value: 'custom' }, '✏️ Clave Personalizada...'),
              ]),
            ]),
            selectedPreset === 'custom'
              ? h('div', { className: 'form-group' }, [
                  h('label', { className: 'form-label text-xs' }, 'Nombre de la Clave'),
                  h('input', {
                    type: 'text',
                    className: 'form-input font-mono text-sm',
                    placeholder: 'ej: stripe_api_key',
                    value: customKeyName,
                    onChange: (e) => setCustomKeyName(e.target.value),
                  }),
                ])
              : h('div', { className: 'form-group' }, [
                  h('label', { className: 'form-label text-xs' }, 'Descripción Opcional'),
                  h('input', {
                    type: 'text',
                    className: 'form-input text-sm',
                    placeholder: 'ej: Token principal',
                    value: secretDescription,
                    onChange: (e) => setSecretDescription(e.target.value),
                  }),
                ]),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label text-xs' }, 'Valor del Secreto (Se cifrará antes de guardarse en el disco)'),
            h('input', {
              type: 'password',
              className: 'form-input font-mono text-sm',
              placeholder: 'Pegá aquí tu clave secreta o token...',
              value: secretValue,
              onChange: (e) => setSecretValue(e.target.value),
            }),
          ]),
          h('div', { className: 'flex justify-end' }, [
            h('button', {
              type: 'submit',
              className: 'btn btn-primary',
              disabled: savingSecret,
            }, savingSecret ? 'Cifrando...' : '🔐 Guardar Cifrado en vault.db'),
          ]),
        ]),
      ]),
    ]),
  ]);
}

// =============================================================================
// Telegram View Component (Standard ADA Design System)
// =============================================================================
function TelegramView({ showToast }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [showConfigCard, setShowConfigCard] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const [allowedChatsInput, setAllowedChatsInput] = useState('');
  const [savingConfig, setSavingConfig] = useState(false);
  const [history, setHistory] = useState([]);

  const fetchStatus = useCallback(async () => {
    try {
      const [data, hist] = await Promise.all([
        api.getTelegramStatus(),
        api.getTelegramHistory().catch(() => ({ messages: [] })),
      ]);
      setStatus(data);
      setHistory(hist?.messages || []);
      if (!data.token_set) {
        setShowConfigCard(true);
      }
    } catch (err) {
      showToast('Error al obtener estado de Telegram: ' + err.message, 'danger');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 4000);
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

  const handleSaveConfig = async (e) => {
    if (e) e.preventDefault();
    if (!tokenInput.trim() && !status?.token_set) {
      showToast('Ingresá un token de Telegram válido', 'warning');
      return;
    }
    setSavingConfig(true);
    try {
      showToast('Guardando configuración de Telegram...', 'info');
      const res = await api.saveTelegramConfig({
        token: tokenInput.trim(),
        allowed_chat_ids: allowedChatsInput,
      });
      showToast(res.message || 'Configuración guardada', 'success');
      setTokenInput('');
      setShowConfigCard(false);
      fetchStatus();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    } finally {
      setSavingConfig(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      showToast('Verificando token con la API oficial de Telegram (getMe)...', 'info');
      const res = await api.testTelegram(tokenInput.trim() ? { token: tokenInput.trim() } : {});
      if (res.ok) {
        setTestResult(res.bot);
        showToast(`¡Conexión exitosa! Bot: @${res.bot?.username || 'bot'}`, 'success');
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
    return h('div', { className: 'initial-loader' }, [
      h('div', { className: 'loader-spinner mb-4' }),
      h('p', { className: 'text-muted' }, 'Cargando estado del servicio Telegram Bot...'),
    ]);
  }

  const isRunning = status?.running === true;

  return h('section', { className: 'tab-view active', id: 'tab-telegram' }, [
    // 1. Control Bar Card
    h('div', { className: 'card mb-6', key: 'telegram-control-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-3' }, [
          h('span', { className: 'text-xl' }, '📱'),
          h('div', null, [
            h('div', { className: 'flex items-center gap-2' }, [
              h('h3', { className: 'card-title' }, 'Control del Servidor Telegram Bot'),
              h('span', { className: `badge ${isRunning ? 'badge-success' : 'badge-danger'}` },
                isRunning ? 'En ejecución (Long-polling)' : 'Detenido'
              ),
            ]),
            h('p', { className: 'text-xs text-muted mt-1' },
              'Daemon independiente desacoplado que reenvía texto, fotos y comandos a los endpoints de razonamiento de ADA.'
            ),
          ]),
        ]),
        h('div', { className: 'flex items-center gap-2' }, [
          h('button', {
            className: `btn btn-sm ${showConfigCard ? 'btn-primary' : 'btn-outline'}`,
            onClick: () => setShowConfigCard(!showConfigCard),
          }, '🔑 ' + (status?.token_set ? 'Cambiar Token' : 'Configurar Token')),
          isRunning
            ? h('button', {
                className: 'btn btn-sm btn-danger',
                onClick: handleStop,
                disabled: actionLoading,
              }, '⏹ Detener Bot')
            : h('button', {
                className: 'btn btn-sm btn-primary',
                onClick: handleStart,
                disabled: actionLoading || !status?.token_set,
              }, '▶ Iniciar Bot'),
          h('button', {
            className: 'btn btn-sm btn-secondary',
            onClick: handleRestart,
            disabled: actionLoading || !isRunning,
          }, '🔄 Reiniciar'),
          h('button', {
            className: 'btn btn-sm btn-outline',
            onClick: handleTestConnection,
            disabled: testing || (!status?.token_set && !tokenInput.trim()),
          }, testing ? '⌛ Probando...' : '🔍 Probar Conexión (getMe)'),
          h('button', {
            className: 'btn btn-sm btn-ghost',
            onClick: fetchStatus,
          }, '🔄'),
        ]),
      ]),
    ]),

    // 2. Token Configuration Form Card (Collapsible)
    showConfigCard ? h('div', { className: 'card mb-6 animate-fade-in', key: 'token-config-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, '🔑 Configuración de Token & Autenticación de Telegram'),
          h('span', { className: 'badge badge-success' }, 'Cifrado en vault.db (AES-256)'),
        ]),
        h('button', { className: 'btn btn-sm btn-ghost', onClick: () => setShowConfigCard(false) }, '✕ Cerrar'),
      ]),
      h('div', { className: 'card-body' }, [
        h('form', { onSubmit: handleSaveConfig, className: 'flex flex-col gap-4' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Token del Bot (entregado por @BotFather)'),
            h('input', {
              type: 'text',
              className: 'form-input font-mono',
              placeholder: status?.token_masked ? `Token actual cargado (${status.token_masked}) - Ingresá uno nuevo para actualizar` : 'Ej: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz',
              value: tokenInput,
              onChange: (e) => setTokenInput(e.target.value),
            }),
            h('span', { className: 'text-xs text-muted mt-1 block' }, 'Se guardará cifrado en ~/Desktop/ADA_Data/vault.db mediante utils.credentials.'),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Chat IDs Autorizados (Opcional, separados por comas)'),
            h('input', {
              type: 'text',
              className: 'form-input font-mono',
              placeholder: 'Ej: 123456789, 987654321 (dejar vacío para acceso libre)',
              value: allowedChatsInput,
              onChange: (e) => setAllowedChatsInput(e.target.value),
            }),
            h('span', { className: 'text-xs text-muted mt-1 block' }, 'Si agregás IDs, el bot solo responderá a esos usuarios específicos.'),
          ]),
          h('div', { className: 'flex justify-end gap-2' }, [
            h('button', {
              type: 'button',
              className: 'btn btn-secondary',
              onClick: handleTestConnection,
              disabled: testing || (!status?.token_set && !tokenInput.trim()),
            }, testing ? 'Probando...' : '🔍 Probar Token'),
            h('button', {
              type: 'submit',
              className: 'btn btn-primary',
              disabled: savingConfig,
            }, savingConfig ? 'Guardando...' : '💾 Guardar Configuración'),
          ]),
        ]),
      ]),
    ]) : null,

    // 3. 4 Stat KPI Cards Grid
    h('div', { className: 'grid grid-cols-4 gap-4 mb-6', key: 'telegram-stats' }, [
      // KPI 1: Estado del Proceso
      h('div', { className: 'card stat-card', key: 'stat-status' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'Estado del Proceso'),
          h('span', { className: `status-indicator ${isRunning ? 'online' : 'offline'}` }),
        ]),
        h('div', { className: `stat-value ${isRunning ? 'text-success' : 'text-muted'}` }, isRunning ? 'ONLINE' : 'OFFLINE'),
        h('div', { className: 'stat-footer' }, isRunning ? `Polling cada ${status.poll_seconds}s activo` : 'Daemon detenido'),
      ]),

      // KPI 2: Token Configurado
      h('div', { className: 'card stat-card', key: 'stat-token' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'Token de Bot'),
          h('span', { className: 'badge ' + (status?.token_set ? 'badge-primary' : 'badge-warning') },
            status?.token_set ? 'Cargado' : 'Falta Token'
          ),
        ]),
        h('div', { className: 'stat-value font-mono text-base', style: { fontSize: '1.05rem', wordBreak: 'break-all' } },
          status?.token_masked || 'No configurado'
        ),
        h('div', { className: 'stat-footer' }, status?.token_set ? 'Token cifrado en vault.db' : 'Falta configurar token'),
      ]),

      // KPI 3: Chats Autorizados
      h('div', { className: 'card stat-card', key: 'stat-chats' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'Seguridad de Acceso'),
          h('span', { className: 'badge badge-accent' },
            (status?.allowed_chat_ids?.length || 0) > 0 ? 'Filtro Activo' : 'Público'
          ),
        ]),
        h('div', { className: 'stat-value' },
          (status?.allowed_chat_ids?.length || 0) > 0 ? `${status.allowed_chat_ids.length} Chat(s)` : 'Acceso Libre'
        ),
        h('div', { className: 'stat-footer' },
          (status?.allowed_chat_ids?.length || 0) > 0 ? `IDs: ${status.allowed_chat_ids.join(', ')}` : 'Sin restricción de ID'
        ),
      ]),

      // KPI 4: Mensajes Recibidos
      h('div', { className: 'card stat-card', key: 'stat-inbox' }, [
        h('div', { className: 'stat-header' }, [
          h('span', { className: 'stat-label' }, 'Mensajes Recibidos'),
          h('span', { className: 'badge badge-outline' }, `${history.length} Total`),
        ]),
        h('div', { className: 'stat-value' }, `${history.length} Interacción(es)`),
        h('div', { className: 'stat-footer' }, 'Sesiones activas vía Telegram'),
      ]),
    ]),

    // 4. Bot Identity Card (if test succeeds)
    testResult && !testResult.error ? h('div', { className: 'card mb-6', key: 'telegram-identity-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, '🤖 Identidad del Bot Verificada por Telegram'),
          h('span', { className: 'badge badge-success' }, 'Conexión Exitosa'),
        ]),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'grid grid-cols-4 gap-4' }, [
          h('div', { className: 'p-3 bg-surface-elevated rounded-lg' }, [
            h('span', { className: 'text-xs text-muted uppercase font-bold block mb-1' }, 'Nombre del Bot'),
            h('span', { className: 'font-semibold text-base' }, testResult.first_name || 'ADA Bot'),
          ]),
          h('div', { className: 'p-3 bg-surface-elevated rounded-lg' }, [
            h('span', { className: 'text-xs text-muted uppercase font-bold block mb-1' }, 'Username Oficial'),
            h('span', { className: 'badge badge-accent text-sm' }, `@${testResult.username}`),
          ]),
          h('div', { className: 'p-3 bg-surface-elevated rounded-lg' }, [
            h('span', { className: 'text-xs text-muted uppercase font-bold block mb-1' }, 'ID de Telegram'),
            h('span', { className: 'font-mono text-sm' }, testResult.id),
          ]),
          h('div', { className: 'p-3 bg-surface-elevated rounded-lg' }, [
            h('span', { className: 'text-xs text-muted uppercase font-bold block mb-1' }, 'Soporte de Grupos'),
            h('span', { className: 'badge ' + (testResult.can_join_groups ? 'badge-success' : 'badge-warning') },
              testResult.can_join_groups ? 'Habilitado' : 'Deshabilitado'
            ),
          ]),
        ]),
      ]),
    ]) : null,

    // 5. Live Received Messages & Conversations Table
    h('div', { className: 'card mb-6', key: 'telegram-conversations-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, '💬 Mensajes & Sesiones de Conversación en Vivo'),
          h('span', { className: 'badge badge-primary' }, `${history.length} Registrados`),
        ]),
        h('button', { className: 'btn btn-sm btn-ghost', onClick: fetchStatus }, '🔄 Refrescar'),
      ]),
      h('div', { className: 'card-body p-0' }, [
        history.length === 0
          ? h('div', { className: 'p-6 text-center text-muted' }, [
              h('p', { className: 'text-base mb-1' }, '📭 Aún no se han registrado mensajes recibidos por Telegram.'),
              h('p', { className: 'text-xs' }, 'Iniciá el bot y enviá un mensaje desde la app de Telegram. Al responder, vas a ver aquí el Conversation ID, usuario (@username), texto y respuesta en tiempo real.'),
            ])
          : h('div', { className: 'overflow-x-auto' }, [
              h('table', { className: 'table w-full', style: { width: '100%', borderCollapse: 'collapse' } }, [
                h('thead', null, [
                  h('tr', { style: { borderBottom: '1px solid var(--border-subtle)', textAlign: 'left' } }, [
                    h('th', { className: 'p-3 text-xs text-muted uppercase' }, 'Conversation ID'),
                    h('th', { className: 'p-3 text-xs text-muted uppercase' }, 'Usuario / Remitente'),
                    h('th', { className: 'p-3 text-xs text-muted uppercase' }, 'Chat ID'),
                    h('th', { className: 'p-3 text-xs text-muted uppercase' }, 'Mensaje Recibido'),
                    h('th', { className: 'p-3 text-xs text-muted uppercase' }, 'Respuesta de ADA'),
                    h('th', { className: 'p-3 text-xs text-muted uppercase' }, 'Fecha / Hora'),
                  ]),
                ]),
                h('tbody', null,
                  history.map((item, idx) =>
                    h('tr', {
                      key: item.id || idx,
                      style: { borderBottom: '1px solid var(--border-subtle)' },
                      className: 'hover:bg-surface-elevated'
                    }, [
                      h('td', { className: 'p-3' }, [
                        h('span', { className: 'badge badge-accent font-mono text-xs' }, item.conversation_id || 'telegram_unknown'),
                      ]),
                      h('td', { className: 'p-3' }, [
                        h('div', { className: 'flex flex-col' }, [
                          h('span', { className: 'font-semibold text-sm text-white' }, item.first_name || 'Usuario'),
                          item.username ? h('span', { className: 'text-xs text-accent' }, item.username) : null,
                        ]),
                      ]),
                      h('td', { className: 'p-3 font-mono text-xs text-muted' }, item.chat_id || '-'),
                      h('td', { className: 'p-3 text-sm text-secondary', style: { maxWidth: '260px', wordBreak: 'break-word' } }, item.message),
                      h('td', { className: 'p-3 text-sm text-white', style: { maxWidth: '320px', wordBreak: 'break-word' } }, item.reply),
                      h('td', { className: 'p-3 text-xs text-muted whitespace-nowrap' }, item.timestamp),
                    ])
                  )
                ),
              ]),
            ]),
      ]),
    ]),

    // 6. Instructions & Execution Card
    h('div', { className: 'grid grid-cols-2 gap-6', key: 'telegram-details' }, [
      // Left Card: CLI Execution
      h('div', { className: 'card', key: 'cli-guide' }, [
        h('div', { className: 'card-header' }, [
          h('div', { className: 'flex items-center gap-2' }, [
            h('h3', { className: 'card-title' }, '💻 Ejecución como Proceso Aislado'),
            h('span', { className: 'badge badge-primary' }, 'CLI & Background'),
          ]),
        ]),
        h('div', { className: 'card-body' }, [
          h('p', { className: 'text-sm text-muted mb-3' },
            'Telegram está diseñado como un servidor/bot completamente independiente en `telegram/bot.py`. Podés ejecutarlo directamente en una terminal separada, en un contenedor o como servicio systemd:'
          ),
          h('pre', {
            className: 'p-4 rounded-lg bg-base font-mono text-xs text-secondary overflow-x-auto border border-subtle leading-relaxed',
            style: { background: '#0a0d14' }
          },
            `# 1. Configurar token en la Bóveda Cifrada (vault.db)\n.venv/bin/python -c "from utils.credentials import SecureVault; SecureVault().set('telegram_bot_token', 'TU_TOKEN')"\n\n# 2. Iniciar el bot de Telegram de forma aislada\n.venv/bin/python telegram/bot.py`
          ),
          h('div', { className: 'flex justify-between items-center mt-3 text-xs text-muted' }, [
            h('span', null, '💡 Se comunica con ADA vía REST HTTP'),
            h('span', { className: 'badge badge-outline' }, 'http://127.0.0.1:5005'),
          ]),
        ]),
      ]),

      // Right Card: Features & Capabilities
      h('div', { className: 'card', key: 'features-guide' }, [
        h('div', { className: 'card-header' }, [
          h('div', { className: 'flex items-center gap-2' }, [
            h('h3', { className: 'card-title' }, '⚡ Capacidades del Bot'),
            h('span', { className: 'badge badge-accent' }, 'Disponibles'),
          ]),
        ]),
        h('div', { className: 'card-body' }, [
          h('ul', { className: 'flex flex-col gap-3 text-sm text-secondary' }, [
            h('li', { className: 'flex items-start gap-2' }, [
              h('span', { className: 'text-success' }, '✓'),
              h('div', null, [
                h('strong', { className: 'text-white' }, 'Consultas en Lenguaje Natural: '),
                h('span', null, 'Respuestas con razonamiento paso a paso impulsadas por el LLM local.'),
              ]),
            ]),
            h('li', { className: 'flex items-start gap-2' }, [
              h('span', { className: 'text-success' }, '✓'),
              h('div', null, [
                h('strong', { className: 'text-white' }, 'Recepción y Análisis de Fotos: '),
                h('span', null, 'Descarga automática en la carpeta externa y evaluación técnica/semántica.'),
              ]),
            ]),
            h('li', { className: 'flex items-start gap-2' }, [
              h('span', { className: 'text-success' }, '✓'),
              h('div', null, [
                h('strong', { className: 'text-white' }, 'Gestión de Compras y Alacena: '),
                h('span', null, 'Comandos para agregar productos a la lista de compras o consultar recetas.'),
              ]),
            ]),
            h('li', { className: 'flex items-start gap-2' }, [
              h('span', { className: 'text-success' }, '✓'),
              h('div', null, [
                h('strong', { className: 'text-white' }, 'Identificación de Sesión y Usuario: '),
                h('span', null, 'Cada remitente posee su conversation_id, nombre y @username en tiempo real.'),
              ]),
            ]),
          ]),
        ]),
      ]),
    ]),
  ]);
}

// =============================================================================
// Main App Component
// =============================================================================
export function App() {
  const validTabs = ['overview', 'ollama', 'models', 'mcps', 'chat', 'telegram', 'memory', 'settings'];
  const [activeTab, setActiveTab] = useState(() => {
    const requested = window.location.hash.replace(/^#/, '');
    return validTabs.includes(requested) ? requested : 'overview';
  });
  const [statusData, setStatusData] = useState(null);
  const [ollamaData, setOllamaData] = useState({ models: [], running: [] });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [debugEnabled, setDebugEnabled] = useState(false);
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
    api.getDebug().then(data => setDebugEnabled(Boolean(data.enabled))).catch(() => {});
    const interval = setInterval(() => {
      api.getStatus().then(setStatusData).catch(() => {});
    }, 15000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const toggleDebug = async () => {
    const next = !debugEnabled;
    await api.setDebug(next);
    setDebugEnabled(next);
    showToast(next ? 'Debug activado: guardando ejecución detallada' : 'Debug desactivado', next ? 'warning' : 'info');
  };

  useEffect(() => {
    const onHashChange = () => {
      const requested = window.location.hash.replace(/^#/, '');
      if (validTabs.includes(requested)) setActiveTab(requested);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const selectTab = (tab) => {
    if (!validTabs.includes(tab)) return;
    setActiveTab(tab);
    window.history.replaceState(null, '', `#${tab}`);
  };

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

  const handleRestartAll = async () => {
    if (!window.confirm('¿Reiniciar todos los servicios administrados por ADA?')) return;
    setIsRestarting(true);
    try {
      await api.restartAll();
      await refreshAll();
      showToast('Servicios reiniciados correctamente', 'success');
    } catch (err) {
      showToast('Error al reiniciar: ' + err.message, 'danger');
    } finally {
      setIsRestarting(false);
    }
  };

  return h('div', { className: 'app-layout' }, [
    h(Sidebar, {
      key: 'sidebar',
      activeTab,
      onSelectTab: selectTab,
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
        onRestartAll: handleRestartAll,
        isRefreshing,
        isRestarting,
        identity: statusData?.identity,
        debugEnabled,
        onToggleDebug: toggleDebug,
      }),
      h('div', { className: 'content-container', key: 'content' }, [
        activeTab === 'overview' ? h(OverviewView, { statusData, onSwitchTab: selectTab, showToast, onRefresh: refreshAll }) : null,
        activeTab === 'ollama' ? h(OllamaView, { modelsData: ollamaData, statusData, onRefresh: refreshAll, showToast, onBenchmark: (m) => { selectTab('models'); } }) : null,
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
