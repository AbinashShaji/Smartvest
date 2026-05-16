(function () {
    const chartColors = {
        line: '#7dd3fc',
        lineFillTop: 'rgba(125,211,252,0.24)',
        lineFillBottom: 'rgba(125,211,252,0.03)',
        grid: 'rgba(255,255,255,0.12)',
        muted: 'rgba(255,255,255,0.72)',
        active: '#4ade80',
        inactive: 'rgba(148,163,184,0.35)',
        axis: 'rgba(255,255,255,0.22)',
    };
    let latestEngagement = null;

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function safeNumber(value) {
        const number = Number(value);
        return Number.isFinite(number) ? number : 0;
    }

    function safePercentChange(current, previous) {
        const now = safeNumber(current);
        const before = safeNumber(previous);
        if (before <= 0) return now > 0 ? 100 : 0;
        return ((now - before) / before) * 100;
    }

    function classifyTrend(value, inverse = false) {
        const adjusted = inverse ? -value : value;
        if (adjusted > 2) return 'up';
        if (adjusted < -2) return 'down';
        return 'stable';
    }

    function trendText(value, inverse = false) {
        const trend = classifyTrend(value, inverse);
        const abs = Math.abs(value).toFixed(1);
        if (trend === 'up') return `\u25B2 +${abs}% this week`;
        if (trend === 'down') return `\u25BC -${abs}% this week`;
        return '\u25CF Stable usage';
    }

    function trendClass(trend) {
        if (trend === 'up') return 'trend-chip trend-chip--up';
        if (trend === 'down') return 'trend-chip trend-chip--down';
        return 'trend-chip trend-chip--stable';
    }

    function setTrend(id, changeValue, inverse = false) {
        const element = document.getElementById(id);
        if (!element) return;
        const trend = classifyTrend(changeValue, inverse);
        element.className = trendClass(trend);
        element.textContent = trendText(changeValue, inverse);
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[char]));
    }

    function setLoadingSurface(elements, isLoading) {
        (elements || []).forEach((element) => {
            if (!element) return;
            element.classList.toggle('sv-loading-surface', !!isLoading);
            element.setAttribute('aria-busy', isLoading ? 'true' : 'false');
        });
    }

    function renderListSkeleton(containerId, count = 3) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = Array.from({ length: count }, () => `
            <article class="admin-skeleton-card" aria-hidden="true">
                <span class="sv-skeleton sv-skeleton-line" style="width: 52%"></span>
                <span class="sv-skeleton sv-skeleton-line" style="width: 78%"></span>
                <span class="sv-skeleton sv-skeleton-line" style="width: 34%"></span>
            </article>
        `).join('');
    }

    function setAdminLoadingState(isLoading) {
        setLoadingSurface([
            ...document.querySelectorAll('.stat-card'),
            ...document.querySelectorAll('.admin-panel'),
            document.querySelector('.admin-monitor-hero'),
        ], isLoading);

        if (isLoading) {
            renderListSkeleton('adminInsights', 3);
            renderListSkeleton('recentSignups', 2);
            renderListSkeleton('recentReviews', 2);
            renderListSkeleton('recentFeedback', 2);
        }
    }

    function clearCanvas(canvas) {
        const ctx = canvas.getContext('2d');
        const scale = window.devicePixelRatio || 1;
        const width = canvas.clientWidth || canvas.width;
        const height = canvas.clientHeight || canvas.height;
        canvas.width = width * scale;
        canvas.height = height * scale;
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
        ctx.clearRect(0, 0, width, height);
        return { ctx, width, height };
    }

    function drawLineChart(canvas, labels = [], values = []) {
        if (!canvas) return;
        const { ctx, width, height } = clearCanvas(canvas);
        const padding = 40;
        const chartWidth = width - padding * 2;
        const chartHeight = height - padding * 2;
        const maxValue = Math.max(...values.map(safeNumber), 1);
        const minValue = Math.min(...values.map(safeNumber), 0);
        const range = Math.max(maxValue - minValue, 1);

        ctx.strokeStyle = chartColors.grid;
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i += 1) {
            const y = padding + (chartHeight / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(width - padding, y);
            ctx.stroke();
        }
        ctx.strokeStyle = chartColors.axis;
        ctx.beginPath();
        ctx.moveTo(padding, height - padding);
        ctx.lineTo(width - padding, height - padding);
        ctx.stroke();

        const points = values.map((value, index) => {
            const x = padding + (chartWidth / Math.max(values.length - 1, 1)) * index;
            const y = padding + chartHeight - ((safeNumber(value) - minValue) / range) * chartHeight;
            return { x, y };
        });

        if (points.length > 1) {
            const gradient = ctx.createLinearGradient(0, padding, 0, height - padding);
            gradient.addColorStop(0, chartColors.lineFillTop);
            gradient.addColorStop(1, chartColors.lineFillBottom);
            ctx.beginPath();
            ctx.moveTo(points[0].x, height - padding);
            points.forEach((point) => ctx.lineTo(point.x, point.y));
            ctx.lineTo(points[points.length - 1].x, height - padding);
            ctx.closePath();
            ctx.fillStyle = gradient;
            ctx.fill();
        }

        ctx.shadowColor = 'rgba(125,211,252,0.55)';
        ctx.shadowBlur = 12;
        ctx.strokeStyle = chartColors.line;
        ctx.lineWidth = 3;
        ctx.beginPath();
        points.forEach((point, index, allPoints) => {
            if (index === 0) {
                ctx.moveTo(point.x, point.y);
            } else {
                const prev = allPoints[index - 1];
                const midX = (prev.x + point.x) / 2;
                const midY = (prev.y + point.y) / 2;
                ctx.quadraticCurveTo(prev.x, prev.y, midX, midY);
                ctx.quadraticCurveTo(midX, midY, point.x, point.y);
            }
        });
        ctx.stroke();
        ctx.shadowBlur = 0;

        points.forEach((point, index, allPoints) => {
            const previous = allPoints[index - 1];
            const positiveMove = !previous || point.y <= previous.y;
            ctx.beginPath();
            ctx.fillStyle = positiveMove ? '#4ade80' : '#fb7185';
            ctx.arc(point.x, point.y, 4.2, 0, Math.PI * 2);
            ctx.fill();
        });

        ctx.fillStyle = chartColors.muted;
        ctx.font = '700 12px Inter, sans-serif';
        labels.forEach((label, index) => {
            const x = padding + (chartWidth / Math.max(labels.length - 1, 1)) * index;
            const shortLabel = String(label).slice(5);
            ctx.fillText(shortLabel, x - Math.min(20, shortLabel.length * 3), height - 10);
        });

        ctx.fillStyle = 'rgba(255,255,255,0.66)';
        ctx.font = '600 11px Inter, sans-serif';
        for (let i = 0; i <= 4; i += 1) {
            const y = padding + (chartHeight / 4) * i;
            const tickValue = Math.round(maxValue - (range / 4) * i);
            ctx.fillText(String(tickValue), 8, y + 3);
        }
    }

    function drawDonutChart(canvas, values = []) {
        if (!canvas) return;
        const { ctx, width, height } = clearCanvas(canvas);
        const active = safeNumber(values[0]);
        const inactive = safeNumber(values[1]);
        const total = Math.max(active + inactive, 1);
        const radius = Math.min(width, height) / 2 - 24;
        const centerX = width / 2;
        const centerY = height / 2;
        let start = -Math.PI / 2;

        [active, inactive].forEach((value, index) => {
            const angle = (value / total) * Math.PI * 2;
            ctx.beginPath();
            ctx.strokeStyle = index === 0 ? chartColors.active : chartColors.inactive;
            ctx.lineWidth = 24;
            ctx.arc(centerX, centerY, radius, start, start + angle);
            ctx.stroke();
            start += angle;
        });

        ctx.fillStyle = '#ffffff';
        ctx.font = '700 28px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${Math.round((active / total) * 100)}%`, centerX, centerY + 4);
        ctx.fillStyle = chartColors.muted;
        ctx.font = '600 13px Inter, sans-serif';
        ctx.fillText('active users', centerX, centerY + 26);
        ctx.textAlign = 'start';
    }

    function renderStats(stats, metrics, reminders) {
        const totalUsers = safeNumber(stats.total_users);
        const activeUsers = safeNumber(stats.active_users);
        const inactiveUsers = safeNumber(stats.inactive_users);
        const newUsers = safeNumber(stats.new_users_week);
        const feedback = safeNumber(stats.feedback_count);
        const reviews = safeNumber(stats.review_count);

        setText('statTotalUsers', totalUsers);
        setText('statActiveUsers', activeUsers);
        setText('statInactiveUsers', inactiveUsers);
        setText('statNewUsers', newUsers);
        setText('statFeedback', feedback);
        setText('statReviews', reviews);

        const weekValues = metrics.weekly_trend?.values || [];
        const previousWeek = safeNumber(weekValues[weekValues.length - 2]);
        const currentWeek = safeNumber(weekValues[weekValues.length - 1]);
        const weeklyChange = safePercentChange(currentWeek, previousWeek);
        setTrend('trendTotalUsers', weeklyChange);
        setText('trendTotalUsersWeek', `${Math.abs(weeklyChange).toFixed(1)}% weekly movement`);

        const activePercent = totalUsers > 0 ? (activeUsers / totalUsers) * 100 : 0;
        const inactivePercent = totalUsers > 0 ? (inactiveUsers / totalUsers) * 100 : 0;
        setTrend('trendActiveUsers', activePercent - 50);
        setTrend('trendInactiveUsers', inactivePercent - 50, true);

        const newUserBase = totalUsers > 0 ? (newUsers / totalUsers) * 100 : 0;
        setTrend('trendNewUsers', newUserBase);
        setText('trendInactiveUsersHint', inactiveUsers > activeUsers ? 'Decline risk rising' : 'Within healthy range');

        const feedbackLoad = safePercentChange(feedback, reviews || 1);
        setTrend('trendFeedback', feedbackLoad, true);
        setTrend('trendReviews', -feedbackLoad);
        setText('trendFeedbackHint', feedback > reviews ? 'Higher issue reports' : 'Steady sentiment');
        setText('trendReviewsHint', reviews > 0 ? 'Review coverage active' : 'No recent review intake');

        const unresolved = safeNumber(reminders.unresolved_admin_actions);
        setText('trendActiveUsersHint', unresolved > 0 ? 'Monitor unresolved actions' : 'Healthy activity quality');
    }

    function renderEngagement(metrics) {
        latestEngagement = metrics;
        setText('engagementPercent', `${safeNumber(metrics.engagement_percent)}% engaged`);
        setText('activeSplitText', `${safeNumber(metrics.active_users)} active / ${safeNumber(metrics.inactive_users)} inactive users`);
        drawLineChart(
            document.getElementById('weeklyActivityChart'),
            metrics.weekly_trend?.labels || [],
            metrics.weekly_trend?.values || []
        );
        drawDonutChart(document.getElementById('activeSplitChart'), metrics.active_split?.values || []);

        const insights = document.getElementById('adminInsights');
        if (!insights) return;
        const items = Array.isArray(metrics.insights) && metrics.insights.length ? metrics.insights : ['No platform activity yet.'];
        insights.innerHTML = items.map((item) => {
            const text = escapeHtml(item);
            const lower = text.toLowerCase();
            let tone = 'info';
            let icon = '\u25CF';
            if (lower.includes('increase') || lower.includes('growth') || lower.includes('up')) {
                tone = 'up';
                icon = '\u25B2';
            } else if (lower.includes('drop') || lower.includes('decrease') || lower.includes('inactive') || lower.includes('fall')) {
                tone = 'down';
                icon = '\u25BC';
            } else if (lower.includes('stable')) {
                tone = 'stable';
            }
            return `<li class="insight-card insight-card--${tone}"><span class="insight-icon">${icon}</span><span>${text}</span></li>`;
        }).join('');

        const trendChip = document.getElementById('engagementTrendChip');
        if (trendChip) {
            const engagement = safeNumber(metrics.engagement_percent);
            const chipTrend = classifyTrend(engagement - 50);
            trendChip.className = trendClass(chipTrend);
            trendChip.textContent = chipTrend === 'up' ? '\u25B2 Growth' : chipTrend === 'down' ? '\u25BC Drop' : '\u25CF Stable';
        }

        const splitSignal = document.getElementById('activeSplitSignal');
        if (splitSignal) {
            const active = safeNumber(metrics.active_users);
            const inactive = safeNumber(metrics.inactive_users);
            const chipTrend = active >= inactive ? 'up' : 'down';
            splitSignal.className = chipTrend === 'up' ? 'status-pill status-pill--up' : 'status-pill status-pill--down';
            splitSignal.textContent = chipTrend === 'up' ? '\u25B2 Active lead' : '\u25BC Inactive rising';
        }
    }

    function redrawEngagementCharts() {
        if (!latestEngagement) return;
        drawLineChart(
            document.getElementById('weeklyActivityChart'),
            latestEngagement.weekly_trend?.labels || [],
            latestEngagement.weekly_trend?.values || []
        );
        drawDonutChart(
            document.getElementById('activeSplitChart'),
            latestEngagement.active_split?.values || []
        );
    }

    function renderReminders(reminders) {
        const pending = safeNumber(reminders.pending_reviews);
        const feedback = safeNumber(reminders.new_feedback);
        const actions = safeNumber(reminders.unresolved_admin_actions);

        setText('reminderPendingReviews', pending);
        setText('reminderNewFeedback', feedback);
        setText('reminderActions', actions);

        const rows = document.querySelectorAll('.severity-row');
        if (rows.length === 3) {
            rows[0].className = `severity-row ${pending > 5 ? 'severity-row--red' : pending > 0 ? 'severity-row--amber' : 'severity-row--green'}`;
            rows[1].className = `severity-row ${feedback > 10 ? 'severity-row--amber' : 'severity-row--blue'}`;
            rows[2].className = `severity-row ${actions > 0 ? 'severity-row--red' : 'severity-row--green'}`;
        }
    }

    function renderList(id, rows, emptyText, formatter) {
        const container = document.getElementById(id);
        if (!container) return;
        if (!Array.isArray(rows) || rows.length === 0) {
            container.innerHTML = `<p class="admin-empty">${escapeHtml(emptyText)}</p>`;
            return;
        }
        container.innerHTML = rows.map(formatter).join('');
    }

    function renderRecent(activity) {
        renderList('recentSignups', activity.signups, 'No new signups yet.', (item) => `
            <article>
                <strong>${escapeHtml(item.username || 'User')}</strong>
                <span>${escapeHtml(item.email || '')}</span>
                <small>${escapeHtml(item.created_at || 'No date')}</small>
            </article>
        `);
        renderList('recentReviews', activity.reviews, 'No reviews yet.', (item) => `
            <article>
                <strong>${escapeHtml(item.username || 'User')} rated ${safeNumber(item.rating)}/5</strong>
                <span>${escapeHtml(item.comment || 'No review text')}</span>
                <small>${escapeHtml(item.status || 'PENDING')} \u00B7 ${escapeHtml(item.date || '')}</small>
            </article>
        `);
        renderList('recentFeedback', activity.feedback, 'No feedback yet.', (item) => `
            <article>
                <strong>${escapeHtml(item.subject || 'Feedback')}</strong>
                <span>${escapeHtml(item.message || 'No message')}</span>
                <small>${escapeHtml(item.username || 'User')} \u00B7 ${escapeHtml(item.date || '')}</small>
            </article>
        `);
    }

    async function loadDashboard() {
        try {
            setAdminLoadingState(true);
            const [stats, engagement, reminders, recent] = await Promise.all([
                API.getAdminActivityStats(),
                API.getAdminEngagementMetrics(),
                API.getAdminReminders(),
                API.getAdminRecentActivity(),
            ]);
            renderStats(stats, engagement, reminders);
            renderEngagement(engagement);
            renderReminders(reminders);
            renderRecent(recent);
        } catch (error) {
            const insights = document.getElementById('adminInsights');
            if (insights) {
                insights.innerHTML = '<li class="insight-card insight-card--down"><span class="insight-icon">\u25BC</span><span>Unable to load dashboard data.</span></li>';
            }
        } finally {
            setAdminLoadingState(false);
        }
    }

    document.addEventListener('DOMContentLoaded', loadDashboard);
    window.addEventListener('resize', () => {
        clearTimeout(window.adminChartResizeTimer);
        window.adminChartResizeTimer = setTimeout(redrawEngagementCharts, 150);
    });
}());
