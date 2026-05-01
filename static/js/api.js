/**
 * SmartVest API Helper
 * Standardized fetch calls for the final modular backend.
 * All endpoints follow the /api/<module>/<object>/<action> format.
 */

const API = {
    // Base fetch wrapper
    async request(endpoint, options = {}) {
        const headers = { ...(options.headers || {}) };
        const hasFormDataBody = typeof FormData !== 'undefined' && options.body instanceof FormData;

        if (!hasFormDataBody && !headers['Content-Type'] && !headers['content-type']) {
            headers['Content-Type'] = 'application/json';
        }

        try {
            const response = await fetch(endpoint, {
                credentials: 'same-origin',
                ...options,
                headers,
            });
            const result = await response.json().catch(() => ({}));

            if (result.status === 'error') {
                throw new Error(result.message || 'API Error');
            }

            if (!response.ok) {
                throw new Error(result.message || `API Error: ${response.status}`);
            }

            return result.data || result;
        } catch (error) {
            console.error(`Fetch error for ${endpoint}:`, error);
            throw error;
        }
    },

    // Auth Modules (/api/auth/)
    login: (data) => API.request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
    signup: (data) => API.request('/api/auth/signup', { method: 'POST', body: JSON.stringify(data) }),
    logout: () => API.request('/api/auth/logout', { method: 'POST' }),
    checkSession: () => API.request('/api/auth/check-session'),
    updateProfile: (data) => API.request('/api/auth/profile/update', { method: 'POST', body: JSON.stringify(data) }),
    changePassword: (data) => API.request('/api/auth/password/change', { method: 'POST', body: JSON.stringify(data) }),

    // Analysis Modules (/api/analysis/)
    getDashboard: () => API.request('/api/analysis/data'),
    getExpenseAnalysis: () => API.request('/api/analysis/report'),
    getStockAnalysis: () => API.request('/api/analysis/dataframe'),
    updateEmergencyFundTarget: (months) => API.request('/api/analysis/ef-override', {
        method: 'POST',
        body: JSON.stringify({ months }),
    }),

    // Expense Modules (/api/expense/)
    getExpenses: () => API.request('/api/expense/all'),
    addExpense: (data) => API.request('/api/expense/add', { method: 'POST', body: JSON.stringify(data) }),
    updateIncome: (data) => API.request('/api/expense/income/update', { method: 'POST', body: JSON.stringify(data) }),
    setIncome: (data) => API.updateIncome(data), // Compatibility alias for older template code
    uploadCSV: (formData) => API.request('/api/expense/upload', { method: 'POST', body: formData }),
    exportCSV: () => API.request('/api/expense/export'),
    getGoals: () => API.request('/api/expense/goal/all'),
    addGoal: (data) => API.request('/api/expense/goal/add', { method: 'POST', body: JSON.stringify(data) }),
    setGoal: (data) => API.addGoal(data), // Compatibility alias for older template code

    // Investment Modules (/api/investment/)
    getOverview: () => API.request('/api/investment/data'),

    // Admin & Community Modules (/api/admin/)
    getMarketMetrics: () => API.request('/api/admin/market-metrics'),
    submitFeedback: (data) => API.request('/api/feedback/add', { method: 'POST', body: JSON.stringify(data) }),
    submitReview: (data) => API.request('/api/review/add', { method: 'POST', body: JSON.stringify(data) }),
    getReviews: () => API.request('/api/admin/review/all'),
    getFeedback: () => API.request('/api/admin/feedback/all'),
    getAdminStats: () => API.request('/api/admin/stats'),
    getAdminMarketInsight: () => API.request('/api/admin/market-insight'),
    getAdminUsers: () => API.request('/api/admin/user/all'),
    deleteUser: (userId) => API.request(`/api/admin/user/delete`, { method: 'DELETE', body: JSON.stringify({ userId }) }),
    deleteReview: (reviewId) => API.request(`/api/admin/review/delete`, { method: 'DELETE', body: JSON.stringify({ reviewId }) }),
    updateMarket: (state) => API.request('/api/admin/market/update', { method: 'POST', body: JSON.stringify({ state }) }),
};

// Export for window access
if (typeof window !== 'undefined') {
    window.API = API;
}
