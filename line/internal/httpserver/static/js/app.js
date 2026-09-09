// ATLAS App — SPA router and pages
const App = {
  currentPage: 'dashboard',
  data: { health: null, tools: null },

  init() {
    this.router();
    window.addEventListener('popstate', () => this.router());
    document.querySelectorAll('.nav a').forEach(a => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        history.pushState(null, '', a.href);
        this.router();
      });
    });
    this.loadVersion();
    this.pollHealth();
  },

  router() {
    const path = location.pathname.slice(1) || 'dashboard';
    this.currentPage = path;
    document.querySelectorAll('.nav a').forEach(a => {
      a.classList.toggle('active', a.dataset.page === path);
    });
    this.render();
  },

  async loadVersion() {
    try {
      const h = await API.health();
      document.getElementById('version').textContent = h.version;
    } catch {}
  },

  async pollHealth() {
    try {
      this.data.health = await API.health();
      document.getElementById('operator-status').textContent = 'active';
    } catch {
      document.getElementById('operator-status').textContent = 'offline';
    }
    setTimeout(() => this.pollHealth(), 5000);
  },

  async render() {
    const el = document.getElementById('content');
    switch (this.currentPage) {
      case 'dashboard': await this.renderDashboard(el); break;
      case 'manjuel': await this.renderChain(el); break;
      case 'agents': await this.renderAgents(el); break;
      case 'rbac': await this.renderRBAC(el); break;
      case 'trust': await this.renderTrust(el); break;
      case 'tools': await this.renderTools(el); break;
      default: el.innerHTML = '<div class="empty"><div class="empty-icon">?</div>Page not found</div>';
    }
  },

  async renderDashboard(el) {
    el.innerHTML = '<div class="loading">Loading dashboard...</div>';
    try {
      const [health, toolsData] = await Promise.all([
        API.health(),
        API.tools()
      ]);
      this.data.health = health;
      this.data.tools = toolsData;

      let tenants = '—';
      let chainStatus = '—';
      try {
        const t = await API.toolCall('tenant_list');
        const match = t.match(/(\d+) carried/);
        tenants = match ? match[1] : '—';
      } catch {}

      el.innerHTML = `
        <h2 style="margin-bottom:24px">Dashboard</h2>
        <div class="stats">
          <div class="stat">
            <div class="stat-label">Health</div>
            <div class="stat-value green">${health.status}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Version</div>
            <div class="stat-value blue">${health.version}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Tools</div>
            <div class="stat-value">${toolsData.tools.length}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Tenants</div>
            <div class="stat-value">${tenants}</div>
          </div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">System Status</span>
          </div>
          <table>
            <tr><td>Server</td><td>${health.server}</td></tr>
            <tr><td>Protocol</td><td>MCP 2025-06-18</td></tr>
            <tr><td>Covenant</td><td><code>1512741580b7239b</code></td></tr>
            <tr><td>Forbidden verbs</td><td><span class="badge badge-green">absent by construction</span></td></tr>
            <tr><td>can_approve</td><td><span class="badge badge-green">false (structural)</span></td></tr>
          </table>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Available Tools</span>
          </div>
          <table>
            <thead><tr><th>Name</th><th>Description</th><th>Writes</th></tr></thead>
            <tbody>
              ${toolsData.tools.map(t => `
                <tr>
                  <td><code>${t.name}</code></td>
                  <td>${t.description.slice(0, 60)}${t.description.length > 60 ? '...' : ''}</td>
                  <td>${t.name.startsWith('mesh_') || t.name === 'remember' || t.name === 'ask_steward' || t.name === 'tenant_rbac_assign' || t.name === 'tenant_trust' ? '<span class="badge badge-yellow">yes</span>' : '<span class="badge badge-muted">no</span>'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>Failed to load: ${e.message}</div>`;
    }
  },

  async renderChain(el) {
    el.innerHTML = '<div class="loading">Loading chain...</div>';
    try {
      const log = await API.toolCall('read_handoffs');
      const lines = log.split('\n').filter(l => l.trim());

      el.innerHTML = `
        <h2 style="margin-bottom:24px">Chain Viewer</h2>
        <div class="card">
          <div class="card-header">
            <span class="card-title">SEAT_LOG entries</span>
            <button class="btn" onclick="App.verifyChain()">Verify</button>
          </div>
          <div id="chain-result"></div>
          <div class="chain" id="chain-timeline">
            ${lines.slice(-20).reverse().map((line, i) => `
              <div class="chain-entry" data-n="${lines.length - i}">
                <div class="chain-entry-header">
                  <span class="chain-entry-n">n=${lines.length - i}</span>
                  <span class="chain-entry-time">${line.slice(0, 10)}</span>
                </div>
                <div class="chain-entry-kind">${line.slice(11, 20).trim()}</div>
                <div style="font-size:12px">${line.slice(22)}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>Failed to load chain: ${e.message}</div>`;
    }
  },

  async verifyChain() {
    const result = document.getElementById('chain-result');
    result.innerHTML = '<div class="loading">Verifying chain...</div>';
    try {
      const v = await API.toolCall('verify_chain');
      const intact = v.includes('INTACT');
      result.innerHTML = `<div class="badge ${intact ? 'badge-green' : 'badge-red'}">${intact ? 'INTACT' : 'TAMPERED'}</div> ${v}`;
    } catch (e) {
      result.innerHTML = `<div class="badge badge-red">ERROR</div> ${e.message}`;
    }
  },

  async renderAgents(el) {
    el.innerHTML = '<div class="loading">Loading agents...</div>';
    try {
      const muster = await API.toolCall('muster');
      const lines = muster.split('\n').filter(l => l.includes(':'));

      el.innerHTML = `
        <h2 style="margin-bottom:24px">Agent Manager</h2>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Enrolled Agents</span>
            <span class="badge badge-blue">${lines.length} agents</span>
          </div>
          <table>
            <thead><tr><th>Agent</th><th>Role</th><th>Status</th></tr></thead>
            <tbody>
              ${lines.map(l => {
                const [agent, role] = l.split(':').map(s => s.trim());
                return `<tr>
                  <td><code>${agent}</code></td>
                  <td>${role || '—'}</td>
                  <td><span class="badge badge-green">enrolled</span></td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>Failed to load agents: ${e.message}</div>`;
    }
  },

  async renderRBAC(el) {
    el.innerHTML = '<div class="loading">Loading RBAC...</div>';
    try {
      const roles = [
        { name: 'operator', desc: 'the hand; holds the gate', perms: ['read:allow', 'edit:allow', 'bash:deny', 'net:deny', 'tools:allow'] },
        { name: 'steward', desc: 'plans, specs, keeps THE_ROAD', perms: ['read:allow', 'edit:allow', 'bash:deny', 'net:deny', 'tools:allow'] },
        { name: 'agent', desc: 'a declared seat with limited scope', perms: ['read:allow', 'edit:deny', 'bash:deny', 'net:deny', 'tools:allow'] },
        { name: 'guest', desc: 'unauthenticated; deny all', perms: ['read:deny', 'edit:deny', 'bash:deny', 'net:deny', 'tools:deny'] }
      ];

      el.innerHTML = `
        <h2 style="margin-bottom:24px">RBAC Panel</h2>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Roles</span>
          </div>
          <table>
            <thead><tr><th>Role</th><th>Description</th><th>Permissions</th></tr></thead>
            <tbody>
              ${roles.map(r => `
                <tr>
                  <td><code>${r.name}</code></td>
                  <td>${r.desc}</td>
                  <td>${r.perms.map(p => {
                    const [tool, mode] = p.split(':');
                    return `<span class="badge ${mode === 'allow' ? 'badge-green' : 'badge-red'}">${tool}:${mode}</span>`;
                  }).join(' ')}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Assign Role</span>
          </div>
          <div style="display:flex;gap:8px;margin-bottom:12px">
            <input id="rbac-agent" placeholder="agent ID" style="flex:1;padding:6px 12px;background:var(--atlas-bg);border:1px solid var(--atlas-border);border-radius:var(--atlas-radius);color:var(--atlas-text);font-family:var(--atlas-font)">
            <select id="rbac-role" style="padding:6px 12px;background:var(--atlas-bg);border:1px solid var(--atlas-border);border-radius:var(--atlas-radius);color:var(--atlas-text);font-family:var(--atlas-font)">
              ${roles.map(r => `<option value="${r.name}">${r.name}</option>`).join('')}
            </select>
            <button class="btn btn-primary" onclick="App.assignRole()">Assign</button>
          </div>
          <div id="rbac-result"></div>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>Failed to load RBAC: ${e.message}</div>`;
    }
  },

  async assignRole() {
    const agent = document.getElementById('rbac-agent').value.trim();
    const role = document.getElementById('rbac-role').value;
    const result = document.getElementById('rbac-result');
    if (!agent) { toast('Enter an agent ID', 'error'); return; }
    try {
      const r = await API.toolCall('tenant_rbac_assign', { actor: agent, role });
      result.innerHTML = `<div class="badge badge-green">OK</div> ${r}`;
      toast(r);
    } catch (e) {
      result.innerHTML = `<div class="badge badge-red">ERROR</div> ${e.message}`;
      toast(e.message, 'error');
    }
  },

  async renderTrust(el) {
    el.innerHTML = `
      <h2 style="margin-bottom:24px">Trust View</h2>
      <div class="card">
        <div class="card-header">
          <span class="card-title">Cross-Tenant Trust</span>
        </div>
        <div class="empty">
          <div class="empty-icon">&#x1f517;</div>
          <p>No trust relationships configured.</p>
          <p style="margin-top:8px;font-size:11px">Use <code>tenant_trust</code> to grant/revoke tool delegation between tenants.</p>
        </div>
      </div>
    `;
  },

  async renderTools(el) {
    el.innerHTML = '<div class="loading">Loading tools...</div>';
    try {
      const data = await API.tools();
      el.innerHTML = `
        <h2 style="margin-bottom:24px">Tool Surface</h2>
        <div class="card">
          <div class="card-header">
            <span class="card-title">${data.tools.length} tools registered</span>
          </div>
          <table>
            <thead><tr><th>Name</th><th>Description</th><th>Arguments</th></tr></thead>
            <tbody>
              ${data.tools.map(t => `
                <tr>
                  <td><code>${t.name}</code></td>
                  <td>${t.description}</td>
                  <td><code>${Object.keys(t.inputSchema?.properties || {}).join(', ')}</code></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>Failed to load tools: ${e.message}</div>`;
    }
  }
};

document.addEventListener('DOMContentLoaded', () => App.init());
