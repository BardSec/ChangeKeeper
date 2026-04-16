// Quick Log — minimal change entry with high-impact expansion

let systemsTags = [];

document.addEventListener('DOMContentLoaded', function() {
    setupTagInput();
    setupImpactToggle();
});

function setupTagInput() {
    const input = document.getElementById('systems-input');
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const value = this.value.trim();
            if (value && !systemsTags.includes(value)) {
                systemsTags.push(value);
                renderTags();
                this.value = '';
                this.style.borderColor = '';
            }
        }
    });
}

function renderTags() {
    const container = document.getElementById('systems-tags');
    container.innerHTML = '';
    systemsTags.forEach(function(tag, index) {
        const el = document.createElement('div');
        el.className = 'tag-item';
        const text = document.createTextNode(tag + ' ');
        el.appendChild(text);
        const remove = document.createElement('span');
        remove.className = 'tag-remove';
        remove.textContent = '\u00d7';
        remove.addEventListener('click', function() {
            systemsTags.splice(index, 1);
            renderTags();
        });
        el.appendChild(remove);
        container.appendChild(el);
    });
}

function setupImpactToggle() {
    const select = document.getElementById('impact_level');
    select.addEventListener('change', toggleHighImpact);
    toggleHighImpact(); // set initial state
}

function toggleHighImpact() {
    const impact = document.getElementById('impact_level').value;
    const expanded = document.getElementById('high-impact-fields');
    const userImpact = document.getElementById('user-impact-group');
    const isHigh = impact === 'High';

    expanded.style.display = isHigh ? 'block' : 'none';
    userImpact.style.display = isHigh ? 'block' : 'none';

    // Update button text
    var btn = document.getElementById('submitBtn');
    if (!btn.disabled) {
        btn.textContent = isHigh ? 'Save Full Change' : 'Save Quick Log';
    }
}

document.getElementById('quickLogForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const title = document.getElementById('title').value.trim();
    if (!title) {
        alert('Please enter what you did');
        return;
    }
    if (!document.getElementById('category').value) {
        alert('Please select a category');
        return;
    }
    if (systemsTags.length === 0) {
        document.getElementById('systems-input').style.borderColor = 'red';
        alert('Please add at least one affected system');
        return;
    }

    var isHigh = document.getElementById('impact_level').value === 'High';

    // Validate expanded fields when High
    if (isHigh) {
        var whatChanged = document.getElementById('what_changed').value.trim();
        var backoutPlan = document.getElementById('backout_plan').value.trim();
        if (!whatChanged) {
            document.getElementById('what_changed').style.borderColor = 'red';
            alert('What Changed is required for High impact changes');
            return;
        }
        if (!backoutPlan) {
            document.getElementById('backout_plan').style.borderColor = 'red';
            alert('Backout Plan is required for High impact changes');
            return;
        }
    }

    const formData = new FormData();
    const csrfInput = document.getElementById('csrf_token');
    if (csrfInput) formData.append('csrf_token', csrfInput.value);

    formData.append('title', title);
    formData.append('category', document.getElementById('category').value);
    formData.append('impact_level', document.getElementById('impact_level').value);
    formData.append('status', document.getElementById('status').value);
    systemsTags.forEach(function(tag) { formData.append('systems_affected', tag); });

    // Include expanded fields when High
    if (isHigh) {
        formData.append('user_impact', document.getElementById('user_impact').value);
        formData.append('what_changed', document.getElementById('what_changed').value);
        formData.append('backout_plan', document.getElementById('backout_plan').value);
        var mw = document.querySelector('[name="maintenance_window"]:checked');
        formData.append('maintenance_window', mw ? mw.value : 'false');
        var notes = document.getElementById('outcome_notes').value;
        if (notes) formData.append('outcome_notes', notes);
    }

    const confirmSecrets = document.getElementById('confirm_no_secrets');
    if (confirmSecrets) {
        formData.append('confirm_no_secrets', confirmSecrets.checked ? 'true' : 'false');
    }

    const btn = document.getElementById('submitBtn');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    var defaultBtnText = isHigh ? 'Save Full Change' : 'Save Quick Log';

    try {
        const response = await fetch('/changes/quick', {
            method: 'POST',
            headers: {'Accept': 'application/json'},
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            window.location.href = '/changes/' + result.change_id;
        } else {
            const result = await response.json();
            if (result.detail && result.detail.includes('secret')) {
                document.getElementById('secret-warning').style.display = 'block';
                document.getElementById('secret-details').textContent = result.detail;
            } else {
                alert('Error: ' + (result.detail || 'Failed to save'));
            }
            btn.disabled = false;
            btn.textContent = defaultBtnText;
        }
    } catch (error) {
        alert('Network error: ' + error.message);
        btn.disabled = false;
        btn.textContent = defaultBtnText;
    }
});
