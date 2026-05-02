/* global API */

(function () {
    const state = {
        data: null,
        mainTab: 'current',
        subTabs: {
            current: 'overview',
            yearly: 'overview',
        },
    };

    function safeNumber(value) {
        const num = Number(value);
        return Number.isFinite(num) ? num : 0;
    }

    function formatMoney(value) {
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(safeNumber(value));
    }

    function formatPercent(value) {
        return `${safeNumber(value).toFixed(1)}%`;
    }

    function formatMonthKey(key) {
        if (!key) {
            return '--';
        }

        const [year, month] = String(key).split('-').map(Number);
        if (!year || !month) {
            return String(key);
        }

        return new Date(year, month - 1, 1).toLocaleString('en-US', {
            month: 'short',
            year: 'numeric',
        });
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.innerText = value;
        }
    }

    function setHtml(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = value;
        }
    }

    function setBadge(id, text, tone) {
        const el = document.getElementById(id);
        if (!el) {
            return;
        }

        el.innerText = text;
        el.className = `analysis-badge analysis-badge--${tone || 'neutral'}`;
    }

    function renderChartImage(id, emptyId, src) {
        const image = document.getElementById(id);
        const empty = document.getElementById(emptyId);
        if (!image) {
            return;
        }

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
        image.src = `${src || ''}?v=${Date.now()}`;
    }

    function renderTopCategories(id, items) {
        const el = document.getElementById(id);
        if (!el) {
            return;
        }

        const topItems = (Array.isArray(items) ? items : [])
            .map((item) => ({
                category: item?.category || 'Other',
                amount: safeNumber(item?.amount),
                percent: safeNumber(item?.percent),
            }))
            .sort((left, right) => right.amount - left.amount)
            .slice(0, 3);

        if (!topItems.length) {
            el.innerHTML = '<div class="analysis-item"><p class="analysis-item-text">No category data yet.</p></div>';
            return;
        }

        el.innerHTML = topItems.map((item, index) => `
            <div class="analysis-item ${index === 0 ? 'analysis-item--highlight' : ''}">
                <p class="analysis-item-title">${index + 1}. ${escapeHtml(item.category)}</p>
                <p class="analysis-item-text">${formatMoney(item.amount)} | ${formatPercent(item.percent)} of total spend</p>
            </div>
        `).join('');
    }

    function renderList(id, items, renderer, emptyText) {
        const el = document.getElementById(id);
        if (!el) {
            return;
        }

        if (!Array.isArray(items) || items.length === 0) {
            el.innerHTML = `<div class="analysis-item"><p class="analysis-item-text">${escapeHtml(emptyText || 'No data available yet.')}</p></div>`;
            return;
        }

        el.innerHTML = items.map(renderer).join('');
    }

    function renderCurrentOverview(current) {
        const breakdown = current.detailed?.category_breakdown || current.category_breakdown || [];
        setText('currentMonthLabel', new Date().toLocaleString('en-US', { month: 'long', year: 'numeric' }));
        setText('currentIncome', formatMoney(current.income));
        setText('currentExpense', formatMoney(current.expense));
        setText('currentSavings', formatMoney(current.savings));
        setText('currentSavingsRate', formatPercent(current.savings_rate));
        setText('currentOverviewInsight', current.insight || 'No insight available yet.');
        setText('currentOverviewTip', current.tip || 'No tip available yet.');

        renderChartImage('currentOverviewChart', 'currentOverviewEmpty', state.data?.charts?.current_pie || state.data?.charts?.category_chart || '/static/current_pie.png');
        renderChartImage('currentOverviewBarChart', 'currentOverviewBarEmpty', state.data?.charts?.current_category_bar || state.data?.charts?.category_bar_chart || '/static/current_category_bar.png');
        renderChartImage('currentOverviewTrendChart', 'currentOverviewTrendEmpty', state.data?.charts?.current_trend || state.data?.charts?.trend_chart || '/static/current_trend.png');
        renderTopCategories('currentTopCategories', breakdown);
    }

    function renderCurrentDetailed(current) {
        const detailed = current.detailed || {};

        renderList(
            'currentCategoryBreakdown',
            detailed.category_breakdown,
            (item, index) => `
                <div class="analysis-item ${index < 3 ? 'analysis-item--highlight' : ''}">
                    <p class="analysis-item-title">${index + 1}. ${escapeHtml(item.category || 'Other')}</p>
                    <p class="analysis-item-text">${formatMoney(item.amount)} • ${formatPercent(item.percent)} of current spend</p>
                </div>
            `,
            'No category breakdown yet.'
        );

        renderChartImage('currentDetailedPieChart', 'currentDetailedPieEmpty', state.data?.charts?.current_pie || state.data?.charts?.category_chart || '/static/current_pie.png');
        renderChartImage('currentDetailedTrendChart', 'currentDetailedTrendEmpty', state.data?.charts?.current_trend || state.data?.charts?.trend_chart || '/static/current_trend.png');

        renderList(
            'currentCategoryChange',
            detailed.category_change,
            (item) => {
                const direction = item.direction === 'up' ? '↑' : item.direction === 'down' ? '↓' : '•';
                return `
                    <div class="analysis-item">
                        <p class="analysis-item-title">${direction} ${escapeHtml(item.category || 'Other')}</p>
                        <p class="analysis-item-text">Current: ${formatMoney(item.current_amount)} | Previous: ${formatMoney(item.previous_amount)} | Change: ${formatMoney(item.change_amount)} (${formatPercent(item.change_percent)})</p>
                    </div>
                `;
            },
            'No category change data yet.'
        );

        renderList(
            'currentPatternAnalysis',
            detailed.pattern_analysis ? [detailed.pattern_analysis] : [],
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">Trend direction: ${escapeHtml(item.direction || 'stable')}</p>
                    <p class="analysis-item-text">${escapeHtml(item.observation || '')}\nVolatility: ${formatPercent(item.volatility)} | Fixed-like spend: ${formatPercent(item.fixed_ratio)} | Variable spend: ${formatPercent(item.variable_ratio)}</p>
                </div>
            `,
            'No pattern analysis available yet.'
        );

        renderList(
            'currentCostCutting',
            detailed.cost_cutting,
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">${escapeHtml(item.category || 'Other')}</p>
                    <p class="analysis-item-text">Potential savings: ${formatMoney(item.potential_savings)}\n${escapeHtml(item.note || '')}</p>
                </div>
            `,
            'No cost cutting opportunities identified yet.'
        );

        renderList(
            'currentEfficiency',
            detailed.savings_efficiency ? [detailed.savings_efficiency] : [],
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">${escapeHtml(item.label || 'Neutral')} zone</p>
                    <p class="analysis-item-text">Current rate: ${formatPercent(item.current_rate)} | Ideal range: ${formatPercent(item.ideal_min)} - ${formatPercent(item.ideal_max)}\n${escapeHtml(item.text || '')}</p>
                </div>
            `,
            'No savings efficiency data available yet.'
        );

        if (detailed.savings_efficiency) {
            setBadge('currentEfficiencyBadge', detailed.savings_efficiency.label || 'Neutral', detailed.savings_efficiency.tone || 'neutral');
        }

        renderList(
            'currentRisk',
            detailed.risk ? [detailed.risk] : [],
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">Risk check</p>
                    <p class="analysis-item-text">${escapeHtml(item.overspending_warning || 'No overspending warning.')}\n${escapeHtml(item.low_savings_alert || 'No low-savings alert.')}\n${escapeHtml(item.volatility_warning || 'No volatility warning.')}</p>
                </div>
            `,
            'No risk data available yet.'
        );

        setText('currentVerdict', detailed.verdict || 'No verdict available yet.');
    }

    function renderYearlyOverview(yearly) {
        setText('yearlyMonthsLabel', `${safeNumber(yearly.months_count).toFixed(0)} months`);
        setText('yearlyIncome', formatMoney(yearly.total_income));
        setText('yearlyExpense', formatMoney(yearly.total_expense));
        setText('yearlySavings', formatMoney(yearly.total_savings));
        setText('yearlyScore', `${safeNumber(yearly.detailed?.score).toFixed(0)}`);
        setText('yearlyOverviewInsight', yearly.insight || 'No yearly insight available yet.');

        renderChartImage('yearlyOverviewChart', 'yearlyOverviewEmpty', state.data?.charts?.yearly_trend_chart || '/static/yearly_trend.png');
    }

    function renderYearlyDetailed(yearly) {
        const detailed = yearly.detailed || {};

        renderList(
            'yearlyMonthlyBreakdown',
            detailed.monthly_breakdown,
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">${escapeHtml(item.label || item.month || '--')}</p>
                    <p class="analysis-item-text">Expense: ${formatMoney(item.expense)} | Savings: ${formatMoney(item.savings)}</p>
                </div>
            `,
            'No monthly breakdown yet.'
        );

        renderList(
            'yearlyTrendAnalysis',
            detailed.trend_analysis ? [detailed.trend_analysis] : [],
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">Trend direction: ${escapeHtml(item.direction || 'stable')}</p>
                    <p class="analysis-item-text">Spike month: ${escapeHtml(item.spike_month?.label || '--')} | Volatility: ${formatPercent(item.volatility)}</p>
                </div>
            `,
            'No trend analysis available yet.'
        );

        const bestWorst = [];
        if (detailed.best_month) {
            bestWorst.push({ type: 'Best month', ...detailed.best_month });
        }
        if (detailed.worst_month) {
            bestWorst.push({ type: 'Worst month', ...detailed.worst_month });
        }

        renderList(
            'yearlyBestWorst',
            bestWorst,
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">${escapeHtml(item.type || 'Month')}: ${escapeHtml(item.label || item.month || '--')}</p>
                    <p class="analysis-item-text">Expense: ${formatMoney(item.expense)} | Savings: ${formatMoney(item.savings)}</p>
                </div>
            `,
            'No best/worst month data yet.'
        );

        renderList(
            'yearlyCategoryDominance',
            detailed.category_dominance ? [detailed.category_dominance] : [],
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">${escapeHtml(item.category || 'Other')}</p>
                    <p class="analysis-item-text">Amount: ${formatMoney(item.amount)} | Share: ${formatPercent(item.share)}</p>
                </div>
            `,
            'No category dominance data yet.'
        );

        renderList(
            'yearlyConsistency',
            detailed.consistency ? [detailed.consistency] : [],
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">${escapeHtml(item.label || 'neutral')}</p>
                    <p class="analysis-item-text">Variance: ${formatPercent(item.variance)}\n${escapeHtml(item.text || '')}</p>
                </div>
            `,
            'No consistency data yet.'
        );

        renderList(
            'yearlyOptimization',
            detailed.optimization,
            (item) => `
                <div class="analysis-item">
                    <p class="analysis-item-title">${escapeHtml(item.category || 'Other')}</p>
                    <p class="analysis-item-text">Potential savings: ${formatMoney(item.potential_savings)}\n${escapeHtml(item.note || '')}</p>
                </div>
            `,
            'No optimization opportunities identified yet.'
        );

        setText('yearlyScoreBig', `${safeNumber(detailed.score).toFixed(0)}`);
        setText('yearlyVerdict', detailed.verdict || 'No yearly verdict available yet.');

        const score = safeNumber(detailed.score);
        const tone = score >= 80 ? 'green' : score >= 60 ? 'yellow' : 'red';
        setBadge('yearlyScoreBadge', `${score.toFixed(0)} / 100`, tone);
    }

    function activateMainTab(tabName) {
        state.mainTab = tabName;

        document.querySelectorAll('[data-main-tab]').forEach((button) => {
            const active = button.dataset.mainTab === tabName;
            button.classList.toggle('active', active);
            button.setAttribute('aria-selected', active ? 'true' : 'false');
        });

        document.querySelectorAll('[data-main-panel]').forEach((panel) => {
            panel.classList.toggle('active', panel.dataset.mainPanel === tabName);
        });

        activateSubTab(tabName, state.subTabs[tabName] || 'overview');
    }

    function activateSubTab(scope, tabName) {
        state.subTabs[scope] = tabName;

        document.querySelectorAll(`[data-scope="${scope}"][data-sub-tab]`).forEach((button) => {
            const active = button.dataset.subTab === tabName;
            button.classList.toggle('active', active);
            button.setAttribute('aria-selected', active ? 'true' : 'false');
        });

        document.querySelectorAll(`[data-scope="${scope}"][data-sub-panel]`).forEach((panel) => {
            panel.classList.toggle('active', panel.dataset.subPanel === tabName);
        });
    }

    function bindEvents() {
        document.querySelectorAll('[data-main-tab]').forEach((button) => {
            button.addEventListener('click', () => activateMainTab(button.dataset.mainTab || 'current'));
        });

        document.querySelectorAll('[data-sub-tab]').forEach((button) => {
            button.addEventListener('click', () => activateSubTab(button.dataset.scope || 'current', button.dataset.subTab || 'overview'));
        });
    }

    async function loadAnalysis() {
        try {
            const data = await API.request('/api/analysis/data');
            state.data = data || { current: {}, yearly: {}, charts: {} };

            renderCurrentOverview(state.data.current || {});
            renderCurrentDetailed(state.data.current || {});
            renderYearlyOverview(state.data.yearly || {});
            renderYearlyDetailed(state.data.yearly || {});
            activateMainTab('current');
        } catch (error) {
            state.data = {
                current: {
                    income: 0,
                    expense: 0,
                    savings: 0,
                    savings_rate: 0,
                    prev_expense: 0,
                    change_percent: 0,
                    top_category: null,
                    category_breakdown: [],
                    trend_data: [],
                    insight: 'Unable to load analysis data right now.',
                    tip: 'Try again after refreshing the page.',
                    alert: {},
                    detailed: {},
                    charts: {},
                },
                yearly: {
                    months_count: 0,
                    total_income: 0,
                    total_expense: 0,
                    total_savings: 0,
                    best_month: null,
                    worst_month: null,
                    trend_data: [],
                    insight: 'Unable to load analysis data right now.',
                    detailed: {},
                    charts: {},
                },
                charts: {},
            };

            renderCurrentOverview(state.data.current);
            renderCurrentDetailed(state.data.current);
            renderYearlyOverview(state.data.yearly);
            renderYearlyDetailed(state.data.yearly);
            activateMainTab('current');
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        loadAnalysis();
    });
})();
