/**
 * RecycleBot frontend — mobile-responsive SPA
 * All API calls go to /api/* (same origin; proxied by FastAPI).
 */

const API = '';   // same-origin; set to 'http://localhost:8000' for dev

// ── User identity ────────────────────────────────────────────────────────────
function _lsGet(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }
function _lsSet(key, val) { try { localStorage.setItem(key, val); } catch (_) {} }

let userId = _lsGet('recyclebot_user_id');
if (!userId) {
  userId = (crypto.randomUUID ?? (() =>
    'u-' + Math.random().toString(36).slice(2) + Date.now().toString(36)))();
  _lsSet('recyclebot_user_id', userId);
}
const headers = () => ({ 'X-User-Id': userId, 'Content-Type': 'application/json' });
const headersNoBody = () => ({ 'X-User-Id': userId });

// ── App state ────────────────────────────────────────────────────────────────
let currentScanResult = null;   // ScanResult from /api/scan
let currentItemIndex  = 0;
let currentRegion     = _lsGet('recyclebot_region') || 'GLOBAL';
let currentLanguage   = _lsGet('recyclebot_lang')   || detectBrowserLanguage();
let chatHistory       = [];     // [{role, content}]
let currentItemForChat = null;  // the DetectedItem we're chatting about

// ── Translations ─────────────────────────────────────────────────────────────
const T = {
  en: {
    navScan:         '📷 Scan',
    navHistory:      '📊 History',
    navSettings:     '⚙️ Settings',
    noLocation:      '📍 No location set — tap to set your region',
    changeLocation:  'Change',
    scanHint:        'Tap to photograph or upload a waste item',
    scanSubhint:     'JPG or PNG, max 15 MB',
    addPhoto:        '📷 Add Photo',
    backBtn:         '← New Scan',
    chatBackBtn:     '← Results',
    chatTitle:       '💬 Ask RecycleBot',
    chatPlaceholder: 'Ask about this item…',
    chatSend:        'Send',
    disclaimer:      '⚠️ AI-generated — disposal instructions may contain errors. Always verify with your local waste authority.',
    disclaimerSmall: '⚠️ AI-generated — may contain errors.',
    askBtn:          '💬 Ask RecycleBot',
    historyTitle:    '📊 My Recycling Impact',
    itemsScanned:    'Items Scanned',
    co2Saved:        'kg CO₂ Saved',
    energySaved:     'kWh Saved',
    noHistory:       'No scan history yet.\nScan your first item to start tracking your impact!',
    settingsTitle:   '⚙️ Settings',
    locationLabel:   '📍 Location',
    gpsBtn:          '🛰️ GPS',
    saveLocation:    'Save Location',
    languageLabel:   '🌐 Language',
    saveLanguage:    'Save Language',
    privacyLabel:    '🔒 Data & Privacy',
    saveHistory:     'Save scan history',
    privacyNote:     'Images are never stored. With history enabled, only item name, material, category, and date are saved locally (GDPR compliant).',
    dataLabel:       '🗑️ Data Management',
    clearHistory:    'Clear All History',
    toastLangSaved:  'Language saved.',
    toastLocSaved:   'Location saved.',
  },
  de: {
    navScan:         '📷 Scannen',
    navHistory:      '📊 Verlauf',
    navSettings:     '⚙️ Einstellungen',
    noLocation:      '📍 Kein Standort — tippen zum Festlegen',
    changeLocation:  'Ändern',
    scanHint:        'Tippen, um ein Abfallobjekt zu fotografieren oder hochzuladen',
    scanSubhint:     'JPG oder PNG, max. 15 MB',
    addPhoto:        '📷 Foto hinzufügen',
    backBtn:         '← Neuer Scan',
    chatBackBtn:     '← Ergebnisse',
    chatTitle:       '💬 RecycleBot fragen',
    chatPlaceholder: 'Frage zu diesem Objekt…',
    chatSend:        'Senden',
    disclaimer:      '⚠️ KI-generiert — Entsorgungshinweise können Fehler enthalten. Bitte bei der lokalen Abfallbehörde überprüfen.',
    disclaimerSmall: '⚠️ KI-generiert — kann Fehler enthalten.',
    askBtn:          '💬 RecycleBot fragen',
    historyTitle:    '📊 Mein Recycling-Einfluss',
    itemsScanned:    'Gescannte Objekte',
    co2Saved:        'kg CO₂ gespart',
    energySaved:     'kWh gespart',
    noHistory:       'Noch kein Scanverlauf.\nScanne dein erstes Objekt!',
    settingsTitle:   '⚙️ Einstellungen',
    locationLabel:   '📍 Standort',
    gpsBtn:          '🛰️ GPS',
    saveLocation:    'Standort speichern',
    languageLabel:   '🌐 Sprache',
    saveLanguage:    'Sprache speichern',
    privacyLabel:    '🔒 Daten & Datenschutz',
    saveHistory:     'Scanverlauf speichern',
    privacyNote:     'Bilder werden nie gespeichert. Mit aktiviertem Verlauf werden nur Name, Material, Kategorie und Datum lokal gespeichert (DSGVO-konform).',
    dataLabel:       '🗑️ Datenverwaltung',
    clearHistory:    'Gesamten Verlauf löschen',
    toastLangSaved:  'Sprache gespeichert.',
    toastLocSaved:   'Standort gespeichert.',
  },
};

function t(key) {
  const lang = (currentLanguage || 'en').startsWith('de') ? 'de' : 'en';
  return T[lang]?.[key] ?? T['en'][key] ?? key;
}

function applyLanguage() {
  const q = id => document.getElementById(id);
  const qs = sel => document.querySelectorAll(sel);

  // Nav
  const navBtns = qs('.nav-btn[data-view]');
  const navKeys = { scan: 'navScan', history: 'navHistory', settings: 'navSettings' };
  navBtns.forEach(btn => {
    const key = navKeys[btn.dataset.view];
    if (key) btn.textContent = t(key);
  });

  // Location bar
  const locText = q('locationText');
  if (locText && (currentRegion === 'GLOBAL' || !currentRegion)) {
    locText.textContent = t('noLocation');
  }
  const changeBtn = q('changeLocationBtn');
  if (changeBtn) changeBtn.textContent = t('changeLocation');

  // Scan zone
  const hint = document.querySelector('.scan-hint');
  if (hint) hint.textContent = t('scanHint');
  const subhint = document.querySelector('.scan-subhint');
  if (subhint) subhint.textContent = t('scanSubhint');
  const addPhoto = q('addPhotoBtn');
  if (addPhoto) addPhoto.textContent = t('addPhoto');

  // Results view
  const backBtn = q('backBtn');
  if (backBtn) backBtn.textContent = t('backBtn');
  const chatBtn = q('chatBtn');
  if (chatBtn) chatBtn.textContent = t('askBtn');
  const disclaimers = document.querySelectorAll('.disclaimer:not(.small)');
  disclaimers.forEach(el => { el.innerHTML = `${t('disclaimer')}`; });
  const disclaimerSmalls = document.querySelectorAll('.disclaimer.small');
  disclaimerSmalls.forEach(el => { el.textContent = t('disclaimerSmall'); });

  // Chat view
  const chatBackBtn = q('chatBackBtn');
  if (chatBackBtn) chatBackBtn.textContent = t('chatBackBtn');
  const chatTitle = document.querySelector('.chat-title');
  if (chatTitle) chatTitle.textContent = t('chatTitle');
  const chatInput = q('chatInput');
  if (chatInput) chatInput.placeholder = t('chatPlaceholder');
  const chatSendBtn = q('chatSendBtn');
  if (chatSendBtn) chatSendBtn.textContent = t('chatSend');

  // History view
  const histTitle = document.querySelector('#historyView .section-title');
  if (histTitle) histTitle.textContent = t('historyTitle');
  const impactLabels = document.querySelectorAll('.impact-label');
  const labelKeys = ['itemsScanned', 'co2Saved', 'energySaved'];
  impactLabels.forEach((el, i) => { if (labelKeys[i]) el.textContent = t(labelKeys[i]); });

  // Settings view
  const settTitle = document.querySelector('#settingsView .section-title');
  if (settTitle) settTitle.textContent = t('settingsTitle');
  const settGroups = document.querySelectorAll('#settingsView .settings-label');
  const settKeys = ['locationLabel', 'languageLabel', 'privacyLabel', 'dataLabel'];
  settGroups.forEach((el, i) => { if (settKeys[i]) el.textContent = t(settKeys[i]); });
  const gpsBtn = q('gpsBtn');
  if (gpsBtn) gpsBtn.textContent = t('gpsBtn');
  const saveLocBtn = q('saveLocationBtn');
  if (saveLocBtn) saveLocBtn.textContent = t('saveLocation');
  const saveLangBtn = q('saveLanguageBtn');
  if (saveLangBtn) saveLangBtn.textContent = t('saveLanguage');
  const saveHistSpan = document.querySelector('.toggle-row span');
  if (saveHistSpan) saveHistSpan.textContent = t('saveHistory');
  const privNote = document.querySelector('.settings-note');
  if (privNote) privNote.innerHTML = t('privacyNote').replace('never stored', '<strong>never stored</strong>');
  const clearBtn = q('clearHistoryBtn');
  if (clearBtn) clearBtn.textContent = t('clearHistory');

  // Language select stays in sync
  const langSel = q('languageSelect');
  if (langSel) {
    const lang = (currentLanguage || 'en').startsWith('de') ? 'de' : 'en';
    langSel.value = lang;
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Bind all UI first so buttons work immediately, even if backend is slow
  populateCountrySelects();
  bindNavigation();
  bindScanZone();
  bindResultsView();
  bindChatView();
  bindSettingsView();
  bindLocationBar();
  bindModals();
  updateLocationBar();

  await loadSettings();
  applyLanguage();

  // Cold-start: if no location set, show modal (design decision #2, Req22)
  if (currentRegion === 'GLOBAL') {
    setTimeout(() => showLocationModal(), 500);
  }
});

// ── Navigation ────────────────────────────────────────────────────────────────
function bindNavigation() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      showView(btn.dataset.view);
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById(name + 'View');
  if (target) { target.classList.remove('hidden'); target.classList.add('active'); }

  if (name === 'history') loadHistory();
}

// ── Scan zone ─────────────────────────────────────────────────────────────────
function bindScanZone() {
  const zone        = document.getElementById('scanZone');
  const fileInput   = document.getElementById('fileInput');
  const addPhotoBtn = document.getElementById('addPhotoBtn');

  const openPicker = () => fileInput.click();

  addPhotoBtn.addEventListener('click', openPicker);
  zone.addEventListener('click', openPicker);
  zone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
  });

  fileInput.addEventListener('change', async e => {
    const file = e.target.files?.[0];
    if (!file) return;
    fileInput.value = '';
    await handleImageFile(file);
  });
}

async function handleImageFile(file) {
  // Show preview in scan zone canvas
  const canvas = document.getElementById('previewCanvas');
  const placeholder = document.getElementById('scanPlaceholder');
  const img = await loadImageFromFile(file);
  canvas.width  = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  canvas.style.display = 'block';
  placeholder.style.display = 'none';

  await runScan(file, img);
}

async function runScan(file, imgEl) {
  showLoading('Detecting items…');
  hideError();

  const formData = new FormData();
  formData.append('file', file, file.name);

  let result;
  try {
    const resp = await fetch(`${API}/api/scan`, {
      method: 'POST',
      headers: headersNoBody(),
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${resp.status}`);
    }
    result = await resp.json();
  } catch (e) {
    hideLoading();
    showError(e.message);
    return;
  }

  if (result.no_items_found || result.items.length === 0) {
    hideLoading();
    showError('No recyclable items detected. Try a clearer photo or a different angle.');
    return;
  }

  currentScanResult = result;
  currentItemIndex  = 0;

  // Draw bounding boxes on result canvas
  const resultCanvas = document.getElementById('resultCanvas');
  resultCanvas.width  = result.image_width;
  resultCanvas.height = result.image_height;
  const ctx = resultCanvas.getContext('2d');
  ctx.drawImage(imgEl, 0, 0, result.image_width, result.image_height);
  drawBoundingBoxes(ctx, result.items);

  // Build item tabs
  buildItemTabs(result.items);

  // Warnings
  const wb = document.getElementById('warningBanner');
  const wt = document.getElementById('warningText');
  if (result.clutter_warning) {
    wt.textContent = '⚠️ Items are very close together — detection may be inaccurate. Try separating them.';
    wb.classList.remove('hidden');
  } else if (result.has_low_confidence) {
    wt.textContent = '⚠️ Some items could not be identified with high confidence. A clearer photo may help.';
    wb.classList.remove('hidden');
  } else {
    wb.classList.add('hidden');
  }

  // Fetch instructions for first item
  await selectItem(0);

  hideLoading();
  showResultsView();
}

// ── Bounding boxes ────────────────────────────────────────────────────────────
const BOX_COLORS = ['#40916C', '#4895EF', '#F4A261', '#E63946', '#9B5DE5', '#F9C74F'];

function drawBoundingBoxes(ctx, items) {
  items.forEach((item, i) => {
    const color = BOX_COLORS[i % BOX_COLORS.length];
    const { x, y, width, height } = item.bbox;
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.strokeRect(x, y, width, height);

    // Label background
    const label = `${item.item_name} ${Math.round(item.confidence * 100)}%`;
    ctx.font = 'bold 14px sans-serif';
    const tw = ctx.measureText(label).width + 10;
    const ty = Math.max(y - 24, 0);
    ctx.fillStyle = color;
    ctx.fillRect(x, ty, tw, 22);
    ctx.fillStyle = '#fff';
    ctx.fillText(label, x + 5, ty + 15);
  });
}

// ── Item tabs & detail ────────────────────────────────────────────────────────
function buildItemTabs(items) {
  const tabs = document.getElementById('itemTabs');
  tabs.innerHTML = '';
  items.forEach((item, i) => {
    const btn = document.createElement('button');
    btn.className = 'item-tab' + (item.material_uncertain ? ' uncertain' : '') + (i === 0 ? ' active' : '');
    btn.textContent = item.item_name;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
    btn.addEventListener('click', () => selectItem(i));
    tabs.appendChild(btn);
  });
}

async function selectItem(index) {
  currentItemIndex = index;
  const items = currentScanResult?.items || [];
  const item  = items[index];
  if (!item) return;

  // Update tab active state
  document.querySelectorAll('.item-tab').forEach((t, i) => {
    t.classList.toggle('active', i === index);
    t.setAttribute('aria-selected', i === index ? 'true' : 'false');
  });

  // Highlight the bbox on the canvas
  const resultCanvas = document.getElementById('resultCanvas');
  const ctx = resultCanvas.getContext('2d');
  // Redraw all boxes, highlight selected
  const img = document.getElementById('previewCanvas');
  ctx.drawImage(img, 0, 0, resultCanvas.width, resultCanvas.height);
  items.forEach((it, i) => {
    const color = i === index ? '#FFFFFF' : BOX_COLORS[i % BOX_COLORS.length];
    const lw = i === index ? 4 : 2;
    ctx.strokeStyle = BOX_COLORS[i % BOX_COLORS.length];
    ctx.lineWidth = lw;
    ctx.strokeRect(it.bbox.x, it.bbox.y, it.bbox.width, it.bbox.height);
    if (i === index) {
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(it.bbox.x - 2, it.bbox.y - 2, it.bbox.width + 4, it.bbox.height + 4);
      ctx.setLineDash([]);
    }
  });

  // Show instructions or loading skeleton in detail panel
  const panel = document.getElementById('itemDetail');
  panel.innerHTML = renderItemSkeleton(item);

  if (item.material_uncertain && !item._manual_material) {
    // Offer manual material selection (SUC3, design decision #7)
    appendManualSelectButton(panel, index);
    return;
  }

  // Fetch disposal instructions
  const material = item._manual_material || item.material || 'Unknown';
  const params = new URLSearchParams({
    item: item.item_name,
    material,
    region: currentRegion,
    lang: currentLanguage,
  });
  try {
    const resp = await fetch(`${API}/api/instructions?${params}`, { headers: headersNoBody() });
    if (resp.ok) {
      const inst = await resp.json();
      item._instructions = inst;
      renderItemDetail(panel, item, inst);
    }
  } catch (e) {
    panel.innerHTML += `<p style="color:var(--red)">Could not load instructions. Check your connection.</p>`;
  }
}

function renderItemSkeleton(item) {
  const conf = Math.round(item.confidence * 100);
  const level = conf >= 80 ? 'high' : conf >= 50 ? 'medium' : 'low';
  return `
    <div class="item-header">
      <h3 class="item-name">${esc(item.item_name)}</h3>
      <div class="certainty-wrap" title="Detection confidence: ${conf}%">
        <span class="certainty-label">Certainty</span>
        <div class="certainty-bar"><div class="certainty-fill ${level}" style="width:${conf}%"></div></div>
        <span class="certainty-pct">${conf}%</span>
      </div>
    </div>
    <div class="material-row">
      <span class="material-badge${item.material_uncertain ? ' uncertain' : ''}">
        ${esc(item._manual_material || item.material || 'Unknown')}${item.material_uncertain ? ' ⚠️' : ''}
      </span>
      <span class="loading-dots" aria-label="Loading instructions…">Loading…</span>
    </div>`;
}

function renderItemDetail(panel, item, inst) {
  const conf = Math.round(item.confidence * 100);
  const level = conf >= 80 ? 'high' : conf >= 50 ? 'medium' : 'low';
  const matConf = item.material_confidence ? Math.round(item.material_confidence * 100) : null;
  const catClass = inst.category.replace(' ', '-').replace('special disposal', 'special');

  let binHtml = '';
  if (inst.bin_color) {
    binHtml = `
      <div class="bin-row">
        <div class="bin-swatch" style="background:${esc(inst.bin_color_hex || '#999')}" aria-hidden="true"></div>
        <span class="bin-label">Bin: <strong>${esc(inst.bin_color)}</strong></span>
      </div>`;
  }

  const stepsHtml = inst.prep_steps.map(s => `<li>${esc(s)}</li>`).join('');
  const impactHtml = inst.impact ? `<div class="impact-row">🌍 ${esc(inst.impact)}</div>` : '';
  const notesHtml  = inst.notes  ? `<p style="font-size:.85rem;color:var(--text-muted)">ℹ️ ${esc(inst.notes)}</p>` : '';
  const noLocalHtml = !inst.location_specific
    ? `<p style="font-size:.82rem;color:var(--orange)">⚠️ No location-specific rules found — showing general advice.</p>`
    : '';

  panel.innerHTML = `
    <div class="item-header">
      <h3 class="item-name">${esc(item.item_name)}</h3>
      <div class="certainty-wrap" title="Detection confidence: ${conf}%">
        <span class="certainty-label">Certainty</span>
        <div class="certainty-bar"><div class="certainty-fill ${level}" style="width:${conf}%"></div></div>
        <span class="certainty-pct">${conf}%</span>
      </div>
    </div>

    <div class="material-row">
      <span class="material-badge">
        ${esc(inst.material)}
        ${matConf !== null ? `<span style="opacity:.7;font-size:.78rem">(${matConf}%)</span>` : ''}
      </span>
      <span class="category-badge ${catClass}">${esc(inst.category)}</span>
    </div>

    ${binHtml}
    ${noLocalHtml}

    <div>
      <p class="steps-title">How to dispose</p>
      <ol class="steps-list">${stepsHtml}</ol>
    </div>

    ${impactHtml}
    ${notesHtml}

    <button class="select-material-btn" data-index="${currentItemIndex}" title="Override material">
      ✏️ Change material
    </button>`;

  // Bind change-material button
  panel.querySelector('.select-material-btn').addEventListener('click', () => {
    showMaterialModal(currentItemIndex);
  });
}

function appendManualSelectButton(panel, index) {
  const btn = document.createElement('button');
  btn.className = 'btn btn-accent';
  btn.textContent = '✏️ Select Material Type';
  btn.style.marginTop = '.5rem';
  btn.addEventListener('click', () => showMaterialModal(index));
  panel.appendChild(btn);
}

// ── Results view helpers ──────────────────────────────────────────────────────
function showResultsView() {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => { v.classList.add('hidden'); v.classList.remove('active'); });
  const rv = document.getElementById('resultsView');
  rv.classList.remove('hidden');
  rv.classList.add('active');
}

function bindResultsView() {
  document.getElementById('backBtn').addEventListener('click', () => {
    const canvas = document.getElementById('previewCanvas');
    canvas.style.display = 'none';
    document.getElementById('scanPlaceholder').style.display = '';
    showView('scan');
    setActiveNav('scan');
  });
  document.getElementById('chatBtn').addEventListener('click', () => {
    const item = currentScanResult?.items[currentItemIndex];
    if (item) openChat(item);
  });
}

// ── Chat ──────────────────────────────────────────────────────────────────────
function bindChatView() {
  document.getElementById('chatBackBtn').addEventListener('click', () => {
    showResultsView();
  });
  document.getElementById('chatSendBtn').addEventListener('click', sendChatMessage);
  document.getElementById('chatInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
  });
}

function openChat(item) {
  currentItemForChat = item;
  chatHistory = [];
  document.getElementById('chatContext').textContent =
    `Context: ${item.item_name} (${item._manual_material || item.material || 'Unknown'}) — ${currentRegion}`;
  document.getElementById('chatMessages').innerHTML = '';
  addChatBubble('assistant',
    `Hi! I'm RecycleBot 🤖. Ask me anything about recycling your ${item.item_name}.`);
  document.querySelectorAll('.view').forEach(v => { v.classList.add('hidden'); v.classList.remove('active'); });
  document.getElementById('chatView').classList.remove('hidden');
  document.getElementById('chatView').classList.add('active');
  document.getElementById('chatInput').focus();
}

async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const msg   = input.value.trim();
  if (!msg || !currentItemForChat) return;
  input.value = '';

  addChatBubble('user', msg);
  const typingId = addChatBubble('assistant', '…', true);

  const item     = currentItemForChat;
  const material = item._manual_material || item.material || 'Unknown';

  const body = {
    message: msg,
    item_name: item.item_name,
    material,
    region: currentRegion,
    language: currentLanguage,
    history: chatHistory.slice(-6),
  };

  let response;
  try {
    const resp = await fetch(`${API}/api/chat`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error('Chat unavailable');
    const data = await resp.json();
    response = data.response;
  } catch (e) {
    response = 'Sorry, the AI assistant is currently unavailable. Please try again.';
  }

  // Replace typing indicator
  const bubble = document.getElementById(typingId);
  if (bubble) {
    bubble.classList.remove('typing');
    bubble.textContent = response;
  }

  chatHistory.push({ role: 'user',      content: msg });
  chatHistory.push({ role: 'assistant', content: response });
}

let _bubbleCounter = 0;
function addChatBubble(role, text, typing = false) {
  const id  = 'bubble-' + (++_bubbleCounter);
  const div = document.createElement('div');
  div.className = `chat-bubble ${role}${typing ? ' typing' : ''}`;
  div.id = id;
  div.textContent = text;
  const container = document.getElementById('chatMessages');
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

// ── History ────────────────────────────────────────────────────────────────────
async function loadHistory() {
  const resp = await fetch(`${API}/api/history`, { headers: headersNoBody() }).catch(() => null);
  if (!resp || !resp.ok) return;
  const data = await resp.json();

  document.getElementById('totalScans').textContent  = data.total_scans;
  document.getElementById('totalCo2').textContent    = data.total_co2_saved.toFixed(2);
  document.getElementById('totalEnergy').textContent = data.total_energy_saved.toFixed(2);

  const list  = document.getElementById('historyList');
  const empty = document.getElementById('noHistory');

  if (!data.history || data.history.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  list.innerHTML = data.history.map(h => `
    <div class="history-item" role="listitem">
      <span class="history-icon">${categoryIcon(h.category)}</span>
      <div class="history-info">
        <div class="history-name">${esc(h.item_name)}</div>
        <div class="history-meta">${esc(h.material)} · ${esc(h.category)} · ${esc(h.region)}</div>
      </div>
      <div class="history-date">${formatDate(h.timestamp)}</div>
    </div>`).join('');
}

function categoryIcon(cat) {
  const m = { recyclable:'♻️', compostable:'🌱', landfill:'🗑️', 'special disposal':'⚡' };
  return m[cat] || '♻️';
}

// ── Settings ───────────────────────────────────────────────────────────────────
function bindSettingsView() {
  document.getElementById('saveLocationBtn').addEventListener('click', async () => {
    const code = document.getElementById('countrySelect').value;
    await saveLocation({ country: code });
  });

  document.getElementById('gpsBtn').addEventListener('click', () => requestGPS('countrySelect'));

  document.getElementById('saveLanguageBtn').addEventListener('click', async () => {
    const lang = document.getElementById('languageSelect').value;
    await fetch(`${API}/api/language?language=${lang}`, { method: 'PUT', headers: headersNoBody() });
    currentLanguage = lang;
    _lsSet('recyclebot_lang', lang);
    applyLanguage();
    showToast(t('toastLangSaved'));
  });

  document.getElementById('consentToggle').addEventListener('change', async e => {
    const consent = e.target.checked;
    await fetch(`${API}/api/consent`, {
      method: 'PUT',
      headers: headers(),
      body: JSON.stringify({ consent }),
    });
    showToast(consent ? 'History enabled.' : 'History disabled and cleared.');
  });

  document.getElementById('clearHistoryBtn').addEventListener('click', async () => {
    if (!confirm('Clear all scan history? This cannot be undone.')) return;
    await fetch(`${API}/api/history`, { method: 'DELETE', headers: headersNoBody() });
    showToast('History cleared.');
  });
}

async function loadSettings() {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 4000);
    const [consentResp, langResp, locResp] = await Promise.all([
      fetch(`${API}/api/consent`,  { headers: headersNoBody(), signal: ctrl.signal }),
      fetch(`${API}/api/language`, { headers: headersNoBody(), signal: ctrl.signal }),
      fetch(`${API}/api/location`, { headers: headersNoBody(), signal: ctrl.signal }),
    ]);
    clearTimeout(t);
    if (consentResp.ok) {
      const d = await consentResp.json();
      document.getElementById('consentToggle').checked = d.consent;
    }
    if (langResp.ok) {
      const d = await langResp.json();
      currentLanguage = d.language;
      _lsSet('recyclebot_lang', d.language);
      const sel = document.getElementById('languageSelect');
      if (sel) sel.value = d.language;
    }
    if (locResp.ok) {
      const d = await locResp.json();
      currentRegion = d.region_code;
      _lsSet('recyclebot_region', d.region_code);
      updateLocationBar(d.display_name);
    }
  } catch (_) { /* server not yet ready */ }
}

// ── Location ───────────────────────────────────────────────────────────────────
function bindLocationBar() {
  document.getElementById('changeLocationBtn').addEventListener('click', showLocationModal);
}

function updateLocationBar(name) {
  const text = document.getElementById('locationText');
  if (name) {
    text.textContent = `📍 ${name}`;
  } else if (currentRegion === 'GLOBAL') {
    text.textContent = '📍 No location set — tap to set your region';
  } else {
    text.textContent = `📍 ${currentRegion}`;
  }
}

async function saveLocation(payload) {
  const resp = await fetch(`${API}/api/location`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(payload),
  });
  if (resp.ok) {
    const d = await resp.json();
    currentRegion = d.region_code;
    _lsSet('recyclebot_region', d.region_code);
    updateLocationBar(d.display_name);

    // Sync settings select
    const sel = document.getElementById('countrySelect');
    if (sel) sel.value = d.region_code;

    showToast(`Location set to ${d.display_name}.`);
  }
}

function requestGPS(selectId) {
  if (!navigator.geolocation) { showToast('GPS not available on this device.'); return; }
  navigator.geolocation.getCurrentPosition(async pos => {
    const { latitude, longitude } = pos.coords;
    const resp = await fetch(`${API}/api/location`, {
      method: 'PUT',
      headers: headers(),
      body: JSON.stringify({ latitude, longitude }),
    });
    if (resp.ok) {
      const d = await resp.json();
      currentRegion = d.region_code;
      _lsSet('recyclebot_region', d.region_code);
      updateLocationBar(d.display_name);
      const sel = document.getElementById(selectId);
      if (sel) sel.value = d.region_code;
      showToast(`Location detected: ${d.display_name}`);
    }
  }, () => showToast('Could not get GPS position. Please select manually.'));
}

async function populateCountrySelects() {
  let countries = [];
  try {
    const resp = await fetch(`${API}/api/location/countries`);
    if (resp.ok) countries = await resp.json();
  } catch (_) {
    countries = [{ code: 'GLOBAL', name: 'Global (General Guide)' }, { code: 'AT', name: 'Austria' }, { code: 'DE', name: 'Germany' }, { code: 'KR', name: 'South Korea' }];
  }
  ['countrySelect', 'modalCountrySelect'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = countries.map(c => `<option value="${esc(c.code)}">${esc(c.name)}</option>`).join('');
    sel.value = currentRegion;
  });
}

// ── Modals ─────────────────────────────────────────────────────────────────────
function bindModals() {
  // Location modal
  document.getElementById('modalSaveBtn').addEventListener('click', async () => {
    const code = document.getElementById('modalCountrySelect').value;
    await saveLocation({ country: code });
    hideLocationModal();
  });
  document.getElementById('modalSkipBtn').addEventListener('click', () => {
    hideLocationModal();
  });
  document.getElementById('modalGpsBtn').addEventListener('click', () => {
    requestGPS('modalCountrySelect');
  });

  // Material modal
  document.getElementById('materialConfirmBtn').addEventListener('click', async () => {
    const mat   = document.getElementById('materialSelect').value;
    const index = parseInt(document.getElementById('materialModal').dataset.itemIndex, 10);
    if (currentScanResult?.items[index]) {
      currentScanResult.items[index]._manual_material = mat;
      currentScanResult.items[index].material_uncertain = false;
    }
    hideMaterialModal();
    await selectItem(index);
  });
  document.getElementById('materialCancelBtn').addEventListener('click', hideMaterialModal);
}

function showLocationModal() {
  document.getElementById('locationModal').classList.remove('hidden');
}
function hideLocationModal() {
  document.getElementById('locationModal').classList.add('hidden');
}

function showMaterialModal(itemIndex) {
  const modal = document.getElementById('materialModal');
  modal.dataset.itemIndex = itemIndex;
  const item = currentScanResult?.items[itemIndex];
  if (item) {
    const sel = document.getElementById('materialSelect');
    if (sel && item.material) sel.value = item.material;
  }
  modal.classList.remove('hidden');
}
function hideMaterialModal() {
  document.getElementById('materialModal').classList.add('hidden');
}

// ── Loading / error helpers ────────────────────────────────────────────────────
const loadingSteps = ['Detecting items…', 'Classifying materials…', 'Fetching instructions…'];
let _loadingTimer = null;
let _loadingStep  = 0;

function showLoading(msg) {
  _loadingStep = 0;
  document.getElementById('loadingText').textContent = msg || loadingSteps[0];
  document.getElementById('loadingOverlay').classList.remove('hidden');
  _loadingTimer = setInterval(() => {
    _loadingStep = (_loadingStep + 1) % loadingSteps.length;
    document.getElementById('loadingText').textContent = loadingSteps[_loadingStep];
  }, 1200);
}
function hideLoading() {
  clearInterval(_loadingTimer);
  document.getElementById('loadingOverlay').classList.add('hidden');
}

function showError(msg) {
  document.getElementById('errorText').textContent = msg;
  document.getElementById('errorBanner').classList.remove('hidden');
  document.getElementById('closeError').onclick = hideError;
}
function hideError() {
  document.getElementById('errorBanner').classList.add('hidden');
}

// ── Misc helpers ───────────────────────────────────────────────────────────────
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch (_) { return ts; }
}

function detectBrowserLanguage() {
  const lang = navigator.language || 'en';
  return lang.split('-')[0];
}

function setActiveNav(view) {
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.view === view);
  });
}

function showToast(msg) {
  let toast = document.getElementById('_toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = '_toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    Object.assign(toast.style, {
      position: 'fixed', bottom: '1.5rem', left: '50%', transform: 'translateX(-50%)',
      background: 'var(--green-dark)', color: '#fff', padding: '.65rem 1.25rem',
      borderRadius: '999px', fontSize: '.9rem', fontWeight: '600',
      boxShadow: '0 4px 20px rgba(0,0,0,.25)', zIndex: '999', maxWidth: '90vw',
      textAlign: 'center', transition: 'opacity .2s',
    });
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = '0'; }, 2800);
}

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload  = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = reject;
    img.src = url;
  });
}
