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
  getCoreState() { return this.request('/api/core/state'); },
  getTimeSeries() { return this.request('/api/metrics/timeseries?hours=24'); },
  getDebug() { return this.request('/api/debug'); },
  setDebug(enabled) { return this.request('/api/debug', { method: 'POST', body: JSON.stringify({ enabled }) }); },

  // Ollama Lifecycle & Config
  getOllamaStatus() { return this.request('/api/ollama/status'); },
  startOllama() { return this.request('/api/ollama/start', { method: 'POST' }); },
  stopOllama() { return this.request('/api/ollama/stop', { method: 'POST' }); },
  restartOllama() { return this.request('/api/ollama/restart', { method: 'POST' }); },
  getOllamaModels() { return this.request('/api/ollama/models'); },
  getOllamaConfig() { return this.request('/api/ollama/config'); },
  saveOllamaConfig(config) { return this.request('/api/ollama/config', { method: 'POST', body: JSON.stringify(config) }); },
  getOllamaDetails(model) { return this.request(`/api/ollama/details?model=${encodeURIComponent(model)}`); },
  loadOllamaModel(model) {
    return this.request('/api/ollama/load', { method: 'POST', body: JSON.stringify({ model }) });
  },
  preloadAllModels() {
    return this.request('/api/ollama/preload_all', { method: 'POST' });
  },
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

  // Metrics Scraper Lifecycle
  getMetricsScraperStatus() { return this.request('/api/metrics/scraper/status'); },
  startMetricsScraper() { return this.request('/api/metrics/scraper/start', { method: 'POST' }); },
  stopMetricsScraper() { return this.request('/api/metrics/scraper/stop', { method: 'POST' }); },

  // Event sources and entry points
  getTriggers() { return this.request('/api/triggers'); },
  controlTrigger(id, action) {
    return this.request(`/api/triggers/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
  },

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
  addCatalogModel(data) { return this.request('/api/models/catalog', { method: 'POST', body: JSON.stringify(data) }); },
  deleteCatalogModel(name) { return this.request('/api/models/catalog', { method: 'DELETE', body: JSON.stringify({ name }) }); },
  getModelsPolicy() { return this.request('/api/models/policy'); },
  saveModelsSelection(data) {
    return this.request('/api/models/policy', { method: 'POST', body: JSON.stringify(data) });
  },
  saveModelsPolicy(policy) {
    return this.request('/api/models/policy', { method: 'POST', body: JSON.stringify({ model_policy: policy }) });
  },
  runBenchmark(model, prompt_key, custom_prompt, run_suite, prompt_keys) {
    return this.request('/api/models/benchmark', {
      method: 'POST',
      body: JSON.stringify({
        model,
        prompt_key,
        custom_prompt,
        run_suite: Boolean(run_suite || prompt_key === 'suite'),
        prompt_keys,
      }),
    });
  },
  getBenchmarkPrompts() {
    return this.request('/api/models/benchmark/prompts');
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

// Small, dependency-free icon set. Keeping icons as SVG makes the interface
// visually consistent and prevents platform-specific emoji rendering.
const ICON_PATHS = {
  overview: ['M3 3h7v7H3z', 'M14 3h7v4h-7z', 'M14 11h7v10h-7z', 'M3 14h7v7H3z'],
  core: ['M12 3a9 9 0 1 0 9 9', 'M12 7a5 5 0 1 0 5 5', 'M12 10a2 2 0 1 0 2 2', 'M12 1v2', 'M23 12h-2', 'M12 23v-2', 'M1 12h2'],
  engine: ['M9 3h6', 'M10 3v3', 'M14 3v3', 'M7 6h10a2 2 0 0 1 2 2v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V8a2 2 0 0 1 2-2Z', 'M9 11h.01', 'M15 11h.01', 'M9 15h6'],
  models: ['M12 2 4 6v12l8 4 8-4V6Z', 'm4 6 8 4 8-4', 'M12 10v12'],
  tools: ['M8 3v4', 'M16 3v4', 'M5 7h14', 'M6 7v5a6 6 0 0 0 12 0V7', 'M12 18v3'],
  chat: ['M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z', 'M8 9h8', 'M8 13h5'],
  telegram: ['m22 2-7 20-4-9-9-4Z', 'm22 2-11 11'],
  triggers: ['M4 4v6', 'M4 14v6', 'M20 4v6', 'M20 14v6', 'M4 7h5a3 3 0 0 1 3 3v4a3 3 0 0 0 3 3h5', 'M2 12h4', 'M18 12h4'],
  activity: ['M3 12h4l2-7 4 14 2-7h6'],
  settings: ['M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z', 'M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.12 2.12-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1 1.55V20h-3v-.09a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.88.34l-.06.06-2.12-2.12.06-.06A1.7 1.7 0 0 0 7 14.7a1.7 1.7 0 0 0-1.55-1H5v-3h.09a1.7 1.7 0 0 0 1.55-1A1.7 1.7 0 0 0 6.3 7.8l-.06-.06 2.12-2.12.06.06A1.7 1.7 0 0 0 10.3 6a1.7 1.7 0 0 0 1-1.55V4h3v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.12 2.12-.06.06A1.7 1.7 0 0 0 19 9.3a1.7 1.7 0 0 0 1.55 1H21v3h-.09a1.7 1.7 0 0 0-1.51 1.7Z'],
  refresh: ['M20 6v5h-5', 'M4 18v-5h5', 'M18.5 9A7 7 0 0 0 6.2 6.2L4 8', 'M5.5 15A7 7 0 0 0 17.8 17.8L20 16'],
  bolt: ['m13 2-8 12h7l-1 8 8-12h-7Z'],
  bug: ['M8 2l1.5 2', 'M16 2l-1.5 2', 'M9 9h6', 'M9 13h6', 'M12 4a5 5 0 0 1 5 5v5a5 5 0 0 1-10 0V9a5 5 0 0 1 5-5Z', 'M3 13h4', 'M17 13h4'],
  restart: ['M20 11a8 8 0 1 0-2.34 5.66', 'M20 4v7h-7'],
  menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  close: ['m6 6 12 12', 'M18 6 6 18'],
  more: ['M5 12h.01', 'M12 12h.01', 'M19 12h.01'],
  check: ['m5 12 4 4L19 6'],
  alert: ['M12 3 2.7 20h18.6Z', 'M12 9v4', 'M12 17h.01'],
};

function Icon({ name, size = 18 }) {
  const paths = ICON_PATHS[name] || ICON_PATHS.activity;
  return h('svg', {
    className: 'ui-icon', width: size, height: size, viewBox: '0 0 24 24',
    fill: 'none', stroke: 'currentColor', strokeWidth: 1.8,
    strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true', focusable: 'false',
  }, paths.map((d, index) => h('path', { d, key: index })));
}

// 1. Sidebar Component
function Sidebar({ activeTab, onSelectTab, statusData, runtimeStatus, isOpen, onClose }) {
  const isOnline = isOllamaAvailable(statusData) || runtimeStatus?.available === true;
  const systemReady = isOnline && statusData?.agent_enabled !== false;
  const toolCount = (statusData?.mcp_servers || []).reduce((total, server) => total + (Number(server.tool_count) || 0), 0);

  const navItems = [
    { id: 'overview', label: 'Resumen', group: 'OPERAR', icon: 'overview' },
    { id: 'core', label: 'Núcleo ADA', group: 'OPERAR', icon: 'core' },
    { id: 'benchmark', label: 'Tests de Prompts', badge: '⚡ Telemetría', badgeClass: 'badge-accent', group: 'OPERAR', icon: 'bolt' },
    { id: 'metrics', label: 'Métricas', group: 'OPERAR', icon: 'activity' },
    { id: 'chat', label: 'Conversar con ADA', group: 'OPERAR', icon: 'chat' },
    { id: 'ollama', label: 'Motor local', badge: isOnline ? 'Activo' : 'Detenido', badgeClass: isOnline ? 'badge-success' : 'badge-danger', group: 'CONFIGURAR', icon: 'engine' },
    { id: 'models', label: 'Modelos y roles', group: 'CONFIGURAR', icon: 'models' },
    { id: 'mcps', label: 'Herramientas', badge: toolCount ? String(toolCount) : null, badgeClass: 'badge-accent', group: 'CONFIGURAR', icon: 'tools' },
    { id: 'triggers', label: 'Disparadores', group: 'CANALES Y DATOS', icon: 'triggers' },
    { id: 'telegram', label: 'Telegram', group: 'CANALES Y DATOS', icon: 'telegram' },
    { id: 'memory', label: 'Actividad y memoria', group: 'CANALES Y DATOS', icon: 'activity' },
    { id: 'settings', label: 'Preferencias', group: 'CANALES Y DATOS', icon: 'settings' },
  ];

  let currentGroup = '';

  return h(React.Fragment, null, [
    h('button', { className: `sidebar-scrim ${isOpen ? 'visible' : ''}`, onClick: onClose, 'aria-label': 'Cerrar navegación', key: 'scrim' }),
    h('aside', { className: `sidebar ${isOpen ? 'mobile-open' : ''}`, id: 'sidebar', 'aria-label': 'Navegación principal', key: 'sidebar' }, [
    h('div', { className: 'sidebar-header', key: 'header' }, [
      h('div', { className: 'brand' }, [
        h('div', { className: 'brand-orb' }, [
          h('span', { className: 'orb-glow' }),
          h('span', { className: 'orb-letter' }, 'A'),
        ]),
        h('div', { className: 'brand-info' }, [
          h('span', { className: 'brand-title' }, 'ADA'),
          h('span', { className: 'brand-tag' }, 'Gestor local'),
        ]),
        h('button', { className: 'icon-button sidebar-close', onClick: onClose, 'aria-label': 'Cerrar navegación' }, h(Icon, { name: 'close' })),
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
            'aria-current': activeTab === item.id ? 'page' : undefined,
          }, [
            h('span', { className: 'nav-item-icon', key: 'icon' }, h(Icon, { name: item.icon })),
            h('span', { className: 'nav-item-label', key: 'lbl' }, item.label),
            item.badge ? h('span', { className: `badge ${item.badgeClass || ''}`, key: 'badge' }, item.badge) : null,
          ])
        );
        return elements;
      })
    ),
    h('div', { className: 'sidebar-footer', key: 'footer' }, [
      h('div', { className: 'runtime-pill', id: 'runtime-status-pill' }, [
        h('span', { className: `status-dot ${systemReady ? 'online' : 'offline'}` }),
        h('span', { className: 'status-text' }, systemReady ? 'Sistema operativo' : 'Requiere atención'),
      ]),
    ]),
    ]),
  ]);
}

// 2. Header Component
function Header({ title, subtitle, onWarmup, onRefresh, onRestartAll, isRefreshing, isRestarting, identity, debugEnabled, onToggleDebug, onOpenNavigation }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return h('header', { className: 'top-header' }, [
    h('div', { className: 'header-left', key: 'left' }, [
      h('button', { className: 'icon-button mobile-menu', onClick: onOpenNavigation, 'aria-label': 'Abrir navegación' }, h(Icon, { name: 'menu' })),
      h('div', { className: 'header-copy' }, [
      h('h1', { className: 'page-title', id: 'page-title' }, title),
      h('span', { className: 'page-subtitle', id: 'page-subtitle' }, subtitle),
      ]),
    ]),
    h('div', { className: 'header-actions', key: 'actions' }, [
      h('button', { className: 'btn btn-secondary', id: 'btn-refresh', onClick: onRefresh, title: 'Actualizar datos' }, [
        h(Icon, { name: 'refresh', key: 'icon' }),
        h('span', { className: 'desktop-label', key: 'label' }, isRefreshing ? 'Actualizando…' : 'Actualizar'),
      ]),
      h('div', { className: 'action-menu' }, [
        h('button', { className: 'icon-button', onClick: () => setMenuOpen(open => !open), 'aria-label': 'Más acciones', 'aria-expanded': menuOpen }, h(Icon, { name: 'more' })),
        menuOpen ? h('div', { className: 'action-menu-popover' }, [
          h('div', { className: 'action-menu-meta' }, [
            h('strong', null, `ADA ${identity?.version ? `v${identity.version}` : ''}`),
            h('span', null, identity?.started_at ? `Activa desde ${new Date(identity.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Instancia local'),
          ]),
          h('button', { onClick: () => { setMenuOpen(false); onWarmup(); } }, [h(Icon, { name: 'bolt' }), h('span', null, 'Preparar motor')]),
          h('button', { onClick: () => { setMenuOpen(false); onToggleDebug(); } }, [h(Icon, { name: 'bug' }), h('span', null, debugEnabled ? 'Desactivar diagnóstico' : 'Activar diagnóstico')]),
          h('div', { className: 'action-menu-separator' }),
          h('button', { className: 'danger-action', onClick: () => { setMenuOpen(false); onRestartAll(); }, disabled: isRestarting }, [h(Icon, { name: 'restart' }), h('span', null, isRestarting ? 'Reiniciando…' : 'Reiniciar servicios')]),
        ]) : null,
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
      const res = await api.startOllama();
      if (res && res.ok) {
        showToast('Ollama iniciado correctamente', 'success');
      } else {
        const reason = res?.runtime?.reason || 'no_disponible';
        const msg = reason === 'ollama_not_installed'
          ? 'No se encontró el ejecutable de Ollama en el sistema'
          : reason === 'startup_timeout'
          ? 'Tiempo de espera agotado al iniciar Ollama'
          : `No se pudo iniciar Ollama (${reason})`;
        showToast(msg, 'danger');
      }
      onRefresh();
    } catch (err) {
      showToast('Error al iniciar Ollama: ' + err.message, 'danger');
    }
  };

  const handleOllamaStop = async () => {
    try {
      showToast('Deteniendo servicio Ollama...', 'info');
      const res = await api.stopOllama();
      if (res && res.ok) {
        showToast('Ollama detenido', 'info');
      } else {
        showToast('No se pudo detener el proceso de Ollama', 'warning');
      }
      onRefresh();
    } catch (err) {
      showToast('Error al detener Ollama: ' + err.message, 'danger');
    }
  };

  const handleOllamaRestart = async () => {
    try {
      showToast('Reiniciando servicio Ollama...', 'info');
      const res = await api.restartOllama();
      if (res && res.ok) {
        showToast('Ollama reiniciado exitosamente', 'success');
      } else {
        const reason = res?.runtime?.reason || 'error';
        showToast(`No se pudo reiniciar Ollama (${reason})`, 'danger');
      }
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

  const effectiveItems = checkItems.map(item => ({
    ...item,
    effectiveStatus: item.id === 'ada_agent' && statusData?.agent_enabled === false
      ? 'stopped'
      : item.id === 'mcps_subsystem' && statusData?.mcp_servers?.length && statusData.mcp_servers.every(server => server.status !== 'active')
        ? 'stopped'
        : item.status,
  }));
  const attentionItems = effectiveItems.filter(item => item.effectiveStatus !== 'ok');
  const okCount = effectiveItems.filter(item => item.effectiveStatus === 'ok').length;
  const mcpCount = statusData?.mcp_servers?.length || 0;
  const activeMcpCount = (statusData?.mcp_servers || []).filter(server => server.status === 'active').length;
  const toolCount = (statusData?.mcp_servers || []).reduce((total, server) => total + (Number(server.tool_count) || 0), 0);
  const installedCount = statusData?.runtime?.models?.installed?.length || 0;
  const roles = statusData?.model_recommendations?.roles || {};
  const resourceCheck = checkItems.find(item => item.id === 'hardware_resources');
  const ramPercent = resourceCheck?.details?.ram_percent;
  const isHealthy = overallStatus === 'healthy' && attentionItems.length === 0;

  const statusLabel = (status) => status === 'ok' ? 'Operativo' : status === 'warning' ? 'Atención' : status === 'stopped' ? 'Detenido' : 'Error';
  const statusClass = (status) => status === 'ok' ? 'badge-success' : status === 'warning' ? 'badge-warning' : 'badge-danger';

  return h('section', { className: 'tab-view active overview-v2', id: 'tab-overview' }, [
    h('section', { className: `system-summary ${isHealthy ? 'healthy' : 'attention'}`, key: 'summary', 'aria-labelledby': 'system-summary-title' }, [
      h('div', { className: 'system-summary-icon' }, h(Icon, { name: isHealthy ? 'check' : 'alert', size: 22 })),
      h('div', { className: 'system-summary-copy' }, [
        h('div', { className: 'eyebrow' }, 'ESTADO GENERAL'),
        h('h2', { id: 'system-summary-title' }, isHealthy ? 'ADA está lista para trabajar' : `${attentionItems.length || 1} ${attentionItems.length === 1 ? 'punto requiere' : 'puntos requieren'} atención`),
        h('p', null, isHealthy
          ? 'Motor, agente, memoria y herramientas responden correctamente.'
          : 'El resto del sistema sigue disponible. Revisá el pendiente antes de depender de ese canal.'),
      ]),
      h('div', { className: 'system-summary-actions' }, [
        h('span', { className: 'health-ratio' }, `${okCount} de ${effectiveItems.length || '—'} comprobaciones · ${healthScore}%`),
        hasPendingFixes ? h('button', {
          className: 'btn btn-primary',
          onClick: handleAutoHeal,
          disabled: isHealing,
        }, [
          h(Icon, { name: 'bolt', key: 'icon' }),
          h('span', { key: 'label' }, isHealing ? 'Resolviendo…' : 'Resolver pendientes'),
        ]) : h('button', { className: 'btn btn-secondary', onClick: loadHealth }, [
          h(Icon, { name: 'refresh', key: 'icon' }),
          h('span', { key: 'label' }, 'Volver a comprobar'),
        ]),
      ]),
    ]),

    attentionItems.length ? h('section', { className: 'attention-panel', key: 'attention', 'aria-labelledby': 'attention-title' }, [
      h('div', { className: 'section-heading' }, [
        h('div', null, [
          h('div', { className: 'eyebrow' }, 'PRIORIDAD'),
          h('h2', { id: 'attention-title' }, 'Requiere tu atención'),
        ]),
        h('span', { className: 'badge badge-warning' }, `${attentionItems.length} pendiente${attentionItems.length === 1 ? '' : 's'}`),
      ]),
      h('div', { className: 'attention-list' }, attentionItems.map(item => h('article', { className: 'attention-item', key: item.id }, [
        h('div', { className: `attention-marker ${item.effectiveStatus}` }, h(Icon, { name: item.effectiveStatus === 'warning' ? 'alert' : 'activity' })),
        h('div', { className: 'attention-copy' }, [
          h('div', { className: 'attention-title-row' }, [
            h('h3', null, item.name),
            h('span', { className: `badge ${statusClass(item.effectiveStatus)}` }, statusLabel(item.effectiveStatus)),
          ]),
          h('p', null, item.effectiveStatus === 'stopped'
            ? (item.id === 'ada_agent' ? 'El núcleo de ADA está detenido.' : 'Este servicio está detenido.')
            : item.message),
        ]),
        item.can_auto_fix ? h('button', {
          className: 'btn btn-secondary',
          onClick: () => handleFixItem(item.fix_action_id),
          disabled: fixingAction === item.fix_action_id,
        }, fixingAction === item.fix_action_id ? 'Iniciando…' : (item.fix_label || 'Resolver')) : null,
      ]))),
    ]) : null,

    h('section', { className: 'overview-section', key: 'services', 'aria-labelledby': 'services-title' }, [
      h('div', { className: 'section-heading' }, [
        h('div', null, [
          h('div', { className: 'eyebrow' }, 'SERVICIOS ESENCIALES'),
          h('h2', { id: 'services-title' }, 'Lo necesario para operar'),
        ]),
      ]),
      h('div', { className: 'service-grid' }, [
        h('article', { className: 'service-card', key: 'ollama' }, [
          h('div', { className: 'service-card-top' }, [
            h('span', { className: 'service-icon' }, h(Icon, { name: 'engine' })),
            h('span', { className: `badge ${isOllamaRunning ? 'badge-success' : 'badge-danger'}` }, isOllamaRunning ? 'Activo' : 'Detenido'),
          ]),
          h('h3', null, 'Motor local'),
          h('p', null, isOllamaRunning
            ? `Responde en ${statusData?.ollama_health?.latency_ms ?? '—'} ms`
            : 'La inferencia local no está disponible.'),
          h('div', { className: 'service-card-actions' }, [
            !isOllamaRunning ? h('button', { className: 'btn btn-primary', onClick: handleOllamaStart }, 'Iniciar motor') : null,
            h('button', { className: 'btn btn-ghost', onClick: () => onSwitchTab('ollama') }, 'Administrar'),
          ]),
        ]),
        h('article', { className: 'service-card', key: 'agent' }, [
          h('div', { className: 'service-card-top' }, [
            h('span', { className: 'service-icon' }, h(Icon, { name: 'chat' })),
            h('span', { className: `badge ${isAgentRunning ? 'badge-success' : 'badge-danger'}` }, isAgentRunning ? 'Listo' : 'Detenido'),
          ]),
          h('h3', null, 'Agente ADA'),
          h('p', null, isAgentRunning ? 'Conversación, router y memoria disponibles.' : 'ADA no puede procesar nuevas solicitudes.'),
          h('div', { className: 'service-card-actions' }, [
            !isAgentRunning ? h('button', { className: 'btn btn-primary', onClick: async () => { await api.startAgent(); onRefresh(); } }, 'Iniciar ADA') : null,
            h('button', { className: 'btn btn-ghost', onClick: () => onSwitchTab('chat') }, 'Abrir conversación'),
          ]),
        ]),
        h('article', { className: 'service-card', key: 'tools' }, [
          h('div', { className: 'service-card-top' }, [
            h('span', { className: 'service-icon' }, h(Icon, { name: 'tools' })),
            h('span', { className: `badge ${areMCPsRunning ? 'badge-success' : 'badge-danger'}` }, `${activeMcpCount}/${mcpCount} activos`),
          ]),
          h('h3', null, 'Herramientas'),
          h('p', null, toolCount ? `${toolCount} capacidades disponibles para ADA.` : 'No hay herramientas disponibles.'),
          h('div', { className: 'service-card-actions' }, [
            !areMCPsRunning ? h('button', { className: 'btn btn-primary', onClick: async () => { await api.startAllMCPServers(); onRefresh(); } }, 'Iniciar herramientas') : null,
            h('button', { className: 'btn btn-ghost', onClick: () => onSwitchTab('mcps') }, 'Ver herramientas'),
          ]),
        ]),
      ]),
    ]),

    h('div', { className: 'overview-split', key: 'details' }, [
      h('section', { className: 'overview-section overview-panel', 'aria-labelledby': 'resources-title' }, [
        h('div', { className: 'section-heading compact' }, [
          h('div', null, [
            h('div', { className: 'eyebrow' }, 'RECURSOS'),
            h('h2', { id: 'resources-title' }, 'Capacidad local'),
          ]),
        ]),
        h('dl', { className: 'metrics-list' }, [
          h('div', { key: 'ram' }, [
            h('dt', null, 'Memoria RAM'),
            h('dd', null, (hardware.ram_used_gb != null && hardware.ram_gb)
              ? `${hardware.ram_used_gb} / ${hardware.ram_gb} GB (${(hardware.ram_percent || ramPercent || 0).toFixed(1)}%)`
              : (ramPercent != null ? `${ramPercent.toFixed(1)}% en uso` : `${hardware.ram_gb || '—'} GB`))
          ]),
          h('div', { key: 'cpu' }, [h('dt', null, 'Procesamiento'), h('dd', null, `${hardware.cpu_cores || hardware.cpu_count || '—'} núcleos · ${hardware.gpu_backend === 'cpu' ? 'sin GPU dedicada' : hardware.gpu_backend || '—'}`)]),
          h('div', { key: 'disk' }, [h('dt', null, 'Espacio disponible'), h('dd', null, hardware.disk_free_gb != null ? `${hardware.disk_free_gb} GB` : '—')]),
          h('div', { key: 'models' }, [h('dt', null, 'Modelos instalados'), h('dd', null, String(installedCount))]),
        ]),
      ]),
      h('section', { className: 'overview-section overview-panel', 'aria-labelledby': 'roles-title' }, [
        h('div', { className: 'section-heading compact' }, [
          h('div', null, [
            h('div', { className: 'eyebrow' }, 'ASIGNACIÓN ACTUAL'),
            h('h2', { id: 'roles-title' }, 'Modelos por tarea'),
          ]),
          h('button', { className: 'btn btn-ghost btn-sm', onClick: () => onSwitchTab('models') }, 'Editar'),
        ]),
        h('dl', { className: 'role-list' }, [
          h('div', { key: 'chat' }, [h('dt', null, 'Conversación'), h('dd', null, roles.chat || 'Sin asignar')]),
          h('div', { key: 'vision' }, [h('dt', null, 'Visión'), h('dd', null, roles.vision || 'Sin asignar')]),
          h('div', { key: 'router' }, [h('dt', null, 'Router'), h('dd', null, roles.router || 'Sin asignar')]),
        ]),
      ]),
    ]),
  ]);
}

function MetricLineChart({ series = [], colors = ['#5ce1e6', '#a78bfa', '#fbbf24'], unit = '', empty = 'Sin muestras en esta ventana' }) {
  const width = 720, height = 190, pad = { top: 12, right: 12, bottom: 24, left: 12 };
  const values = series.flatMap(item => item.values || []).map(Number).filter(Number.isFinite);
  if (!values.length) return h('div', { className: 'metrics-chart-empty' }, empty);
  const min = Math.min(...values), max = Math.max(...values), range = Math.max(0.0001, max - min);
  const longest = Math.max(...series.map(item => item.values.length), 1);
  const points = (item) => item.values.map((value, index) => {
    const x = pad.left + (index / Math.max(1, longest - 1)) * (width - pad.left - pad.right);
    const y = pad.top + (1 - (Number(value) - min) / range) * (height - pad.top - pad.bottom);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return h('div', { className: 'metrics-chart-wrap' }, [
    h('svg', { className: 'metrics-line-chart', viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': 'Serie temporal de métricas' }, [
      [0, .5, 1].map((fraction, index) => h('line', { key: `grid-${index}`, x1: pad.left, x2: width - pad.right, y1: pad.top + fraction * (height - pad.top - pad.bottom), y2: pad.top + fraction * (height - pad.top - pad.bottom), className: 'metrics-grid-line' })),
      series.map((item, index) => h('polyline', { key: item.label || index, points: points(item), fill: 'none', stroke: colors[index % colors.length], strokeWidth: 2.5, strokeLinecap: 'round', strokeLinejoin: 'round' })),
    ]),
    h('div', { className: 'metrics-chart-scale' }, [h('span', null, `${max.toFixed(max < 10 ? 1 : 0)}${unit}`), h('span', null, `${min.toFixed(min < 10 ? 1 : 0)}${unit}`)]),
    h('div', { className: 'metrics-legend' }, series.map((item, index) => h('span', { key: item.label || index }, [h('i', { style: { background: colors[index % colors.length] } }), item.label]))),
  ]);
}

function MetricBarList({ items = [], empty = 'Sin actividad registrada' }) {
  const max = Math.max(...items.map(item => item.value), 1);
  if (!items.length) return h('div', { className: 'metrics-chart-empty' }, empty);
  return h('div', { className: 'metrics-bar-list' }, items.slice(0, 8).map(item => h('div', { className: 'metrics-bar-row', key: item.label }, [
    h('div', { className: 'metrics-bar-meta' }, [h('span', null, item.label), h('strong', null, item.value.toLocaleString('es-AR'))]),
    h('div', { className: 'metrics-bar-track' }, h('i', { style: { width: `${Math.max(4, item.value / max * 100)}%` } })),
  ])));
}

function MetricsView() {
  const [data, setData] = useState({ samples: [] });
  useEffect(() => { let live = true; const load = () => api.getTimeSeries().then(v => live && setData(v)).catch(() => {}); load(); const id = setInterval(load, 10000); return () => { live = false; clearInterval(id); }; }, []);
  const samples = data.samples || [];
  const counterBases = new Set(['messages_received', 'chat_invocations', 'router_invocations', 'model_invocations', 'capability_invocations', 'tool_invocations', 'chat_errors', 'chat_successes', 'initializer_invocations']);
  const parseSample = (sample) => {
    let metric = String(sample.metric || ''), kind = 'gauge';
    if (metric.endsWith('_avg_seconds')) { kind = 'timing'; metric = metric.slice(0, -12); }
    else if (metric.endsWith('_count')) { kind = 'count'; metric = metric.slice(0, -6); }
    const pieces = metric.split('.');
    const base = pieces.shift();
    const tags = {};
    pieces.join('.').split('.').forEach(part => { const index = part.indexOf('='); if (index > 0) tags[part.slice(0, index)] = part.slice(index + 1); });
    return { ...sample, base, kind, tags };
  };
  const parsed = samples.map(parseSample);
  const seriesFor = (base, filter = {}) => {
    const groups = new Map();
    parsed.filter(item => item.base === base && Object.entries(filter).every(([key, value]) => item.tags[key] === value)).forEach(item => {
      const key = Object.entries(item.tags).filter(([name]) => name !== 'status').map(([name, value]) => `${name}=${value}`).join(' · ') || 'total';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    });
    return [...groups.entries()].map(([label, values]) => ({ label, values: values.sort((a, b) => a.ts - b.ts) }));
  };
  const latest = (base, filter = {}) => seriesFor(base, filter).flatMap(item => item.values).sort((a, b) => a.ts - b.ts).at(-1)?.value;
  const delta = (base, filter = {}) => seriesFor(base, filter).reduce((total, item) => item.values.length > 1 ? total + Math.max(0, Number(item.values.at(-1).value) - Number(item.values[0].value)) : total, 0);
  const counterItems = (base, tag) => seriesFor(base).map(item => ({ label: item.label === 'total' ? 'General' : (item.label.split('=')[1] || item.label), value: item.values.length > 1 ? Math.max(0, Number(item.values.at(-1).value) - Number(item.values[0].value)) : 0 })).filter(item => item.value > 0).sort((a, b) => b.value - a.value);
  const timingStats = (base) => {
    const values = seriesFor(base).flatMap(item => item.values).map(item => Number(item.value) * 1000).filter(Number.isFinite).sort((a, b) => a - b);
    if (!values.length) return { avg: null, p95: null };
    return { avg: values.reduce((sum, value) => sum + value, 0) / values.length, p95: values[Math.min(values.length - 1, Math.floor(values.length * .95))] };
  };
  const formatCount = value => Number(value || 0).toLocaleString('es-AR', { maximumFractionDigits: 0 });
  const formatMs = value => value == null ? '—' : `${Math.round(value).toLocaleString('es-AR')} ms`;
  const lastSample = data.last_sample_at ? new Date(data.last_sample_at * 1000).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
  const systemOk = data.scraper?.ok && latest('ada_up') === 1;
  const cpuSeries = ['ada', 'ollama', 'telegram'].map(service => ({ label: service.toUpperCase(), values: seriesFor(`${service}_process_cpu_percent`).flatMap(item => item.values).slice(-60).map(item => Number(item.value)) })).filter(item => item.values.length);
  const ramSeries = ['ada', 'ollama', 'telegram'].map(service => ({ label: service.toUpperCase(), values: seriesFor(`${service}_process_rss_mb`).flatMap(item => item.values).slice(-60).map(item => Number(item.value)) })).filter(item => item.values.length);
  const events = ['messages_received', 'chat_invocations', 'router_invocations', 'model_invocations', 'capability_invocations', 'tool_invocations'].reduce((sum, name) => sum + delta(name), 0);
  const errors = delta('chat_errors') + delta('provider.errors') + delta('capability.errors');
  const chatLatency = timingStats('chat_response_seconds');
  const toolLatency = timingStats('tool_response_seconds');
  const modelLatency = timingStats('provider.duration');
  const section = (eyebrow, title, copy, content, className = '') => h('section', { className: `metrics-section ${className}` }, [h('div', { className: 'metrics-section-heading' }, [h('div', null, [h('span', { className: 'eyebrow' }, eyebrow), h('h2', null, title), h('p', null, copy)])]), content]);
  const kpiCards = [
    ['Estado', systemOk ? 'Operativo' : 'Revisar', systemOk ? 'Scraper y ADA responden' : (data.scraper?.message || 'No hay datos recientes'), 'primary'],
    ['Eventos / ventana', formatCount(events), 'Mensajes, modelos, router y herramientas', ''],
    ['Latencia p95', formatMs(chatLatency.p95), 'Respuesta completa de chat', chatLatency.p95 > 30000 ? 'danger' : ''],
    ['Errores observados', formatCount(errors), errors ? 'Revisar señales de fallo' : 'Sin errores de chat', errors ? 'warning' : ''],
  ].map(([label, value, copy, tone]) => h('article', { className: `metric-kpi metric-kpi-${tone}`, key: label }, [h('span', null, label), h('strong', null, value), h('small', null, copy)]));
  return h('section', { className: 'tab-view active metrics-view metrics-dashboard' }, [
    h('div', { className: 'metrics-hero' }, [h('div', null, [h('span', { className: 'eyebrow' }, 'OBSERVABILIDAD / LIVE'), h('h1', null, 'ADA Telemetry'), h('p', null, 'Un mapa operativo para detectar saturación, latencia y componentes que necesitan atención.')]), h('div', { className: 'metrics-freshness' }, [h('span', { className: `status-dot ${systemOk ? 'online' : 'offline'}` }), h('div', null, [h('strong', null, systemOk ? 'Sistema saludable' : 'Telemetría degradada'), h('span', null, `Última muestra ${lastSample}`)])])]),
    h('div', { className: 'metrics-kpis metrics-kpis-wide' }, kpiCards),
    section('RECURSOS', 'CPU y memoria por proceso', 'La línea permite ver picos, fugas y el costo relativo de cada servicio.', h('div', { className: 'metrics-chart-grid' }, [h('article', { className: 'metrics-panel chart-panel' }, [h('div', { className: 'metrics-panel-title' }, [h('h3', null, 'CPU de procesos'), h('small', null, 'últimas 60 muestras')]), h(MetricLineChart, { series: cpuSeries, unit: '%' })]), h('article', { className: 'metrics-panel chart-panel' }, [h('div', { className: 'metrics-panel-title' }, [h('h3', null, 'Memoria residente'), h('small', null, 'RSS · MB')]), h(MetricLineChart, { series: ramSeries, unit: ' MB' })])])),
    section('RENDIMIENTO', 'Tiempos de invocación', 'Promedio y p95 observado; un salto sostenido suele indicar saturación, modelo frío o MCP lento.', h('div', { className: 'metrics-latency-grid' }, [['chat_response_seconds', 'Chat completo', chatLatency], ['provider.duration', 'Modelo / Ollama', modelLatency], ['tool_response_seconds', 'MCP / herramienta', toolLatency], ['router_response_seconds', 'Router', timingStats('router_response_seconds')]].map(([name, label, stats]) => h('article', { className: 'metrics-panel latency-card', key: name }, [h('span', { className: 'metric-card-label' }, label), h('strong', null, formatMs(stats.p95)), h('div', { className: 'latency-detail' }, [h('span', null, `promedio ${formatMs(stats.avg)}`), h('span', null, `${seriesFor(name).reduce((sum, item) => sum + item.values.length, 0)} muestras`)]), h('div', { className: `latency-signal ${stats.p95 > 30000 ? 'bad' : stats.p95 > 5000 ? 'warn' : ''}` }, stats.p95 == null ? 'Esperando datos' : stats.p95 > 30000 ? 'Lento · investigar' : stats.p95 > 5000 ? 'Vigilar tendencia' : 'Dentro de objetivo')]))),
    section('DISTRIBUCIÓN', '¿Dónde se está usando ADA?', 'Ranking por dimensión para saber qué modelo, MCP o inicializador concentra el trabajo.', h('div', { className: 'metrics-distribution-grid' }, [['model_invocations', 'Por modelo', 'model'], ['capability_invocations', 'Por capacidad / MCP', 'capability'], ['tool_invocations', 'Por herramienta', 'tool'], ['initializer_invocations', 'Por inicializador', 'initializer']].map(([name, title, tag]) => h('article', { className: 'metrics-panel distribution-card', key: name }, [h('div', { className: 'metrics-panel-title' }, [h('h3', null, title), h('small', null, `${formatCount(delta(name))} invocaciones`)]), h(MetricBarList, { items: counterItems(name, tag), empty: name === 'initializer_invocations' ? 'Aún no hay eventos de inicialización' : 'Sin actividad en la ventana' })])))),
    section('SEÑALES', 'Puntos de mejora', 'Lecturas rápidas para priorizar una investigación antes de que el problema se convierta en una caída.', h('div', { className: 'metrics-insights-grid' }, [
      h('article', { className: 'metrics-panel insight-card' }, [h('span', { className: 'insight-icon' }, '↗'), h('div', null, [h('strong', null, chatLatency.p95 > 30000 ? 'La conversación está lenta' : 'Latencia de conversación estable'), h('p', null, chatLatency.p95 > 30000 ? 'Revisá el modelo activo, la memoria disponible y el tiempo de respuesta de Ollama.' : 'Seguí esta serie durante una carga real para encontrar regresiones.')])]),
      h('article', { className: 'metrics-panel insight-card' }, [h('span', { className: 'insight-icon' }, errors ? '!' : '✓'), h('div', null, [h('strong', null, errors ? 'Hay errores que requieren triage' : 'Sin errores de chat registrados'), h('p', null, errors ? 'Usá la actividad y el log de depuración para correlacionar el fallo con modelo o MCP.' : 'La ausencia de errores es una buena señal, pero no reemplaza revisar la latencia.')])]),
      h('article', { className: 'metrics-panel insight-card' }, [h('span', { className: 'insight-icon' }, '◌'), h('div', null, [h('strong', null, data.stale ? 'La fuente de métricas está atrasada' : 'Telemetría llegando en tiempo'), h('p', null, data.stale ? (data.scraper?.message || 'Revisá el proceso metrics_scraper.') : 'Las muestras se actualizan automáticamente cada 10 segundos en esta vista.')])]),
    ])),
  ]);
}

function CoreView({ onSwitchTab }) {
  const [coreData, setCoreData] = useState(null);
  const [metricsData, setMetricsData] = useState({ samples: [] });
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const data = await api.getCoreState();
        if (mounted) {
          setCoreData(data);
          setLoadError('');
        }
      } catch (error) {
        if (mounted) setLoadError(error.message || 'No pude leer el estado del núcleo');
      }
    };
    load();
    const interval = setInterval(load, 1000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    const loadMetrics = () => api.getTimeSeries().then(data => {
      if (mounted) setMetricsData(data || { samples: [] });
    }).catch(() => {});
    loadMetrics();
    const interval = setInterval(loadMetrics, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const [activeTraceTab, setActiveTraceTab] = useState('current');
  const [selectedHistoryTask, setSelectedHistoryTask] = useState(null);

  const activity = coreData?.activity || {
    status: 'idle', phase: 'idle', label: 'Conectando con ADA', detail: 'Leyendo el estado del sistema', recent: [],
  };
  const activeModels = coreData?.models?.active || {};
  const modelGroups = Object.entries(activeModels).reduce((groups, [role, model]) => {
    if (!model) return groups;
    const existing = groups.find(item => item.name === model);
    if (existing) existing.roles.push(role);
    else groups.push({ name: model, roles: [role] });
    return groups;
  }, []);
  const telegram = coreData?.connectors?.telegram || {};
  const connectors = [
    {
      id: 'telegram', name: 'Telegram', kind: 'Canal', online: telegram.status === 'running',
      meta: telegram.status === 'degraded' ? 'Conflicto de listener' : telegram.running ? 'Escuchando mensajes' : (telegram.configured ? 'Detenido' : 'Sin configurar'), tab: 'telegram',
    },
    ...(coreData?.connectors?.mcps || []).map(server => ({
      id: server.name,
      name: server.name,
      kind: 'MCP',
      online: server.status === 'active',
      meta: `${server.tool_count || 0} herramientas`,
      tab: 'mcps',
    })),
    ...(coreData?.connectors?.triggers || []).filter(trigger => trigger.id !== 'telegram').map(trigger => ({
      id: `trigger:${trigger.id}`,
      sourceId: trigger.id,
      name: trigger.name,
      kind: 'Entrada',
      online: trigger.running === true,
      meta: trigger.status === 'ready' ? 'Preparado' : trigger.summary,
      tab: 'triggers',
    })),
  ];
  const working = activity.status === 'working';
  const elapsed = activity.started_at && working
    ? Math.max(0, Math.round((Number(coreData?.server_time || Date.now() / 1000) - Number(activity.started_at))))
    : 0;
  const activeConnector = (node) => working && (
    activity.component === node.id
    || activity.component === node.sourceId
    || (activity.component === 'filesystem' && node.id === 'filesystem')
    || (activity.component === 'sqlite' && node.id === 'sqlite-memory')
    || (activity.channel === 'telegram' && node.id === 'telegram')
  );
  const roleLabels = {
    chat: 'Chat', router: 'Router', reasoning: 'Razonamiento', coding: 'Código', tools: 'Herramientas', vision: 'Visión',
  };
  const statusText = activity.status === 'working' ? 'Trabajando' : activity.status === 'error' ? 'Requiere atención' : activity.status === 'complete' ? 'Completado' : 'En espera';
  const samples = metricsData.samples || [];
  const counterNames = new Set(['messages_received', 'chat_invocations', 'router_invocations', 'model_invocations', 'capability_invocations']);
  const byMetric = samples.reduce((groups, sample) => {
    (groups[sample.metric] ||= []).push(sample);
    return groups;
  }, {});
  const samplesForMetric = (name) => Object.entries(byMetric).flatMap(([metric, values]) => (
    metric === name || (counterNames.has(name) && metric.startsWith(`${name}_`)) ? values : []
  ));
  const metricSeries = (name) => {
    const groups = new Map();
    samplesForMetric(name).forEach(sample => {
      const key = `${sample.metric}:${sample.tags || 'default'}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(sample);
    });
    return [...groups.values()].map(series => series.sort((a, b) => a.ts - b.ts));
  };
  const latestMetric = (name) => {
    const values = samplesForMetric(name).slice().sort((a, b) => a.ts - b.ts);
    return values.at(-1)?.value;
  };
  const metricDelta = (name) => metricSeries(name).reduce((total, series) => {
    if (series.length < 2) return total;
    const first = Number(series[0].value) || 0;
    const last = Number(series.at(-1).value) || 0;
    return total + Math.max(0, last - first);
  }, 0);
  const windowActivity = [...counterNames].reduce((total, name) => total + metricDelta(name), 0);
  const sparkValues = (name) => {
    if (!counterNames.has(name)) return samplesForMetric(name).slice(-28).map(sample => Number(sample.value) || 0);
    return metricSeries(name).flatMap(series => series.slice(1).map((sample, index) => Math.max(0, Number(sample.value) - Number(series[index].value)))).slice(-28);
  };
  const formatMetric = (name, suffix = '') => {
    const value = latestMetric(name);
    return value == null ? '—' : `${Number(value).toFixed(name.includes('percent') ? 1 : 0)}${suffix}`;
  };
  const activeConnections = connectors.filter(connector => connector.online).length;
  const flowPoint = (index, total) => {
    const leftCount = Math.ceil(total / 2);
    const isLeft = index < leftCount;
    const localIndex = isLeft ? index : index - leftCount;
    const localTotal = isLeft ? leftCount : Math.max(1, total - leftCount);
    const y = 12 + (localIndex / Math.max(1, localTotal - 1)) * 76;
    return { x: isLeft ? 12 : 88, y };
  };
  const modelPoint = (index, total) => {
    if (total === 1) return { x: 50, y: 50 };
    const spread = Math.min(23, 13 + total * 2);
    return { x: index % 2 === 0 ? 50 - spread : 50 + spread, y: index < 2 ? 43 : 60 };
  };
  const renderSpark = (name, tone = 'cyan') => {
    const values = sparkValues(name);
    const peak = Math.max(...values, 1);
    return h('div', { className: `core-spark core-spark-${tone}`, 'aria-hidden': 'true' }, values.length
      ? values.map((value, index) => h('i', { key: `${name}-${index}`, style: { height: `${Math.max(9, Math.round((value / peak) * 100))}%` } }))
      : [h('i', { key: 'empty', style: { height: '12%' } })]);
  };
  const center = 400;
  const connectorRadius = 302;
  const modelRadius = 150;

  return h('section', { className: `tab-view active core-view core-status-${activity.status}`, id: 'tab-core' }, [
    h('div', { className: 'core-toolbar', key: 'toolbar' }, [
      h('div', { className: 'core-live-state', role: 'status', 'aria-live': 'polite' }, [
        h('span', { className: 'core-live-dot', 'aria-hidden': 'true' }),
        h('div', null, [
          h('strong', null, statusText),
          h('span', null, working && elapsed ? `${activity.label} · ${elapsed}s` : activity.label),
        ]),
      ]),
      h('div', { className: 'core-mode-copy' }, [
        h('span', null, 'Política de modelos'),
        h('strong', null, ({ hybrid: 'Híbrido', turbo: 'Turbo', light: 'Liviano', manual: 'Manual' })[coreData?.models?.mode] || '—'),
      ]),
    ]),
    loadError ? h('div', { className: 'core-load-error', role: 'alert' }, loadError) : null,
    h('div', { className: 'core-kpi-strip', key: 'kpis' }, [
      h('article', { className: 'core-kpi core-kpi-primary' }, [
        h('span', { className: 'core-kpi-label' }, 'NÚCLEO ADA'),
        h('strong', null, statusText),
        h('small', null, activity.label),
      ]),
      h('article', { className: 'core-kpi' }, [
        h('span', { className: 'core-kpi-label' }, 'CPU DEL PROCESO'),
        h('strong', null, formatMetric('ada_process_cpu_percent', '%')),
        renderSpark('ada_process_cpu_percent', 'violet'),
      ]),
      h('article', { className: 'core-kpi' }, [
        h('span', { className: 'core-kpi-label' }, 'MEMORIA ADA'),
        h('strong', null, formatMetric('ada_process_rss_mb', ' MB')),
        renderSpark('ada_process_rss_mb', 'cyan'),
      ]),
      h('article', { className: 'core-kpi' }, [
        h('span', { className: 'core-kpi-label' }, 'CONEXIONES'),
        h('strong', null, `${activeConnections}/${connectors.length}`),
        h('small', null, 'canales y herramientas activas'),
      ]),
    ]),
    h('div', { className: 'core-layout', key: 'core-layout' }, [
      h('aside', { className: 'core-stat-rail', 'aria-label': 'Resumen de métricas del núcleo' }, [
        h('div', { className: 'core-rail-brand' }, [h('span', null, 'A'), h('strong', null, 'NÚCLEO')]),
        h('div', { className: 'core-rail-section' }, [
          h('span', { className: 'core-rail-label' }, 'ESTADO'),
          h('strong', { className: 'core-rail-value core-rail-value-ring' }, '98%'),
          h('span', { className: 'core-rail-meta' }, 'Operativo'),
        ]),
        h('div', { className: 'core-rail-section' }, [
          h('span', { className: 'core-rail-label' }, 'MEMORIA'),
          h('strong', { className: 'core-rail-value' }, formatMetric('ada_process_rss_mb', ' MB')),
          h('span', { className: 'core-rail-meta' }, 'Proceso ADA'),
          renderSpark('ada_process_rss_mb', 'cyan'),
        ]),
        h('div', { className: 'core-rail-section' }, [
          h('span', { className: 'core-rail-label' }, 'MODELOS'),
          h('strong', { className: 'core-rail-value' }, String(modelGroups.length)),
          h('span', { className: 'core-rail-meta' }, 'activos ahora'),
        ]),
        h('div', { className: 'core-rail-footer' }, [
          h('span', { className: 'core-node-signal' }),
          h('span', null, `${activeConnections} conexiones activas`),
        ]),
      ]),
      h('div', {
        className: 'core-network',
        role: 'region',
        'aria-label': `${statusText}. ${activity.label}. ${modelGroups.length} modelos y ${connectors.length} conectores visibles.`,
        key: 'network',
      }, [
        h('svg', { className: 'core-link-layer', viewBox: '0 0 800 800', 'aria-hidden': 'true' }, [
          h('circle', { cx: center, cy: center, r: connectorRadius, className: 'core-orbit orbit-outer', key: 'outer' }),
          h('circle', { cx: center, cy: center, r: modelRadius, className: 'core-orbit orbit-inner', key: 'inner' }),
          ...Array.from({ length: 18 }, (_, index) => {
            const side = index % 2 === 0 ? -1 : 1;
            const band = Math.floor(index / 2);
            const endX = center + side * (145 + band * 24);
            const endY = 255 + (band % 9) * 34;
            const controlX = center + side * (48 + band * 9);
            const controlY = center + (band - 4) * 21;
            return h('path', {
              key: `strand-${index}`,
              d: `M ${center} ${center} C ${controlX} ${controlY - 55} ${controlX} ${controlY + 35} ${endX} ${endY}`,
              className: 'core-neural-strand',
            });
          }),
          ...connectors.map((node, index) => {
            const point = flowPoint(index, connectors.length);
            const outerX = point.x * 8;
            const outerY = point.y * 8;
            const direction = point.x < 50 ? -1 : 1;
            const controlX = center + direction * 90;
            const controlY = outerY + (center - outerY) * .35;
            return h('path', {
              key: `line-${node.id}`,
              d: `M ${center} ${center} C ${center + direction * 72} ${center - 50} ${controlX} ${controlY} ${outerX} ${outerY}`,
              className: `core-link ${node.online ? 'online' : 'offline'} ${activeConnector(node) ? 'active' : ''}`,
            });
          }),
        ]),
        h('div', { className: 'core-sphere-wrap' }, [
          h('div', { className: 'core-sphere-halo halo-one' }),
          h('div', { className: 'core-sphere-halo halo-two' }),
          h('div', { className: 'core-sphere' }, [
            h('div', { className: 'core-sphere-grid' }),
            h('span', { className: 'core-sphere-kicker' }, 'NÚCLEO LOCAL'),
            h('strong', { className: 'core-sphere-name' }, 'ADA'),
            h('span', { className: 'core-sphere-state' }, activity.label),
            activity.model ? h('span', { className: 'core-sphere-model' }, activity.model) : null,
          ]),
        ]),
        h('div', { className: 'core-model-orbit', 'aria-label': 'Modelos activos' },
          modelGroups.map((model, index) => {
            const point = modelPoint(index, modelGroups.length);
            const x = point.x;
            const y = point.y;
            const isActive = working && (
              (activity.component === 'model' && (
                activity.model === model.name || model.roles.includes(activity.role)
              ))
              || (activity.component === 'router' && model.roles.includes('router'))
            );
            return h('button', {
              key: model.name,
              type: 'button',
              className: `core-model-node ${isActive ? 'active' : ''}`,
              style: { left: `${x}%`, top: `${y}%` },
              onClick: () => onSwitchTab('models'),
              'aria-label': `${model.name}: ${model.roles.map(role => roleLabels[role] || role).join(', ')}`,
            }, [
              h('span', { className: 'core-node-signal' }),
              h('strong', null, model.name),
              h('span', null, model.roles.map(role => roleLabels[role] || role).join(' · ')),
            ]);
          })
        ),
        h('div', { className: 'core-connectors', 'aria-label': 'Conectores y MCP' },
          connectors.map((node, index) => {
            const point = flowPoint(index, connectors.length);
            const x = point.x;
            const y = point.y;
            return h('button', {
              key: node.id,
              type: 'button',
              className: `core-connector ${node.online ? 'online' : 'offline'} ${activeConnector(node) ? 'active' : ''}`,
              style: { left: `${x}%`, top: `${y}%` },
              onClick: () => onSwitchTab(node.tab),
              'aria-label': `${node.name}, ${node.kind}, ${node.online ? 'activo' : 'inactivo'}, ${node.meta}`,
            }, [
              h('span', { className: 'core-node-signal' }),
              h('strong', null, node.name),
              h('span', null, node.kind === 'MCP' ? node.meta : node.kind),
            ]);
          })
        ),
      ]),
      h('div', { className: 'core-activity-panel', key: 'activity' }, [
        h('div', { className: 'core-activity-header' }, [
          h('span', { className: 'core-activity-icon', 'aria-hidden': 'true' }, h(Icon, { name: working ? 'bolt' : activity.status === 'error' ? 'alert' : 'check' })),
          h('div', { className: 'core-activity-title' }, [
            h('span', { className: 'core-activity-eyebrow' }, activity.phase === 'idle' ? 'ESTADO ACTUAL' : activity.phase.replaceAll('_', ' ').toUpperCase()),
            h('strong', null, activity.label),
          ]),
        ]),
        h('div', { className: 'core-activity-body' }, [
          h('p', { className: 'core-activity-desc' }, activity.detail || 'Núcleo en espera de nuevas instrucciones o disparadores.'),
        ]),
        activity.prompt ? h('div', { className: 'core-current-request' }, [
          h('span', null, 'Pedido actual'),
          h('p', null, activity.prompt),
        ]) : null,
        h('div', { className: 'core-panel-meta' }, [
          h('div', { className: 'core-meta-item' }, [
            h('span', { className: 'core-meta-label' }, 'Modo de trabajo'),
            h('strong', { className: 'core-meta-val' }, ({ hybrid: 'Híbrido', turbo: 'Turbo', light: 'Liviano', manual: 'Manual' })[coreData?.models?.mode] || '—'),
          ]),
          h('div', { className: 'core-meta-item' }, [
            h('span', { className: 'core-meta-label' }, 'Conexiones activas'),
            h('strong', { className: 'core-meta-val text-accent' }, `${connectors.filter(c => c.online).length} de ${connectors.length}`),
          ]),
        ]),
        // Trace / Historial View Tabs & Content
        h('div', { className: 'core-trace-container' }, [
          h('div', { className: 'core-trace-nav' }, [
            h('span', { className: 'core-activity-eyebrow' }, activeTraceTab === 'current' ? 'TRAZA EN TIEMPO REAL' : 'HISTORIAL DE TAREAS'),
            h('div', { className: 'core-trace-tabs' }, [
              h('button', {
                type: 'button',
                className: `core-trace-tab ${activeTraceTab === 'current' ? 'active' : ''}`,
                onClick: () => { setActiveTraceTab('current'); setSelectedHistoryTask(null); },
              }, 'Paso a Paso'),
              h('button', {
                type: 'button',
                className: `core-trace-tab ${activeTraceTab === 'history' ? 'active' : ''}`,
                onClick: () => setActiveTraceTab('history'),
              }, `Historial (${(activity.history || []).length})`),
            ]),
          ]),

          // Tab 1: Current Live / Selected Task Trace Steps
          activeTraceTab === 'current' ? h('div', { className: 'core-trace-timeline' },
            (() => {
              const activeSteps = selectedHistoryTask ? selectedHistoryTask.trace : (activity.trace || []);
              if (!activeSteps.length) {
                return [h('span', { key: 'empty', className: 'text-xs text-muted py-2' }, 'Sin trazas de ejecución en este momento.')];
              }
              return activeSteps.map((step, idx) => {
                const isModel = step.phase.includes('model');
                const isRouter = step.phase.includes('router') || step.phase.includes('route_');
                const isTool = step.phase.includes('capability') || step.phase.includes('folder_');
                const tagClass = isModel ? 'tag-model' : isRouter ? 'tag-router' : isTool ? 'tag-tool' : '';
                const tagLabel = isModel ? (step.model || 'Modelo') : isRouter ? 'Decisión Router' : isTool ? 'Herramienta' : (step.component || 'Agente');

                return h('div', { key: `${step.at}-${idx}`, className: `core-trace-step step-${step.status}` }, [
                  h('div', { className: 'core-trace-step-dot' }),
                  h('div', { className: 'core-trace-step-header' }, [
                    h('span', { className: 'core-trace-step-title' }, step.label),
                    h('span', { className: `core-trace-step-tag ${tagClass}` }, tagLabel),
                  ]),
                  step.detail ? h('div', { className: 'core-trace-step-detail' }, step.detail) : null,
                ]);
              });
            })()
          ) : null,

          // Tab 2: Completed Tasks History
          activeTraceTab === 'history' ? h('div', { className: 'core-history-list' },
            (() => {
              const history = activity.history || [];
              if (!history.length) {
                return [h('span', { key: 'empty', className: 'text-xs text-muted py-2' }, 'No hay tareas registradas en el historial reciente.')];
              }
              return history.map(item => {
                const isSelected = selectedHistoryTask?.id === item.id;
                return h('div', {
                  key: item.id,
                  className: `core-history-item ${isSelected ? 'selected' : ''}`,
                  onClick: () => {
                    setSelectedHistoryTask(item);
                    setActiveTraceTab('current');
                  },
                }, [
                  h('div', { className: 'core-history-item-top' }, [
                    h('span', { className: 'core-history-prompt' }, item.prompt),
                    h('span', { className: `badge ${item.status === 'complete' ? 'badge-success' : 'badge-danger'} text-2xs` }, item.status === 'complete' ? 'Completado' : 'Error'),
                  ]),
                  h('div', { className: 'core-history-meta' }, [
                    h('span', null, `⏱ ${item.duration_seconds}s`),
                    item.model ? h('span', { className: 'font-mono text-accent' }, item.model) : null,
                    item.decision?.action ? h('span', { className: 'text-primary' }, `→ ${item.decision.action}`) : null,
                    h('span', null, `${(item.trace || []).length} pasos`),
                  ]),
                ]);
              });
            })()
          ) : null,
        ]),
      ]),
    ]),
    h('div', { className: 'core-telemetry-grid', key: 'telemetry' }, [
      h('section', { className: 'core-telemetry-card core-telemetry-wide' }, [
        h('div', { className: 'core-telemetry-heading' }, [
          h('div', null, [
            h('span', { className: 'core-activity-eyebrow' }, 'OBSERVABILIDAD EN TIEMPO REAL'),
            h('h3', null, 'Pulso operativo'),
          ]),
          h('span', { className: 'core-live-badge' }, [h('span', { className: 'core-live-dot' }), 'LIVE']),
        ]),
        h('div', { className: 'core-telemetry-charts' }, [
          h('div', { className: 'core-chart-block' }, [
            h('div', { className: 'core-chart-label' }, [h('span', null, 'ADA / CPU'), h('strong', null, formatMetric('ada_process_cpu_percent', '%'))]),
            renderSpark('ada_process_cpu_percent', 'cyan'),
          ]),
          h('div', { className: 'core-chart-block' }, [
            h('div', { className: 'core-chart-label' }, [h('span', null, 'OLLAMA / MEMORIA'), h('strong', null, formatMetric('ollama_process_rss_mb', ' MB'))]),
            renderSpark('ollama_process_rss_mb', 'violet'),
          ]),
          h('div', { className: 'core-chart-block' }, [
            h('div', { className: 'core-chart-label' }, [h('span', null, 'EVENTOS EN LA VENTANA'), h('strong', null, String(windowActivity))]),
            renderSpark('messages_received', 'green'),
          ]),
        ]),
      ]),
      h('section', { className: 'core-telemetry-card core-signal-card' }, [
        h('div', { className: 'core-telemetry-heading' }, [
          h('div', null, [h('span', { className: 'core-activity-eyebrow' }, 'SEÑALES DEL SISTEMA'), h('h3', null, 'Estado de la red')]),
        ]),
        h('div', { className: 'core-signal-grid' }, [
          h('div', null, [h('strong', null, String(modelGroups.length)), h('span', null, 'modelos activos')]),
          h('div', null, [h('strong', null, String(connectors.filter(connector => connector.kind === 'MCP' && connector.online).length)), h('span', null, 'MCP conectados')]),
          h('div', null, [h('strong', null, String(connectors.filter(connector => connector.kind === 'Entrada' && connector.online).length)), h('span', null, 'entradas listas')]),
          h('div', null, [h('strong', null, String(metricDelta('messages_received'))), h('span', null, 'mensajes en la ventana')]),
        ]),
      ]),
    ]),
  ]);
}

const TIMEOUT_PRESETS = {
  fast: {
    label: 'Rápido', description: 'Para pedidos simples', taskLabel: '2 min por tarea',
    router_timeout: 10, model_timeout: 60, chat_timeout_seconds: 120, food_advisor_timeout: 60,
  },
  balanced: {
    label: 'Equilibrado', description: 'Uso cotidiano', taskLabel: '5 min por tarea',
    router_timeout: 20, model_timeout: 180, chat_timeout_seconds: 300, food_advisor_timeout: 120,
  },
  patient: {
    label: 'Agente paciente', description: 'Prioriza completar bien', taskLabel: '15 min por tarea',
    router_timeout: 30, model_timeout: 300, chat_timeout_seconds: 900, food_advisor_timeout: 180,
  },
};

// 4. Ollama Tab View (Advanced Resource Controls, Diagnostics, Real-Time Download % & Model Management)
function OllamaView({ modelsData, statusData, onRefresh, showToast, onBenchmark }) {
  const [pullInput, setPullInput] = useState('');
  const [pulling, setPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState({ percent: 0, status: '', text: '', completed_fmt: '', total_fmt: '' });

  // Ollama Advanced Config State
  const [ollamaConfig, setOllamaConfig] = useState({
    cpu_limit_percent: 50,
    ollama_num_thread: 4,
    ollama_num_ctx: 4096,
    ollama_keep_alive: '5m',
    ollama_temperature: 0.2,
    timeout_profile: 'patient',
    router_timeout: 30,
    model_timeout: 300,
    chat_timeout_seconds: 900,
    food_advisor_timeout: 180,
    recommended_threads: 4,
    hardware: { cpu_cores: 8, ram_gb: 16, gpu_backend: 'cpu' },
  });
  const [savingConfig, setSavingConfig] = useState(false);
  const [modelDetailsModal, setModelDetailsModal] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [catalog, setCatalog] = useState([]);

  const models = modelsData?.models || [];
  const running = modelsData?.running || [];
  const isOnline = isOllamaAvailable(statusData);

  useEffect(() => {
    api.getOllamaConfig().then(data => {
      if (data) setOllamaConfig(data);
    }).catch(() => {});

    api.getModelsCatalog().then(data => {
      if (data?.catalog) setCatalog(data.catalog);
    }).catch(() => {});
  }, []);

  const handleSaveConfig = async () => {
    if (Number(ollamaConfig.chat_timeout_seconds) < Number(ollamaConfig.model_timeout)) {
      showToast('El tiempo de la tarea completa debe ser mayor o igual al de una llamada al modelo.', 'danger');
      return;
    }
    if (Number(ollamaConfig.food_advisor_timeout) > Number(ollamaConfig.chat_timeout_seconds)) {
      showToast('El tiempo del asesor de comida no puede superar el de la tarea completa.', 'danger');
      return;
    }
    setSavingConfig(true);
    try {
      const res = await api.saveOllamaConfig(ollamaConfig);
      if (res.ok) {
        setOllamaConfig(res.config);
        showToast('Rendimiento y paciencia del agente guardados', 'success');
      }
    } catch (err) {
      showToast('Error al guardar configuración: ' + err.message, 'danger');
    } finally {
      setSavingConfig(false);
    }
  };

  const handleStart = async () => {
    try {
      showToast('Iniciando servicio Ollama...', 'info');
      const res = await api.startOllama();
      if (res && res.ok) {
        showToast('Ollama iniciado correctamente', 'success');
      } else {
        const reason = res?.runtime?.reason || 'no_disponible';
        const msg = reason === 'ollama_not_installed'
          ? 'No se encontró el ejecutable de Ollama en el sistema'
          : reason === 'startup_timeout'
          ? 'Tiempo de espera agotado al iniciar Ollama'
          : `No se pudo iniciar Ollama (${reason})`;
        showToast(msg, 'danger');
      }
      onRefresh();
    } catch (err) {
      showToast('Error al iniciar: ' + err.message, 'danger');
    }
  };

  const handleStop = async () => {
    try {
      showToast('Deteniendo servicio Ollama...', 'info');
      const res = await api.stopOllama();
      if (res && res.ok) {
        showToast('Ollama detenido', 'info');
      } else {
        showToast('No se pudo detener el proceso de Ollama', 'warning');
      }
      onRefresh();
    } catch (err) {
      showToast('Error al detener: ' + err.message, 'danger');
    }
  };

  const handleRestart = async () => {
    try {
      showToast('Reiniciando servicio Ollama...', 'info');
      const res = await api.restartOllama();
      if (res && res.ok) {
        showToast('Ollama reiniciado exitosamente', 'success');
      } else {
        const reason = res?.runtime?.reason || 'error';
        showToast(`No se pudo reiniciar Ollama (${reason})`, 'danger');
      }
      onRefresh();
    } catch (err) {
      showToast('Error al reiniciar: ' + err.message, 'danger');
    }
  };

  const startPullForModel = async (modelName) => {
    if (!modelName || !modelName.trim()) return;
    const targetModel = modelName.trim();
    setPulling(true);
    setPullProgress({
      percent: 0,
      status: `Iniciando conexión con el registro para ${targetModel}...`,
      text: '0%',
      completed_fmt: '0 B',
      total_fmt: 'Calculando...',
    });

    try {
      const token = api.getCookie('ada_csrf');
      const res = await fetch('/api/ollama/pull/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-ADA-Token': token },
        body: JSON.stringify({ model: targetModel }),
      });

      if (!res.ok) {
        throw new Error(`Error en servidor: ${res.statusText}`);
      }

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
              if (data.error) {
                showToast(`Error al descargar ${targetModel}: ${data.error}`, 'danger');
                setPulling(false);
                return;
              }
              if (data.status) {
                setPullProgress({
                  percent: data.percent || 0,
                  status: data.status,
                  text: `${data.percent || 0}%`,
                  completed_fmt: data.completed_formatted || '',
                  total_fmt: data.total_formatted || '',
                });
              }
              if (data.done) {
                showToast(`¡Modelo ${targetModel} descargado e instalado con éxito!`, 'success');
                setPulling(false);
                setPullInput('');
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

  const handleLoad = async (name) => {
    try {
      showToast(`Cargando ${name} en memoria...`, 'info');
      const res = await api.loadOllamaModel(name);
      if (res && res.ok) {
        showToast(`Modelo ${name} precargado en memoria (VRAM/RAM)`, 'success');
      } else {
        showToast(`No se pudo cargar el modelo ${name}`, 'danger');
      }
      onRefresh();
    } catch (err) {
      showToast('Error al cargar modelo: ' + err.message, 'danger');
    }
  };

  const handlePreloadAll = async () => {
    try {
      showToast('Precalentando modelos en memoria según la política activa...', 'info');
      const res = await api.preloadAllModels();
      if (res && res.ok) {
        showToast(`Modelos levantados: ${(res.loaded || []).join(', ') || 'Listos'}`, 'success');
      } else {
        showToast('No se pudieron precargar los modelos', 'warning');
      }
      onRefresh();
    } catch (err) {
      showToast('Error al precargar modelos: ' + err.message, 'danger');
    }
  };

  const handleUnload = async (name) => {
    try {
      await api.unloadOllamaModel(name);
      showToast(`Modelo ${name} descargado de VRAM / Memoria`, 'info');
      onRefresh();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handleDelete = async (name) => {
    if (!window.confirm(`¿Estás seguro de que deseás eliminar el modelo ${name} de disco?`)) return;
    try {
      await api.deleteOllamaModel(name);
      showToast(`Modelo ${name} eliminado del almacenamiento local`, 'info');
      onRefresh();
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    }
  };

  const handleShowDetails = async (name) => {
    setLoadingDetails(true);
    setModelDetailsModal({ name, loading: true });
    try {
      const details = await api.getOllamaDetails(name);
      setModelDetailsModal({ name, data: details });
    } catch (err) {
      showToast('Error al obtener detalles: ' + err.message, 'danger');
      setModelDetailsModal(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  const maxCores = ollamaConfig.hardware?.cpu_cores || 8;
  const applyTimeoutPreset = (profile) => {
    const preset = TIMEOUT_PRESETS[profile];
    if (!preset) return;
    setOllamaConfig({
      ...ollamaConfig,
      timeout_profile: profile,
      router_timeout: preset.router_timeout,
      model_timeout: preset.model_timeout,
      chat_timeout_seconds: preset.chat_timeout_seconds,
      food_advisor_timeout: preset.food_advisor_timeout,
    });
  };
  const updateTimeout = (key, seconds) => {
    const safeSeconds = Math.max(1, Math.min(86400, Number(seconds) || 1));
    setOllamaConfig({ ...ollamaConfig, timeout_profile: 'custom', [key]: safeSeconds });
  };

  return h('section', { className: 'tab-view active', id: 'tab-ollama' }, [
    // 1. Service Lifecycle Control Header
    h('div', { className: 'card mb-6', key: 'service-control-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-3' }, [
          h('div', { className: `status-dot ${isOnline ? 'online' : 'offline'}` }),
          h('div', null, [
            h('h3', { className: 'card-title' }, 'Motor de inferencia local'),
            h('span', { className: 'text-xs text-muted' }, `${ollamaConfig.hardware?.gpu_backend?.toUpperCase() || 'CPU'} · ${ollamaConfig.hardware?.ram_gb || '16'} GB de RAM · ${ollamaConfig.hardware?.cpu_cores || 8} núcleos`),
          ]),
          h('span', { className: `badge ${isOnline ? 'badge-success' : 'badge-danger'} ml-2` },
            isOnline ? 'En línea' : 'Detenido'
          ),
        ]),
        h('div', { className: 'flex items-center gap-2' }, [
          !isOnline ? h('button', { className: 'btn btn-sm btn-primary', onClick: handleStart }, 'Iniciar motor') : null,
          isOnline ? h('button', { className: 'btn btn-sm btn-secondary text-danger', onClick: handleStop }, 'Detener') : null,
          h('button', { className: 'btn btn-sm btn-ghost', onClick: handleRestart }, 'Reiniciar'),
        ]),
      ]),
    ]),

    // 2. Hardware Resource & Inference Limits Configuration
    h('div', { className: 'card mb-6', key: 'config-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', null, [
          h('h3', { className: 'card-title' }, 'Rendimiento y memoria'),
          h('span', { className: 'text-xs text-muted' }, 'Ajustá cuánto puede usar el motor. Los valores actuales priorizan calidad sobre velocidad.'),
        ]),
        h('button', { className: 'btn btn-sm btn-primary', onClick: handleSaveConfig, disabled: savingConfig },
          savingConfig ? 'Guardando…' : 'Guardar cambios'
        ),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'grid grid-cols-3 gap-6' }, [
          // CPU Threads & Budget
          h('div', { className: 'form-group' }, [
            h('div', { className: 'flex justify-between items-center' }, [
              h('label', { className: 'form-label', htmlFor: 'ollama-threads' }, 'Hilos de CPU'),
              h('span', { className: 'badge badge-accent' }, `${ollamaConfig.ollama_num_thread || ollamaConfig.recommended_threads} núcleos`),
            ]),
            h('input', {
              type: 'range',
              id: 'ollama-threads',
              min: 1,
              max: maxCores,
              step: 1,
              className: 'w-full',
              value: ollamaConfig.ollama_num_thread || ollamaConfig.recommended_threads || 4,
              onChange: (e) => setOllamaConfig({ ...ollamaConfig, ollama_num_thread: parseInt(e.target.value) }),
            }),
            h('span', { className: 'form-help' }, `Máximo disponible: ${maxCores} cores. Recomendado: ${ollamaConfig.recommended_threads}`),
          ]),

          // Context Window (num_ctx)
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label', htmlFor: 'ollama-context' }, 'Ventana de contexto'),
            h('select', {
              id: 'ollama-context',
              className: 'form-select',
              value: ollamaConfig.ollama_num_ctx || 4096,
              onChange: (e) => setOllamaConfig({ ...ollamaConfig, ollama_num_ctx: parseInt(e.target.value) }),
            }, [
            h('option', { value: 2048 }, '2,048 tokens (Ultra ligero - Bajo consumo RAM)'),
            h('option', { value: 8192 }, '8,192 tokens (Turbo estable)'),
            h('option', { value: 90000 }, '90,000 tokens (Experimental - alto consumo RAM)'),
              h('option', { value: 4096 }, '4,096 tokens (Recomendado estándar)'),
              h('option', { value: 8192 }, '8,192 tokens (Contexto amplio / Documentos largos)'),
              h('option', { value: 16384 }, '16,384 tokens (Modo Agéntico / Código multi-archivo)'),
              h('option', { value: 32768 }, '32,768 tokens (Máximo contexto)'),
            ]),
            h('span', { className: 'form-help' }, 'Determina cuántos tokens de historial y herramientas recuerda por turno.'),
          ]),

          // Keep Alive in Memory
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label', htmlFor: 'ollama-retention' }, 'Mantener el modelo en memoria'),
            h('select', {
              id: 'ollama-retention',
              className: 'form-select',
              value: ollamaConfig.ollama_keep_alive || '5m',
              onChange: (e) => setOllamaConfig({ ...ollamaConfig, ollama_keep_alive: e.target.value }),
            }, [
              h('option', { value: '0m' }, '0m (Liberar RAM/VRAM inmediatamente tras responder)'),
              h('option', { value: '2m' }, '2 minutos'),
              h('option', { value: '5m' }, '5 minutos (Predeterminado)'),
              h('option', { value: '10m' }, '10 minutos'),
              h('option', { value: '15m' }, '15 minutos'),
              h('option', { value: '30m' }, '30 minutos'),
              h('option', { value: '-1' }, 'Indefinido (Mantener siempre en RAM)'),
            ]),
            h('span', { className: 'form-help' }, 'Tiempo que el modelo permanece precargado para respuestas instantáneas.'),
          ]),
        ]),
      ]),
    ]),

    // 3. Independent timeout policy for patient agent work
    h('div', { className: 'card mb-6 agent-timeout-card', key: 'timeout-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', null, [
          h('div', { className: 'eyebrow' }, 'INDEPENDIENTE DEL MODO DE MODELO'),
          h('h3', { className: 'card-title' }, 'Paciencia del agente'),
          h('span', { className: 'text-xs text-muted' }, 'Define cuánto puede trabajar ADA antes de cancelar. Cambiar entre Liviano, Híbrido o Turbo ya no modifica estos tiempos.'),
        ]),
        h('button', { className: 'btn btn-sm btn-primary', onClick: handleSaveConfig, disabled: savingConfig },
          savingConfig ? 'Guardando…' : 'Guardar tiempos'
        ),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'timeout-preset-grid', role: 'group', 'aria-label': 'Perfiles de paciencia' },
          Object.entries(TIMEOUT_PRESETS).map(([key, preset]) => h('button', {
            key,
            type: 'button',
            className: `timeout-preset ${ollamaConfig.timeout_profile === key ? 'active' : ''}`,
            'aria-pressed': ollamaConfig.timeout_profile === key,
            onClick: () => applyTimeoutPreset(key),
          }, [
            h('span', { className: 'timeout-preset-title' }, [
              preset.label,
              key === 'patient' ? h('span', { className: 'badge badge-accent' }, 'Recomendado') : null,
            ]),
            h('span', { className: 'timeout-preset-description' }, preset.description),
            h('strong', null, preset.taskLabel),
          ]))
        ),
        ollamaConfig.timeout_profile === 'custom'
          ? h('div', { className: 'custom-timeout-note' }, 'Perfil personalizado · se guardarán los valores escritos abajo.')
          : null,
        h('div', { className: 'grid grid-cols-4 gap-4 timeout-fields' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label', htmlFor: 'router-timeout' }, 'Entender el pedido'),
            h('div', { className: 'input-with-unit' }, [
              h('input', {
                id: 'router-timeout', type: 'number', className: 'form-input', min: 1, max: 86400, step: 1,
                value: ollamaConfig.router_timeout || 30,
                onChange: (e) => updateTimeout('router_timeout', e.target.value),
              }),
              h('span', null, 'seg'),
            ]),
            h('span', { className: 'form-help' }, 'Clasificación inicial del pedido.'),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label', htmlFor: 'model-timeout' }, 'Una llamada al modelo'),
            h('div', { className: 'input-with-unit' }, [
              h('input', {
                id: 'model-timeout', type: 'number', className: 'form-input', min: 1 / 60, max: 1440, step: 0.5,
                value: Number((Number(ollamaConfig.model_timeout || 300) / 60).toFixed(2)),
                onChange: (e) => updateTimeout('model_timeout', Number(e.target.value) * 60),
              }),
              h('span', null, 'min'),
            ]),
            h('span', { className: 'form-help' }, 'Incluye carga y generación local.'),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label', htmlFor: 'task-timeout' }, 'Tarea completa'),
            h('div', { className: 'input-with-unit' }, [
              h('input', {
                id: 'task-timeout', type: 'number', className: 'form-input', min: 1 / 60, max: 1440, step: 1,
                value: Number((Number(ollamaConfig.chat_timeout_seconds || 900) / 60).toFixed(2)),
                onChange: (e) => updateTimeout('chat_timeout_seconds', Number(e.target.value) * 60),
              }),
              h('span', null, 'min'),
            ]),
            h('span', { className: 'form-help' }, 'Límite total del agente y sus pasos.'),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label', htmlFor: 'food-timeout' }, 'Asesor de comida'),
            h('div', { className: 'input-with-unit' }, [
              h('input', {
                id: 'food-timeout', type: 'number', className: 'form-input', min: 1 / 60, max: 1440, step: 0.5,
                value: Number((Number(ollamaConfig.food_advisor_timeout || 180) / 60).toFixed(2)),
                onChange: (e) => updateTimeout('food_advisor_timeout', Number(e.target.value) * 60),
              }),
              h('span', null, 'min'),
            ]),
            h('span', { className: 'form-help' }, 'Análisis nutricional y recetas.'),
          ]),
        ]),
        h('div', { className: 'timeout-rule-note' }, [
          h('span', { 'aria-hidden': 'true' }, '⏱'),
          h('span', null, 'ADA mantiene la conexión abierta e informa que sigue trabajando cada 3 segundos. La tarea completa debe tener al menos tanto tiempo como una llamada al modelo.'),
        ]),
      ]),
    ]),

    // 4. Download & Pull Manager (Real-Time % Progress)
    h('div', { className: 'card mb-6', key: 'pull-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', null, [
          h('h3', { className: 'card-title' }, 'Descargar un modelo'),
          h('span', { className: 'text-xs text-muted' }, 'Instalá un modelo desde la biblioteca de Ollama y seguí el progreso sin salir del gestor.'),
        ]),
      ]),
      h('div', { className: 'card-body flex flex-col gap-4' }, [
        h('div', { className: 'pull-form flex gap-3' }, [
          h('input', {
            type: 'text',
            className: 'form-input flex-1',
            placeholder: 'Nombre y versión, por ejemplo qwen2.5-coder:14b',
            'aria-label': 'Nombre del modelo que querés descargar',
            value: pullInput,
            onChange: (e) => setPullInput(e.target.value),
            onKeyDown: (e) => e.key === 'Enter' && !pulling && startPullForModel(pullInput),
            disabled: pulling,
          }),
          h('button', { className: 'btn btn-primary', onClick: () => startPullForModel(pullInput), disabled: pulling || !pullInput.trim() }, [
            h('span', null, pulling ? 'Descargando…' : 'Descargar'),
          ]),
        ]),

        // Active Download Progress Box
        pulling ? h('div', { className: 'download-progress-card p-4 bg-surface-elevated rounded-lg border border-primary', style: { background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.3)' } }, [
          h('div', { className: 'flex justify-between items-center mb-2' }, [
            h('div', { className: 'flex items-center gap-2' }, [
              h('span', { className: 'font-semibold text-primary' }, `Descargando: ${pullInput}`),
              h('span', { className: 'text-xs text-muted' }, `• ${pullProgress.status || 'Descargando paquetes...'}`),
            ]),
            h('div', { className: 'flex items-center gap-2' }, [
              pullProgress.total_fmt ? h('span', { className: 'text-xs font-mono text-muted' }, `${pullProgress.completed_fmt} / ${pullProgress.total_fmt}`) : null,
              h('span', { className: 'badge badge-primary font-mono' }, `${pullProgress.percent}%`),
            ]),
          ]),
          h('div', { className: 'progress-bar-bg', style: { height: '10px', background: 'rgba(255,255,255,0.1)', borderRadius: '5px', overflow: 'hidden' } }, [
            h('div', {
              className: 'progress-bar-fill',
              style: {
                width: `${pullProgress.percent}%`,
                height: '100%',
                background: 'linear-gradient(90deg, #6366f1, #a855f7, #ec4899)',
                transition: 'width 0.3s ease-out',
                boxShadow: '0 0 10px rgba(168, 85, 247, 0.5)',
              }
            }),
          ]),
        ]) : null,

        // Quick Pick from Recommended Catalog
        catalog.length > 0 ? h('div', { className: 'mt-2' }, [
          h('span', { className: 'text-xs font-semibold text-muted uppercase tracking-wide block mb-2' }, 'Sugerencias para este equipo'),
          h('div', { className: 'flex flex-wrap gap-2' },
            catalog.map(cat => {
              const isInstalled = models.some(m => m.name === cat.name || m.name.startsWith(cat.name + ':'));
              return h('button', {
                key: cat.name,
                className: `btn btn-sm ${isInstalled ? 'btn-ghost' : 'btn-secondary'} text-xs flex items-center gap-1.5`,
                disabled: pulling || isInstalled,
                onClick: () => {
                  setPullInput(cat.name);
                  startPullForModel(cat.name);
                },
              }, [
                h('span', null, isInstalled ? '✅' : '📥'),
                h('span', { className: 'font-mono' }, cat.name),
                h('span', { className: 'text-muted text-2xs' }, `(${cat.min_ram_gb}GB+)`),
              ]);
            })
          ),
        ]) : null,
      ]),
    ]),

    // 4. Running VRAM / Active Models
    h('div', { className: 'card mb-6', key: 'running-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, 'Modelos Activos en Memoria / VRAM (Ollama ps)'),
          h('span', { className: 'badge badge-accent' }, `${running.length} cargado(s)`),
        ]),
      ]),
      h('div', { className: 'card-body' }, [
        !running.length ? h('div', { className: 'empty-state-sm text-center py-4 text-muted text-sm' }, 'No hay ningún modelo ocupando memoria en este momento.')
          : h('div', { className: 'grid grid-cols-2 gap-4' },
              running.map(r => h('div', { className: 'model-card border-accent p-4 rounded-lg bg-surface-elevated', key: r.name }, [
                h('div', { className: 'flex justify-between items-start mb-2' }, [
                  h('div', null, [
                    h('span', { className: 'model-name block font-semibold text-primary font-mono' }, r.name),
                    h('span', { className: 'text-xs text-muted' }, `Expira en: ${r.expires_at || 'Al agotarse keep-alive'}`),
                  ]),
                  h('span', { className: 'badge badge-success' }, `VRAM/RAM: ${r.size_vram_formatted}`),
                ]),
                h('div', { className: 'flex justify-end gap-2 mt-3 pt-2 border-t border-subtle' }, [
                  h('button', { className: 'btn btn-sm btn-secondary text-danger', onClick: () => handleUnload(r.name) }, '🔻 Liberar Memoria'),
                ]),
              ]))
            ),
      ]),
    ]),

    // 5. Installed Models List & Management
    h('div', { className: 'card', key: 'installed-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-2' }, [
          h('h3', { className: 'card-title' }, 'Biblioteca de Modelos Instalados en Disco'),
          h('span', { className: 'badge badge-primary' }, `${models.length} modelos`),
        ]),
        h('div', { className: 'flex items-center gap-2' }, [
          models.length > 0 ? h('button', { className: 'btn btn-sm btn-primary', onClick: handlePreloadAll, title: 'Carga los modelos en memoria para que respondan al instante sin demoras' }, '⚡ Precargar Todos en Memoria') : null,
          h('button', { className: 'btn btn-sm btn-ghost', onClick: onRefresh }, '🔄 Actualizar Lista'),
        ]),
      ]),
      h('div', { className: 'card-body' }, [
        !models.length ? h('div', { className: 'empty-state-sm text-center py-6 text-muted' }, 'No se encontraron modelos descargados en este equipo.')
          : h('div', { className: 'grid grid-cols-3 gap-4' },
              models.map(m => {
                const isRunning = running.some(r => r.name === m.name);
                return h('div', { className: `model-card p-4 rounded-lg bg-surface-elevated flex flex-col justify-between ${isRunning ? 'border-primary' : ''}`, key: m.name }, [
                  h('div', null, [
                    h('div', { className: 'flex justify-between items-start mb-2' }, [
                      h('span', { className: 'model-name font-mono font-bold text-white' }, m.name),
                      h('span', { className: 'badge badge-accent' }, m.size_formatted),
                    ]),
                    h('div', { className: 'model-meta flex flex-wrap gap-1.5 mb-3' }, [
                      isRunning ? h('span', { className: 'badge badge-success text-2xs', key: 'running' }, '🟢 En Memoria') : null,
                      m.details?.parameter_size ? h('span', { className: 'badge text-2xs', key: 'p' }, m.details.parameter_size) : null,
                      m.details?.quantization_level ? h('span', { className: 'badge text-2xs', key: 'q' }, m.details.quantization_level) : null,
                      m.details?.family ? h('span', { className: 'badge text-2xs', key: 'f' }, m.details.family) : null,
                    ]),
                  ]),
                  h('div', { className: 'flex flex-col gap-2 mt-3 pt-2 border-t border-subtle' }, [
                    !isRunning ? h('button', { className: 'btn btn-sm btn-primary w-full text-xs font-semibold', onClick: () => handleLoad(m.name) }, '⚡ Cargar en Memoria')
                               : h('button', { className: 'btn btn-sm btn-secondary text-danger w-full text-xs', onClick: () => handleUnload(m.name) }, '🔻 Descargar de Memoria'),
                    h('div', { className: 'flex justify-between items-center gap-1' }, [
                      h('div', { className: 'flex gap-1' }, [
                        h('button', { className: 'btn btn-sm btn-ghost text-xs', title: 'Ver Arquitectura y Modelfile', onClick: () => handleShowDetails(m.name) }, 'ℹ️ Info'),
                        h('button', { className: 'btn btn-sm btn-ghost text-xs', title: 'Testear velocidad de respuesta', onClick: () => onBenchmark(m.name) }, '⚡ Bench'),
                      ]),
                      h('button', { className: 'btn btn-sm btn-ghost text-danger text-xs', title: 'Borrar de disco', onClick: () => handleDelete(m.name) }, '🗑️ Borrar'),
                    ]),
                  ]),
                ]);
              })
            ),
      ]),
    ]),

    // Model Details Modal
    modelDetailsModal ? h('div', { className: 'modal-overlay', style: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }, onClick: () => setModelDetailsModal(null) }, [
      h('div', { className: 'modal-content card', style: { width: '600px', maxHeight: '80vh', overflowY: 'auto' }, onClick: (e) => e.stopPropagation() }, [
        h('div', { className: 'card-header flex justify-between items-center' }, [
          h('h3', { className: 'card-title font-mono' }, `Detalles de ${modelDetailsModal.name}`),
          h('button', { className: 'btn btn-sm btn-ghost', onClick: () => setModelDetailsModal(null) }, '✕'),
        ]),
        h('div', { className: 'card-body' }, [
          modelDetailsModal.data ? h('div', { className: 'flex flex-col gap-3 text-xs font-mono' }, [
            h('div', null, [
              h('span', { className: 'text-muted block' }, 'Familia & Formato:'),
              h('span', { className: 'text-primary' }, `${modelDetailsModal.data.details?.family || 'N/A'} (${modelDetailsModal.data.details?.format || 'gguf'})`),
            ]),
            h('div', null, [
              h('span', { className: 'text-muted block' }, 'Parámetros & Cuantización:'),
              h('span', { className: 'text-white' }, `${modelDetailsModal.data.details?.parameter_size || 'N/A'} - ${modelDetailsModal.data.details?.quantization_level || 'N/A'}`),
            ]),
            modelDetailsModal.data.parameters ? h('div', null, [
              h('span', { className: 'text-muted block mb-1' }, 'Parámetros Modelfile:'),
              h('pre', { className: 'p-2 bg-surface rounded text-2xs overflow-x-auto' }, modelDetailsModal.data.parameters),
            ]) : null,
            modelDetailsModal.data.template ? h('div', null, [
              h('span', { className: 'text-muted block mb-1' }, 'Template de Prompt:'),
              h('pre', { className: 'p-2 bg-surface rounded text-2xs overflow-x-auto' }, modelDetailsModal.data.template.slice(0, 300) + '...'),
            ]) : null,
          ]) : h('div', { className: 'py-6 text-center text-muted' }, 'Cargando información del modelo...'),
        ]),
      ]),
    ]) : null,
  ]);
}

// 5. Models Tab View (Roles & Benchmark)
function ModelsView({ installedModels, showToast }) {
  const roleLabels = {
    chat: 'Conversación',
    router: 'Router rápido',
    reasoning: 'Razonamiento',
    coding: 'Código',
    tools: 'Herramientas',
    vision: 'Visión y OCR',
  };
  const modeCards = [
    { id: 'manual', name: 'Manual', eyebrow: 'Control total', description: 'Elegís un modelo para cada tipo de tarea.' },
    { id: 'light', name: 'Liviano', eyebrow: 'Más rápido', description: 'Menos RAM, menos temperatura y respuestas ágiles.' },
    { id: 'hybrid', name: 'Híbrido', eyebrow: 'Recomendado', description: 'Modelo rápido para lo simple y especialistas cuando hacen falta.' },
    { id: 'turbo', name: 'Turbo', eyebrow: 'Máxima calidad', description: 'Usa el modelo más potente que entra con margen seguro.' },
  ];
  const [selectionMode, setSelectionMode] = useState('manual');
  const [policyData, setPolicyData] = useState(null);
  const [manualRoles, setManualRoles] = useState({ chat: '', router: '', reasoning: '', coding: '', tools: '', vision: '' });
  const [savingMode, setSavingMode] = useState(false);
  const [benchModel, setBenchModel] = useState('');
  const [benchPrompt, setBenchPrompt] = useState('quick');
  const [customPromptText, setCustomPromptText] = useState('');
  const [benchResult, setBenchResult] = useState(null);
  const [benchLoading, setBenchLoading] = useState(false);
  const [promptCatalog, setPromptCatalog] = useState(null);
  const [expandedPromptIdx, setExpandedPromptIdx] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newModelForm, setNewModelForm] = useState({
    name: '',
    roles: 'chat',
    description: '',
    min_ram_gb: 8,
    quality_tier: 'medium',
  });

  useEffect(() => {
    api.getModelsPolicy().then(data => {
      setPolicyData(data);
      setSelectionMode(data.mode || 'manual');
      const source = data.manual_policy || data.policy || {};
      setManualRoles(Object.fromEntries(Object.keys(roleLabels).map(role => [role, source?.[role]?.preferred || ''])));
    }).catch(() => {});

    api.getModelsCatalog().then(data => {
      setCatalog(data.catalog || []);
    }).catch(() => {});

    api.getBenchmarkPrompts().then(data => {
      if (data?.prompts) setPromptCatalog(data.prompts);
    }).catch(() => {});
  }, []);

  const handleApplyMode = async () => {
    const manualPolicy = Object.fromEntries(
      Object.keys(roleLabels).map(role => [role, { preferred: manualRoles[role] || null, fallbacks: [] }])
    );
    setSavingMode(true);
    try {
      const result = await api.saveModelsSelection({
        selection_mode: selectionMode,
        ...(selectionMode === 'manual' ? { manual_policy: manualPolicy } : {}),
      });
      setPolicyData(result);
      showToast(`Modo ${modeCards.find(item => item.id === selectionMode)?.name} aplicado`, 'success');
    } catch (err) {
      showToast('Error: ' + err.message, 'danger');
    } finally {
      setSavingMode(false);
    }
  };

  const previewPolicy = selectionMode === 'manual'
    ? Object.fromEntries(Object.keys(roleLabels).map(role => [role, { preferred: manualRoles[role] || null, fallbacks: [] }]))
    : policyData?.mode_previews?.[selectionMode] || policyData?.policy || {};
  const previewRuntime = policyData?.runtime_presets?.[selectionMode] || policyData?.runtime_settings || {};
  const compatibleByRole = (role) => {
    const profiles = policyData?.installed || [];
    const names = profiles.filter(item => (item.roles || []).includes(role)).map(item => item.name);
    return installedModels.filter(item => names.includes(item.name));
  };
  const installedProfile = (name) => (policyData?.installed || []).find(item => item.name === name);

  const handleBenchmark = async () => {
    const target = benchModel || previewPolicy?.chat?.preferred || installedModels[0]?.name;
    if (!target) {
      showToast('Seleccioná un modelo para benchmark', 'warning');
      return;
    }
    setBenchLoading(true);
    setBenchResult(null);
    try {
      const isSuite = benchPrompt === 'suite';
      const customPrompt = benchPrompt === 'custom' ? customPromptText : null;
      const res = await api.runBenchmark(target, isSuite ? 'quick' : benchPrompt, customPrompt, isSuite);
      setBenchResult(res);
      if (res.ok) {
        showToast(isSuite ? 'Suite de pruebas completada' : 'Benchmark finalizado', 'success');
      } else {
        showToast(res.error || 'Error al ejecutar prueba', 'danger');
      }
    } catch (err) {
      setBenchResult({ ok: false, error: err.message });
      showToast('Error de conexión con el motor', 'danger');
    } finally {
      setBenchLoading(false);
    }
  };

  return h('section', { className: 'tab-view active', id: 'tab-models' }, [
    h('div', { className: 'card mb-6 model-mode-shell', key: 'mode-selector' }, [
      h('div', { className: 'card-header model-mode-header' }, [
        h('div', null, [
          h('span', { className: 'section-kicker' }, 'Política de ejecución'),
          h('h3', { className: 'card-title' }, '¿Cómo querés que ADA elija los modelos?'),
          h('p', { className: 'text-sm text-muted mt-1' }, 'Los modos automáticos usan solamente modelos descargados y dejan margen para el sistema.'),
        ]),
        h('button', { className: 'btn btn-primary', onClick: handleApplyMode, disabled: savingMode || !policyData },
          savingMode ? 'Aplicando…' : 'Aplicar configuración'
        ),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'model-mode-grid', role: 'radiogroup', 'aria-label': 'Modo de selección de modelos' },
          modeCards.map(mode => h('button', {
            key: mode.id,
            type: 'button',
            role: 'radio',
            'aria-checked': selectionMode === mode.id,
            className: `model-mode-card ${selectionMode === mode.id ? 'selected' : ''}`,
            onClick: () => setSelectionMode(mode.id),
          }, [
            h('span', { className: 'model-mode-check', 'aria-hidden': 'true' }, selectionMode === mode.id ? '✓' : ''),
            h('span', { className: 'model-mode-eyebrow' }, mode.eyebrow),
            h('strong', null, mode.name),
            h('span', { className: 'model-mode-description' }, mode.description),
          ]))
        ),
        selectionMode === 'manual' ? h('div', { className: 'manual-role-grid mt-6' },
          Object.entries(roleLabels).map(([role, label]) => {
            const compatible = compatibleByRole(role);
            const options = compatible.length ? compatible : (role === 'vision' ? [] : installedModels);
            return h('label', { className: 'manual-role-field', key: role }, [
              h('span', { className: 'form-label' }, label),
              h('select', {
                className: 'form-select',
                'aria-label': `Modelo manual para ${label}`,
                value: manualRoles[role] || '',
                onChange: (event) => setManualRoles({ ...manualRoles, [role]: event.target.value }),
              }, [
                h('option', { value: '' }, role === 'vision' ? 'Sin modelo compatible' : 'Sin asignar'),
                ...options.map(model => {
                  const profile = installedProfile(model.name);
                  const warning = profile && !profile.hardware_fit ? ' · ⚠ excede la RAM segura' : '';
                  return h('option', { key: model.name, value: model.name }, `${model.name} · ${model.size_formatted}${warning}`);
                }),
              ]),
              !compatible.length ? h('span', { className: 'form-help text-warning' }, 'No hay un modelo especializado descargado.') : null,
            ]);
          })
        ) : null,
      ]),
    ]),

    h('div', { className: 'grid grid-cols-2 gap-6 mb-6', key: 'top-grid' }, [
      h('div', { className: 'card model-plan-card', key: 'active-plan' }, [
        h('div', { className: 'card-header' }, [
          h('div', null, [
            h('h3', { className: 'card-title' }, 'Configuración resultante'),
            h('span', { className: 'text-xs text-muted' }, 'Vista previa antes de aplicar'),
          ]),
          selectionMode === 'hybrid' ? h('span', { className: 'badge badge-success' }, 'Recomendado') : null,
        ]),
        h('div', { className: 'card-body' }, [
          h('dl', { className: 'model-plan-list' }, Object.entries(roleLabels).map(([role, label]) =>
            h('div', { key: role }, [
              h('dt', null, label),
              h('dd', { className: !previewPolicy?.[role]?.preferred ? 'missing' : '' }, previewPolicy?.[role]?.preferred || 'No disponible'),
            ])
          )),
          selectionMode === 'manual' ? h('p', { className: 'model-manual-runtime' }, 'Los límites de CPU y contexto se administran desde Motor local.') : h('div', { className: 'model-runtime-strip' }, [
            h('span', null, `${previewRuntime.ollama_num_thread || '—'} hilos`),
            h('span', null, `${Number(previewRuntime.ollama_num_ctx || 0).toLocaleString('es-AR')} tokens`),
            h('span', null, `${previewRuntime.cpu_limit_percent || '—'}% CPU`),
          ]),
          policyData?.warnings?.length ? h('div', { className: 'model-policy-warning' }, [
            h('strong', null, 'Atención'),
            h('span', null, policyData.warnings[0]),
          ]) : null,
        ]),
      ]),

      // Benchmark & Prompt Test Runner with Full Telemetry
      h('div', { className: 'card', key: 'bench-card' }, [
        h('div', { className: 'card-header' }, [
          h('div', null, [
            h('h3', { className: 'card-title' }, '🧪 Ejecución de Prompts de Test & Telemetría'),
            h('span', { className: 'text-xs text-muted' }, 'Medición completa de tiempos, velocidad de inferencia y recursos consumidos (CPU / RAM / VRAM).'),
          ]),
        ]),
        h('div', { className: 'card-body flex flex-col gap-4' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Seleccionar Modelo'),
            h('select', { className: 'form-select', 'aria-label': 'Modelo para la prueba de rendimiento', value: benchModel || previewPolicy?.chat?.preferred || installedModels[0]?.name || '', onChange: (e) => setBenchModel(e.target.value) },
              installedModels.map(model => {
                const profile = installedProfile(model.name);
                return h('option', { key: model.name, value: model.name }, `${model.name}${profile && !profile.hardware_fit ? ' · ⚠ supera RAM segura' : ''}`);
              })
            ),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Tipo de Prueba de Prompts'),
            h('select', { className: 'form-select', 'aria-label': 'Tipo de prueba de rendimiento', value: benchPrompt, onChange: (e) => setBenchPrompt(e.target.value) }, [
              h('option', { value: 'suite' }, '⚡ Suite Completa (Ejecutar todos los prompts de prueba)'),
              h('option', { value: 'quick' }, '🚀 Respuesta Rápida (Explicación básica)'),
              h('option', { value: 'reasoning' }, '🧠 Razonamiento Lógico (Paso a paso)'),
              h('option', { value: 'json' }, '📊 Estructuración JSON (Validación de esquema)'),
              h('option', { value: 'planning' }, '🛠️ Planificación y Tareas (Workflow de agentes)'),
              h('option', { value: 'coding' }, '💻 Generación de Código (Algoritmo Python)'),
              h('option', { value: 'custom' }, '✍️ Prompt Personalizado (Ingresar texto libre)'),
            ]),
          ]),
          benchPrompt === 'custom' ? h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Texto del Prompt Personalizado'),
            h('textarea', {
              className: 'form-input form-textarea',
              rows: 3,
              placeholder: 'Escribí el prompt de prueba para evaluar la respuesta y rendimiento...',
              value: customPromptText,
              onChange: (e) => setCustomPromptText(e.target.value),
            }),
          ]) : null,
          h('button', { className: 'btn btn-primary', onClick: handleBenchmark, disabled: benchLoading }, [
            h('span', null, benchLoading ? '⏳ Midiendo tiempos y recursos del sistema...' : (benchPrompt === 'suite' ? '⚡ Iniciar Suite Completa de Prompts' : '⚡ Ejecutar Prompt de Test')),
          ]),
          benchResult ? h('div', { className: 'benchmark-results-box' }, [
            benchResult.ok ? (benchResult.suite_run ? h('div', { className: 'bench-suite-container' }, [
              // Suite Summary Header
              h('div', { className: 'bench-suite-summary-header' }, [
                h('div', { className: 'flex justify-between items-center mb-3' }, [
                  h('h4', { className: 'text-sm font-semibold' }, `Resumen de Suite: ${benchResult.model}`),
                  h('span', { className: 'badge badge-success' }, `✓ ${benchResult.summary?.successful_prompts}/${benchResult.summary?.total_prompts} Completados`),
                ]),
                h('div', { className: 'bench-stats-grid grid-cols-3 gap-3 mb-4' }, [
                  h('div', { className: 'bench-stat-item' }, [
                    h('span', { className: 'bench-stat-label' }, 'Velocidad Media'),
                    h('span', { className: 'bench-stat-val text-primary' }, `${benchResult.summary?.avg_tokens_per_second} t/s`),
                  ]),
                  h('div', { className: 'bench-stat-item' }, [
                    h('span', { className: 'bench-stat-label' }, 'Tiempo Total Suite'),
                    h('span', { className: 'bench-stat-val' }, `${benchResult.summary?.total_duration_s} s`),
                  ]),
                  h('div', { className: 'bench-stat-item' }, [
                    h('span', { className: 'bench-stat-label' }, 'Tokens Generados'),
                    h('span', { className: 'bench-stat-val' }, `${benchResult.summary?.total_tokens_generated}`),
                  ]),
                  h('div', { className: 'bench-stat-item' }, [
                    h('span', { className: 'bench-stat-label' }, 'CPU Media / Pico'),
                    h('span', { className: 'bench-stat-val text-warning' }, `${benchResult.summary?.avg_cpu_percent}% / ${benchResult.summary?.peak_cpu_percent}%`),
                  ]),
                  h('div', { className: 'bench-stat-item' }, [
                    h('span', { className: 'bench-stat-label' }, 'RAM Media / Pico'),
                    h('span', { className: 'bench-stat-val' }, `${benchResult.summary?.avg_ram_used_gb} GB / ${benchResult.summary?.peak_ram_used_gb} GB`),
                  ]),
                  h('div', { className: 'bench-stat-item' }, [
                    h('span', { className: 'bench-stat-label' }, 'Aceleración'),
                    h('span', { className: 'bench-stat-val' }, benchResult.resources?.vram_gb > 0 ? `${benchResult.resources.vram_gb} GB (${benchResult.resources.gpu_backend})` : `CPU (${benchResult.resources?.cpu_cores || 1} cores)`),
                  ]),
                ]),
              ]),
              // Suite Individual Prompts
              h('div', { className: 'bench-suite-list flex flex-col gap-2 mt-4' },
                (benchResult.results || []).map((item, idx) => {
                  const isExpanded = expandedPromptIdx === idx;
                  return h('div', { key: idx, className: 'bench-suite-item' }, [
                    h('div', {
                      className: 'bench-suite-item-header flex justify-between items-center cursor-pointer',
                      onClick: () => setExpandedPromptIdx(isExpanded ? null : idx),
                    }, [
                      h('div', { className: 'flex items-center gap-2' }, [
                        h('span', { className: item.ok ? 'text-success font-bold' : 'text-danger font-bold' }, item.ok ? '✓' : '✗'),
                        h('strong', { className: 'text-sm' }, item.prompt_title || `Prueba ${idx + 1}`),
                        h('span', { className: 'text-xs text-muted' }, `· ${item.tokens_per_second || 0} t/s · ${item.total_time_s || 0}s`),
                      ]),
                      h('div', { className: 'flex items-center gap-2' }, [
                        h('span', { className: 'badge badge-sm' }, `CPU ${item.resources?.cpu_percent ?? 0}%`),
                        h('span', { className: 'badge badge-sm' }, `RAM ${item.resources?.ram_used_gb ?? 0} GB`),
                        h('span', { className: 'text-xs text-muted' }, isExpanded ? '▲ Ocultar' : '▼ Ver respuesta'),
                      ]),
                    ]),
                    isExpanded ? h('div', { className: 'bench-suite-item-body mt-3' }, [
                      h('div', { className: 'text-xs text-muted mb-1' }, `Prompt: ${item.prompt}`),
                      h('div', { className: 'bench-output' }, item.response || item.error || 'Sin respuesta'),
                    ]) : null,
                  ]);
                })
              ),
            ]) : h('div', null, [
              // Single Prompt Timing Metrics
              h('div', { className: 'text-xs font-semibold uppercase text-muted mb-2' }, '⏱️ Medición de Tiempos & Inferencia'),
              h('div', { className: 'bench-stats-grid' }, [
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'Velocidad Inferencia'),
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
              // Single Prompt Resource Telemetry
              h('div', { className: 'text-xs font-semibold uppercase text-muted mt-3 mb-2' }, '💻 Recursos Consumidos'),
              h('div', { className: 'bench-stats-grid' }, [
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'CPU Utilizada'),
                  h('span', { className: 'bench-stat-val text-warning' }, `${benchResult.resources?.cpu_percent ?? 0}%`),
                ]),
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'RAM Sistema (Uso / Delta)'),
                  h('span', { className: 'bench-stat-val' }, `${benchResult.resources?.ram_used_gb ?? 0} GB (${(benchResult.resources?.ram_delta_mb || 0) > 0 ? '+' : ''}${benchResult.resources?.ram_delta_mb ?? 0} MB)`),
                ]),
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'Tokens Generados'),
                  h('span', { className: 'bench-stat-val' }, `${benchResult.eval_count || 0} tokens`),
                ]),
              ]),
              // Generated Output
              h('div', { className: 'text-xs font-semibold uppercase text-muted mt-3 mb-1' }, '💬 Respuesta Generada'),
              h('div', { className: 'bench-output' }, benchResult.response),
            ])) : h('div', { className: 'text-danger text-sm' }, `Error: ${benchResult.error}`),
          ]) : null,
        ]),
      ]),
    ]),

    // Catalog & DB Model Management
    h('div', { className: 'card', key: 'catalog-card' }, [
      h('div', { className: 'card-header flex justify-between items-center' }, [
        h('div', null, [
          h('h3', { className: 'card-title' }, 'Catálogo de Modelos en Base de Datos (SQLite)'),
          h('span', { className: 'text-xs text-muted' }, 'Modelos registrados en la BD para gestión y descarga automatizada.'),
        ]),
        h('div', { className: 'flex gap-2' }, [
          h('button', { className: 'btn btn-sm btn-primary', onClick: () => setShowAddModal(true) }, '➕ Agregar Modelo a BD'),
        ]),
      ]),
      h('div', { className: 'card-body' }, [
        h('div', { className: 'catalog-grid' },
          catalog.map(c => {
            const isInstalled = installedModels.some(m => m.name === c.name || m.name.startsWith(c.name + ':'));
            return h('div', { className: 'model-card flex flex-col justify-between', key: c.name }, [
              h('div', null, [
                h('div', { className: 'model-card-header' }, [
                  h('span', { className: 'model-name font-mono' }, c.name),
                  h('span', { className: `badge ${c.hardware_fit ? 'badge-success' : 'badge-warning'}` },
                    c.hardware_fit ? 'Apto para tu RAM' : 'Requiere más RAM'
                  ),
                ]),
                h('p', { className: 'text-xs text-muted my-2' }, c.description || 'Sin descripción'),
                h('div', { className: 'model-meta mb-3' }, [
                  h('span', { className: 'badge badge-accent' }, `Roles: ${(c.roles || []).join(', ')}`),
                  h('span', { className: 'badge' }, `Mín: ${c.min_ram_gb} GB RAM`),
                  isInstalled ? h('span', { className: 'badge badge-success' }, '🟢 Instalado') : null,
                ]),
              ]),
              h('div', { className: 'flex justify-between items-center pt-2 border-t border-subtle mt-2' }, [
                !isInstalled ? h('button', {
                  className: 'btn btn-sm btn-primary text-xs',
                  onClick: async () => {
                    showToast(`Iniciando descarga en gestor para ${c.name}...`, 'info');
                    window.location.hash = '#ollama';
                  }
                }, '📥 Descargar en Ollama') : h('span', { className: 'text-xs text-success font-semibold' }, '✓ Listo para uso'),
                h('button', {
                  className: 'btn btn-sm btn-ghost text-danger text-xs',
                  title: 'Quitar del catálogo BD',
                  onClick: async () => {
                    if (!confirm(`¿Eliminar ${c.name} del catálogo de la Base de Datos?`)) return;
                    try {
                      await api.deleteCatalogModel(c.name);
                      showToast(`Modelo ${c.name} removido de la BD`, 'info');
                      const data = await api.getModelsCatalog();
                      setCatalog(data.catalog || []);
                    } catch (err) {
                      showToast('Error: ' + err.message, 'danger');
                    }
                  }
                }, '✕ Quitar'),
              ]),
            ]);
          })
        ),
      ]),
    ]),

    // Add Model to SQLite DB Modal
    showAddModal ? h('div', { className: 'modal-overlay', style: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }, onClick: () => setShowAddModal(false) }, [
      h('div', { className: 'modal-content card', style: { width: '500px' }, onClick: (e) => e.stopPropagation() }, [
        h('div', { className: 'card-header flex justify-between items-center' }, [
          h('h3', { className: 'card-title' }, 'Registrar Nuevo Modelo en BD'),
          h('button', { className: 'btn btn-sm btn-ghost', onClick: () => setShowAddModal(false) }, '✕'),
        ]),
        h('div', { className: 'card-body flex flex-col gap-4' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Tag / Nombre en Ollama'),
            h('input', {
              type: 'text',
              className: 'form-input font-mono',
              placeholder: 'Ej: phi4:14b, mistral:7b, qwen2.5:14b',
              value: newModelForm.name,
              onChange: (e) => setNewModelForm({ ...newModelForm, name: e.target.value }),
            }),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Roles (separados por coma)'),
            h('input', {
              type: 'text',
              className: 'form-input',
              placeholder: 'chat, reasoning, coding, tools',
              value: newModelForm.roles,
              onChange: (e) => setNewModelForm({ ...newModelForm, roles: e.target.value }),
            }),
          ]),
          h('div', { className: 'grid grid-cols-2 gap-4' }, [
            h('div', { className: 'form-group' }, [
              h('label', { className: 'form-label' }, 'Mínimo RAM (GB)'),
              h('input', {
                type: 'number',
                className: 'form-input',
                value: newModelForm.min_ram_gb,
                onChange: (e) => setNewModelForm({ ...newModelForm, min_ram_gb: e.target.value }),
              }),
            ]),
            h('div', { className: 'form-group' }, [
              h('label', { className: 'form-label' }, 'Tier / Categoría'),
              h('select', {
                className: 'form-select',
                value: newModelForm.quality_tier,
                onChange: (e) => setNewModelForm({ ...newModelForm, quality_tier: e.target.value }),
              }, [
                h('option', { value: 'tiny' }, 'Tiny (< 3B)'),
                h('option', { value: 'small' }, 'Small (3B - 7B)'),
                h('option', { value: 'medium' }, 'Medium (7B - 9B)'),
                h('option', { value: 'large' }, 'Large (14B - 20B)'),
                h('option', { value: 'huge' }, 'Huge (> 30B)'),
              ]),
            ]),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Descripción'),
            h('input', {
              type: 'text',
              className: 'form-input',
              placeholder: 'Descripción de capacidades y especialidad',
              value: newModelForm.description,
              onChange: (e) => setNewModelForm({ ...newModelForm, description: e.target.value }),
            }),
          ]),
          h('div', { className: 'flex justify-end gap-2 mt-2' }, [
            h('button', { className: 'btn btn-secondary', onClick: () => setShowAddModal(false) }, 'Cancelar'),
            h('button', {
              className: 'btn btn-primary',
              onClick: async () => {
                if (!newModelForm.name.trim()) {
                  showToast('Ingresá el nombre del modelo', 'warning');
                  return;
                }
                const rolesArray = newModelForm.roles.split(',').map(r => r.trim()).filter(Boolean);
                try {
                  await api.addCatalogModel({
                    name: newModelForm.name.trim(),
                    roles: rolesArray.length ? rolesArray : ['chat'],
                    description: newModelForm.description.trim(),
                    quality_tier: newModelForm.quality_tier,
                    min_ram_gb: parseFloat(newModelForm.min_ram_gb) || 4,
                  });
                  showToast(`Modelo ${newModelForm.name} guardado en BD`, 'success');
                  setShowAddModal(false);
                  setNewModelForm({ name: '', roles: 'chat', description: '', min_ram_gb: 8, quality_tier: 'medium' });
                  const data = await api.getModelsCatalog();
                  setCatalog(data.catalog || []);
                } catch (err) {
                  showToast('Error al guardar: ' + err.message, 'danger');
                }
              }
            }, '💾 Guardar en BD'),
          ]),
        ]),
      ]),
    ]) : null,
  ]);
}

// 5.1 Dedicated Benchmark & Prompt Test Suite View
function BenchmarkView({ installedModels, showToast }) {
  const [benchModel, setBenchModel] = useState('');
  const [benchPrompt, setBenchPrompt] = useState('suite');
  const [customPromptText, setCustomPromptText] = useState('');
  const [benchResult, setBenchResult] = useState(null);
  const [benchLoading, setBenchLoading] = useState(false);
  const [expandedPromptIdx, setExpandedPromptIdx] = useState(null);
  const [promptCatalog, setPromptCatalog] = useState(null);

  useEffect(() => {
    api.getBenchmarkPrompts().then(data => {
      if (data?.prompts) setPromptCatalog(data.prompts);
    }).catch(() => {});
  }, []);

  const handleBenchmark = async () => {
    const target = benchModel || installedModels[0]?.name;
    if (!target) {
      showToast('Seleccioná un modelo para benchmark', 'warning');
      return;
    }
    setBenchLoading(true);
    setBenchResult(null);
    try {
      const isSuite = benchPrompt === 'suite';
      const customPrompt = benchPrompt === 'custom' ? customPromptText : null;
      const res = await api.runBenchmark(target, isSuite ? 'quick' : benchPrompt, customPrompt, isSuite);
      setBenchResult(res);
      if (res.ok) {
        showToast(isSuite ? 'Suite de pruebas completada' : 'Benchmark finalizado', 'success');
      } else {
        showToast(res.error || 'Error al ejecutar prueba', 'danger');
      }
    } catch (err) {
      setBenchResult({ ok: false, error: err.message });
      showToast('Error de conexión con el motor', 'danger');
    } finally {
      setBenchLoading(false);
    }
  };

  return h('section', { className: 'tab-view active', id: 'tab-benchmark' }, [
    // Top Info & Controls Grid
    h('div', { className: 'grid grid-cols-3 gap-6 mb-6', key: 'bench-top-grid' }, [
      // Control Panel Card
      h('div', { className: 'card col-span-1', key: 'bench-control' }, [
        h('div', { className: 'card-header' }, [
          h('h3', { className: 'card-title' }, '⚙️ Configuración del Test'),
        ]),
        h('div', { className: 'card-body flex flex-col gap-4' }, [
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Modelo a Evaluar'),
            h('select', {
              className: 'form-select font-mono',
              'aria-label': 'Modelo a evaluar',
              value: benchModel || installedModels[0]?.name || '',
              onChange: (e) => setBenchModel(e.target.value)
            },
              installedModels.map(m => h('option', { key: m.name, value: m.name }, `${m.name} (${m.size_formatted || 'local'})`))
            ),
          ]),
          h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Modo de Ejecución'),
            h('select', {
              className: 'form-select',
              'aria-label': 'Modo de ejecución',
              value: benchPrompt,
              onChange: (e) => setBenchPrompt(e.target.value)
            }, [
              h('option', { value: 'suite' }, '⚡ Suite Completa (5 Prompts de Test)'),
              h('option', { value: 'quick' }, '🚀 Respuesta Rápida (Latencia corta)'),
              h('option', { value: 'reasoning' }, '🧠 Razonamiento Lógico (Aritmética)'),
              h('option', { value: 'json' }, '📊 Estructuración JSON (Esquema estricto)'),
              h('option', { value: 'planning' }, '🛠️ Planificación y Agentes (Workflow)'),
              h('option', { value: 'coding' }, '💻 Generación de Código (Python)'),
              h('option', { value: 'custom' }, '✍️ Prompt Personalizado (Texto libre)'),
            ]),
          ]),
          benchPrompt === 'custom' ? h('div', { className: 'form-group' }, [
            h('label', { className: 'form-label' }, 'Texto del Prompt'),
            h('textarea', {
              className: 'form-input form-textarea',
              rows: 4,
              placeholder: 'Escribí el prompt de prueba...',
              value: customPromptText,
              onChange: (e) => setCustomPromptText(e.target.value)
            }),
          ]) : null,
          h('button', {
            className: 'btn btn-primary w-full py-3 text-sm font-semibold',
            onClick: handleBenchmark,
            disabled: benchLoading || !installedModels.length
          }, [
            h(Icon, { name: 'bolt', key: 'icon' }),
            h('span', { key: 'lbl' }, benchLoading ? '⏳ Ejecutando y midiendo telemetría...' : (benchPrompt === 'suite' ? '▶ Iniciar Suite Completa' : '▶ Ejecutar Test de Prompt')),
          ]),
        ]),
      ]),

      // Preset Prompts Catalog Preview
      h('div', { className: 'card col-span-2', key: 'bench-prompts-card' }, [
        h('div', { className: 'card-header flex justify-between items-center' }, [
          h('h3', { className: 'card-title' }, '📋 Suite Estándar de Prompts de Prueba'),
          h('span', { className: 'badge badge-accent' }, '5 pruebas predefinidas'),
        ]),
        h('div', { className: 'card-body' }, [
          h('div', { className: 'grid grid-cols-2 gap-3' },
            Object.entries(promptCatalog || {}).map(([k, p]) =>
              h('div', {
                key: k,
                className: `p-3 rounded-lg border cursor-pointer transition-all ${benchPrompt === k ? 'bg-surface-elevated border-primary' : 'border-subtle hover:border-muted'}`,
                onClick: () => setBenchPrompt(k),
              }, [
                h('div', { className: 'flex justify-between items-center mb-1' }, [
                  h('strong', { className: 'text-sm' }, p.title),
                  benchPrompt === k ? h('span', { className: 'badge badge-primary badge-sm' }, 'Seleccionado') : null,
                ]),
                h('p', { className: 'text-xs text-muted mb-2' }, p.description),
                h('div', { className: 'text-xs font-mono p-2 bg-base rounded border border-subtle text-secondary truncate' }, p.prompt),
              ])
            )
          ),
        ]),
      ]),
    ]),

    // Results & Telemetry View
    benchResult ? h('div', { className: 'card mb-6', key: 'bench-result-panel' }, [
      h('div', { className: 'card-header flex justify-between items-center' }, [
        h('div', null, [
          h('h3', { className: 'card-title' }, `📊 Resultados y Telemetría: ${benchResult.model}`),
          h('span', { className: 'text-xs text-muted' }, `Fecha: ${benchResult.timestamp || 'Reciente'}`),
        ]),
        h('span', { className: `badge ${benchResult.ok ? 'badge-success' : 'badge-danger'}` }, benchResult.ok ? '✓ Test Finalizado' : '✗ Falló'),
      ]),
      h('div', { className: 'card-body' }, [
        benchResult.ok ? (benchResult.suite_run ? h('div', { className: 'bench-suite-container' }, [
          // Suite Aggregated Metrics Banner
          h('div', { className: 'bench-suite-summary-header mb-4' }, [
            h('div', { className: 'bench-stats-grid grid-cols-3 gap-4 mb-2' }, [
              h('div', { className: 'bench-stat-item' }, [
                h('span', { className: 'bench-stat-label' }, '⚡ Velocidad Media'),
                h('span', { className: 'bench-stat-val text-primary' }, `${benchResult.summary?.avg_tokens_per_second} t/s`),
              ]),
              h('div', { className: 'bench-stat-item' }, [
                h('span', { className: 'bench-stat-label' }, '⏱️ Tiempo Total Suite'),
                h('span', { className: 'bench-stat-val' }, `${benchResult.summary?.total_duration_s} s`),
              ]),
              h('div', { className: 'bench-stat-item' }, [
                h('span', { className: 'bench-stat-label' }, '⏱️ TTFT Promedio'),
                h('span', { className: 'bench-stat-val' }, benchResult.summary?.avg_ttft_ms ? `${benchResult.summary.avg_ttft_ms} ms` : '—'),
              ]),
              h('div', { className: 'bench-stat-item' }, [
                h('span', { className: 'bench-stat-label' }, '💻 CPU Media / Pico'),
                h('span', { className: 'bench-stat-val text-warning' }, `${benchResult.summary?.avg_cpu_percent}% / ${benchResult.summary?.peak_cpu_percent}%`),
              ]),
              h('div', { className: 'bench-stat-item' }, [
                h('span', { className: 'bench-stat-label' }, '💾 RAM Media / Pico'),
                h('span', { className: 'bench-stat-val' }, `${benchResult.summary?.avg_ram_used_gb} GB / ${benchResult.summary?.peak_ram_used_gb} GB`),
              ]),
              h('div', { className: 'bench-stat-item' }, [
                h('span', { className: 'bench-stat-label' }, '🎮 VRAM / Backend'),
                h('span', { className: 'bench-stat-val' }, benchResult.resources?.vram_gb > 0 ? `${benchResult.resources.vram_gb} GB (${benchResult.resources.gpu_backend})` : `CPU (${benchResult.resources?.cpu_cores || 1} núcleos)`),
              ]),
            ]),
          ]),
          // Suite Individual Prompt Cards
          h('div', { className: 'bench-suite-list flex flex-col gap-3' },
            (benchResult.results || []).map((item, idx) => {
              const isExpanded = expandedPromptIdx === idx;
              return h('div', { key: idx, className: 'bench-suite-item' }, [
                h('div', {
                  className: 'bench-suite-item-header flex justify-between items-center cursor-pointer p-2',
                  onClick: () => setExpandedPromptIdx(isExpanded ? null : idx),
                }, [
                  h('div', { className: 'flex items-center gap-3' }, [
                    h('span', { className: item.ok ? 'text-success font-bold text-base' : 'text-danger font-bold text-base' }, item.ok ? '✓' : '✗'),
                    h('strong', { className: 'text-sm' }, item.prompt_title || `Prueba ${idx + 1}`),
                    h('span', { className: 'text-xs text-muted' }, `· ${item.tokens_per_second || 0} t/s · ${item.total_time_s || 0}s · ${item.eval_count || 0} tokens`),
                  ]),
                  h('div', { className: 'flex items-center gap-2' }, [
                    h('span', { className: 'badge badge-sm' }, `CPU ${item.resources?.cpu_percent ?? 0}%`),
                    h('span', { className: 'badge badge-sm' }, `RAM ${item.resources?.ram_used_gb ?? 0} GB`),
                    h('span', { className: 'text-xs text-muted' }, isExpanded ? '▲ Ocultar respuesta' : '▼ Ver respuesta'),
                  ]),
                ]),
                isExpanded ? h('div', { className: 'bench-suite-item-body mt-3 p-3 bg-base rounded border border-subtle' }, [
                  h('div', { className: 'text-xs text-muted mb-2 font-semibold' }, `PROMPT: ${item.prompt}`),
                  h('div', { className: 'bench-output' }, item.response || item.error || 'Sin respuesta'),
                ]) : null,
              ]);
            })
          ),
        ]) : h('div', null, [
          // Single Prompt Telemetry
          h('div', { className: 'grid grid-cols-2 gap-6 mb-4' }, [
            h('div', { className: 'p-4 bg-base rounded-lg border border-subtle' }, [
              h('h4', { className: 'text-xs font-bold uppercase text-muted mb-3' }, '⏱️ Medición de Tiempos & Inferencia'),
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
            ]),
            h('div', { className: 'p-4 bg-base rounded-lg border border-subtle' }, [
              h('h4', { className: 'text-xs font-bold uppercase text-muted mb-3' }, '💻 Recursos Consumidos'),
              h('div', { className: 'bench-stats-grid' }, [
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'CPU Utilizada'),
                  h('span', { className: 'bench-stat-val text-warning' }, `${benchResult.resources?.cpu_percent ?? 0}%`),
                ]),
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'RAM Sistema (Uso / Delta)'),
                  h('span', { className: 'bench-stat-val' }, `${benchResult.resources?.ram_used_gb ?? 0} GB (${(benchResult.resources?.ram_delta_mb || 0) > 0 ? '+' : ''}${benchResult.resources?.ram_delta_mb ?? 0} MB)`),
                ]),
                h('div', { className: 'bench-stat-item' }, [
                  h('span', { className: 'bench-stat-label' }, 'Tokens Generados'),
                  h('span', { className: 'bench-stat-val' }, `${benchResult.eval_count || 0} tokens`),
                ]),
              ]),
            ]),
          ]),
          h('div', { className: 'mt-3' }, [
            h('h4', { className: 'text-xs font-bold uppercase text-muted mb-2' }, `💬 Respuesta Generada (${benchResult.prompt_title || 'Prompt'}):`),
            h('div', { className: 'bench-output' }, benchResult.response),
          ]),
        ])) : h('div', { className: 'text-danger p-4' }, `Error en la prueba: ${benchResult.error}`),
      ]),
    ]) : null,
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
            'aria-label': 'Filtrar servidores',
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
                'aria-label': 'Filtrar herramientas del servidor seleccionado',
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
                          'aria-label': `Argumentos JSON para ${t.name}`,
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
            'aria-label': 'Idioma de la conversación',
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
          'aria-label': 'Mensaje para ADA',
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
            'aria-label': 'Nombre del asistente',
            value: config.name || '',
            onChange: (e) => setConfig({ ...config, name: e.target.value }),
          }),
        ]),
        h('div', { className: 'form-group' }, [
          h('label', { className: 'form-label' }, 'URL de Ollama Endpoint'),
          h('input', {
            type: 'text',
            className: 'form-input',
            'aria-label': 'URL del servicio Ollama',
            value: config.ollama_url || '',
            onChange: (e) => setConfig({ ...config, ollama_url: e.target.value }),
          }),
        ]),
        h('div', { className: 'form-group' }, [
          h('label', { className: 'form-label' }, 'Carpeta de Fotos (photo_root)'),
          h('input', {
            type: 'text',
            className: 'form-input',
            'aria-label': 'Carpeta de fotos',
            value: config.photo_root || '',
            onChange: (e) => setConfig({ ...config, photo_root: e.target.value }),
          }),
        ]),
        h('div', { className: 'form-group' }, [
          h('label', { className: 'form-label' }, 'Carpetas Permitidas (allowed_roots)'),
          h('input', {
            type: 'text',
            className: 'form-input',
            'aria-label': 'Carpetas permitidas',
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
                'aria-label': 'Tipo de secreto o servicio',
                value: selectedPreset,
                onChange: (e) => setSelectedPreset(e.target.value),
              }, [
                h('option', { value: 'telegram_bot_token' }, '📱 Telegram Bot Token (telegram_bot_token)'),
                h('option', { value: 'event_token' }, '⚡ Webhook Event Token (event_token)'),
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
                    'aria-label': 'Nombre de la clave personalizada',
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
                    'aria-label': 'Descripción opcional del secreto',
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
              'aria-label': 'Valor del secreto',
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
// Trigger sources: every external entry point into ADA
// =============================================================================
function TriggersView({ showToast, onSwitchTab }) {
  const [data, setData] = useState(null);
  const [busyId, setBusyId] = useState('');

  const refresh = useCallback(async () => {
    try {
      setData(await api.getTriggers());
    } catch (error) {
      showToast('No pude leer los disparadores: ' + error.message, 'danger');
    }
  }, [showToast]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, [refresh]);

  const control = async (trigger, action) => {
    setBusyId(trigger.id);
    try {
      const result = await api.controlTrigger(trigger.id, action);
      showToast(result.message || `${trigger.name}: ${action}`, 'success');
      await refresh();
    } catch (error) {
      showToast(`${trigger.name}: ${error.message}`, 'danger');
    } finally {
      setBusyId('');
    }
  };

  if (!data) return h('div', { className: 'initial-loader' }, [h('div', { className: 'loader-spinner' })]);
  const labels = {
    running: ['Activo', 'success'], starting: ['Iniciando', 'warning'], degraded: ['Conflicto', 'danger'], recovering: ['Recuperando', 'warning'], ready: ['Preparado', 'accent'],
    needs_config: ['Falta configurar', 'warning'], needs_adapter: ['Adaptador pendiente', 'warning'], stopped: ['Detenido', 'outline'],
  };
  const kindLabels = { channel: 'Canal', device: 'Dispositivo', schedule: 'Programación', event: 'Evento HTTP' };

  return h('section', { className: 'tab-view active triggers-view', id: 'tab-triggers' }, [
    h('div', { className: 'trigger-flow', key: 'flow', 'aria-label': 'Flujo de disparadores hacia ADA' }, [
      h('div', { className: 'trigger-flow-source' }, [
        h(Icon, { name: 'triggers', size: 20 }),
        h('div', { className: 'trigger-flow-copy' }, [
          h('strong', null, 'Entradas externas'),
          h('small', null, 'mensajes · eventos · horarios · dispositivos'),
        ]),
      ]),
      h('span', { className: 'trigger-flow-line', 'aria-hidden': 'true' }),
      h('div', { className: 'trigger-flow-gate' }, [
        h('strong', null, 'Cola de eventos'),
        h('span', null, 'autenticación · deduplicación · reintentos'),
      ]),
      h('span', { className: 'trigger-flow-line', 'aria-hidden': 'true' }),
      h('div', { className: 'trigger-flow-core' }, [h('strong', null, 'ADA'), h('span', null, 'decide y ejecuta')]),
    ]),
    h('div', { className: 'trigger-summary', key: 'summary' }, [
      h('div', null, [h('span', null, 'Fuentes previstas'), h('strong', null, data.counts?.total || 0)]),
      h('div', null, [h('span', null, 'Ejecutándose'), h('strong', null, data.counts?.running || 0)]),
      h('div', null, [h('span', null, 'Contratos listos'), h('strong', null, data.counts?.ready || 0)]),
    ]),
    h('div', { className: 'trigger-grid', key: 'grid' }, (data.triggers || []).map(trigger => {
      const status = labels[trigger.status] || [trigger.status || 'Desconocido', 'outline'];
      const isTelegram = trigger.id === 'telegram';
      const running = trigger.running === true;
      return h('article', { className: `trigger-card trigger-${trigger.status}`, key: trigger.id }, [
        h('div', { className: 'trigger-card-head' }, [
          h('span', { className: 'trigger-card-icon' }, h(Icon, { name: isTelegram ? 'telegram' : trigger.kind === 'schedule' ? 'activity' : 'triggers' })),
          h('div', null, [
            h('span', { className: 'trigger-kind' }, kindLabels[trigger.kind] || 'Disparador'),
            h('h3', null, trigger.name),
          ]),
          h('span', { className: `badge badge-${status[1]}` }, status[0]),
        ]),
        h('p', null, trigger.description),
        h('div', { className: 'trigger-runtime' }, [
          h('span', null, trigger.summary || 'Preparado para integrarse al bus de eventos'),
          isTelegram && trigger.pid ? h('code', null, `PID ${trigger.pid}`) : null,
          trigger.endpoint ? h('code', null, trigger.endpoint) : null,
        ]),
        isTelegram && trigger.last_error ? h('div', { className: 'trigger-warning', role: 'status' }, trigger.last_error) : null,
        h('div', { className: 'trigger-actions' }, isTelegram ? [
          h('button', {
            className: `btn btn-sm ${running ? 'btn-danger' : 'btn-primary'}`,
            disabled: busyId === trigger.id || (!running && !trigger.configured),
            onClick: () => control(trigger, running ? 'stop' : 'start'),
          }, busyId === trigger.id ? 'Procesando…' : running ? 'Detener' : 'Iniciar'),
          h('button', {
            className: 'btn btn-sm btn-secondary', disabled: busyId === trigger.id || !running,
            onClick: () => control(trigger, 'restart'),
          }, 'Reiniciar'),
          h('button', { className: 'btn btn-sm btn-ghost', onClick: () => onSwitchTab('telegram') }, 'Configurar'),
        ] : [
          h('span', { className: 'trigger-contract' }, 'Interfaz de entrada registrada'),
          trigger.id === 'webhook'
            ? h('button', { className: 'btn btn-sm btn-ghost', onClick: () => onSwitchTab('settings') }, 'Configurar credencial')
            : null,
        ]),
      ]);
    })),
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
  const isDegraded = status?.status === 'degraded';

  return h('section', { className: 'tab-view active', id: 'tab-telegram' }, [
    // 1. Control Bar Card
    h('div', { className: 'card mb-6', key: 'telegram-control-card' }, [
      h('div', { className: 'card-header' }, [
        h('div', { className: 'flex items-center gap-3' }, [
          h('span', { className: 'text-xl' }, '📱'),
          h('div', null, [
            h('div', { className: 'flex items-center gap-2' }, [
              h('h3', { className: 'card-title' }, 'Control del Servidor Telegram Bot'),
              h('span', { className: `badge ${isDegraded ? 'badge-danger' : isRunning ? 'badge-success' : 'badge-danger'}` },
                isDegraded ? 'Conflicto de listener' : isRunning ? 'En ejecución (Long-polling)' : 'Detenido'
              ),
            ]),
            h('p', { className: 'text-xs text-muted mt-1' },
              status?.survives_dashboard_restart
                ? 'Servicio independiente supervisado por ADA. Sigue activo aunque el dashboard se reinicie.'
                : 'Servicio de mensajería conectado a los endpoints de razonamiento de ADA.'
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

    isDegraded ? h('div', { className: 'trigger-warning mb-6', role: 'alert', key: 'telegram-health-warning' }, [
      h('strong', null, 'Telegram está ejecutándose, pero no está saludable. '),
      h('span', null, status.last_error || 'Revisá el log persistente del disparador.'),
    ]) : null,

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
          h('span', { className: `status-indicator ${isRunning && !isDegraded ? 'online' : 'offline'}` }),
        ]),
        h('div', { className: `stat-value ${isDegraded ? 'text-warning' : isRunning ? 'text-success' : 'text-muted'}` },
          isDegraded ? 'CONFLICTO' : isRunning ? 'ONLINE' : 'OFFLINE'),
        h('div', { className: 'stat-footer' }, isRunning
          ? `PID ${status.pid || '—'} · polling cada ${status.poll_seconds}s`
          : status?.desired_state === 'running' ? 'Recuperación automática pendiente' : 'Detenido desde el dashboard'),
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
            h('h3', { className: 'card-title' }, '💻 Servicio administrado por ADA'),
            h('span', { className: 'badge badge-primary' }, 'Persistente'),
          ]),
        ]),
        h('div', { className: 'card-body' }, [
          h('p', { className: 'text-sm text-muted mb-3' },
            'El dashboard controla el estado deseado, pero Telegram corre fuera del proceso web. Si el gestor se reinicia, ADA adopta el PID existente o lo recupera automáticamente si terminó.'
          ),
          h('pre', {
            className: 'p-4 rounded-lg bg-base font-mono text-xs text-secondary overflow-x-auto border border-subtle leading-relaxed',
            style: { background: '#0a0d14' }
          },
            `Estado deseado: ${status?.desired_state || 'stopped'}\nProceso: ${status?.pid ? `PID ${status.pid}` : 'sin proceso'}\nLog persistente: ${status?.log_path || '~/Desktop/ADA_Data/runtime/triggers/telegram.log'}`
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
  const validTabs = ['overview', 'core', 'benchmark', 'metrics', 'ollama', 'models', 'mcps', 'chat', 'triggers', 'telegram', 'memory', 'settings'];
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
  const [navigationOpen, setNavigationOpen] = useState(false);

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
    setNavigationOpen(false);
    window.history.replaceState(null, '', `#${tab}`);
  };

  const titles = {
    overview: ['Resumen', 'Estado y decisiones importantes de tu asistente local'],
    core: ['Núcleo ADA', 'Actividad en vivo de modelos, canales y herramientas'],
    benchmark: ['🧪 Tests de Prompts & Telemetría', 'Medición en vivo de velocidad, latencia, CPU, RAM y VRAM'],
    metrics: ['Métricas', 'Telemetría de ADA con retención de 7 días'],
    ollama: ['Motor local', 'Modelos instalados, consumo y configuración de inferencia'],
    models: ['Modelos y roles', 'Qué modelo usa ADA para cada tipo de tarea'],
    mcps: ['Herramientas', 'Capacidades e integraciones disponibles para ADA'],
    chat: ['Conversar con ADA', 'Probá solicitudes y revisá la respuesta del agente'],
    triggers: ['Disparadores', 'Todos los canales, eventos y horarios que pueden activar a ADA'],
    telegram: ['Telegram', 'Configuración y actividad del canal de mensajería'],
    memory: ['Actividad y memoria', 'Historial persistente, métricas y auditoría'],
    settings: ['Preferencias', 'Comportamiento, seguridad y credenciales del sistema'],
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
      isOpen: navigationOpen,
      onClose: () => setNavigationOpen(false),
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
        onOpenNavigation: () => setNavigationOpen(true),
      }),
      h('div', { className: 'content-container', key: 'content' }, [
        activeTab === 'overview' ? h(OverviewView, { statusData, onSwitchTab: selectTab, showToast, onRefresh: refreshAll }) : null,
        activeTab === 'core' ? h(CoreView, { onSwitchTab: selectTab }) : null,
        activeTab === 'benchmark' ? h(BenchmarkView, { installedModels: ollamaData.models || [], showToast }) : null,
        activeTab === 'metrics' ? h(MetricsView) : null,
        activeTab === 'ollama' ? h(OllamaView, { modelsData: ollamaData, statusData, onRefresh: refreshAll, showToast, onBenchmark: (m) => { selectTab('benchmark'); } }) : null,
        activeTab === 'models' ? h(ModelsView, { installedModels: ollamaData.models || [], showToast }) : null,
        activeTab === 'mcps' ? h(MCPsView, { showToast }) : null,
        activeTab === 'chat' ? h(ChatView, { showToast }) : null,
        activeTab === 'triggers' ? h(TriggersView, { showToast, onSwitchTab: selectTab }) : null,
        activeTab === 'telegram' ? h(TelegramView, { showToast }) : null,
        activeTab === 'memory' ? h(MemoryView, null) : null,
        activeTab === 'settings' ? h(SettingsView, { showToast }) : null,
      ]),
    ]),
    // Toast Container
    h('div', { className: 'toast-container', key: 'toasts', 'aria-live': 'polite', 'aria-atomic': 'false' },
      toasts.map(t => h('div', { className: `toast toast-${t.type}`, key: t.id, role: t.type === 'danger' ? 'alert' : 'status' }, t.msg))
    ),
  ]);
}

// Auto-mount on load
if (typeof window !== 'undefined') {
  const mountApp = () => {
    const rootElem = document.getElementById('root');
    if (rootElem && window.ReactDOM) {
      const root = window.ReactDOM.createRoot(rootElem);
      root.render(h(App));
    }
  };
  if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', mountApp, { once: true });
  else mountApp();
}
