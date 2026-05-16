/* global API */

(function () {
    const state = {
        expenses: [],
        income: 0,
        incomeEmpty: true,
        dashboardLoadSeq: 0,
        dashboardMutationSeq: 0,
        chartVersion: 0,
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
        }).format(safeNumber(value));
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.innerText = value;
        }
    }

    async function fetchJSON(url, options = {}) {
        return API.request(url, options);
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

    function getEl(id) {
        return document.getElementById(id);
    }

    function beginDashboardLoad() {
        state.dashboardLoadSeq += 1;
        return {
            loadSeq: state.dashboardLoadSeq,
            mutationSeq: state.dashboardMutationSeq,
        };
    }

    function invalidateDashboardMutations() {
        state.dashboardMutationSeq += 1;
        return state.dashboardMutationSeq;
    }

    function isLatestDashboardRequest(snapshot) {
        return snapshot
            && snapshot.loadSeq === state.dashboardLoadSeq
            && snapshot.mutationSeq === state.dashboardMutationSeq;
    }

    function ensureChartOverlay(frame) {
        if (!frame) {
            return null;
        }
        let overlay = frame.querySelector('.sv-chart-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'sv-chart-overlay';
            overlay.setAttribute('aria-hidden', 'true');
            frame.appendChild(overlay);
        }
        return overlay;
    }

    function setSurfaceLoading(elements, isLoading) {
        (elements || []).forEach((element) => {
            if (!element) return;
            element.classList.toggle('sv-loading-surface', !!isLoading);
            element.setAttribute('aria-busy', isLoading ? 'true' : 'false');
        });
    }

    function setDashboardLoadingState(isLoading) {
        setSurfaceLoading([
            getEl('dashboardIncomeCard'),
            ...document.querySelectorAll('.dashboard-kpi-card'),
            ...document.querySelectorAll('.dashboard-chart-panel'),
            ...document.querySelectorAll('.dashboard-side-card'),
            ...document.querySelectorAll('.dashboard-activity-panel'),
        ], isLoading);

        const chartFrame = getEl('dashboardChartFrame');
        if (chartFrame) {
            chartFrame.classList.toggle('sv-loading-surface', !!isLoading);
            chartFrame.setAttribute('aria-busy', isLoading ? 'true' : 'false');
            const overlay = ensureChartOverlay(chartFrame);
            if (overlay) {
                overlay.hidden = !isLoading;
            }
        }

        if (isLoading) {
            renderRecentActivitySkeleton();
        }
    }

    function pulseUpdatedIncomeCard() {
        const card = getEl('dashboardIncomeCard');
        if (!card) return;
        card.classList.add('sv-kpi-updated');
        window.setTimeout(() => card.classList.remove('sv-kpi-updated'), 260);
    }

    function preloadImage(src) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = () => resolve(src);
            image.onerror = reject;
            image.src = src;
        });
    }

    function renderRecentActivitySkeleton() {
        const tbody = getEl('recentActivity');
        if (!tbody) {
            return;
        }

        tbody.innerHTML = Array.from({ length: 4 }, () => `
            <tr class="sv-table-skeleton-row" aria-hidden="true">
                <td><span class="sv-skeleton sv-skeleton-line"></span></td>
                <td><span class="sv-skeleton sv-skeleton-line"></span></td>
                <td><span class="sv-skeleton sv-skeleton-line"></span></td>
                <td><span class="sv-skeleton sv-skeleton-line"></span></td>
            </tr>
        `).join('');
    }

    async function refreshChart(image, frame, src) {
        if (!image) {
            return;
        }

        const nextSrc = `${src || '/static/trend.png'}?v=${Date.now()}-${state.chartVersion}`;
        const overlay = ensureChartOverlay(frame);
        if (frame) {
            frame.classList.add('sv-loading-surface');
        }
        if (overlay) {
            overlay.hidden = false;
        }

        try {
            await preloadImage(nextSrc);
            image.style.opacity = '0.72';
            image.style.filter = 'blur(2px)';
            image.src = nextSrc;
            image.hidden = false;
            window.requestAnimationFrame(() => {
                image.style.opacity = '1';
                image.style.filter = 'none';
                if (frame) {
                    frame.classList.remove('sv-loading-surface');
                }
                if (overlay) {
                    overlay.hidden = true;
                }
            });
        } catch {
            image.hidden = false;
            image.style.opacity = '1';
            image.style.filter = 'none';
            if (frame) {
                frame.classList.remove('sv-loading-surface');
            }
            if (overlay) {
                overlay.hidden = true;
            }
            image.src = src || '/static/trend.png';
        }
    }

    function applyDashboardData(dashboardData = {}, expenses = null, options = {}) {
        const current = dashboardData.current || {};
        if (typeof current.income !== 'undefined') {
            state.income = safeNumber(current.income);
            state.incomeEmpty = state.income <= 0;
            renderIncomeKpi(state.incomeEmpty);
        }

        renderKPIs(dashboardData);
        renderInsight(dashboardData);
        renderChart(dashboardData);

        if (Array.isArray(expenses)) {
            state.expenses = expenses;
        }
        renderRecentActivity(state.expenses);

        if (options.pulseUpdatedIncome) {
            pulseUpdatedIncomeCard();
        }
    }

    async function loadIncome() {
        const data = await fetchJSON('/api/income/get');
        state.income = safeNumber(data?.income);
        state.incomeEmpty = !!data?.is_empty || state.income <= 0;
        renderIncomeKpi(state.incomeEmpty);
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

    async function renderChart(dashboardData = {}) {
        const image = getEl('dashboardTrendChart');
        const frame = getEl('dashboardChartFrame');
        if (!image) {
            return;
        }

        const chartPath = dashboardData.charts?.trend_chart || '/static/trend.png';
        state.chartVersion += 1;
        await refreshChart(image, frame, chartPath);
    }

    function renderRecentActivity(expenses) {
        const tbody = getEl('recentActivity');
        const count = getEl('dashboardActivityCount');
        const query = String(getEl('dashboardSearch')?.value || '').trim().toLowerCase();

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
        const input = getEl('incomeAmount');
        const error = getEl('incomeFormError');
        const submitBtn = getEl('saveIncomeBtn');
        const value = safeNumber(input?.value);

        if (!(value > 0)) {
            if (error) {
                error.innerText = 'Please enter a valid monthly income.';
                error.hidden = false;
            }
            return;
        }

        try {
            invalidateDashboardMutations();
            if (submitBtn) {
                submitBtn.disabled = true;
            }
            const result = await API.updateIncome({ income: value });
            closeIncomeModal();
            if (result?.analysis) {
                await renderChart(result.analysis);
                applyDashboardData(result.analysis, null, { pulseUpdatedIncome: true });
            } else {
                await loadDashboard();
            }
            setDashboardLoadingState(false);
            if (error) {
                error.hidden = true;
                error.innerText = '';
            }
        } catch (err) {
            if (error) {
                error.innerText = err.message || 'Unable to save income.';
                error.hidden = false;
            }
            setDashboardLoadingState(false);
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
            }
        }
    }

    async function loadDashboard() {
        const requestSnapshot = beginDashboardLoad();
        setDashboardLoadingState(true);
        try {
            const [dashboardResult, expensesResult] = await Promise.allSettled([
                API.getDashboard(),
                API.getRecentExpenses ? API.getRecentExpenses() : API.getExpenses(),
            ]);

            if (!isLatestDashboardRequest(requestSnapshot)) {
                return;
            }

            const data = dashboardResult.status === 'fulfilled' ? dashboardResult.value : {};
            const expenses = expensesResult.status === 'fulfilled' && Array.isArray(expensesResult.value)
                ? expensesResult.value
                : [];

            await renderChart(data);
            applyDashboardData(data, expenses);
        } catch (error) {
            if (!isLatestDashboardRequest(requestSnapshot)) {
                return;
            }
            state.expenses = [];
            state.income = 0;
            state.incomeEmpty = true;
            await renderChart({
                charts: { trend_chart: '/static/trend.png' },
            });
            applyDashboardData({
                current: {
                    expense: 0,
                    savings: 0,
                    savings_rate: 0,
                    alert: {},
                },
                charts: { trend_chart: '/static/trend.png' },
            }, []);
        } finally {
            if (isLatestDashboardRequest(requestSnapshot)) {
                setDashboardLoadingState(false);
            }
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
