/* global API */

(function () {
    const state = {
        goals: [],
        deleteGoalId: null,
    };

    const currencyFormatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 2,
    });

    function safeNumber(value, fallback = 0) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatCurrency(value) {
        return currencyFormatter.format(safeNumber(value));
    }

    function formatMonths(value) {
        if (!Number.isFinite(value)) {
            return 'n/a';
        }

        return `${Math.max(0, value).toFixed(value >= 10 ? 1 : 2)} mo`;
    }

    function formatFeasibility(value) {
        const normalized = String(value || '').trim().toLowerCase();
        if (!normalized) {
            return '';
        }

        return normalized.charAt(0).toUpperCase() + normalized.slice(1);
    }

    function apiRequest(endpoint, options = {}) {
        const headers = { ...(options.headers || {}) };
        if (!(options.body instanceof FormData) && !headers['Content-Type'] && !headers['content-type']) {
            headers['Content-Type'] = 'application/json';
        }

        return fetch(endpoint, {
            credentials: 'same-origin',
            ...options,
            headers,
        }).then(async (response) => {
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || payload.status === 'error') {
                throw new Error(payload.message || `Request failed (${response.status})`);
            }
            return payload.data ?? payload;
        });
    }

    function renderSummary(goals) {
        const first = goals[0];
        const avgSavings = document.getElementById('summaryAvgSavings');
        const topCategory = document.getElementById('summaryTopCategory');
        const feasibility = document.getElementById('summaryFeasibility');
        const feasibilityMeta = document.getElementById('summaryFeasibilityMeta');

        if (!first) {
            if (avgSavings) avgSavings.innerText = 'No data yet';
            if (topCategory) topCategory.innerText = 'No data yet';
            if (feasibility) feasibility.innerText = 'No data yet';
            if (feasibilityMeta) feasibilityMeta.innerText = 'Based on current savings pace';
            return;
        }

        const analysis = first.analysis || {};
        const avg = safeNumber(first.smart_analysis?.avg_savings);
        const top = first.smart_analysis?.top_category || 'No data yet';
        const label = formatFeasibility(analysis.feasibility) || 'No data yet';

        if (avgSavings) avgSavings.innerText = formatCurrency(avg);
        if (topCategory) topCategory.innerText = top;
        if (feasibility) feasibility.innerText = label;
        if (feasibilityMeta) feasibilityMeta.innerText = analysis.warning || 'Based on current savings pace';
    }

    function renderGoalCard(goal) {
        const analysis = goal.analysis || {};
        const progressPercent = safeNumber(goal.progress_percent);
        const remaining = safeNumber(goal.remaining_amount);
        const target = safeNumber(goal.target_amount);
        const saved = safeNumber(goal.saved_amount);
        const months = goal.smart_analysis?.last_3_months || [];
        const monthsText = months.length
            ? months.map((item) => `${escapeHtml(item.label || item.month || '')}: ${formatCurrency(item.savings)}`).join(' | ')
            : 'No data yet';

        return `
            <article
                class="goals-card glass-card"
                data-goal-card="${goal.id}"
                data-target="${target}"
                data-saved="${saved}"
                data-remaining="${remaining}"
                data-progress="${progressPercent}"
                data-analysis-best="${escapeHtml(analysis.best_months ?? '')}"
                data-analysis-realistic="${escapeHtml(analysis.realistic_months ?? '')}"
                data-analysis-worst="${escapeHtml(analysis.worst_months ?? '')}"
                data-analysis-feasibility="${escapeHtml(analysis.feasibility || '')}"
                data-analysis-tone="${escapeHtml(analysis.tone || '')}"
                data-analysis-insight="${escapeHtml(analysis.insight || '')}"
                data-analysis-warning="${escapeHtml(analysis.warning || '')}"
                data-analysis-tip="${escapeHtml(analysis.tip || '')}"
            >
                <div class="goals-card-top">
                    <div>
                        <h4 class="goals-card-title">${escapeHtml(goal.goal_name)}</h4>
                        <p class="goals-card-subtitle">${goal.deadline ? `Deadline: ${escapeHtml(goal.deadline)}` : 'No deadline set'}</p>
                    </div>
                    <span class="goals-badge goals-badge--${analysis.tone || 'neutral'}">${formatFeasibility(analysis.feasibility) || 'No data yet'}</span>
                </div>

                <div class="goals-progress">
                    <div class="goals-progress-row">
                        <span>${progressPercent.toFixed(0)}% complete</span>
                        <span>${formatCurrency(remaining)} remaining</span>
                    </div>
                    <div class="goals-progress-bar">
                        <div class="goals-progress-fill" style="width: ${Math.max(0, Math.min(100, progressPercent))}%"></div>
                    </div>
                </div>

                <div class="goals-stats-grid">
                    <div class="goals-stat">
                        <span class="goals-stat-label">Target</span>
                        <strong>${formatCurrency(target)}</strong>
                    </div>
                    <div class="goals-stat">
                        <span class="goals-stat-label">Saved</span>
                        <strong>${formatCurrency(saved)}</strong>
                    </div>
                    <div class="goals-stat">
                        <span class="goals-stat-label">Remaining</span>
                        <strong>${formatCurrency(remaining)}</strong>
                    </div>
                </div>

                <div class="goals-stats-grid">
                    <div class="goals-stat">
                        <span class="goals-stat-label">Best</span>
                        <strong data-role="best-months">${formatMonths(analysis.best_months)}</strong>
                    </div>
                    <div class="goals-stat">
                        <span class="goals-stat-label">Realistic</span>
                        <strong data-role="real-months">${formatMonths(analysis.realistic_months)}</strong>
                    </div>
                    <div class="goals-stat">
                        <span class="goals-stat-label">Worst</span>
                        <strong data-role="worst-months">${formatMonths(analysis.worst_months)}</strong>
                    </div>
                </div>

                <div class="goals-insight">
                    <strong data-role="goal-insight">${escapeHtml(analysis.insight)}</strong>
                    <span data-role="goal-tip">${escapeHtml(analysis.tip || 'No tip available yet')}</span>
                    <small data-role="goal-warning">${escapeHtml(analysis.warning)}</small>
                    <p class="goals-month-summary">${monthsText}</p>
                </div>

                <div class="goals-extra-savings">
                    <label for="extra-saving-${goal.id}">Extra monthly saving</label>
                    <input id="extra-saving-${goal.id}" type="number" min="0" step="0.01" value="0" class="goals-input" data-role="extra-saving">
                </div>

                <div class="goals-card-actions">
                    <button type="button" class="goals-action-btn" data-edit-goal="${goal.id}">Edit</button>
                    <button type="button" class="goals-action-btn goals-action-btn--danger" data-delete-goal="${goal.id}">Delete</button>
                </div>
            </article>
        `;
    }

    function renderGoals(goals) {
        const container = document.getElementById('goalsContainer');
        if (!container) {
            return;
        }

        if (!goals.length) {
            container.innerHTML = `
                <div class="goals-empty-state glass-card">
                    <h4>No goals yet</h4>
                    <p>Create your first goal to start tracking progress and savings pace.</p>
                    <button type="button" class="btn-premium" data-focus-create>Create Your First Goal</button>
                </div>
            `;
            return;
        }

        container.innerHTML = goals.map(renderGoalCard).join('');
    }

    function refreshGoalCard(card) {
        if (!card) {
            return;
        }

        const remaining = safeNumber(card.dataset.remaining);
        const progress = safeNumber(card.dataset.progress);
        const analysis = {
            best_months: safeNumber(card.dataset.analysisBest, Number.NaN),
            realistic_months: safeNumber(card.dataset.analysisRealistic, Number.NaN),
            worst_months: safeNumber(card.dataset.analysisWorst, Number.NaN),
            feasibility: card.dataset.analysisFeasibility || '',
            tone: card.dataset.analysisTone || '',
            insight: card.dataset.analysisInsight || 'No clear timeline yet',
            warning: card.dataset.analysisWarning || '',
            tip: card.dataset.analysisTip || '',
        };

        const bestNode = card.querySelector('[data-role="best-months"]');
        const realNode = card.querySelector('[data-role="real-months"]');
        const worstNode = card.querySelector('[data-role="worst-months"]');
        const insightNode = card.querySelector('[data-role="goal-insight"]');
        const tipNode = card.querySelector('[data-role="goal-tip"]');
        const warningNode = card.querySelector('[data-role="goal-warning"]');
        const badgeNode = card.querySelector('.goals-badge');
        const progressFill = card.querySelector('.goals-progress-fill');
        const progressText = card.querySelector('.goals-progress-row span:first-child');
        const remainingText = card.querySelector('.goals-progress-row span:last-child');

        if (bestNode) bestNode.innerText = formatMonths(analysis.best_months);
        if (realNode) realNode.innerText = formatMonths(analysis.realistic_months);
        if (worstNode) worstNode.innerText = formatMonths(analysis.worst_months);
        if (insightNode) insightNode.innerText = analysis.insight;
        if (tipNode) tipNode.innerText = analysis.tip || 'No tip available yet';
        if (warningNode) warningNode.innerText = analysis.warning;
        if (badgeNode) {
            badgeNode.className = `goals-badge goals-badge--${analysis.tone || 'neutral'}`;
            badgeNode.innerText = formatFeasibility(analysis.feasibility) || 'No data yet';
        }
        if (progressFill) progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
        if (progressText) progressText.innerText = `${progress.toFixed(0)}% complete`;
        if (remainingText) remainingText.innerText = `${formatCurrency(remaining)} remaining`;
    }

    function openEditModal(goal) {
        const modal = document.getElementById('goalEditModal');
        if (!modal || !goal) {
            return;
        }

        document.getElementById('goalEditId').value = goal.id;
        document.getElementById('goalEditName').value = goal.goal_name || '';
        document.getElementById('goalEditTarget').value = safeNumber(goal.target_amount);
        document.getElementById('goalEditSaved').value = safeNumber(goal.saved_amount);
        document.getElementById('goalEditDeadline').value = goal.deadline || '';
        document.getElementById('goalEditType').value = String(goal.goal_type || 'short').toUpperCase();
        document.getElementById('goalEditStatus').innerText = '';
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
    }

    function closeModal(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.remove('is-open');
            modal.setAttribute('aria-hidden', 'true');
        }
    }

    function openDeleteModal(goal) {
        const modal = document.getElementById('goalDeleteModal');
        if (!modal || !goal) {
            return;
        }

        state.deleteGoalId = goal.id;
        document.getElementById('goalDeleteTitle').innerText = `Remove ${goal.goal_name || 'this goal'}?`;
        document.getElementById('goalDeleteText').innerText = `Deleting ${goal.goal_name || 'this goal'} will remove it from the dashboard.`;
        document.getElementById('goalDeleteStatus').innerText = '';
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
    }

    async function loadGoals() {
        const container = document.getElementById('goalsContainer');
        if (!container) {
            return;
        }

        container.innerHTML = '<div class="goals-empty-state glass-card">Loading goals...</div>';

        try {
            const [dashboardResult, goalsResult] = await Promise.allSettled([
                typeof API !== 'undefined' && API.getDashboard ? API.getDashboard() : apiRequest('/api/analysis/data'),
                typeof API !== 'undefined' && API.getGoals ? API.getGoals() : apiRequest('/api/expense/goal/all'),
            ]);

            const goals = goalsResult.status === 'fulfilled' && Array.isArray(goalsResult.value) ? goalsResult.value : [];
            state.goals = goals;

            renderSummary(goals);
            renderGoals(goals);

            if (goals.length) {
                container.querySelectorAll('[data-goal-card]').forEach((card) => refreshGoalCard(card));
            }
        } catch (error) {
            container.innerHTML = `<div class="goals-empty-state glass-card">Unable to load goals. ${escapeHtml(error.message || '')}</div>`;
            renderSummary([]);
        }
    }

    async function handleCreateGoal(event) {
        event.preventDefault();

        const status = document.getElementById('goalStatusMsg');
        const form = event.currentTarget;
        const payload = {
            name: form.name.value.trim(),
            target: safeNumber(form.target.value),
            saved: safeNumber(form.saved.value),
            deadline: form.deadline.value,
            type: form.type.value,
        };

        if (status) {
            status.innerText = 'Creating goal...';
        }

        try {
            await (typeof API !== 'undefined' && API.addGoal
                ? API.addGoal(payload)
                : apiRequest('/api/expense/goal/add', { method: 'POST', body: JSON.stringify(payload) }));
            if (status) {
                status.innerText = 'Goal created successfully.';
                status.classList.add('is-success');
            }
            form.reset();
            form.type.value = 'short';
            loadGoals();
        } catch (error) {
            if (status) {
                status.innerText = error.message || 'Unable to create goal.';
                status.classList.remove('is-success');
            }
        }
    }

    async function handleEditGoal(event) {
        event.preventDefault();

        const status = document.getElementById('goalEditStatus');
        const form = event.currentTarget;
        const payload = {
            goal_id: form.goal_id.value,
            name: form.name.value.trim(),
            target: safeNumber(form.target.value),
            saved: safeNumber(form.saved.value),
            deadline: form.deadline.value,
            type: form.type.value,
        };

        if (status) {
            status.innerText = 'Saving changes...';
        }

        try {
            await apiRequest('/api/expense/goal/update', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            if (status) {
                status.innerText = 'Goal updated.';
                status.classList.add('is-success');
            }
            closeModal('goalEditModal');
            loadGoals();
        } catch (error) {
            if (status) {
                status.innerText = error.message || 'Unable to update goal.';
                status.classList.remove('is-success');
            }
        }
    }

    async function handleDeleteGoal() {
        const status = document.getElementById('goalDeleteStatus');

        if (!state.deleteGoalId) {
            closeModal('goalDeleteModal');
            return;
        }

        if (status) {
            status.innerText = 'Deleting goal...';
        }

        try {
            await apiRequest('/api/expense/goal/delete', {
                method: 'POST',
                body: JSON.stringify({ goal_id: state.deleteGoalId }),
            });
            if (status) {
                status.innerText = 'Goal deleted.';
                status.classList.add('is-success');
            }
            state.deleteGoalId = null;
            closeModal('goalDeleteModal');
            loadGoals();
        } catch (error) {
            if (status) {
                status.innerText = error.message || 'Unable to delete goal.';
                status.classList.remove('is-success');
            }
        }
    }

    function bindEvents() {
        const goalForm = document.getElementById('goalForm');
        const editForm = document.getElementById('goalEditForm');
        const goalsContainer = document.getElementById('goalsContainer');

        if (goalForm) {
            goalForm.addEventListener('submit', handleCreateGoal);
        }

        if (editForm) {
            editForm.addEventListener('submit', handleEditGoal);
        }

        if (goalsContainer) {
            goalsContainer.addEventListener('click', (event) => {
                const editBtn = event.target.closest('[data-edit-goal]');
                const deleteBtn = event.target.closest('[data-delete-goal]');
                const firstGoalBtn = event.target.closest('[data-focus-create]');

                if (editBtn) {
                    const goal = state.goals.find((item) => String(item.id) === String(editBtn.dataset.editGoal));
                    openEditModal(goal);
                    return;
                }

                if (deleteBtn) {
                    const goal = state.goals.find((item) => String(item.id) === String(deleteBtn.dataset.deleteGoal));
                    openDeleteModal(goal);
                    return;
                }

                if (firstGoalBtn) {
                    document.getElementById('goalName')?.focus();
                }
            });

            goalsContainer.addEventListener('input', (event) => {
                const input = event.target.closest('[data-role="extra-saving"]');
                if (!input) {
                    return;
                }

                const card = input.closest('[data-goal-card]');
                refreshGoalCard(card);
            });
        }

        document.querySelectorAll('[data-focus-create]').forEach((button) => {
            button.addEventListener('click', () => {
                document.getElementById('goalName')?.focus();
            });
        });

        document.querySelectorAll('[data-close-edit-modal]').forEach((button) => {
            button.addEventListener('click', () => closeModal('goalEditModal'));
        });

        document.querySelectorAll('[data-close-delete-modal]').forEach((button) => {
            button.addEventListener('click', () => closeModal('goalDeleteModal'));
        });

        document.getElementById('goalEditModal')?.addEventListener('click', (event) => {
            if (event.target.id === 'goalEditModal') {
                closeModal('goalEditModal');
            }
        });

        document.getElementById('goalDeleteModal')?.addEventListener('click', (event) => {
            if (event.target.id === 'goalDeleteModal') {
                closeModal('goalDeleteModal');
            }
        });

        document.getElementById('confirmDeleteGoal')?.addEventListener('click', handleDeleteGoal);

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeModal('goalEditModal');
                closeModal('goalDeleteModal');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        loadGoals();
    });
})();
