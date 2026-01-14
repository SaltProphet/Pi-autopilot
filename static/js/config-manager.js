// Configuration Manager JavaScript

// State
let currentConfig = {};
let isLoading = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkSecurityWarning();
    loadConfiguration();
    setupFormHandlers();
});

// Check for HTTPS or localhost
function checkSecurityWarning() {
    const isSecure = window.location.protocol === 'https:';
    const isLocalhost = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1';
    
    if (!isSecure && !isLocalhost) {
        document.getElementById('security-warning').style.display = 'block';
    }
}

// Load current configuration
async function loadConfiguration() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        if (data.success) {
            currentConfig = data.config;
            populateForm(currentConfig);
        } else {
            showToast('Failed to load configuration', 'error');
        }
    } catch (error) {
        showToast('Error loading configuration: ' + error.message, 'error');
    }
}

// Populate form with current config
function populateForm(config) {
    // API Keys
    if (config.api_keys) {
        for (const [key, value] of Object.entries(config.api_keys)) {
            const input = document.querySelector(`[name="${key}"]`);
            if (input && value) {
                input.value = value;
                input.setAttribute('data-original', value);
            }
        }
    }
    
    // Toggles
    if (config.toggles) {
        for (const [key, value] of Object.entries(config.toggles)) {
            const input = document.querySelector(`[name="${key}"]`);
            if (input) {
                input.checked = value === true;
            }
        }
    }
    
    // Cost Limits
    if (config.cost_limits) {
        for (const [key, value] of Object.entries(config.cost_limits)) {
            const input = document.querySelector(`[name="${key}"]`);
            if (input && value !== null) {
                input.value = value;
            }
        }
    }
    
    // Pipeline Settings
    if (config.pipeline) {
        for (const [key, value] of Object.entries(config.pipeline)) {
            const input = document.querySelector(`[name="${key}"]`);
            if (input && value !== null) {
                input.value = value;
            }
        }
    }
}

// Setup form handlers
function setupFormHandlers() {
    const form = document.getElementById('config-form');
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await saveConfiguration();
    });
}

// Gather form data
function gatherFormData() {
    const formData = {
        api_keys: {},
        toggles: {},
        cost_limits: {},
        pipeline: {}
    };
    
    // API Keys
    const apiKeyInputs = document.querySelectorAll('#config-form input[type="password"], #config-form input[name*="REDDIT_USER_AGENT"], #config-form input[name*="CLIENT_ID"]');
    apiKeyInputs.forEach(input => {
        const name = input.name;
        let value = input.value;
        
        // If value is masked and unchanged, don't include it
        if (input.hasAttribute('data-masked') && value === input.getAttribute('data-original')) {
            return;
        }
        
        if (name && value) {
            formData.api_keys[name] = value;
        }
    });
    
    // Toggles
    const toggleInputs = document.querySelectorAll('.toggle-input');
    toggleInputs.forEach(input => {
        if (input.name) {
            formData.toggles[input.name] = input.checked;
        }
    });
    
    // Cost Limits
    ['MAX_USD_PER_RUN', 'MAX_USD_LIFETIME', 'MAX_TOKENS_PER_RUN'].forEach(name => {
        const input = document.querySelector(`[name="${name}"]`);
        if (input && input.value) {
            formData.cost_limits[name] = parseFloat(input.value) || parseInt(input.value);
        }
    });
    
    // Pipeline Settings
    ['REDDIT_SUBREDDITS', 'REDDIT_MIN_SCORE', 'REDDIT_POST_LIMIT'].forEach(name => {
        const input = document.querySelector(`[name="${name}"]`);
        if (input && input.value) {
            if (name === 'REDDIT_SUBREDDITS') {
                formData.pipeline[name] = input.value;
            } else {
                formData.pipeline[name] = parseInt(input.value);
            }
        }
    });
    
    return formData;
}

// Save configuration
async function saveConfiguration() {
    if (isLoading) return;
    
    isLoading = true;
    const submitBtn = document.querySelector('.btn-primary');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Saving...';
    
    try {
        const formData = gatherFormData();
        
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showToast('Configuration saved successfully!', 'success');
            
            // Show warnings if any
            if (data.warnings && data.warnings.length > 0) {
                data.warnings.forEach(warning => {
                    showToast(warning, 'warning');
                });
            }
            
            // Reload configuration
            await loadConfiguration();
        } else {
            const errorMsg = data.detail?.errors?.join(', ') || data.detail || 'Failed to save configuration';
            showToast(errorMsg, 'error');
        }
    } catch (error) {
        showToast('Error saving configuration: ' + error.message, 'error');
    } finally {
        isLoading = false;
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// Test API key
async function testApiKey(service, inputId) {
    const input = document.getElementById(inputId);
    const statusEl = document.getElementById(inputId + '_status');
    const testBtn = event.target;
    
    if (!input.value) {
        showToast('Please enter an API key first', 'warning');
        return;
    }
    
    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';
    statusEl.textContent = '';
    
    try {
        const response = await fetch('/api/config/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service: service,
                api_key: input.value
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            statusEl.textContent = '✓ ' + data.message;
            statusEl.className = 'test-status success';
        } else {
            statusEl.textContent = '✗ ' + data.message;
            statusEl.className = 'test-status error';
        }
    } catch (error) {
        statusEl.textContent = '✗ Test failed: ' + error.message;
        statusEl.className = 'test-status error';
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Test';
    }
}

// Test Reddit credentials
async function testRedditCredentials() {
    const clientId = document.getElementById('reddit_client_id').value;
    const clientSecret = document.getElementById('reddit_client_secret').value;
    const userAgent = document.getElementById('reddit_user_agent').value;
    const statusEl = document.getElementById('reddit_status');
    const testBtn = event.target;
    
    if (!clientId || !clientSecret || !userAgent) {
        showToast('Please enter all Reddit credentials', 'warning');
        return;
    }
    
    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';
    statusEl.textContent = '';
    
    try {
        const response = await fetch('/api/config/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service: 'REDDIT',
                client_id: clientId,
                client_secret: clientSecret,
                user_agent: userAgent,
                api_key: 'dummy'  // Required by API but not used
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            statusEl.textContent = '✓ ' + data.message;
            statusEl.className = 'test-status success';
        } else {
            statusEl.textContent = '✗ ' + data.message;
            statusEl.className = 'test-status error';
        }
    } catch (error) {
        statusEl.textContent = '✗ Test failed: ' + error.message;
        statusEl.className = 'test-status error';
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Test';
    }
}

// Toggle visibility of password fields
function toggleVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
    } else {
        input.type = 'password';
    }
}

// Reset form to current saved values
function resetForm() {
    if (confirm('Reset all fields to last saved values?')) {
        populateForm(currentConfig);
        showToast('Form reset to saved values', 'success');
    }
}

// Confirm Kill Switch toggle
function confirmKillSwitch(checkbox) {
    if (checkbox.checked) {
        if (!confirm('⚠️ WARNING: This will immediately stop all pipeline execution!\n\nAre you sure you want to enable the Kill Switch?')) {
            checkbox.checked = false;
        }
    }
}

// View backups modal
async function viewBackups() {
    const modal = document.getElementById('backup-modal');
    const backupList = document.getElementById('backup-list');
    
    modal.style.display = 'flex';
    backupList.innerHTML = '<div class="spinner"></div> Loading backups...';
    
    try {
        const response = await fetch('/api/config/backups');
        const data = await response.json();
        
        if (data.success && data.backups.length > 0) {
            backupList.innerHTML = data.backups.map(backup => `
                <div class="backup-item">
                    <div class="backup-info">
                        <div class="backup-name">${backup.filename}</div>
                        <div class="backup-meta">
                            ${new Date(backup.timestamp).toLocaleString()} | ${formatBytes(backup.size)}
                        </div>
                    </div>
                    <button class="btn-restore" onclick="restoreBackup('${backup.filename}')">
                        Restore
                    </button>
                </div>
            `).join('');
        } else {
            backupList.innerHTML = '<p style="color: #999;">No backups found</p>';
        }
    } catch (error) {
        backupList.innerHTML = '<p style="color: #dc3545;">Error loading backups: ' + error.message + '</p>';
    }
}

// Close backup modal
function closeBackupModal() {
    document.getElementById('backup-modal').style.display = 'none';
}

// Restore from backup
async function restoreBackup(filename) {
    if (!confirm(`Restore configuration from backup "${filename}"?\n\nYour current configuration will be backed up first.`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/config/restore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                backup_filename: filename
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showToast('Configuration restored successfully!', 'success');
            closeBackupModal();
            
            // Reload configuration
            await loadConfiguration();
        } else {
            const errorMsg = data.detail?.errors?.join(', ') || data.detail || 'Failed to restore backup';
            showToast(errorMsg, 'error');
        }
    } catch (error) {
        showToast('Error restoring backup: ' + error.message, 'error');
    }
}

// Show toast notification
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? '✓' : type === 'error' ? '✗' : '⚠';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Remove after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Format bytes to human readable
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Close modal on outside click
window.onclick = function(event) {
    const modal = document.getElementById('backup-modal');
    if (event.target === modal) {
        closeBackupModal();
    }
}
