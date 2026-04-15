/**
 * SmartVest API Helper
 * Standardized fetch calls for the intelligent financial system.
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
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `API Error: ${response.status}`);
            }

            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                return await response.json().catch(() => ({}));
            }

            return {};
        } catch (error) {
            console.error(`Fetch error for ${endpoint}:`, error);
            throw error;
        }
    },

    // Auth
    login: (data) => API.request('/api/login', { method: 'POST', body: JSON.stringify(data) }),
    signup: (data) => API.request('/api/signup', { method: 'POST', body: JSON.stringify(data) }),
    logout: () => API.request('/api/logout', { method: 'POST' }),

    // Dashboard & Modules
    getDashboard: () => API.request('/api/dashboard'),
    getExpenses: () => API.request('/api/expenses'),
    addExpense: (data) => API.request('/api/add-expense', { method: 'POST', body: JSON.stringify(data) }),
    setIncome: (data) => API.request('/api/set-income', { method: 'POST', body: JSON.stringify(data) }),
    getExpenseAnalysis: () => API.request('/api/expense-analysis'),
    getGoals: () => API.request('/api/goal-status'),
    setGoal: (data) => API.request('/api/set-goal', { method: 'POST', body: JSON.stringify(data) }),
    getInvestmentSuggestions: () => API.request('/api/investment'),

    // Feedback & Reviews
    submitFeedback: (data) => API.request('/api/feedback', { method: 'POST', body: JSON.stringify(data) }),
    submitReview: (data) => API.request('/api/review', { method: 'POST', body: JSON.stringify(data) }),
    getReviews: () => API.request('/api/reviews'),

    // Admin
    getAdminStats: () => API.request('/api/admin/dashboard'),
    getAdminUsers: () => API.request('/api/admin/users'),
    deleteUser: (userId) => API.request(`/api/admin/delete-user`, { method: 'DELETE', body: JSON.stringify({ userId }) }),
    updateMarket: (state) => API.request('/api/admin/market', { method: 'POST', body: JSON.stringify({ state }) }),
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
} else {
    window.API = API;
}
