/**
 * SmartVest API helper.
 *
 * Big picture:
 * - standardize fetch calls
 * - attach CSRF tokens automatically
 * - keep route names in one place for the frontend
 */

const API = {
    getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    },

    // Base fetch wrapper:
    // The app uses one path for JSON, form data, CSRF, and error handling.
    async request(endpoint, options = {}) {
        const returnEnvelope = !!options.returnEnvelope;
        const requestOptions = { ...options };
        delete requestOptions.returnEnvelope;
        const headers = { ...(options.headers || {}) };
        const hasFormDataBody = typeof FormData !== 'undefined' && requestOptions.body instanceof FormData;

        if (!hasFormDataBody && !headers['Content-Type'] && !headers['content-type']) {
            headers['Content-Type'] = 'application/json';
        }
        const method = String(requestOptions.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && !headers['X-CSRF-Token']) {
            headers['X-CSRF-Token'] = API.getCsrfToken();
        }

        try {
            const response = await fetch(endpoint, {
                credentials: 'same-origin',
                ...requestOptions,
                headers,
            });
            const result = await response.json().catch(() => ({}));

            if (result.status === 'error') {
                throw new Error(result.message || 'API Error');
            }

            if (!response.ok) {
                throw new Error(result.message || `API Error: ${response.status}`);
            }

            return returnEnvelope ? result : (result.data || result);
        } catch (error) {
            console.error(`Fetch error for ${endpoint}:`, error);
            throw error;
        }
    },

    // Auth endpoints share the same session and CSRF handling.
    login: (data) => API.request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
    signup: (data) => API.request('/api/auth/signup', { method: 'POST', body: JSON.stringify(data) }),
    logout: () => API.request('/api/auth/logout', { method: 'POST' }),
    checkSession: () => API.request('/api/auth/check-session'),
    updateProfile: (data) => API.request('/api/auth/profile/update', { method: 'POST', body: JSON.stringify(data) }),
    changePassword: (data) => API.request('/api/auth/password/change', { method: 'POST', body: JSON.stringify(data) }),

    // Analysis endpoints power the dashboard and chart views.
    getDashboard: () => API.request('/api/analysis/data'),
    getExpenseAnalysis: () => API.request('/api/analysis/report'),
    getStockAnalysis: () => API.request('/api/analysis/dataframe'),
    updateEmergencyFundTarget: (months) => API.request('/api/analysis/ef-override', {
        method: 'POST',
        body: JSON.stringify({ months }),
    }),

    // Expense endpoints cover expense CRUD, income, and goals.
    getExpenses: () => API.request('/api/expense/all'),
    getRecentExpenses: () => API.request('/api/expense/recent'),
    addExpense: (data) => API.request('/api/expense/add', { method: 'POST', body: JSON.stringify(data) }),
    updateIncome: (data) => API.request('/api/expense/income/update', { method: 'POST', body: JSON.stringify(data) }),
    uploadCSV: (formData) => API.request('/api/expense/upload', { method: 'POST', body: formData }),
    exportCSV: () => API.request('/api/expense/export'),
    getGoals: () => API.request('/api/expense/goal/all'),
    getGoalDetail: (goalId) => API.request(`/api/expense/goal/${goalId}`),
    setGoalStatus: (data) => API.request('/api/expense/goal/status', { method: 'POST', body: JSON.stringify(data) }),
    addGoal: (data) => API.request('/api/expense/goal/add', { method: 'POST', body: JSON.stringify(data) }),

    // Investment endpoint returns the full recommendation payload.
    getOverview: () => API.request('/api/investment/data'),

    // Admin and community endpoints support moderation and uploads.
    getMarketMetrics: () => API.request('/api/admin/market-metrics'),
    getMarketDatasetList: () => API.request('/api/admin/market-dataset/list'),
    getMarketDatasetPreview: () => API.request('/api/admin/market-dataset/preview'),
    uploadMarketDataset: (formData) => API.request('/api/admin/market-dataset/upload', { method: 'POST', body: formData }),
    submitFeedback: (data) => API.request('/api/feedback/add', { method: 'POST', body: JSON.stringify(data) }),
    submitReview: (data) => API.request('/api/review/add', { method: 'POST', body: JSON.stringify(data) }),
    getReviews: () => API.request('/api/public/reviews'),
    getIncomingReviews: () => API.request('/api/admin/review/incoming'),
    getAcceptedReviews: () => API.request('/api/admin/review/accepted'),
    acceptReview: (reviewId) => API.request('/api/admin/review/accept', { method: 'POST', body: JSON.stringify({ reviewId }) }),
    setReviewPublicVisibility: (reviewId, showPublic) => API.request('/api/admin/review/public-toggle', {
        method: 'POST',
        body: JSON.stringify({ reviewId, showPublic }),
    }),
    getPublicReviews: () => API.request('/api/public/reviews'),
    getFeedback: () => API.request('/api/admin/feedback/all'),
    getIncomingFeedback: () => API.request('/api/admin/feedback/incoming'),
    getAcceptedFeedback: () => API.request('/api/admin/feedback/accepted'),
    acceptFeedback: (feedbackId) => API.request('/api/admin/feedback/accept', { method: 'POST', body: JSON.stringify({ feedbackId }) }),
    deleteFeedback: (feedbackId) => API.request('/api/admin/feedback/delete', { method: 'DELETE', body: JSON.stringify({ feedbackId }) }),
    markFeedbackResolved: (feedbackId) => API.request('/api/admin/feedback/resolve', { method: 'POST', body: JSON.stringify({ feedbackId }) }),
    markFeedbackUnresolved: (feedbackId) => API.request('/api/admin/feedback/unresolve', { method: 'POST', body: JSON.stringify({ feedbackId }) }),
    getAdminActivityStats: () => API.request('/api/admin/activity-stats'),
    getAdminEngagementMetrics: () => API.request('/api/admin/engagement-metrics'),
    getAdminRecentActivity: () => API.request('/api/admin/recent-activity'),
    getAdminReminders: () => API.request('/api/admin/reminders'),
    getAdminUsers: () => API.request('/api/admin/user/all'),
    deleteUser: (userId) => API.request(`/api/admin/user/delete`, { method: 'DELETE', body: JSON.stringify({ userId }) }),
    deleteReview: (reviewId) => API.request(`/api/admin/review/delete`, { method: 'DELETE', body: JSON.stringify({ reviewId }) }),
};

// Export for window access so inline template scripts can call API.*
if (typeof window !== 'undefined') {
    window.API = API;
}
