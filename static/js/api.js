/**
 * SmartVest API Helper
 * Standardized fetch calls for the final modular backend.
 * All endpoints follow the /api/<module>/<object>/<action> format.
 */

const API = {
    // Base fetch wrapper
    async request(endpoint, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        try {
            const response = await fetch(endpoint, { ...defaultOptions, ...options });
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

    // Expense Modules (/api/expense/)
    getExpenses: () => API.request('/api/expense/all'),
    addExpense: (data) => API.request('/api/expense/add', { method: 'POST', body: JSON.stringify(data) }),
    updateIncome: (data) => API.request('/api/expense/income/update', { method: 'POST', body: JSON.stringify(data) }),
    uploadCSV: (formData) => API.request('/api/expense/upload', { method: 'POST', body: formData }),
    exportCSV: () => API.request('/api/expense/export'),
    getGoals: () => API.request('/api/expense/goal/all'),
    addGoal: (data) => API.request('/api/expense/goal/add', { method: 'POST', body: JSON.stringify(data) }),

    // Investment Modules (/api/investment/)
    getOverview: () => API.request('/api/investment/data'),
    getStrategies: () => API.request('/api/investment/strategy/all'),
    getMarketStatus: () => API.request('/api/investment/market/status'),

    // Admin & Community Modules (/api/admin/)
    submitFeedback: (data) => API.request('/api/admin/feedback/add', { method: 'POST', body: JSON.stringify(data) }),
    submitReview: (data) => API.request('/api/admin/review/add', { method: 'POST', body: JSON.stringify(data) }),
    getReviews: () => API.request('/api/admin/review/all'),
    getFeedback: () => API.request('/api/admin/feedback/all'),
    getAdminStats: () => API.request('/api/admin/stats'),
    getAdminUsers: () => API.request('/api/admin/user/all'),
    deleteUser: (userId) => API.request(`/api/admin/user/delete`, { method: 'DELETE', body: JSON.stringify({ userId }) }),
    updateMarket: (state) => API.request('/api/admin/market/update', { method: 'POST', body: JSON.stringify({ state }) }),
};

// Export for window access
if (typeof window !== 'undefined') {
    window.API = API;
}
