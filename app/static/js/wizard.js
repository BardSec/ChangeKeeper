// Multi-step wizard with sessionStorage persistence

let currentStep = 1;
let systemsTags = [];
let linksTags = [];

// Load draft from sessionStorage on page load
document.addEventListener('DOMContentLoaded', function() {
    loadDraft();
    setupTagInputs();
    setupBackoutValidation();
});

// Navigation functions
function nextStep(stepNumber) {
    if (!validateCurrentStep()) {
        return;
    }

    saveDraft();
    showStep(stepNumber);
}

function prevStep(stepNumber) {
    saveDraft();
    showStep(stepNumber);
}

function showStep(stepNumber) {
    document.querySelectorAll('.wizard-step').forEach(step => {
        step.classList.remove('active');
    });

    document.getElementById(`step-${stepNumber}`).classList.add('active');

    document.querySelectorAll('.step').forEach((step, index) => {
        if (index + 1 <= stepNumber) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });

    currentStep = stepNumber;
    window.scrollTo(0, 0);
}

// Validation
function validateCurrentStep() {
    const currentStepEl = document.getElementById(`step-${currentStep}`);
    const requiredFields = currentStepEl.querySelectorAll('[required]');

    let isValid = true;

    requiredFields.forEach(field => {
        if (!field.value && field.type !== 'radio') {
            field.style.borderColor = 'red';
            isValid = false;
        } else if (field.type === 'radio') {
            const radioGroup = currentStepEl.querySelectorAll(`[name="${field.name}"]`);
            const checked = Array.from(radioGroup).some(r => r.checked);
            if (!checked) {
                isValid = false;
                radioGroup[0].parentElement.parentElement.style.borderColor = 'red';
            }
        } else {
            field.style.borderColor = '';
        }
    });

    // Special validation for systems tags
    if (currentStep === 1 && systemsTags.length === 0) {
        document.getElementById('systems-input').style.borderColor = 'red';
        alert('Please add at least one affected system');
        isValid = false;
    }

    // Backout plan validation
    if (currentStep === 2) {
        const impactLevel = document.getElementById('impact_level').value;
        const backoutPlan = document.getElementById('backout_plan').value;

        if ((impactLevel === 'Medium' || impactLevel === 'High') && !backoutPlan.trim()) {
            document.getElementById('backout_plan').style.borderColor = 'red';
            alert('Backout plan is required for Medium and High impact changes');
            isValid = false;
        }
    }

    if (!isValid) {
        alert('Please fill in all required fields');
    }

    return isValid;
}

// Tag inputs
function setupTagInputs() {
    const systemsInput = document.getElementById('systems-input');
    systemsInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const value = this.value.trim();
            if (value && !systemsTags.includes(value)) {
                systemsTags.push(value);
                renderSystemsTags();
                this.value = '';
                this.style.borderColor = '';
            }
        }
    });

    const linksInput = document.getElementById('links-input');
    linksInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const value = this.value.trim();
            if (value && (value.startsWith('http://') || value.startsWith('https://'))) {
                if (!linksTags.includes(value)) {
                    linksTags.push(value);
                    renderLinksTags();
                    this.value = '';
                }
            } else if (value) {
                alert('Please enter a valid URL starting with http:// or https://');
            }
        }
    });
}

function renderSystemsTags() {
    const container = document.getElementById('systems-tags');
    container.innerHTML = '';

    systemsTags.forEach((tag, index) => {
        const tagEl = document.createElement('div');
        tagEl.className = 'tag-item';

        const textNode = document.createTextNode(tag + ' ');
        tagEl.appendChild(textNode);

        const removeSpan = document.createElement('span');
        removeSpan.className = 'tag-remove';
        removeSpan.textContent = '\u00d7';
        removeSpan.addEventListener('click', () => removeSystemTag(index));
        tagEl.appendChild(removeSpan);

        container.appendChild(tagEl);
    });
}

function renderLinksTags() {
    const container = document.getElementById('links-tags');
    container.innerHTML = '';

    linksTags.forEach((tag, index) => {
        const tagEl = document.createElement('div');
        tagEl.className = 'tag-item';

        const display = tag.length > 50 ? tag.substring(0, 50) + '...' : tag;
        const textNode = document.createTextNode(display + ' ');
        tagEl.appendChild(textNode);

        const removeSpan = document.createElement('span');
        removeSpan.className = 'tag-remove';
        removeSpan.textContent = '\u00d7';
        removeSpan.addEventListener('click', () => removeLinkTag(index));
        tagEl.appendChild(removeSpan);

        container.appendChild(tagEl);
    });
}

function removeSystemTag(index) {
    systemsTags.splice(index, 1);
    renderSystemsTags();
    saveDraft();
}

function removeLinkTag(index) {
    linksTags.splice(index, 1);
    renderLinksTags();
    saveDraft();
}

// Backout plan requirement
function setupBackoutValidation() {
    const impactLevel = document.getElementById('impact_level');
    impactLevel.addEventListener('change', checkBackoutRequired);
}

function checkBackoutRequired() {
    const impactLevel = document.getElementById('impact_level').value;
    const backoutGroup = document.getElementById('backout-group');
    const backoutRequired = document.getElementById('backout-required');
    const backoutPlan = document.getElementById('backout_plan');

    if (impactLevel === 'Medium' || impactLevel === 'High') {
        backoutRequired.style.display = 'inline';
        backoutPlan.required = true;
    } else {
        backoutRequired.style.display = 'none';
        backoutPlan.required = false;
    }
}

// Draft persistence (sessionStorage -- cleared when tab closes)
function saveDraft() {
    const formData = {
        title: document.getElementById('title').value,
        category: document.getElementById('category').value,
        systems_affected: systemsTags,
        planned_start: document.getElementById('planned_start').value,
        planned_end: document.getElementById('planned_end').value,
        implementer: document.getElementById('implementer').value,
        impact_level: document.getElementById('impact_level').value,
        user_impact: document.getElementById('user_impact').value,
        maintenance_window: document.querySelector('[name="maintenance_window"]:checked')?.value,
        backout_plan: document.getElementById('backout_plan').value,
        what_changed: document.getElementById('what_changed').value,
        ticket_id: document.getElementById('ticket_id').value,
        links: linksTags,
        status: document.getElementById('status').value,
        outcome_notes: document.getElementById('outcome_notes').value,
        post_change_issues: document.getElementById('post_change_issues').value,
    };

    sessionStorage.setItem('changeDraft', JSON.stringify(formData));
}

function loadDraft() {
    const draft = sessionStorage.getItem('changeDraft');
    if (!draft) return;

    try {
        const data = JSON.parse(draft);

        if (confirm('You have a saved draft. Would you like to restore it?')) {
            document.getElementById('title').value = data.title || '';
            document.getElementById('category').value = data.category || '';
            systemsTags = data.systems_affected || [];
            renderSystemsTags();
            document.getElementById('planned_start').value = data.planned_start || '';
            document.getElementById('planned_end').value = data.planned_end || '';
            document.getElementById('implementer').value = data.implementer || '';
            document.getElementById('impact_level').value = data.impact_level || '';
            document.getElementById('user_impact').value = data.user_impact || '';

            if (data.maintenance_window) {
                const radio = document.querySelector(`[name="maintenance_window"][value="${data.maintenance_window}"]`);
                if (radio) radio.checked = true;
            }

            document.getElementById('backout_plan').value = data.backout_plan || '';
            document.getElementById('what_changed').value = data.what_changed || '';
            document.getElementById('ticket_id').value = data.ticket_id || '';
            linksTags = data.links || [];
            renderLinksTags();
            document.getElementById('status').value = data.status || 'Planned';
            document.getElementById('outcome_notes').value = data.outcome_notes || '';
            document.getElementById('post_change_issues').value = data.post_change_issues || '';
        } else {
            sessionStorage.removeItem('changeDraft');
        }
    } catch (e) {
        console.error('Error loading draft:', e);
        sessionStorage.removeItem('changeDraft');
    }
}

function clearDraft() {
    sessionStorage.removeItem('changeDraft');
}

// Form submission
document.getElementById('wizardForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    if (!validateCurrentStep()) {
        return;
    }

    const formData = new FormData();

    // Include CSRF token
    const csrfInput = document.getElementById('csrf_token');
    if (csrfInput) {
        formData.append('csrf_token', csrfInput.value);
    }

    formData.append('title', document.getElementById('title').value);
    formData.append('category', document.getElementById('category').value);
    systemsTags.forEach(tag => formData.append('systems_affected', tag));
    formData.append('planned_start', document.getElementById('planned_start').value);
    formData.append('planned_end', document.getElementById('planned_end').value);
    formData.append('implementer', document.getElementById('implementer').value);
    formData.append('impact_level', document.getElementById('impact_level').value);
    formData.append('user_impact', document.getElementById('user_impact').value);
    formData.append('maintenance_window', document.querySelector('[name="maintenance_window"]:checked')?.value);
    formData.append('backout_plan', document.getElementById('backout_plan').value);
    formData.append('what_changed', document.getElementById('what_changed').value);
    formData.append('ticket_id', document.getElementById('ticket_id').value);
    linksTags.forEach(link => formData.append('links', link));
    formData.append('status', document.getElementById('status').value);
    formData.append('outcome_notes', document.getElementById('outcome_notes').value);
    formData.append('post_change_issues', document.getElementById('post_change_issues').value);

    const emailCopy = document.getElementById('email_copy');
    if (emailCopy) {
        formData.append('email_copy', emailCopy.checked ? 'true' : 'false');
    }

    const confirmSecrets = document.getElementById('confirm_no_secrets');
    if (confirmSecrets) {
        formData.append('confirm_no_secrets', confirmSecrets.checked ? 'true' : 'false');
    }

    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating...';

    try {
        const response = await fetch('/changes', {
            method: 'POST',
            headers: {'Accept': 'application/json'},
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            clearDraft();
            window.location.href = `/changes/${result.change_id}`;
        } else {
            const result = await response.json();

            if (result.detail && result.detail.includes('secret')) {
                document.getElementById('secret-warning').style.display = 'block';
                document.getElementById('secret-details').textContent = result.detail;
            } else {
                alert('Error: ' + (result.detail || 'Failed to create change record'));
            }

            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Change Record';
        }
    } catch (error) {
        alert('Network error: ' + error.message);
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Change Record';
    }
});

// Auto-save on input
let saveTimeout;
document.querySelectorAll('input, select, textarea').forEach(field => {
    field.addEventListener('input', function() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(saveDraft, 1000);
    });
});
