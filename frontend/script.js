/* Updated script.js — aligned with provided HTML & CSS
   - Fixes mode switching (maps 'unidoc' -> 'unidocbuilderMode')
   - Removes duplicate functions
   - Implements togglePanel, toggleSubItems
   - Implements handleUpload for Uni Doc Builder items (upload, preview, delete)
   - Keeps existing Standard & Checklist logic but tidies minor bugs
*/

const API_BASE = 'https://file-combiner.onrender.com';

// Fetch with timeout (single definition)
function fetchWithTimeout(resource, options = {}, timeout = 120000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  return fetch(resource, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(id));
}

// Global state
let currentMode = 'standard';
let standardFiles = [];
let checklists = [];
let checklistIdCounter = 0;
// Store UniDoc files by data-key (string) -> File or Array<File>
const uniDocFiles = new Map();

// ---------- MODE SWITCHING ----------
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const mode = btn.dataset.mode;
    switchMode(mode);
  });
});

function switchMode(mode) {
  currentMode = mode;

  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });

  const idMap = {
    'standard': 'standardMode',
    'checklist': 'checklistMode',
    'unidoc': 'unidocbuilderMode'
  };

  document.querySelectorAll('.mode-content').forEach(content => {
    content.classList.toggle('active', content.id === idMap[mode]);
  });

  // toggle UniDoc action buttons
  const uniDocActions = document.getElementById("unidocActions");
  if (mode === 'unidoc') {
    uniDocActions.style.display = "flex";
  } else {
    uniDocActions.style.display = "none";
  }
}


// ---------- STANDARD MODE ----------
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const filesList = document.getElementById('filesList');
const filesContainer = document.getElementById('filesContainer');
const fileCount = document.getElementById('fileCount');
const combineBtn = document.getElementById('combineBtn');
const clearBtn = document.getElementById('clearBtn');
const standardActions = document.getElementById('standardActions');
const statusMessage = document.getElementById('statusMessage');

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadArea.classList.add('drag-over');
});
uploadArea.addEventListener('dragleave', () => {
  uploadArea.classList.remove('drag-over');
});
uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('drag-over');
  handleStandardFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
  handleStandardFiles(e.target.files);
});

function handleStandardFiles(files) {
  for (let file of files) standardFiles.push(file);
  updateStandardFilesList();
}

function updateStandardFilesList() {
  if (standardFiles.length === 0) {
    filesList.style.display = 'none';
    standardActions.style.display = 'none';
    return;
  }

  filesList.style.display = 'block';
  standardActions.style.display = 'flex';
  fileCount.textContent = standardFiles.length;

  filesContainer.innerHTML = standardFiles.map((file, index) => {
    const ext = file.name.split('.').pop().toLowerCase();
    const size = formatFileSize(file.size);
    const iconClass = getIconClass(ext);

    return `
      <div class="file-item">
        <div class="file-info">
          <div class="file-icon ${iconClass}">${ext.toUpperCase()}</div>
          <div>
            <div class="file-name">${file.name}</div>
            <div style="font-size: 0.9em; color: #999;">${size}</div>
          </div>
        </div>
        <button class="remove-file" onclick="removeStandardFile(${index})">×</button>
      </div>
    `;
  }).join('');
}

function removeStandardFile(index) {
  standardFiles.splice(index, 1);
  updateStandardFilesList();
}

clearBtn.addEventListener('click', () => {
  standardFiles = [];
  fileInput.value = '';
  updateStandardFilesList();
  hideStatus();
});

combineBtn.addEventListener('click', async () => {
  if (standardFiles.length === 0) {
    showStatus('Please upload at least one file', 'error');
    return;
  }

  showStatus('Processing files...', 'processing');
  combineBtn.disabled = true;

  try {
    const formData = new FormData();
    standardFiles.forEach(file => formData.append('files', file));

    const response = await fetchWithTimeout(`${API_BASE}/combine`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) throw new Error('Combination failed');

    const blob = await response.blob();
    downloadFile(blob, `combined_${Date.now()}.pdf`);

    showStatus('✓ Files combined successfully!', 'success');
  } catch (error) {
    showStatus('✗ Error: ' + error.message, 'error');
  } finally {
    combineBtn.disabled = false;
  }
});

// ---------- CHECKLIST MODE ----------
const addChecklistBtn = document.getElementById('addChecklistBtn');
const checklistsContainer = document.getElementById('checklistsContainer');
const combineChecklistBtn = document.getElementById('combineChecklistBtn');
const clearChecklistBtn = document.getElementById('clearChecklistBtn');
const checklistActions = document.getElementById('checklistActions');
const checklistStatusMessage = document.getElementById('checklistStatusMessage');

addChecklistBtn.addEventListener('click', () => addChecklist());

function addChecklist(name = '') {
  const id = checklistIdCounter++;
  checklists.push({ id, name: name || `Section ${checklists.length + 1}`, files: [] });
  renderChecklists();
}

function renderChecklists() {
  if (checklists.length === 0) {
    checklistsContainer.innerHTML = '<p style="text-align: center; color: #999; padding: 40px;">No checklist sections yet. Click "Add New Checklist Section" to get started.</p>';
    checklistActions.style.display = 'none';
    return;
  }

  checklistActions.style.display = 'flex';

  checklistsContainer.innerHTML = checklists.map(checklist => `
    <div class="checklist-section" data-id="${checklist.id}">
      <div class="checklist-header">
        <input type="text" class="checklist-name-input" value="${escapeHtml(checklist.name)}" placeholder="Enter section name..." onchange="updateChecklistName(${checklist.id}, this.value)">
        <button class="delete-checklist-btn" onclick="deleteChecklist(${checklist.id})">🗑️ Delete</button>
      </div>

      <div class="checklist-upload-area" id="checklist_area_${checklist.id}">
        <div style="font-size: 2.5em; margin-bottom: 10px;">📤</div>
        <div style="font-weight: 600; color: #1a1a2e;">Upload files for this section</div>
        <div style="color: #999; font-size: 0.9em; margin-top: 5px;">Tap or drag files here</div>
        <input type="file" id="checklistFile_${checklist.id}" multiple accept=".pdf,.docx,.pptx,.txt,.jpg,.jpeg,.png,.gif" style="display:none;" onchange="handleChecklistFiles(${checklist.id}, this.files)">
      </div>

      <div class="files-list" id="checklistFiles_${checklist.id}" style="margin-top: 20px;">
        ${renderChecklistFiles(checklist)}
      </div>
    </div>
  `).join('');

  // add drag/drop listeners
  checklists.forEach(checklist => {
    const area = document.getElementById(`checklist_area_${checklist.id}`);
    if (!area) return;

    area.addEventListener('click', () => document.getElementById(`checklistFile_${checklist.id}`).click());

    area.addEventListener('dragover', (e) => {
      e.preventDefault(); area.classList.add('drag-over');
    });
    area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
    area.addEventListener('drop', (e) => {
      e.preventDefault(); area.classList.remove('drag-over'); handleChecklistFiles(checklist.id, e.dataTransfer.files);
    });
  });
}

function renderChecklistFiles(checklist) {
  if (checklist.files.length === 0) return '';

  return checklist.files.map((file, index) => {
    const ext = file.name.split('.').pop().toLowerCase();
    const size = formatFileSize(file.size);
    const iconClass = getIconClass(ext);

    return `
      <div class="file-item">
        <div class="file-info">
          <div class="file-icon ${iconClass}">${ext.toUpperCase()}</div>
          <div>
            <div class="file-name">${escapeHtml(file.name)}</div>
            <div style="font-size: 0.9em; color: #999;">${size}</div>
          </div>
        </div>
        <button class="remove-file" onclick="removeChecklistFile(${checklist.id}, ${index})">×</button>
      </div>
    `;
  }).join('');
}

function handleChecklistFiles(checklistId, files) {
  const checklist = checklists.find(c => c.id === checklistId);
  if (!checklist) return;

  for (let file of files) checklist.files.push(file);
  renderChecklists();
}

function updateChecklistName(checklistId, name) {
  const checklist = checklists.find(c => c.id === checklistId);
  if (checklist) checklist.name = name;
}

function deleteChecklist(checklistId) {
  checklists = checklists.filter(c => c.id !== checklistId);
  renderChecklists();
}

function removeChecklistFile(checklistId, fileIndex) {
  const checklist = checklists.find(c => c.id === checklistId);
  if (!checklist) return;
  checklist.files.splice(fileIndex, 1);
  renderChecklists();
}

clearChecklistBtn.addEventListener('click', () => {
  checklists = [];
  renderChecklists();
  hideChecklistStatus();
});

combineChecklistBtn.addEventListener('click', async () => {
  const validChecklists = checklists.filter(c => c.files.length > 0);
  if (validChecklists.length === 0) {
    showChecklistStatus('Please add files to at least one checklist section', 'error');
    return;
  }

  showChecklistStatus('Generating PDF with dividers...', 'processing');
  combineChecklistBtn.disabled = true;

  try {
    const formData = new FormData();

    const checklistData = validChecklists.map((checklist, idx) => {
      const fileKeys = [];
      checklist.files.forEach((file, fileIdx) => {
        const key = `checklist_${idx}_file_${fileIdx}`;
        formData.append(key, file);
        fileKeys.push(key);
      });
      return { name: checklist.name, files: fileKeys };
    });

    formData.append('checklist_data', JSON.stringify(checklistData));

    const response = await fetch(`${API_BASE}/combine-checklist`, { method: 'POST', body: formData });
    if (!response.ok) throw new Error('Combination failed');

    const blob = await response.blob();
    downloadFile(blob, `checklist_combined_${Date.now()}.pdf`);

    showChecklistStatus('✓ PDF with dividers generated successfully!', 'success');
  } catch (error) {
    showChecklistStatus('✗ Error: ' + error.message, 'error');
  } finally { combineChecklistBtn.disabled = false; }
});

// ---------- UNI DOC BUILDER HELPERS ----------
function togglePanel(panelId, btnEl) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  panel.classList.toggle('active');
  // rotate arrow
  const span = btnEl.querySelector('span');
  if (span) span.textContent = panel.classList.contains('active') ? '▴' : '▾';
}

function toggleSubItems(subId, btnEl) {
  const sub = document.getElementById(subId);
  if (!sub) return;
  sub.classList.toggle('active');
  btnEl.textContent = sub.classList.contains('active') ? 'Collapse ▴' : 'Expand ▾';
}

// Called by inline onclick in HTML: handleUpload(this)
function handleUpload(buttonEl) {
  // find closest controls block
  const controls = buttonEl.closest('.controls');
  if (!controls) return;
  const input = controls.querySelector('.file-input');
  if (!input) return;

  // trigger file chooser
  input.click();

  // wire change handler (only once)
  if (!input._bound) {
    input.addEventListener('change', (e) => {
      const files = Array.from(e.target.files || []);
      // find list item parent to get data-key
      const li = input.closest('li');
      const key = li ? (li.dataset.key || li.getAttribute('data-key')) : null;

      if (!key) {
        // fallback: store by generated id
        const fallbackKey = `unidoc_fallback_${Date.now()}`;
        if (files.length === 1) uniDocFiles.set(fallbackKey, files[0]);
        else uniDocFiles.set(fallbackKey, files);
        updateUniControls(controls, files);
        return;
      }

      // If input allows multiple, store array
      if (input.hasAttribute('multiple')) {
        uniDocFiles.set(key, files);
      } else {
        uniDocFiles.set(key, files[0] || null);
      }

      updateUniControls(controls, files);
    });
    input._bound = true;
  }
}

function updateUniControls(controls, files) {
  const previewBtn = controls.querySelector('.btn.preview');
  const deleteBtn = controls.querySelector('.btn.delete');
  const filenameSpan = controls.querySelector('.filename');

  if (!files || files.length === 0) {
    if (previewBtn) previewBtn.disabled = true;
    if (deleteBtn) deleteBtn.disabled = true;
    if (filenameSpan) filenameSpan.textContent = '';
    return;
  }

  const first = files[0];
  if (filenameSpan) filenameSpan.textContent = files.length > 1 ? `${files.length} files selected` : first.name;

  if (previewBtn) {
    previewBtn.disabled = false;
    previewBtn.onclick = () => {
      // open first file
      const fileToOpen = first;
      if (!fileToOpen) return;
      const url = URL.createObjectURL(fileToOpen);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 1000 * 30);
    };
  }

  if (deleteBtn) {
    deleteBtn.disabled = false;
    deleteBtn.onclick = () => {
      // clear input value and controls
      const input = controls.querySelector('.file-input');
      if (input) input.value = '';
      if (filenameSpan) filenameSpan.textContent = '';

      // remove from uniDocFiles map if possible
      const li = controls.closest('li');
      const key = li ? (li.dataset.key || li.getAttribute('data-key')) : null;
      if (key) uniDocFiles.delete(key);

      // disable buttons
      if (previewBtn) previewBtn.disabled = true;
      if (deleteBtn) deleteBtn.disabled = true;
    };
  }
}

// ---------- UTILITY FUNCTIONS (shared) ----------
function getIconClass(ext) {
  const map = { pdf: 'pdf', docx: 'docx', doc: 'docx', pptx: 'pptx', ppt: 'pptx', txt: 'txt', jpg: 'img', jpeg: 'img', png: 'img', gif: 'img' };
  return map[ext] || 'pdf';
}

function formatFileSize(bytes) {
  if (!bytes) return '0 Bytes';
  const k = 1024; const sizes = ['Bytes','KB','MB','GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function downloadFile(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  window.URL.revokeObjectURL(url); document.body.removeChild(a);
}

function showStatus(message, type) {
  statusMessage.className = 'status-message active ' + type;
  statusMessage.innerHTML = type === 'processing' ? `<div class="loader"></div>${message}` : message;
}
function hideStatus() { statusMessage.classList.remove('active'); }

function showChecklistStatus(message, type) {
  checklistStatusMessage.className = 'status-message active ' + type;
  checklistStatusMessage.innerHTML = type === 'processing' ? `<div class="loader"></div>${message}` : message;
}
function hideChecklistStatus() { checklistStatusMessage.classList.remove('active'); }

// Simple escaping to avoid injected HTML from file names
function escapeHtml(unsafe) {
  return String(unsafe).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"})[c]);
}

// ---------- UniDoc action helpers ----------
const combineUniDocBtn = document.getElementById('combineUniDocBtn');
const clearUniDocBtn = document.getElementById('clearUniDocBtn');
const unidocStatusMessage = document.getElementById('unidocStatusMessage');

function showUnidocStatus(message, type='') {
  if (!unidocStatusMessage) return;
  unidocStatusMessage.className = 'status-message active ' + type;
  unidocStatusMessage.innerHTML = type === 'processing' ? `<div class="loader"></div>${message}` : message;
}

// fully reset UniDoc inputs + UI
function clearUniDoc(resetTextInputs = true) {
  const container = document.getElementById('unidocbuilderMode');
  if (!container) return;

  // 1) Clear actual file input values
  container.querySelectorAll('input[type="file"]').forEach(input => {
    try { input.value = ''; } catch (e) { /* ignore */ }
  });

  // 2) Clear internal map that stores selected files
  if (typeof uniDocFiles !== 'undefined' && uniDocFiles instanceof Map) {
    uniDocFiles.clear();
  }

  // 3) Reset per-control UI (filename, preview, delete)
  container.querySelectorAll('.controls').forEach(ctrl => {
    const filenameSpan = ctrl.querySelector('.filename');
    if (filenameSpan) filenameSpan.textContent = '';

    const previewBtn = ctrl.querySelector('.btn.preview');
    const deleteBtn  = ctrl.querySelector('.btn.delete');

    if (previewBtn)  { previewBtn.disabled = true; previewBtn.onclick = null; }
    if (deleteBtn)   { deleteBtn.disabled = true;  deleteBtn.onclick = null;  }
  });

  // 4) Optionally clear text fields at top (program, course code, etc.)
  if (resetTextInputs) {
    container.querySelectorAll('input[type="text"]').forEach(inp => inp.value = '');
  }

  // 5) Status message
  showUnidocStatus('All UniDoc inputs cleared.', 'success');
  setTimeout(() => {
    if (unidocStatusMessage) unidocStatusMessage.classList.remove('active');
  }, 1800);
}

// wire Clear All
if (clearUniDocBtn) {
  clearUniDocBtn.addEventListener('click', (ev) => {
    ev.preventDefault();
    clearUniDoc(true);
  });
}

// (optional) combine handler skeleton that gathers files from uniDocFiles map
if (combineUniDocBtn) {
  combineUniDocBtn.addEventListener('click', async () => {
    if (!uniDocFiles || uniDocFiles.size === 0) {
      showUnidocStatus('Please upload at least one file', 'error');
      return;
    }

    showUnidocStatus('Merging Uni Docs into PDF...', 'processing');
    combineUniDocBtn.disabled = true;

    try {
      const formData = new FormData();
      let fileIndex = 0;
      for (const [key, payload] of uniDocFiles.entries()) {
        if (Array.isArray(payload)) {
          payload.forEach(f => formData.append(`file_${fileIndex++}`, f));
        } else if (payload instanceof File) {
          formData.append(`file_${fileIndex++}`, payload);
        }
      }

      // call your API endpoint (example)
      const res = await fetchWithTimeout(`${API_BASE}/combine-unidoc`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Merge failed');
      const blob = await res.blob();
      downloadFile(blob, `unidoc_combined_${Date.now()}.pdf`);
      showUnidocStatus('✓ UniDocs merged successfully!', 'success');
    } catch (err) {
      showUnidocStatus('✗ Error: ' + err.message, 'error');
    } finally {
      combineUniDocBtn.disabled = false;
    }
  });
}



// ---------- BOOTSTRAP / INITIAL STATE ----------
// Initialize with example checklist sections (as originally intended)
addChecklist('Exam Files');
addChecklist('Fees Files');
addChecklist('Student ID Proofs');

// Enhance existing Uni Doc controls: enable preview/delete where files exist (if user prefilled)
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.controls').forEach(ctrl => {
    const filenameSpan = ctrl.querySelector('.filename');
    const previewBtn = ctrl.querySelector('.btn.preview');
    const deleteBtn = ctrl.querySelector('.btn.delete');
    if (filenameSpan && filenameSpan.textContent.trim() !== '') {
      if (previewBtn) previewBtn.disabled = false;
      if (deleteBtn) deleteBtn.disabled = false;
    }
  });
});
