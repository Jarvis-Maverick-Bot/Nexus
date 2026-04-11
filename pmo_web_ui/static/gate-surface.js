// static/gate-surface.js - gate interaction surface
// Extracted from index.html (RFC-2, gate surface extraction)

async function doLoadGate() {
    const taskId = document.getElementById('gate-task-id').value.trim();
    const out = document.getElementById('gate-output');
    if (!taskId) { _warn(out, 'Enter a task ID first.'); return; }
    _neutral(out, 'Loading…');
    const d = await _api('GET', '/gate/' + encodeURIComponent(taskId));
    if (!d.ok) { _err(out, d.message || 'Failed'); return; }

    const stages = ['INTAKE','BA','SA','DEV','QA','DONE'];
    const stageIdx = stages.indexOf(d.current_stage) || 1;

    out.innerHTML = `
      <div style="margin-bottom:0.75rem">
        <div style="font-size:0.95rem;font-weight:600;color:var(--text)">${_esc(d.task_title)}</div>
        <div style="font-size:0.75rem;color:var(--text-dim);margin-top:0.1rem">${_esc(d.task_id)}</div>
      </div>
      <div style="margin-bottom:0.75rem">
        ${stages.map((s, i) => {
          const done = i < stageIdx;
          const cur = i === stageIdx;
          return `<div style="display:inline-flex;flex-direction:column;align-items:center;gap:0.2rem;margin-right:0.5rem">
            <div style="width:28px;height:28px;border-radius:50%;border:2px solid ${done ? 'var(--green)' : cur ? 'var(--accent)' : 'var(--border-light)'};background:${done ? 'var(--green-bg)' : cur ? 'var(--accent-glow)' : 'var(--surface)'};display:flex;align-items:center;justify-content:center;font-size:0.75rem;color:${done ? 'var(--green)' : cur ? 'var(--accent)' : 'var(--text-muted)'}">${done ? '✓' : cur ? '→' : ''}</div>
            <div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;color:${done ? 'var(--green)' : cur ? 'var(--accent)' : 'var(--text-muted)'}">${s}</div>
          </div>` + (i < stages.length - 1 ? `<div style="display:inline-block;width:16px;height:2px;background:${i < stageIdx ? 'var(--green)' : 'var(--border)'};vertical-align:14px;margin-right:0.5rem"></div>` : '');
        }).join('')}
      </div>
      ${d.gate_status === 'pending' ? `
        <div class="form-row" style="margin-top:0.75rem">
          <div class="field" style="flex:2">
            <label>Decision note</label>
            <input id="gate-decision-note" placeholder="Note (optional)" />
          </div>
          <div style="display:flex;align-items:flex-end;gap:0.4rem">
            <button class="success sm" onclick="doApproveGate('${taskId}')">✓ Approve</button>
            <button class="danger sm" onclick="doRejectGate('${taskId}')">✗ Reject</button>
          </div>
        </div>
      ` : `<div class="output ${d.gate_status === 'APPROVED' ? 'ok' : 'error'}">Gate: ${d.gate_status}${d.decision_note ? ' — ' + _esc(d.decision_note) : ''}</div>`}
    `;
  }

  async function doApproveGate(taskId) {
    const note = document.getElementById('gate-decision-note')?.value.trim() || '';
    const actor = prompt('Your name:');
    if (!actor) return;
    const d = await _api('POST', '/gate/' + encodeURIComponent(taskId) + '/approve', {actor, note});
    if (d.ok) doLoadGate();
    else alert(d.message || 'Failed');
  }

  async function doRejectGate(taskId) {
    const note = document.getElementById('gate-decision-note')?.value.trim();
    if (!note) { alert('Rejection note is required.'); return; }
    const actor = prompt('Your name:');
    if (!actor) return;
    const d = await _api('POST', '/gate/' + encodeURIComponent(taskId) + '/reject', {actor, reason: note});
    if (d.ok) doLoadGate();
    else alert(d.message || 'Failed');
  }
