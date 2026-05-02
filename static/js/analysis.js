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

    function svgPointString(values, width, height, padding) {
        const cleanValues = values.map((value) => safeNumber(value));
        const maxValue = Math.max(...cleanValues, 1);
        const innerWidth = width - padding * 2;
        const innerHeight = height - padding * 2;

        return cleanValues.map((value, index) => {
            const x = padding + (index * innerWidth) / Math.max(cleanValues.length - 1, 1);
            const y = padding + innerHeight - ((value / maxValue) * innerHeight);
            return `${x},${y}`;
        }).join(' ');
    }

    function renderSparkline(values) {
        const width = 280;
        const height = 92;
        const padding = 12;
        const cleanValues = values.length ? values : [0];
        const points = svgPointString(cleanValues, width, height, padding);

        return `
            <svg class="analysis-pattern-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
                <defs>
                    <linearGradient id="patternSparklineFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="rgba(20, 184, 166, 0.35)"></stop>
                        <stop offset="100%" stop-color="rgba(20, 184, 166, 0.02)"></stop>
                    </linearGradient>
                </defs>
                <polyline fill="none" stroke="#14b8a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${points}"></polyline>
                <polyline fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="1" points="${points}"></polyline>
            </svg>
        `;
    }

    function renderBarMiniChart(items) {
        const cleanItems = (Array.isArray(items) ? items : [])
            .map((item) => ({
                label: item?.label || item?.category || 'Other',
                amount: safeNumber(item?.amount),
            }))
            .slice(0, 5);

        if (!cleanItems.length) {
            return '<p class="analysis-pattern-note">No category split available yet.</p>';
        }

        const maxValue = Math.max(...cleanItems.map((item) => item.amount), 1);
        return cleanItems.map((item) => `
            <div class="analysis-pattern-bar">
                <div class="analysis-pattern-bar-head">
                    <span>${escapeHtml(item.label)}</span>
                    <span>${formatMoney(item.amount)}</span>
                </div>
                <div class="analysis-pattern-bar-track">
                    <div class="analysis-pattern-bar-fill" style="width: ${(item.amount / maxValue) * 100}%"></div>
                </div>
            </div>
        `).join('');
    }

    function renderPatternInsights(current) {
        const detailed = current.detailed || {};
        const pattern = detailed.pattern_analysis || {};
        const breakdown = detailed.category_breakdown || current.category_breakdown || [];
        const trendData = current.trend_data || [];

        const changePercent = safeNumber(current.change_percent);
        const changeLabel = changePercent > 0 ? 'Increase' : changePercent < 0 ? 'Decrease' : 'Flat';

        const topCategory = breakdown[0] || {};
        const volatileCategory = (detailed.category_change || [])
            .slice()
            .sort((left, right) => Math.abs(safeNumber(right.change_percent)) - Math.abs(safeNumber(left.change_percent)))[0] || {};

        const monthlyValues = trendData.map((item) => safeNumber(item.expense));
        const avgMonthlySpend = monthlyValues.length
            ? monthlyValues.reduce((sum, value) => sum + value, 0) / monthlyValues.length
            : safeNumber(current.expense);

        const peakMonth = trendData.reduce((best, item) => (safeNumber(item.expense) > safeNumber(best.expense) ? item : best), trendData[0] || {});
        const lowMonth = trendData.reduce((best, item) => (safeNumber(item.expense) < safeNumber(best.expense) ? item : best), trendData[0] || {});

        const volatility = safeNumber(pattern.volatility);
        const fixedRatio = safeNumber(pattern.fixed_ratio);
        const variableRatio = safeNumber(pattern.variable_ratio);
        const direction = pattern.direction || 'stable';
        const observation = pattern.observation || 'No spending data yet. Add a few expenses to reveal a trend.';

        const leftColumn = `
            <div class="analysis-pattern-column">
                <div class="analysis-pattern-metrics">
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Trend Direction</span>
                        <span class="analysis-pattern-value">${escapeHtml(direction)}</span>
                        <span class="analysis-pattern-subvalue">${escapeHtml(observation)}</span>
                    </div>
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Monthly Change</span>
                        <span class="analysis-pattern-value">${changeLabel} ${formatPercent(Math.abs(changePercent))}</span>
                        <span class="analysis-pattern-subvalue">vs previous month</span>
                    </div>
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Avg Monthly Spend</span>
                        <span class="analysis-pattern-value">${formatMoney(avgMonthlySpend)}</span>
                        <span class="analysis-pattern-subvalue">Average of recent monthly values</span>
                    </div>
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Volatility</span>
                        <span class="analysis-pattern-value">${formatPercent(volatility)}</span>
                        <span class="analysis-pattern-subvalue">Variation in monthly spend</span>
                    </div>
                </div>

                <div class="analysis-pattern-metrics">
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Highest Category</span>
                        <span class="analysis-pattern-value">${escapeHtml(topCategory.category || current.top_category || 'No data')}</span>
                        <span class="analysis-pattern-subvalue">${formatMoney(topCategory.amount || 0)}</span>
                    </div>
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Most Volatile Category</span>
                        <span class="analysis-pattern-value">${escapeHtml(volatileCategory.category || 'No data')}</span>
                        <span class="analysis-pattern-subvalue">${formatPercent(Math.abs(safeNumber(volatileCategory.change_percent)))}</span>
                    </div>
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Peak Month</span>
                        <span class="analysis-pattern-value">${escapeHtml(peakMonth.label || peakMonth.month || '--')}</span>
                        <span class="analysis-pattern-subvalue">${formatMoney(peakMonth.expense || 0)}</span>
                    </div>
                    <div class="analysis-pattern-metric">
                        <span class="analysis-pattern-label">Lowest Month</span>
                        <span class="analysis-pattern-value">${escapeHtml(lowMonth.label || lowMonth.month || '--')}</span>
                        <span class="analysis-pattern-subvalue">${formatMoney(lowMonth.expense || 0)}</span>
                    </div>
                </div>

                <div class="analysis-pattern-bars">
                    <div class="analysis-pattern-bar">
                        <div class="analysis-pattern-bar-head">
                            <span>Fixed Spend</span>
                            <span>${formatPercent(fixedRatio)}</span>
                        </div>
                        <div class="analysis-pattern-bar-track">
                            <div class="analysis-pattern-bar-fill" style="width: ${Math.max(0, Math.min(100, fixedRatio))}%"></div>
                        </div>
                    </div>
                    <div class="analysis-pattern-bar">
                        <div class="analysis-pattern-bar-head">
                            <span>Variable Spend</span>
                            <span>${formatPercent(variableRatio)}</span>
                        </div>
                        <div class="analysis-pattern-bar-track">
                            <div class="analysis-pattern-bar-fill" style="width: ${Math.max(0, Math.min(100, variableRatio))}%; background: linear-gradient(90deg, rgba(96, 165, 250, 0.95), rgba(148, 163, 184, 0.85));"></div>
                        </div>
                    </div>
                    <p class="analysis-pattern-note">Fixed spend represents recurring categories. Variable spend is the remaining share of current spend.</p>
                </div>
            </div>
        `;

        const rightColumn = `
            <div class="analysis-pattern-column analysis-pattern-visuals">
                <div class="analysis-pattern-visual-card">
                    <h4>Category Split</h4>
                    <div>${renderBarMiniChart(breakdown)}</div>
                </div>
                <div class="analysis-pattern-visual-card">
                    <h4>Spending Sparkline</h4>
                    <div>${renderSparkline(monthlyValues)}</div>
                </div>
            </div>
        `;

        setHtml('currentPatternAnalysis', `
            <div class="analysis-pattern-board">
                ${leftColumn}
                ${rightColumn}
            </div>
        `);
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
        const pattern = detailed.pattern_analysis || {};
        console.log('Spending Pattern:', detailed.pattern_analysis);

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

        renderPatternInsights(current);

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
        renderChartImage('yearlyOverviewBarChart', 'yearlyOverviewBarEmpty', state.data?.charts?.yearly_expense_bar || state.data?.charts?.yearly_bar_chart || '/static/yearly_expense_bar.png');
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
