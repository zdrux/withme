(() => {
  const $ = (sel) => document.querySelector(sel);
  const tokenInput = $('#token');
  const authStatus = $('#authStatus');
  const agentsDiv = $('#agents');
  const agentDetail = $('#agentDetail');
  const scenariosDiv = $('#scenarios');
  const eventsDiv = $('#events');

  let TOKEN = localStorage.getItem('withme_token') || 'dev';
  let SELECTED_AGENT = null;
  tokenInput.value = TOKEN;

  function headers() {
    return { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' };
  }

  async function api(path, opts={}) {
    const res = await fetch(path, { ...opts, headers: { ...(opts.headers||{}), ...headers() } });
    if (!res.ok) {
      let msg = await res.text().catch(()=> '');
      throw new Error('HTTP '+res.status+': '+msg);
    }
    if (res.status === 204) return null;
    const ct = (res.headers.get('content-type')||'').toLowerCase();
    if (ct.includes('application/json')) {
      const txt = await res.text();
      return txt ? JSON.parse(txt) : null;
    }
    return res.text();
  }

  async function loadAgents() {
    agentsDiv.textContent = 'Loading...';
    try {
      const data = await api('/admin/agents');
      agentsDiv.innerHTML = '';
      const list = document.createElement('div');
      (data.items || []).forEach(a => {
        const row = document.createElement('div');
        row.className = 'item-row';
        row.innerHTML = `
          <div>
            <strong>${a.name}</strong> <small class="id">${a.id}</small><br/>
            mood=${a.mood?.toFixed?.(2) ?? a.mood} affinity=${a.affinity?.toFixed?.(2) ?? a.affinity}
          </div>
          <div>
            <button data-id="${a.id}" class="selectAgent">Open</button>
            <button data-id="${a.id}" class="deleteAgent danger">Delete</button>
          </div>
        `;
        list.appendChild(row);
      });
      agentsDiv.appendChild(list);
      agentsDiv.onclick = async (e) => {
        const btnOpen = e.target.closest('.selectAgent');
        const btnDel = e.target.closest('.deleteAgent');
        if (btnOpen) {
          const id = btnOpen.getAttribute('data-id');
          await openAgent(id);
        } else if (btnDel) {
          const id = btnDel.getAttribute('data-id');
          if (confirm('Delete this agent and all related data?')) {
            try {
              await api(`/admin/agents/${id}`, { method: 'DELETE' });
              if (SELECTED_AGENT === id) {
                SELECTED_AGENT = null;
                agentDetail.textContent = 'None selected';
                scenariosDiv.textContent = '';
                eventsDiv.textContent = '';
              }
              await loadAgents();
            } catch (err) {
              alert('Delete failed: ' + err.message);
            }
          }
        }
      };
    } catch (e) {
      agentsDiv.textContent = 'Error: ' + e.message;
    }
  }

  async function openAgent(id) {
    agentDetail.textContent = 'Loading...';
    SELECTED_AGENT = id;
    try {
      // Get agent snapshot (safe) and also load scenarios and events
      const snapshot = await api(`/admin/agents/${id}`);
      // Show editable fields using admin PATCH route (works with selected id)
      const editor = document.createElement('div');
      editor.innerHTML = `
        <div class="form-grid">
          <label>Name <input id="e_name" /></label>
          <label>Romance Allowed <input id="e_romance" type="checkbox" /></label>
          <label>Initiation <input id="e_init" type="number" min="0" max="1" step="0.05" /></label>
          <label>Image Threshold <input id="e_imgthr" type="number" min="0" max="1" step="0.05" /></label>
          <label>Mood <input id="e_mood" type="number" min="-1" max="1" step="0.05" /></label>
          <label>Affinity <input id="e_aff" type="number" min="0" max="1" step="0.01" /></label>
          <label>Timezone
            <select id="e_tz"></select>
          </label>
          <label>Home City <input id="e_city" placeholder="e.g., London" /></label>
          <label>Occupation <input id="e_job" placeholder="e.g., product manager" /></label>
        </div>
        <div class="form-row">
          <label>Base Image</label>
          <div id="e_baseimg_box"></div>
        </div>
        <label>Persona JSON <textarea id="e_persona" rows="12"></textarea></label>
        <div class="row">
          <button id="e_save">Save</button>
          <button id="e_delete" class="danger">Delete</button>
        </div>
      `;
      agentDetail.innerHTML = '';
      agentDetail.appendChild(editor);

      // Fill with data from list lookup
      $('#e_name').value = snapshot.name || '';
      $('#e_romance').checked = !!snapshot.romance_allowed;
      $('#e_init').value = (snapshot.initiation_tendency ?? 0.4);
      $('#e_imgthr').value = (snapshot.image_threshold ?? 0.6);
      $('#e_mood').value = (snapshot.mood ?? 0);
      $('#e_aff').value = (snapshot.affinity ?? 0.3);
      $('#e_persona').value = JSON.stringify(snapshot.persona || {}, null, 2);

      // Base image preview/link
      const box = document.getElementById('e_baseimg_box');
      box.innerHTML = '';
      if (snapshot.base_image_url) {
        const link = document.createElement('a');
        link.href = snapshot.base_image_url; link.textContent = 'Open image in new tab'; link.target = '_blank';
        const img = document.createElement('img');
        img.src = snapshot.base_image_url; img.alt = 'Base image'; img.className = 'base-image';
        box.appendChild(link);
        box.appendChild(document.createElement('br'));
        box.appendChild(img);
      } else {
        const note = document.createElement('div');
        note.className = 'help';
        note.textContent = 'No base image yet. Provide an Appearance Prompt and (re)generate to create one.';
        box.appendChild(note);
      }

      // Timezone & identity
      const TZ = [
        'UTC','America/New_York','America/Chicago','America/Denver','America/Los_Angeles',
        'Europe/London','Europe/Berlin','Europe/Paris','Europe/Madrid','Europe/Rome',
        'Asia/Tokyo','Asia/Seoul','Asia/Shanghai','Asia/Singapore','Asia/Kolkata',
        'Australia/Sydney','America/Toronto','America/Sao_Paulo'
      ];
      const tzSel = $('#e_tz');
      tzSel.innerHTML = TZ.map(z => `<option value="${z}">${z}</option>`).join('');
      tzSel.value = snapshot.timezone || 'UTC';
      $('#e_city').value = snapshot.persona?.home_city || '';
      $('#e_job').value = snapshot.persona?.occupation || '';

      $('#e_save').onclick = async () => {
        try {
          const personaObj = JSON.parse($('#e_persona').value || '{}');
          personaObj.home_city = $('#e_city').value || personaObj.home_city;
          personaObj.occupation = $('#e_job').value || personaObj.occupation;
          const payload = {
            name: $('#e_name').value,
            romance_allowed: $('#e_romance').checked,
            initiation_tendency: parseFloat($('#e_init').value),
            image_threshold: parseFloat($('#e_imgthr').value),
            mood: parseFloat($('#e_mood').value),
            affinity: parseFloat($('#e_aff').value),
            persona: personaObj,
            timezone: $('#e_tz').value,
          };
          await api(`/admin/agents/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
          alert('Saved');
          loadAgents();
        } catch (e) {
          alert('Save failed: ' + e.message);
        }
      };

      $('#e_delete').onclick = async () => {
        if (!confirm('Delete this agent and all related data?')) return;
        try {
          await api(`/admin/agents/${id}`, { method: 'DELETE' });
          SELECTED_AGENT = null;
          agentDetail.textContent = 'None selected';
          await loadAgents();
          scenariosDiv.textContent = '';
          eventsDiv.textContent = '';
        } catch (e) {
          alert('Delete failed: ' + e.message);
        }
      };

      await loadScenarios(SELECTED_AGENT);
      await loadEvents(SELECTED_AGENT);
    } catch (e) {
      agentDetail.textContent = 'Error: ' + e.message;
    }
  }

  async function loadScenarios(agentId) {
    scenariosDiv.textContent = 'Loading...';
    try {
      const items = await api(`/admin/scenarios${agentId ? ('?agent_id=' + encodeURIComponent(agentId)) : ''}`);
      const list = document.createElement('div');
      (items||[]).forEach(s => {
        const row = document.createElement('div');
        row.className = 'item-row';
        row.innerHTML = `
          <div>
            <strong>${s.track}</strong> ${s.title}<br/>
            progress=${(s.progress*100).toFixed(0)}%
          </div>
          <div>
            <button class="editScenario" data-id="${s.id}">Edit</button>
          </div>
        `;
        list.appendChild(row);
      });
      scenariosDiv.innerHTML = '';
      scenariosDiv.appendChild(list);

      scenariosDiv.onclick = (e) => {
        const btn = e.target.closest('.editScenario');
        if (!btn) return;
        const id = btn.getAttribute('data-id');
        const progress = prompt('Progress 0..1');
        if (progress == null) return;
        api(`/admin/scenarios/${id}`, { method:'PATCH', body: JSON.stringify({ progress: parseFloat(progress) }) })
          .then(() => loadScenarios(SELECTED_AGENT))
          .catch(err => alert('Update failed: '+err.message));
      };
    } catch (e) {
      scenariosDiv.textContent = 'Error: ' + e.message;
    }
  }

  async function loadEvents(agentId) {
    eventsDiv.textContent = 'Loading...';
    try {
      const items = await api(`/admin/events${agentId ? ('?agent_id=' + encodeURIComponent(agentId)) : ''}`);
      const list = document.createElement('div');
      (items||[]).forEach(ev => {
        const row = document.createElement('div');
        row.className = 'item-row';
        row.innerHTML = `
          <div>
            <strong>${ev.type}</strong> delta=${ev.mood_delta} <small>${ev.occurred_at}</small>
            <pre>${JSON.stringify(ev.payload, null, 2)}</pre>
          </div>
        `;
        list.appendChild(row);
      });
      eventsDiv.innerHTML = '';
      eventsDiv.appendChild(list);
    } catch (e) {
      eventsDiv.textContent = 'Error: ' + e.message;
    }
  }

  // Dialogs
  const createDlg = $('#createDlg');
  $('#openCreate').onclick = () => createDlg.showModal();
  $('#createCancel').onclick = () => createDlg.close();
  $('#createSubmit').onclick = async () => {
    try {
      const payload = {
        name: $('#createName').value || 'Daniel',
        romance_allowed: $('#createRomance').checked,
        initiation_tendency: parseFloat($('#createInit').value || '0.4'),
        persona: JSON.parse($('#createPersona').value || '{}'),
        appearance_prompt: $('#createAppearance').value || null,
      };
      await api('/admin', { method:'POST', body: JSON.stringify(payload) });
      createDlg.close();
      loadAgents();
    } catch (e) {
      alert('Create failed: ' + e.message);
    }
  };

  const generateDlg = $('#generateDlg');
  $('#openGenerate').onclick = () => generateDlg.showModal();
  $('#genCancel').onclick = () => generateDlg.close();
  // Prefill archetype presets and quick chips
  const ARCH_PRESETS = [
    'busy product manager in a big city, warm evenings',
    'graduate student in biology, thoughtful and introverted',
    'barista and part-time musician, playful and flirty',
    'nurse on night shifts, empathetic but tired mornings',
    'small-town bookshop owner, cozy and attentive',
    'software engineer into indie games, dry humor',
    'fitness trainer, high energy, encouraging',
    'single parent juggling work, grounded and caring',
    'art school senior, creative and spontaneous',
    'travel blogger between trips, curious and upbeat',
  ];
  const TRAIT_CHIPS = ['witty','grounded','curious','playful','attentive','ambitious','dry humor','empathetic','high energy','reserved'];
  const LIKE_CHIPS = ['coffee','long walks','indie music','sci-fi novels','bouldering','sushi','photo walks','jazz','cooking','hiking'];
  const DISLIKE_CHIPS = ['lateness','loud bars','spoilers','messy plans','ghosting','negativity'];

  function fillSelect(id, items) {
    const sel = document.querySelector(id);
    if (!sel) return;
    items.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
  }

  function makeChips(id, items, targetInputId) {
    const holder = document.querySelector(id);
    if (!holder) return;
    holder.innerHTML = '';
    items.forEach(v => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip';
      b.textContent = v;
      b.onclick = () => {
        const inp = document.querySelector(targetInputId);
        const arr = (inp.value || '').split(',').map(s=>s.trim()).filter(Boolean);
        if (!arr.includes(v)) arr.push(v);
        inp.value = arr.join(', ');
      };
      holder.appendChild(b);
    });
  }

  fillSelect('#genArchPreset', ARCH_PRESETS);
  makeChips('#traitChips', TRAIT_CHIPS, '#genTraits');
  makeChips('#likeChips', LIKE_CHIPS, '#genLikes');
  makeChips('#dislikeChips', DISLIKE_CHIPS, '#genDislikes');
  $('#genSubmit').onclick = async () => {
    try {
      const btn = $('#genSubmit');
      btn.disabled = true;
      const sp = document.createElement('span');
      sp.className = 'spinner';
      btn.appendChild(sp);
      const traits = ($('#genTraits').value || '').split(',').map(s => s.trim()).filter(Boolean);
      const likes = ($('#genLikes').value || '').split(',').map(s => s.trim()).filter(Boolean);
      const dislikes = ($('#genDislikes').value || '').split(',').map(s => s.trim()).filter(Boolean);
      const preset = ($('#genArchPreset').value || '').trim();
      const custom = ($('#genArch').value || '').trim();
      const archetype = custom || preset || '';
      const payload = {
        name: $('#genName').value || null,
        archetype: archetype || null,
        traits, likes, dislikes,
        romance_allowed: $('#genRomance').checked,
        initiation_tendency: parseFloat($('#genInit').value || '0.4'),
        image_threshold: parseFloat($('#genImageThr').value || '0.6'),
        appearance_prompt: $('#genAppearance').value || null,
      };
      await api('/admin/agent/generate', { method:'POST', body: JSON.stringify(payload) });
      generateDlg.close();
      loadAgents();
    } catch (e) {
      alert('Generate failed: ' + e.message);
    } finally {
      const btn = $('#genSubmit');
      btn.disabled = false;
      const sp = btn.querySelector('.spinner');
      if (sp) sp.remove();
    }
  };

  $('#refreshAgents').onclick = loadAgents;
  $('#saveToken').onclick = () => {
    TOKEN = tokenInput.value || 'dev';
    localStorage.setItem('withme_token', TOKEN);
    authStatus.textContent = 'Token updated.';
    loadAgents();
  };

  // Initial load
  loadAgents();
})();
