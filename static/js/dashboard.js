/* global API */

(function () {
    const state = {
        expenses: [],
        income: 0,
        incomeEmpty: true,
    };

    function safeNumber(value) {
        const num = Number(value);
        return Number.isFinite(num) ? num : 0;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function currency(value) {
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value);
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.innerText = value;
        }
    }

    async function fetchJSON(url, options = {}) {
        const response = await fetch(url, {
            credentials: 'same-origin',
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {}),
            },
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.status === 'error') {
            throw new Error(payload.message || `Request failed (${response.status})`);
        }
        return payload.data ?? payload;
    }

    function renderIncomeKpi(incomeEmpty) {
        const value = document.getElementById('currentIncome');
        const actionBtn = document.getElementById('incomeActionBtn');
        const note = document.getElementById('incomeNote');
        const warning = document.getElementById('incomeWarning');
        const income = safeNumber(state.income);

        if (value) {
            value.innerText = currency(income);
        }

        if (actionBtn) {
            actionBtn.innerText = incomeEmpty ? 'Set Income' : 'Edit Income';
        }

        if (note) {
            note.innerText = incomeEmpty
                ? 'Monthly income is not set yet.'
                : 'Single monthly income used for savings calculations.';
        }

        if (warning) {
            warning.hidden = !incomeEmpty;
        }
    }

    async function loadIncome() {
        const data = await fetchJSON('/api/income/get');
        state.income = safeNumber(data?.income);
        state.incomeEmpty = !!data?.is_empty || state.income <= 0;
        renderIncomeKpi();
    }

    function renderKPIs(dashboardData = {}) {
        const current = dashboardData.current || {};
        const currentExpense = safeNumber(current.expense);
        const savings = safeNumber(current.savings);
        const rate = safeNumber(current.savings_rate);

        setText('totalExpenses', currency(currentExpense));
        setText('totalSavings', currency(savings));
        setText('savingsRate', `${rate.toFixed(1)}%`);
    }

    function renderInsight(dashboardData = {}) {
        const current = dashboardData.current || {};
        const alert = current.alert || {};

        setText('dashboardSummary', current.insight || 'No data yet.');
        setText('dashboardTopCategory', current.top_category || 'No data yet');
        setText('dashboardAlertBadge', alert.label || 'Neutral');
        setText('dashboardAlertText', alert.text || 'No alert yet.');

        const badge = document.getElementById('dashboardAlertBadge');
        if (badge) {
            badge.className = `dashboard-alert-badge dashboard-alert-badge--${alert.tone || 'neutral'}`;
        }
    }

    function renderChart(dashboardData = {}) {
        const image = document.getElementById('dashboardTrendChart');
        const empty = document.getElementById('dashboardChartEmpty');
        if (!image) {
            return;
        }

        const chartPath = dashboardData.charts?.trend_chart || '/static/trend.png';
        if (empty) {
            empty.hidden = false;
        }
        image.onload = () => {
            if (empty) {
                empty.hidden = true;
            }
            image.hidden = false;
        };
        image.onerror = () => {
            image.hidden = true;
            if (empty) {
                empty.hidden = false;
            }
        };
        image.src = `${chartPath}?v=${Date.now()}`;
    }

    function renderRecentActivity(expenses) {
        const tbody = document.getElementById('recentActivity');
        const count = document.getElementById('dashboardActivityCount');
        const query = String(document.getElementById('dashboardSearch')?.value || '').trim().toLowerCase();

        if (!tbody) {
            return;
        }

        const rows = (expenses || []).filter((expense) => {
            if (!query) {
                return true;
            }

            const note = String(expense.note ?? expense.description ?? '').toLowerCase();
            const category = String(expense.category ?? '').toLowerCase();
            return note.includes(query) || category.includes(query);
        });

        if (count) {
            count.innerText = `${rows.length} item${rows.length === 1 ? '' : 's'}`;
        }

        if (!rows.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="empty-state">No results</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = rows.map((expense) => `
            <tr>
                <td>${escapeHtml(expense.note || expense.description || 'Expense')}</td>
                <td><span class="dashboard-chip">${escapeHtml(expense.category || 'Other')}</span></td>
                <td class="dashboard-muted">${escapeHtml(expense.date || '')}</td>
                <td class="dashboard-table-amount">${currency(-safeNumber(expense.amount))}</td>
            </tr>
        `).join('');
    }

    function openIncomeModal() {
        const modal = document.getElementById('incomeModal');
        const title = document.getElementById('incomeModalTitle');
        const input = document.getElementById('incomeAmount');
        const error = document.getElementById('incomeFormError');

        if (modal) {
            modal.classList.add('is-open');
            modal.setAttribute('aria-hidden', 'false');
        }

        if (title) {
            title.innerText = state.incomeEmpty ? 'Set Income' : 'Edit Income';
        }

        if (input) {
            input.value = state.income > 0 ? state.income : '';
            input.focus();
        }

        if (error) {
            error.hidden = true;
            error.innerText = '';
        }
    }

    function closeIncomeModal() {
        const modal = document.getElementById('incomeModal');
        if (modal) {
            modal.classList.remove('is-open');
            modal.setAttribute('aria-hidden', 'true');
        }
    }

    async function saveIncome(event) {
        event.preventDefault();
        const input = document.getElementById('incomeAmount');
        const error = document.getElementById('incomeFormError');
        const value = safeNumber(input?.value);

        if (!(value > 0)) {
            if (error) {
                error.innerText = 'Please enter a valid monthly income.';
                error.hidden = false;
            }
            return;
        }

        try {
            await fetchJSON('/api/income/set', {
                method: 'POST',
                body: JSON.stringify({ amount: value }),
            });
            closeIncomeModal();
            await loadDashboard();
        } catch (err) {
            if (error) {
                error.innerText = err.message || 'Unable to save income.';
                error.hidden = false;
            }
        }
    }

    async function loadDashboard() {
        try {
            const [dashboardResult, expensesResult] = await Promise.allSettled([
                API.getDashboard(),
                API.getExpenses(),
            ]);

            const data = dashboardResult.status === 'fulfilled' ? dashboardResult.value : {};
            const expenses = expensesResult.status === 'fulfilled' && Array.isArray(expensesResult.value)
                ? expensesResult.value
                : [];

            state.expenses = expenses;
            state.income = safeNumber(data?.current?.income ?? 0);
            state.incomeEmpty = state.income <= 0;
            renderIncomeKpi(state.incomeEmpty);

            renderKPIs(data);
            renderInsight(data);
            renderChart(data);
            renderRecentActivity(state.expenses);
        } catch (error) {
            state.expenses = [];
            state.income = 0;
            state.incomeEmpty = true;
            renderIncomeKpi(true);
            renderKPIs({
                current: {
                    expense: 0,
                    savings: 0,
                    savings_rate: 0,
                },
            });
            renderInsight({ current: { alert: {} } });
            renderChart({ charts: { trend_chart: '/static/trend.png' } });
            renderRecentActivity([]);
        }
    }

    function bindEvents() {
        const searchInput = document.getElementById('dashboardSearch');
        const filterActivity = () => renderRecentActivity(state.expenses);

        searchInput?.addEventListener('input', filterActivity);
        searchInput?.addEventListener('change', filterActivity);

        document.getElementById('incomeActionBtn')?.addEventListener('click', openIncomeModal);
        document.getElementById('closeIncomeModal')?.addEventListener('click', closeIncomeModal);
        document.getElementById('cancelIncomeBtn')?.addEventListener('click', closeIncomeModal);
        document.getElementById('incomeForm')?.addEventListener('submit', saveIncome);

        document.getElementById('incomeModal')?.addEventListener('click', (event) => {
            if (event.target.id === 'incomeModal') {
                closeIncomeModal();
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeIncomeModal();
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        loadDashboard();
    });
})();
