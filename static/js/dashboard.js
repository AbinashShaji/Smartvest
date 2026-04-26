/* global API, formatCurrency */

(function () {
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

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.innerText = value;
        }
    }

    function renderKpis(data) {
        const income = safeNumber(data?.monthly_income);
        const expenses = safeNumber(data?.total_expenses);
        const savings = safeNumber(data?.total_savings);
        const rate = income > 0 ? (savings / income) * 100 : 0;

        setText('currentIncome', formatCurrency(income));
        setText('totalExpenses', formatCurrency(expenses));
        setText('totalSavings', formatCurrency(savings));
        setText('savingsRate', `${rate.toFixed(1)}%`);
    }

    function renderInsight(report, analysis) {
        const summary = report?.summary || 'No data yet';
        const topCategory = analysis?.top_category && analysis.top_category !== 'None'
            ? analysis.top_category
            : 'No data yet';

        setText('dashboardSummary', summary);
        setText('dashboardTopCategory', topCategory);
    }

    function renderChart(analysis) {
        const img = document.getElementById('dashboardChartImg');
        if (!img) {
            return;
        }

        const chartPath = analysis?.bar_chart || analysis?.line_chart || '';
        if (chartPath) {
            img.src = `${chartPath}?v=${Date.now()}`;
            img.style.display = 'block';
            return;
        }

        img.removeAttribute('src');
        img.style.display = 'none';
    }

    function renderRecentActivity(expenses) {
        const tbody = document.getElementById('recentActivity');
        if (!tbody) {
            return;
        }

        const items = Array.isArray(expenses) ? expenses.slice(0, 5) : [];
        if (items.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="empty-state">No expenses yet.</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = items.map((expense) => `
            <tr>
                <td>${escapeHtml(expense.description || 'Expense')}</td>
                <td><span class="dashboard-chip">${escapeHtml(expense.category || 'Other')}</span></td>
                <td class="dashboard-muted">${escapeHtml(expense.date || '')}</td>
                <td class="dashboard-table-amount">-$${safeNumber(expense.amount).toFixed(2)}</td>
            </tr>
        `).join('');
    }

    async function loadDashboard() {
        try {
            const [dashboard, report, analysis, expenses] = await Promise.all([
                API.getDashboard(),
                API.getExpenseAnalysis(),
                API.getStockAnalysis(),
                API.getExpenses(),
            ]);

            renderKpis(dashboard);
            renderInsight(report, analysis);
            renderChart(analysis);
            renderRecentActivity(expenses);
        } catch (error) {
            renderKpis({});
            renderInsight({}, {});
            renderChart({});
            renderRecentActivity([]);
            const tbody = document.getElementById('recentActivity');
            if (tbody) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="4" class="empty-state">Unable to load recent activity.</td>
                    </tr>
                `;
            }
        }
    }

    document.addEventListener('DOMContentLoaded', loadDashboard);
})();
