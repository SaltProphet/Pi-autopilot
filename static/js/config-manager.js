// Config Manager Frontend Logic
let currentConfig = {};

// Load configuration on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadConfiguration();
    checkSecurityWarning();
});

/**
 * Load current configuration from API
 */
async function loadConfiguration() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        if (data.success) {
            currentConfig = data.config;
            populateForm(data.config);
        } else {
            showError('Failed to load configuration: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        showError('Error loading configuration: ' + e.message);
    }
}

/**
 * Populate form fields with configuration data
 */
function populateForm(config) {
    // Populate API keys
    if (config.api_keys) {
        for (const [key, data] of Object.entries(config.api_keys)) {
            const inputId = key.toLowerCase();
            const input = document.getElementById(inputId);
            if (input) {
                input.value = data.value || '';
                input.setAttribute('data-original', data.value || '');
            }
        }
    }
    
    // Populate toggles
    if (config.toggles) {
        for (const [key, data] of Object.entries(config.toggles)) {
            const inputId = key.toLowerCase();
            const input = document.getElementById(inputId);
            if (input) {
                input.checked = data.value || false;
            }
        }
    }
    
    // Populate cost limits
    if (config.cost_limits) {
        for (const [key, data] of Object.entries(config.cost_limits)) {
            const inputId = key.toLowerCase();
            const input = document.getElementById(inputId);
            if (input) {
                input.value = data.value || '';
            }
        }
    }
    
    // Populate pipeline settings
    if (config.pipeline) {
        for (const [key, data] of Object.entries(config.pipeline)) {
            const inputId = key.toLowerCase();
            const input = document.getElementById(inputId);
            if (input) {
                input.value = data.value || '';
            }
        }
    }
}

/**
 * Save configuration to API
 */
async function saveConfiguration() {
    // Gather all form values
    const updates = {
        api_keys: {},
        toggles: {},
        cost_limits: {},
        pipeline: {}
    };
    
    // Gather API keys (only if changed)
    const apiKeys = ['OPENAI_API_KEY', 'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USER_AGENT', 'GUMROAD_ACCESS_TOKEN'];
    for (const key of apiKeys) {
        const input = document.getElementById(key.toLowerCase());
        if (input) {
            const originalValue = input.getAttribute('data-original') || '';
            const currentValue = input.value;
            
            // Only include if value has changed and is not a masked placeholder
            if (currentValue !== originalValue && !currentValue.includes('...')) {
                updates.api_keys[key] = currentValue;
            }
        }
    }
    
    // Gather toggles
    const toggles = ['OPENAI_ENABLED', 'REDDIT_ENABLED', 'GUMROAD_ENABLED', 'KILL_SWITCH'];
    for (const key of toggles) {
        const input = document.getElementById(key.toLowerCase());
        if (input) {
            updates.toggles[key] = input.checked;
        }
    }
    
    // Gather cost limits
    const costLimits = ['MAX_USD_PER_RUN', 'MAX_USD_LIFETIME', 'MAX_TOKENS_PER_RUN'];
    for (const key of costLimits) {
        const input = document.getElementById(key.toLowerCase());
        if (input && input.value) {
            const value = key === 'MAX_TOKENS_PER_RUN' ? parseInt(input.value) : parseFloat(input.value);
            updates.cost_limits[key] = value;
        }
    }
    
    // Gather pipeline settings
    const pipelineSettings = ['REDDIT_SUBREDDITS', 'REDDIT_MIN_SCORE', 'REDDIT_POST_LIMIT'];
    for (const key of pipelineSettings) {
        const input = document.getElementById(key.toLowerCase());
        if (input && input.value) {
            if (key === 'REDDIT_SUBREDDITS') {
                updates.pipeline[key] = input.value;
            } else {
                updates.pipeline[key] = parseInt(input.value);
            }
        }
    }
    
    // Client-side validation
    if (Object.keys(updates.api_keys).length === 0 && 
        Object.keys(updates.cost_limits).length === 0 && 
        Object.keys(updates.pipeline).length === 0) {
        // Only toggles changed is okay
        if (Object.keys(updates.toggles).length === 0) {
            showError('No changes detected');
            return;
        }
    }
    
    // Confirm Kill Switch if enabling
    const killSwitchInput = document.getElementById('kill_switch');
    if (killSwitchInput && killSwitchInput.checked && 
        currentConfig.toggles?.KILL_SWITCH?.value === false) {
        if (!confirm('⚠️ Are you sure you want to enable the KILL SWITCH? This will stop ALL pipeline execution!')) {
            killSwitchInput.checked = false;
            return;
        }
    }
    
    // Show loading state
    const saveButton = document.querySelector('.btn-primary');
    const originalText = saveButton.textContent;
    saveButton.textContent = '⏳ Saving...';
    saveButton.disabled = true;
    
    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updates)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            showSuccess('✓ Configuration saved successfully!');
            // Reload configuration to get updated masked values
            await loadConfiguration();
        } else {
            const errors = result.errors || ['Unknown error'];
            showError('Failed to save: ' + errors.join(', '));
        }
    } catch (e) {
        showError('Error saving configuration: ' + e.message);
    } finally {
        saveButton.textContent = originalText;
        saveButton.disabled = false;
    }
}

/**
 * Test API key validity
 */
async function testApiKey(service, inputId) {
    const input = document.getElementById(inputId);
    const statusEl = document.getElementById(`${inputId}_status`);
    const apiKey = input.value;
    
    if (!apiKey || apiKey.includes('...')) {
        statusEl.textContent = 'Please enter an API key';
        statusEl.className = 'status-message error';
        return;
    }
    
    statusEl.textContent = '⏳ Testing...';
    statusEl.className = 'status-message';
    
    try {
        const response = await fetch(`/api/config/test?service=${service}&api_key=${encodeURIComponent(apiKey)}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        statusEl.textContent = result.message;
        statusEl.className = result.success ? 'status-message success' : 'status-message error';
        
        // Log to audit
        if (result.success) {
            console.log(`API key test passed for ${service}`);
        }
    } catch (e) {
        statusEl.textContent = 'Test failed: ' + e.message;
        statusEl.className = 'status-message error';
    }
}

/**
 * Toggle password visibility
 */
function toggleVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
    } else {
        input.type = 'password';
    }
}

/**
 * Reset form to current saved values
 */
function resetForm() {
    if (confirm('Reset all fields to current saved values?')) {
        loadConfiguration();
        
        // Clear all status messages
        const statusMessages = document.querySelectorAll('.status-message');
        statusMessages.forEach(el => {
            el.textContent = '';
            el.className = 'status-message';
        });
    }
}

/**
 * View and manage backups
 */
async function viewBackups() {
    const modal = document.getElementById('backupModal');
    const backupList = document.getElementById('backupList');
    
    modal.style.display = 'block';
    backupList.innerHTML = '<p>Loading backups...</p>';
    
    try {
        const response = await fetch('/api/config/backups');
        const data = await response.json();
        
        if (data.success && data.backups.length > 0) {
            backupList.innerHTML = data.backups.map(backup => `
                <div class="backup-item">
                    <div class="backup-info">
                        <div class="backup-filename">${backup.filename}</div>
                        <div class="backup-meta">
                            Created: ${new Date(backup.created_at).toLocaleString()}
                            | Size: ${(backup.size_bytes / 1024).toFixed(2)} KB
                        </div>
                    </div>
                    <button class="btn-restore" onclick="restoreBackup('${backup.filename}')">
                        Restore
                    </button>
                </div>
            `).join('');
        } else if (data.success && data.backups.length === 0) {
            backupList.innerHTML = '<p style="color: #aaa;">No backups available yet.</p>';
        } else {
            backupList.innerHTML = '<p style="color: #dc3545;">Failed to load backups.</p>';
        }
    } catch (e) {
        backupList.innerHTML = `<p style="color: #dc3545;">Error: ${e.message}</p>`;
    }
}

/**
 * Close backup modal
 */
function closeBackupModal() {
    const modal = document.getElementById('backupModal');
    modal.style.display = 'none';
}

/**
 * Restore configuration from backup
 */
async function restoreBackup(filename) {
    if (!confirm(`Restore configuration from backup: ${filename}?\n\nThis will replace your current configuration.`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/config/restore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ backup_filename: filename })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('✓ Configuration restored successfully!');
            closeBackupModal();
            // Reload configuration
            await loadConfiguration();
        } else {
            showError('Restore failed: ' + result.message);
        }
    } catch (e) {
        showError('Error restoring backup: ' + e.message);
    }
}

/**
 * Check if connection is secure
 */
function checkSecurityWarning() {
    const isSecure = window.location.protocol === 'https:' || 
                     window.location.hostname === 'localhost' ||
                     window.location.hostname === '127.0.0.1';
    
    const warningEl = document.getElementById('securityWarning');
    
    if (!isSecure) {
        warningEl.style.display = 'block';
        warningEl.classList.add('critical');
    }
}

/**
 * Show success message
 */
function showSuccess(message) {
    const statusEl = document.getElementById('saveStatus');
    statusEl.innerHTML = message;
    statusEl.className = 'status-banner success';
    statusEl.style.display = 'block';
    
    setTimeout(() => {
        statusEl.style.display = 'none';
    }, 5000);
}

/**
 * Show error message
 */
function showError(message) {
    const statusEl = document.getElementById('saveStatus');
    statusEl.innerHTML = message;
    statusEl.className = 'status-banner error';
    statusEl.style.display = 'block';
    
    // Don't auto-hide errors
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('backupModal');
    if (event.target === modal) {
        closeBackupModal();
    }
}
