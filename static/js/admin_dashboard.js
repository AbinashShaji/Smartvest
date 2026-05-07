(function () {
    const chartColors = {
        line: '#ffffff',
        grid: 'rgba(255,255,255,0.08)',
        muted: 'rgba(255,255,255,0.55)',
        active: '#4ade80',
        inactive: 'rgba(255,255,255,0.16)',
    };

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function safeNumber(value) {
        const number = Number(value);
        return Number.isFinite(number) ? number : 0;
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
        const padding = 28;
        const chartWidth = width - padding * 2;
        const chartHeight = height - padding * 2;
        const maxValue = Math.max(...values.map(safeNumber), 1);

        ctx.strokeStyle = chartColors.grid;
        ctx.lineWidth = 1;
        for (let i = 0; i <= 3; i += 1) {
            const y = padding + (chartHeight / 3) * i;
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(width - padding, y);
            ctx.stroke();
        }

        const points = values.map((value, index) => {
            const x = padding + (chartWidth / Math.max(values.length - 1, 1)) * index;
            const y = padding + chartHeight - (safeNumber(value) / maxValue) * chartHeight;
            return { x, y };
        });

        ctx.strokeStyle = chartColors.line;
        ctx.lineWidth = 2;
        ctx.beginPath();
        points.forEach((point, index) => {
            if (index === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
        });
        ctx.stroke();

        ctx.fillStyle = chartColors.line;
        points.forEach((point) => {
            ctx.beginPath();
            ctx.arc(point.x, point.y, 3, 0, Math.PI * 2);
            ctx.fill();
        });

        ctx.fillStyle = chartColors.muted;
        ctx.font = '11px Inter, sans-serif';
        labels.forEach((label, index) => {
            const x = padding + (chartWidth / Math.max(labels.length - 1, 1)) * index;
            ctx.fillText(String(label).slice(5), x - 14, height - 8);
        });
    }

    function drawDonutChart(canvas, values = []) {
        if (!canvas) return;
        const { ctx, width, height } = clearCanvas(canvas);
        const active = safeNumber(values[0]);
        const inactive = safeNumber(values[1]);
        const total = Math.max(active + inactive, 1);
        const radius = Math.min(width, height) / 2 - 18;
        const centerX = width / 2;
        const centerY = height / 2;
        let start = -Math.PI / 2;

        [active, inactive].forEach((value, index) => {
            const angle = (value / total) * Math.PI * 2;
            ctx.beginPath();
            ctx.strokeStyle = index === 0 ? chartColors.active : chartColors.inactive;
            ctx.lineWidth = 22;
            ctx.arc(centerX, centerY, radius, start, start + angle);
            ctx.stroke();
            start += angle;
        });

        ctx.fillStyle = '#ffffff';
        ctx.font = '700 24px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${Math.round((active / total) * 100)}%`, centerX, centerY + 4);
        ctx.fillStyle = chartColors.muted;
        ctx.font = '12px Inter, sans-serif';
        ctx.fillText('active', centerX, centerY + 24);
        ctx.textAlign = 'start';
    }

    function renderStats(stats) {
        setText('statTotalUsers', safeNumber(stats.total_users));
        setText('statActiveUsers', safeNumber(stats.active_users));
        setText('statInactiveUsers', safeNumber(stats.inactive_users));
        setText('statNewUsers', safeNumber(stats.new_users_week));
        setText('statFeedback', safeNumber(stats.feedback_count));
        setText('statReviews', safeNumber(stats.review_count));
    }

    function renderEngagement(metrics) {
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
        insights.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    }

    function renderReminders(reminders) {
        setText('reminderPendingReviews', safeNumber(reminders.pending_reviews));
        setText('reminderNewFeedback', safeNumber(reminders.new_feedback));
        setText('reminderActions', safeNumber(reminders.unresolved_admin_actions));
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
                <small>${escapeHtml(item.status || 'PENDING')} · ${escapeHtml(item.date || '')}</small>
            </article>
        `);
        renderList('recentFeedback', activity.feedback, 'No feedback yet.', (item) => `
            <article>
                <strong>${escapeHtml(item.subject || 'Feedback')}</strong>
                <span>${escapeHtml(item.message || 'No message')}</span>
                <small>${escapeHtml(item.username || 'User')} · ${escapeHtml(item.date || '')}</small>
            </article>
        `);
    }

    async function loadDashboard() {
        try {
            const [stats, engagement, reminders, recent] = await Promise.all([
                API.getAdminActivityStats(),
                API.getAdminEngagementMetrics(),
                API.getAdminReminders(),
                API.getAdminRecentActivity(),
            ]);
            renderStats(stats);
            renderEngagement(engagement);
            renderReminders(reminders);
            renderRecent(recent);
        } catch (error) {
            setText('adminInsights', 'Unable to load dashboard data.');
            console.error('Admin dashboard load failed:', error);
        }
    }

    document.addEventListener('DOMContentLoaded', loadDashboard);
    window.addEventListener('resize', loadDashboard);
}());
