// static/utils.js - pure UI helpers
// Extracted from index.html (RFC-2 slice 1)

function _esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

function _ts(o) {
    if (!o) return '—';
    return new Date(o).toLocaleString();
  }

function _fmt(o) {
    if (o == null) return '—';
    if (typeof o === 'object') return JSON.stringify(o, null, 2);
    return String(o);
  }

function _ok(el, msg) { el.className='output ok'; el.textContent=msg; }

function _err(el, msg) { el.className='output error'; el.textContent=msg; }

function _warn(el, msg) { el.className='output warn'; el.textContent=msg; }

function _neutral(el, msg) { el.className='output'; el.textContent=msg; }

function _badgeClass(status) {
    const map = {active:'badge-active', on_hold:'badge-hold', closed:'badge-closed', shutdown:'badge-shutdown'};
    return map[status] || 'badge-closed';
  }

function escHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

