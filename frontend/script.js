const API_BASE = 'https://file-combiner.onrender.com';
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

// Mode switching
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

    document.querySelectorAll('.mode-content').forEach(content => {
        content.classList.toggle('active', content.id === `${mode}Mode`);
    });
}

// ===== STANDARD MODE =====
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
    uploadArea.style.borderColor = '#764ba2';
    uploadArea.style.transform = 'scale(1.02)';
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = 'rgba(102, 126, 234, 0.3)';
    uploadArea.style.transform = 'scale(1)';
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = 'rgba(102, 126, 234, 0.3)';
    uploadArea.style.transform = 'scale(1)';
    handleStandardFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    handleStandardFiles(e.target.files);
});

function handleStandardFiles(files) {
    for (let file of files) {
        standardFiles.push(file);
    }
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
        standardFiles.forEach(file => {
            formData.append('files', file);
        });

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

// ===== CHECKLIST MODE =====
const addChecklistBtn = document.getElementById('addChecklistBtn');
const checklistsContainer = document.getElementById('checklistsContainer');
const combineChecklistBtn = document.getElementById('combineChecklistBtn');
const clearChecklistBtn = document.getElementById('clearChecklistBtn');
const checklistActions = document.getElementById('checklistActions');
const checklistStatusMessage = document.getElementById('checklistStatusMessage');

addChecklistBtn.addEventListener('click', () => {
    addChecklist();
});

function addChecklist(name = '') {
    const id = checklistIdCounter++;
    checklists.push({
        id: id,
        name: name || `Section ${checklists.length + 1}`,
        files: []
    });
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
                        <input type="text" 
                               class="checklist-name-input" 
                               value="${checklist.name}" 
                               placeholder="Enter section name..."
                               onchange="updateChecklistName(${checklist.id}, this.value)">
                        <button class="delete-checklist-btn" onclick="deleteChecklist(${checklist.id})">🗑️ Delete</button>
                    </div>
                    
                    <div class="checklist-upload-area" onclick="document.getElementById('checklistFile_${checklist.id}').click()">
                        <div style="font-size: 2.5em; margin-bottom: 10px;">📤</div>
                        <div style="font-weight: 600; color: #1a1a2e;">Upload files for this section</div>
                        <div style="color: #999; font-size: 0.9em; margin-top: 5px;">Tap or drag files here</div>
                        <input type="file" 
                               id="checklistFile_${checklist.id}" 
                               multiple 
                               accept=".pdf,.docx,.pptx,.txt,.jpg,.jpeg,.png,.gif"
                               style="display: none;"
                               onchange="handleChecklistFiles(${checklist.id}, this.files)">
                    </div>
                    
                    <div class="files-list" id="checklistFiles_${checklist.id}" style="margin-top: 20px;">
                        ${renderChecklistFiles(checklist)}
                    </div>
                </div>
            `).join('');

    // Add drag-drop to checklist areas
    checklists.forEach(checklist => {
        const area = document.querySelector(`[data-id="${checklist.id}"] .checklist-upload-area`);
        if (area) {
            area.addEventListener('dragover', (e) => {
                e.preventDefault();
                area.style.borderColor = '#764ba2';
                area.style.background = 'rgba(102, 126, 234, 0.1)';
            });
            area.addEventListener('dragleave', () => {
                area.style.borderColor = 'rgba(102, 126, 234, 0.3)';
                area.style.background = 'transparent';
            });
            area.addEventListener('drop', (e) => {
                e.preventDefault();
                area.style.borderColor = 'rgba(102, 126, 234, 0.3)';
                area.style.background = 'transparent';
                handleChecklistFiles(checklist.id, e.dataTransfer.files);
            });
        }
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
                                <div class="file-name">${file.name}</div>
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

    for (let file of files) {
        checklist.files.push(file);
    }
    renderChecklists();
}

function updateChecklistName(checklistId, name) {
    const checklist = checklists.find(c => c.id === checklistId);
    if (checklist) {
        checklist.name = name;
    }
}

function deleteChecklist(checklistId) {
    checklists = checklists.filter(c => c.id !== checklistId);
    renderChecklists();
}

function removeChecklistFile(checklistId, fileIndex) {
    const checklist = checklists.find(c => c.id === checklistId);
    if (checklist) {
        checklist.files.splice(fileIndex, 1);
        renderChecklists();
    }
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

        // Prepare checklist data
        const checklistData = validChecklists.map((checklist, idx) => {
            const fileKeys = [];
            checklist.files.forEach((file, fileIdx) => {
                const key = `checklist_${idx}_file_${fileIdx}`;
                formData.append(key, file);
                fileKeys.push(key);
            });
            return {
                name: checklist.name,
                files: fileKeys
            };
        });

        formData.append('checklist_data', JSON.stringify(checklistData));

        const response = await fetch(`${API_BASE}/combine-checklist`, {
            method: 'POST',
            body: formData
        });


        if (!response.ok) throw new Error('Combination failed');

        const blob = await response.blob();
        downloadFile(blob, `checklist_combined_${Date.now()}.pdf`);

        showChecklistStatus('✓ PDF with dividers generated successfully!', 'success');
    } catch (error) {
        showChecklistStatus('✗ Error: ' + error.message, 'error');
    } finally {
        combineChecklistBtn.disabled = false;
    }
});

// ===== UTILITY FUNCTIONS =====
function getIconClass(ext) {
    const map = {
        'pdf': 'pdf',
        'docx': 'docx',
        'doc': 'docx',
        'pptx': 'pptx',
        'ppt': 'pptx',
        'txt': 'txt',
        'jpg': 'img',
        'jpeg': 'img',
        'png': 'img',
        'gif': 'img'
    };
    return map[ext] || 'pdf';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function downloadFile(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

function showStatus(message, type) {
    statusMessage.className = 'status-message active ' + type;
    statusMessage.innerHTML = type === 'processing'
        ? `<div class="loader"></div>${message}`
        : message;
}

function hideStatus() {
    statusMessage.classList.remove('active');
}

function showChecklistStatus(message, type) {
    checklistStatusMessage.className = 'status-message active ' + type;
    checklistStatusMessage.innerHTML = type === 'processing'
        ? `<div class="loader"></div>${message}`
        : message;
}

function hideChecklistStatus() {
    checklistStatusMessage.classList.remove('active');
}

function fetchWithTimeout(resource, options = {}, timeout = 120000) { // 2 minutes
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    return fetch(resource, { ...options, signal: controller.signal })
        .finally(() => clearTimeout(id));
}

const response = await fetchWithTimeout(`${API_BASE}/combine-checklist`, {
    method: 'POST',
    body: formData
});


// Initialize with example checklist
addChecklist('Exam Files');
addChecklist('Fees Files');
addChecklist('Student ID Proofs');
