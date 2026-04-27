/* global API, Chart, formatCurrency */

(function () {
    const state = {
        chart: null,
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

    function monthKey(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return null;
        }
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    }

    function monthLabel(key) {
        const [year, month] = key.split('-').map(Number);
        return new Date(year, month - 1, 1).toLocaleString('en-US', { month: 'short', year: 'numeric' });
    }

    function buildTrendData(expenses) {
        const months = [];
        const now = new Date();
        for (let offset = 5; offset >= 0; offset -= 1) {
            const d = new Date(now.getFullYear(), now.getMonth() - offset, 1);
            months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
        }

        const totals = new Map(months.map((key) => [key, 0]));
        (expenses || []).forEach((expense) => {
            const key = monthKey(expense.date);
            if (!key || !totals.has(key)) {
                return;
            }
            totals.set(key, totals.get(key) + safeNumber(expense.amount));
        });

        return {
            labels: months.map(monthLabel),
            values: months.map((key) => totals.get(key) || 0),
        };
    }

    function getCurrentMonthExpense(expenses) {
        const now = new Date();
        const currentMonth = now.getMonth();
        const currentYear = now.getFullYear();

        return (expenses || []).reduce((sum, expense) => {
            const date = new Date(expense.date);
            if (Number.isNaN(date.getTime())) {
                return sum;
            }

            if (date.getMonth() === currentMonth && date.getFullYear() === currentYear) {
                return sum + safeNumber(expense.amount);
            }

            return sum;
        }, 0);
    }

    function computeTopCategory(expenses) {
        const totals = new Map();
        (expenses || []).forEach((expense) => {
            const category = String(expense.category || 'Other').trim() || 'Other';
            totals.set(category, (totals.get(category) || 0) + safeNumber(expense.amount));
        });

        if (!totals.size) {
            return null;
        }

        return [...totals.entries()].sort((a, b) => b[1] - a[1])[0][0];
    }

    function computeAlert(income, savings) {
        if (income <= 0) {
            return {
                label: 'Set Income',
                tone: 'yellow',
                text: 'Set your monthly income to unlock savings analysis.',
            };
        }

        const rate = income > 0 ? (savings / income) * 100 : 0;

        if (rate < 0) {
            return {
                label: 'Alert',
                tone: 'red',
                text: 'You are overspending this month.',
            };
        }

        if (rate < 20) {
            return {
                label: 'Watch',
                tone: 'yellow',
                text: 'Your savings are low.',
            };
        }

        return {
            label: 'On Track',
            tone: 'green',
            text: 'You are saving well.',
        };
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

    function renderIncomeKpi() {
        const value = document.getElementById('currentIncome');
        const actionBtn = document.getElementById('incomeActionBtn');
        const note = document.getElementById('incomeNote');
        const warning = document.getElementById('incomeWarning');

        if (value) {
            value.innerText = currency(state.income);
        }

        if (actionBtn) {
            actionBtn.innerText = state.incomeEmpty ? 'Set Income' : 'Edit Income';
        }

        if (note) {
            note.innerText = state.incomeEmpty
                ? 'Monthly income is not set yet.'
                : 'Single monthly income used for savings calculations.';
        }

        if (warning) {
            warning.hidden = !state.incomeEmpty;
        }
    }

    async function loadIncome() {
        const data = await fetchJSON('/api/income/get');
        state.income = safeNumber(data?.income);
        state.incomeEmpty = !!data?.is_empty || state.income <= 0;
        renderIncomeKpi();
    }

    function renderKPIs(expenses, dashboardData = {}) {
        const currentExpense = safeNumber(
            dashboardData.current_expense ?? getCurrentMonthExpense(expenses)
        );
        const savings = safeNumber(
            dashboardData.current_savings ?? (state.income - currentExpense)
        );
        const rate = state.income > 0 ? (savings / state.income) * 100 : 0;

        setText('totalExpenses', currency(currentExpense));
        setText('totalSavings', currency(savings));
        setText('savingsRate', `${rate.toFixed(1)}%`);

        return { currentExpense, savings, rate };
    }

    function renderInsight(report, expenses, totals) {
        const topCategory = computeTopCategory(expenses);
        const alert = computeAlert(state.income, totals.savings);

        setText('dashboardSummary', report?.summary || 'No data yet.');
        setText('dashboardTopCategory', topCategory || 'No data yet');
        setText('dashboardAlertBadge', alert.label);
        setText('dashboardAlertText', alert.text);

        const badge = document.getElementById('dashboardAlertBadge');
        if (badge) {
            badge.className = `dashboard-alert-badge dashboard-alert-badge--${alert.tone}`;
        }
    }

    function renderChart(expenses) {
        const canvas = document.getElementById('dashboardTrendChart');
        const empty = document.getElementById('dashboardChartEmpty');
        if (!canvas) {
            return;
        }

        const data = buildTrendData(expenses);
        const hasData = data.values.some((value) => value > 0);

        if (state.chart) {
            state.chart.destroy();
            state.chart = null;
        }

        if (!hasData) {
            canvas.style.display = 'none';
            if (empty) empty.hidden = false;
            return;
        }

        if (empty) empty.hidden = true;
        canvas.style.display = 'block';

        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 320);
        gradient.addColorStop(0, 'rgba(56, 189, 248, 0.35)');
        gradient.addColorStop(1, 'rgba(56, 189, 248, 0.02)');

        state.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Spending',
                    data: data.values,
                    borderColor: '#38bdf8',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.42,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: '#ffffff',
                    pointBorderColor: '#38bdf8',
                    pointBorderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#0f172a',
                        borderColor: 'rgba(148, 163, 184, 0.18)',
                        borderWidth: 1,
                        titleColor: '#f8fafc',
                        bodyColor: '#cbd5e1',
                        displayColors: false,
                    },
                },
                scales: {
                    x: {
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148, 163, 184, 0.08)' },
                    },
                    y: {
                        ticks: {
                            color: '#94a3b8',
                            callback: (value) => currency(value),
                        },
                        grid: { color: 'rgba(148, 163, 184, 0.08)' },
                    },
                },
            },
        });
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
            const [dashboardResult, reportResult, expensesResult, incomeResult] = await Promise.allSettled([
                API.getDashboard(),
                API.getExpenseAnalysis(),
                API.getExpenses(),
                fetchJSON('/api/income/get'),
            ]);

            const data = dashboardResult.status === 'fulfilled' ? dashboardResult.value : {};
            console.log(data);
            const report = reportResult.status === 'fulfilled' ? reportResult.value : {};
            const expenses = expensesResult.status === 'fulfilled' && Array.isArray(expensesResult.value)
                ? expensesResult.value
                : [];
            const incomeData = incomeResult.status === 'fulfilled' ? incomeResult.value : { income: 0, is_empty: true };

            state.expenses = expenses;
            state.income = safeNumber(incomeData?.income ?? data?.monthly_income);
            state.incomeEmpty = !!incomeData?.is_empty || state.income <= 0;
            renderIncomeKpi();

            const totals = renderKPIs(state.expenses, data);
            renderInsight(report, state.expenses, totals);
            renderChart(state.expenses);
            renderRecentActivity(state.expenses);
        } catch (error) {
            state.expenses = [];
            state.income = 0;
            state.incomeEmpty = true;
            renderIncomeKpi();
            renderKPIs([]);
            renderInsight({}, [], { savings: 0 });
            renderChart([]);
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
