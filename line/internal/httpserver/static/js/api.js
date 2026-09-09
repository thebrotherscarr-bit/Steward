// ATLAS API Client — wraps HTTP endpoints
const API = {
  async health() {
    const r = await fetch('/health');
    return r.json();
  },

  async tools() {
    const r = await fetch('/tools');
    return r.json();
  },

  async rpc(method, params = {}) {
    const r = await fetch('/rpc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: Date.now(),
        method: 'tools/call',
        params: { name: method, arguments: params }
      })
    });
    const data = await r.json();
    if (data.error) throw new Error(data.error.message);
    if (data.result && data.result.isError) {
      throw new Error(data.result.content[0].text);
    }
    return data.result?.content?.[0]?.text || '';
  },

  async toolCall(name, args = {}) {
    return this.rpc(name, args);
  }
};

// Toast notifications
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 3000);
}

// Format time relative
function timeAgo(date) {
  const s = Math.floor((Date.now() - date) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`;
  return `${Math.floor(s/86400)}d ago`;
}

// SHA-256 hash for chain verification
async function sha256(str) {
  const encoder = new TextEncoder();
  const data = encoder.encode(str);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}
