/* global API */

(function () {
    const state = {
        goals: [],
        portfolio: {},
        allocation: {},
        decision: {},
        detailGoalId: null,
        view: 'dashboard',
        filterStatus: 'all',
        sortBy: 'priority',
        search: '',
        compact: false,
    };

    const CURRENCY = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const PRIORITY_ORDER = { critical: 1, high: 2, medium: 3, low: 4 };

    const $ = (selector) => document.querySelector(selector);
    const escapeHtml = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    const num = (value, fallback = 0) => {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    };
    const money = (value) => CURRENCY.format(num(value));
    const titleCase = (value) => {
        const normalized = String(value || '').trim().toLowerCase();
        return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : 'n/a';
    };

    function toggleModal(modalId, isOpen) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.toggle('is-open', isOpen);
        modal.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
    }

    function setView(view) {
        state.view = view;
        ['dashboard', 'portfolio', 'detail'].forEach((key) => {
            const node = document.getElementById(`goals${key[0].toUpperCase()}${key.slice(1)}View`);
            if (node) node.classList.toggle('is-hidden', key !== view);
        });
        document.querySelectorAll('[data-view-btn]').forEach((button) => {
            button.classList.toggle('is-active', button.dataset.viewBtn === view);
        });
    }

    function renderDashboard() {
        const summaryGrid = $('#goalsSummaryGrid');
        if (!summaryGrid) return;

        const p = state.portfolio || {};
        const feasibility = titleCase(p.portfolio_feasibility || 'healthy');
        const warnings = (p.warnings || []).slice(0, 2);
        summaryGrid.innerHTML = `
            <div class="goals-hero-metric">
                <div>
                    <p class="goals-eyebrow">Portfolio Health</p>
                    <h3 class="goals-hero-value">${escapeHtml(feasibility)}</h3>
                    <p class="goals-hero-sub">Total progress ${num(p.avg_progress).toFixed(1)}% across ${num(p.total_goals)} goals</p>
                </div>
                <div class="goals-hero-sub">Required monthly savings: <strong style="color:#fff;">$${money(p.required_monthly_savings)}</strong></div>
            </div>
            <div class="goals-summary-strip">
                <div class="goals-summary-item"><span class="goals-summary-label">Target</span><strong class="goals-summary-value">$${money(p.total_target)}</strong><span class="goals-summary-sub">Portfolio total</span></div>
                <div class="goals-summary-item"><span class="goals-summary-label">Saved</span><strong class="goals-summary-value">$${money(p.total_saved)}</strong><span class="goals-summary-sub">Current progress</span></div>
                <div class="goals-summary-item"><span class="goals-summary-label">Remaining</span><strong class="goals-summary-value">$${money(p.total_remaining)}</strong><span class="goals-summary-sub">To complete</span></div>
                <div class="goals-summary-item"><span class="goals-summary-label">Active</span><strong class="goals-summary-value">${num(p.active_goals)}</strong><span class="goals-summary-sub">In execution</span></div>
                <div class="goals-summary-item"><span class="goals-summary-label">Paused/Done</span><strong class="goals-summary-value">${num(p.paused_goals)}/${num(p.completed_goals)}</strong><span class="goals-summary-sub">Lifecycle mix</span></div>
            </div>
            <div class="goals-inline-risks">
                ${warnings.length ? warnings.map((item) => `<div class="goals-risk"><span class="goals-risk-dot"></span>${escapeHtml(item)}</div>`).join('') : '<div class="goals-risk"><span class="goals-risk-dot" style="background:#10b981;"></span>No critical warnings in current plan.</div>'}
            </div>
        `;

        const feasibilityPanel = $('#portfolioFeasibilityPanel');
        if (feasibilityPanel) {
            const ratio = num(state.allocation.allocation_load_ratio);
            const tone = ratio > 1 ? 'is-risk' : ratio > 0.8 ? 'is-watch' : 'is-good';
            feasibilityPanel.className = `goals-insight-panel glass-card ${tone}`;
            feasibilityPanel.innerHTML = `
                <p class="goals-eyebrow">Allocation Load</p>
                <h4>${titleCase(p.portfolio_feasibility || 'healthy')}</h4>
                <p>Available savings: $${money(state.allocation.available_monthly_savings)}</p>
                <p>Load ratio: ${ratio.toFixed(2)}x</p>
            `;
        }

        const warningsPanel = $('#portfolioWarningsPanel');
        if (warningsPanel) {
            const panelWarnings = (p.warnings || []).slice(0, 4);
            warningsPanel.className = 'goals-insight-panel glass-card is-watch';
            warningsPanel.innerHTML = `
                <p class="goals-eyebrow">Feasibility Signals</p>
                <h4>Warnings</h4>
                ${panelWarnings.length ? `<ul>${panelWarnings.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '<p>No portfolio warnings right now.</p>'}
            `;
        }

        const deadlinesPanel = $('#portfolioDeadlinesPanel');
        if (deadlinesPanel) {
            const conflicts = (p.conflicts || []).slice(0, 4);
            deadlinesPanel.className = `goals-insight-panel glass-card ${conflicts.length ? 'is-risk' : 'is-good'}`;
            deadlinesPanel.innerHTML = `
                <p class="goals-eyebrow">Upcoming Risks</p>
                <h4>Deadline Conflicts</h4>
                ${conflicts.length ? `<ul>${conflicts.map((item) => `<li>${escapeHtml(item.message || item.type || 'Conflict detected')}</li>`).join('')}</ul>` : '<p>No high-risk conflicts detected.</p>'}
            `;
        }
    }

    function applyGoalFilters(goals) {
        return goals
            .filter((goal) => state.filterStatus === 'all' || String(goal.status || '').toLowerCase() === state.filterStatus)
            .filter((goal) => !state.search || String(goal.goal_name || '').toLowerCase().includes(state.search.toLowerCase()))
            .sort((a, b) => {
                if (state.sortBy === 'deadline') return String(a.deadline || '9999-12-31').localeCompare(String(b.deadline || '9999-12-31'));
                if (state.sortBy === 'progress') return num(b.progress_percent) - num(a.progress_percent);
                if (state.sortBy === 'remaining') return num(b.remaining_amount) - num(a.remaining_amount);
                return (PRIORITY_ORDER[String(a.priority || 'medium').toLowerCase()] || 3) - (PRIORITY_ORDER[String(b.priority || 'medium').toLowerCase()] || 3);
            });
    }

    function lifecycleActions(status) {
        const normalized = String(status || 'active').toLowerCase();
        if (normalized === 'active') return ['paused', 'completed', 'archived'];
        if (normalized === 'paused') return ['active', 'archived'];
        if (normalized === 'completed') return ['archived'];
        return [];
    }

    function renderPortfolio() {
        const grid = $('#goalsPortfolioGrid');
        if (!grid) return;

        const goals = applyGoalFilters(state.goals);
        grid.classList.toggle('is-compact', state.compact);

        if (!goals.length) {
            grid.innerHTML = '<div class="goals-empty-state">No goals match this view.</div>';
            return;
        }

        grid.innerHTML = goals.map((goal) => {
            const actions = lifecycleActions(goal.status)
                .map((targetStatus) => `<button type="button" class="goals-action-btn" data-action="status" data-goal-id="${goal.id}" data-target-status="${targetStatus}">${titleCase(targetStatus)}</button>`)
                .join('');
            const progress = Math.max(0, Math.min(100, num(goal.progress_percent)));
            const deadlineClass = goal.analysis?.required_monthly > goal.analysis?.allocated_monthly ? ' style="border-left:3px solid #ef4444;"' : '';

            return `
                <article class="goals-portfolio-card glass-card"${deadlineClass}>
                    <div class="goals-progress-ring" style="--progress:${progress};">
                        <span>${progress.toFixed(0)}%</span>
                    </div>
                    <div class="goals-card-main">
                        <div>
                            <h4 class="goals-card-title">${escapeHtml(goal.goal_name || 'Untitled Goal')}</h4>
                            <p class="goals-card-subtitle">${goal.deadline ? `Deadline: ${escapeHtml(goal.deadline)}` : 'No deadline set'}</p>
                        </div>
                        <div class="goals-status-line">
                            <span class="goals-status-item status-${escapeHtml(String(goal.status || 'active').toLowerCase())}">
                                <span class="goals-dot status-${escapeHtml(String(goal.status || 'active').toLowerCase())}"></span>${titleCase(goal.status || 'active')}
                            </span>
                            <span class="goals-status-item">
                                <span class="goals-dot" style="background:#4f8ef7;"></span>${titleCase(goal.priority || 'medium')}
                            </span>
                        </div>
                        <div class="goals-card-stats">
                            <div class="goals-card-stat"><strong>$${money(goal.remaining_amount)}</strong><span>Remaining</span></div>
                            <div class="goals-card-stat"><strong>$${money(goal.analysis?.allocated_monthly)}</strong><span>Allocated / mo</span></div>
                            <div class="goals-card-stat"><strong>${goal.analysis?.realistic_months == null ? 'n/a' : `${num(goal.analysis.realistic_months).toFixed(1)} mo`}</strong><span>Projection</span></div>
                        </div>
                    </div>
                    <div class="goals-card-actions">
                        <button type="button" class="goals-action-btn" data-action="detail" data-goal-id="${goal.id}">View Analysis</button>
                        <div class="goals-overflow">
                            <button type="button" class="goals-overflow-trigger">···</button>
                            <div class="goals-overflow-menu">
                                <button type="button" class="goals-action-btn" data-action="edit" data-goal-id="${goal.id}">Edit</button>
                                ${actions}
                                <button type="button" class="goals-action-btn goals-action-btn--danger" data-action="status" data-goal-id="${goal.id}" data-target-status="archived">Archive</button>
                            </div>
                        </div>
                    </div>
                </article>
            `;
        }).join('');
    }

    function renderDetailSelector() {
        const select = $('#goalDetailSelect');
        if (!select) return;

        if (!state.goals.length) {
            select.innerHTML = '<option value="">No goals available</option>';
            state.detailGoalId = null;
            return;
        }

        const preferred = state.detailGoalId || state.goals[0].id;
        state.detailGoalId = preferred;
        select.innerHTML = state.goals.map((goal) => `
            <option value="${goal.id}" ${String(goal.id) === String(preferred) ? 'selected' : ''}>
                ${escapeHtml(goal.goal_name)} (${titleCase(goal.status || 'active')})
            </option>
        `).join('');
    }

    async function renderDetailCard() {
        const card = $('#goalDetailCard');
        if (!card) return;

        if (!state.detailGoalId) {
            card.innerHTML = '<div class="goals-empty-state">Pick a goal to view deep analysis.</div>';
            return;
        }

        card.innerHTML = '<div class="goals-empty-state">Loading detail...</div>';
        try {
            const detail = await API.getGoalDetail(state.detailGoalId);
            const analysis = detail.analysis || {};
            const smart = detail.smart_analysis || {};
            const velocity = Math.max(0, Math.min(100, num(detail.progress_percent)));
            card.innerHTML = `
                <div class="goals-card-top">
                    <div>
                        <p class="goals-eyebrow">Goal Detail Report</p>
                        <h3 class="goals-card-title">${escapeHtml(detail.goal_name || 'Goal')}</h3>
                        <p class="goals-card-subtitle">${detail.deadline ? `Deadline: ${escapeHtml(detail.deadline)}` : 'No deadline set'}</p>
                    </div>
                    <div class="goals-status-line">
                        <span class="goals-status-item status-${escapeHtml(String(detail.status || 'active').toLowerCase())}">
                            <span class="goals-dot status-${escapeHtml(String(detail.status || 'active').toLowerCase())}"></span>${titleCase(detail.status || 'active')}
                        </span>
                    </div>
                </div>
                <div class="goals-detail-layout">
                    <div class="goals-narrative">
                        <div class="goals-narrative-block">
                            <h5>Financial Snapshot</h5>
                            <p>Target $${money(detail.target_amount)}. Saved $${money(detail.saved_amount)}. Remaining $${money(detail.remaining_amount)}.</p>
                        </div>
                        <div class="goals-narrative-block">
                            <h5>Feasibility</h5>
                            <p>${escapeHtml(analysis.insight || 'No recommendation yet')}</p>
                            <p>${escapeHtml(analysis.warning || analysis.tip || '')}</p>
                        </div>
                        <div class="goals-narrative-block">
                            <h5>Behavior Signal</h5>
                            <p>Top expense category impacting pace: ${escapeHtml(smart.top_category || 'n/a')}.</p>
                        </div>
                    </div>
                    <div class="goals-velocity">
                        <p class="goals-eyebrow">Savings Velocity</p>
                        <div class="goals-velocity-track"><div class="goals-velocity-fill" style="width:${velocity.toFixed(2)}%"></div></div>
                        <div class="goals-metric-list">
                            <div class="goals-metric-list-row"><span>Progress</span><strong>${velocity.toFixed(1)}%</strong></div>
                            <div class="goals-metric-list-row"><span>Allocated / month</span><strong>$${money(analysis.allocated_monthly)}</strong></div>
                            <div class="goals-metric-list-row"><span>Required / month</span><strong>$${money(analysis.required_monthly)}</strong></div>
                            <div class="goals-metric-list-row"><span>Projected completion</span><strong>${analysis.realistic_months == null ? 'n/a' : `${num(analysis.realistic_months).toFixed(1)} mo`}</strong></div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            card.innerHTML = `<div class="goals-empty-state">${escapeHtml(error.message || 'Unable to load goal detail.')}</div>`;
        }
    }

    async function refreshAll() {
        const portfolioBundle = await API.getGoalsPortfolioBundle();
        const goalsPayload = await API.getGoals();
        state.portfolio = (portfolioBundle && portfolioBundle.data) || {};
        state.allocation = (portfolioBundle && portfolioBundle.allocation) || {};
        state.decision = (portfolioBundle && portfolioBundle.decision) || {};
        state.goals = Array.isArray(goalsPayload) ? goalsPayload : [];

        if (state.detailGoalId && !state.goals.some((goal) => String(goal.id) === String(state.detailGoalId))) {
            state.detailGoalId = state.goals.length ? state.goals[0].id : null;
        }

        renderDashboard();
        renderPortfolio();
        renderDetailSelector();
        await renderDetailCard();
    }

    function openEditModal(goalId) {
        const goal = state.goals.find((item) => String(item.id) === String(goalId));
        if (!goal) return;
        $('#goalEditId').value = goal.id;
        $('#goalEditName').value = goal.goal_name || '';
        $('#goalEditTarget').value = num(goal.target_amount);
        $('#goalEditSaved').value = num(goal.saved_amount);
        $('#goalEditDeadline').value = goal.deadline || '';
        $('#goalEditPriority').value = String(goal.priority || 'medium').toLowerCase();
        $('#goalEditStatus').innerText = '';
        toggleModal('goalEditModal', true);
    }

    async function handleCreateGoal(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const statusNode = $('#goalStatusMsg');
        statusNode.innerText = 'Creating goal...';
        statusNode.classList.remove('is-success');
        try {
            await API.addGoal({
                name: form.name.value.trim(),
                target: num(form.target.value),
                saved: num(form.saved.value),
                deadline: form.deadline.value,
                priority: form.priority.value,
                status: 'active',
            });
            statusNode.innerText = 'Goal created successfully.';
            statusNode.classList.add('is-success');
            form.reset();
            form.priority.value = 'medium';
            await refreshAll();
            toggleModal('goalCreateModal', false);
        } catch (error) {
            statusNode.innerText = error.message || 'Unable to create goal.';
        }
    }

    async function handleEditGoal(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const statusNode = $('#goalEditStatus');
        statusNode.innerText = 'Saving changes...';
        statusNode.classList.remove('is-success');
        try {
            await API.request('/api/expense/goal/update', {
                method: 'POST',
                body: JSON.stringify({
                    goal_id: form.goal_id.value,
                    name: form.name.value.trim(),
                    target: num(form.target.value),
                    saved: num(form.saved.value),
                    deadline: form.deadline.value,
                    priority: form.priority.value,
                }),
            });
            statusNode.innerText = 'Goal updated.';
            statusNode.classList.add('is-success');
            toggleModal('goalEditModal', false);
            await refreshAll();
        } catch (error) {
            statusNode.innerText = error.message || 'Unable to update goal.';
        }
    }

    async function handleLifecycle(goalId, targetStatus) {
        await API.setGoalStatus({ goal_id: goalId, status: targetStatus });
        await refreshAll();
    }

    function bindEvents() {
        document.querySelectorAll('[data-view-btn]').forEach((button) => {
            button.addEventListener('click', () => setView(button.dataset.viewBtn));
        });

        $('[data-open-create-modal]')?.addEventListener('click', () => toggleModal('goalCreateModal', true));
        document.querySelectorAll('[data-close-create-modal]').forEach((button) => button.addEventListener('click', () => toggleModal('goalCreateModal', false)));
        document.querySelectorAll('[data-close-edit-modal]').forEach((button) => button.addEventListener('click', () => toggleModal('goalEditModal', false)));

        $('#goalCreateModal')?.addEventListener('click', (event) => {
            if (event.target.id === 'goalCreateModal') toggleModal('goalCreateModal', false);
        });
        $('#goalEditModal')?.addEventListener('click', (event) => {
            if (event.target.id === 'goalEditModal') toggleModal('goalEditModal', false);
        });

        $('#goalForm')?.addEventListener('submit', handleCreateGoal);
        $('#goalEditForm')?.addEventListener('submit', handleEditGoal);

        $('#goalsLifecycleTabs')?.addEventListener('click', (event) => {
            const tab = event.target.closest('[data-status-filter]');
            if (!tab) return;
            state.filterStatus = tab.dataset.statusFilter;
            document.querySelectorAll('[data-status-filter]').forEach((item) => item.classList.remove('is-active'));
            tab.classList.add('is-active');
            renderPortfolio();
        });

        $('#goalsSearchInput')?.addEventListener('input', (event) => {
            state.search = event.target.value || '';
            renderPortfolio();
        });

        $('#goalsSortSelect')?.addEventListener('change', (event) => {
            state.sortBy = event.target.value || 'priority';
            renderPortfolio();
        });

        $('#goalsCompactToggle')?.addEventListener('click', () => {
            state.compact = !state.compact;
            $('#goalsCompactToggle').innerText = state.compact ? 'Expanded Mode' : 'Compact Mode';
            renderPortfolio();
        });

        $('#goalsPortfolioGrid')?.addEventListener('click', async (event) => {
            const actionButton = event.target.closest('[data-action]');
            if (!actionButton) return;
            const goalId = actionButton.dataset.goalId;
            const action = actionButton.dataset.action;
            if (action === 'detail') {
                state.detailGoalId = goalId;
                setView('detail');
                renderDetailSelector();
                await renderDetailCard();
                return;
            }
            if (action === 'edit') {
                openEditModal(goalId);
                return;
            }
            if (action === 'status') {
                await handleLifecycle(goalId, actionButton.dataset.targetStatus);
            }
        });

        $('#goalDetailSelect')?.addEventListener('change', async (event) => {
            state.detailGoalId = event.target.value;
            await renderDetailCard();
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                toggleModal('goalCreateModal', false);
                toggleModal('goalEditModal', false);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', async () => {
        bindEvents();
        try {
            await refreshAll();
        } catch (error) {
            const fallback = $('#goalsDashboardView');
            if (fallback) fallback.innerHTML = `<div class="goals-empty-state">Unable to load goals data: ${escapeHtml(error.message || '')}</div>`;
        }
    });
})();
