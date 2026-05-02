/**
 * SmartVest Expense Module
 * Shared behavior for the Add, List, and Export expense pages.
 */

(function () {
    const root = document.querySelector('[data-expense-page]');

    if (!root) {
        return;
    }

    const page = root.dataset.expensePage || 'add';
    const state = {
        expenses: [],
        visibleExpenses: [],
        selectedIds: new Set(),
        deleteTargetIds: [],
        isEditMode: false,
        isFilterMode: false,
    };

    document.addEventListener('DOMContentLoaded', initExpenseModule);

    async function initExpenseModule() {
        if (page === 'add') {
            initAddPage();
            return;
        }

        try {
            await refreshExpenseCache();
        } catch (error) {
            // The page still loads, but we show a friendly message in the UI.
            console.error('Unable to load expenses:', error);
            showPageStatus(page === 'list' ? 'expenseListStatus' : 'expenseExportStatus', error.message || 'Unable to load expenses.', 'error');
            if (page === 'list') {
                renderExpenseRows([]);
            }
            return;
        }

        if (page === 'list') {
            initListPage();
            renderCurrentList();
            return;
        }

        if (page === 'export') {
            initExportPage();
        }
    }

    function initAddPage() {
        const manualForm = document.getElementById('expenseManualForm');
        const importForm = document.getElementById('expenseImportForm');
        const dateInput = document.getElementById('expenseDate');

        setTodayValue(dateInput);

        if (manualForm) {
            manualForm.addEventListener('submit', handleManualSubmit);
        }

        if (importForm) {
            importForm.addEventListener('submit', handleImportSubmit);
        }
    }

    function initListPage() {
        const filterForm = document.getElementById('expenseFilterForm');
        const filterMode = document.getElementById('expenseFilterMode');
        const resetButton = document.getElementById('expenseFilterReset');
        const selectAllToolbar = document.getElementById('expenseSelectAll');
        const selectAllHeader = document.getElementById('expenseSelectAllHeader');
        const bulkDeleteButton = document.getElementById('expenseBulkDeleteBtn');
        const tableBody = document.getElementById('expenseTableBody');
        const editForm = document.getElementById('expenseEditForm');
        const editModal = document.getElementById('expenseEditModal');
        const deleteModal = document.getElementById('expenseDeleteModal');

        const modeFilterBtn = document.getElementById('modeFilterBtn');
        const modeEditBtn = document.getElementById('modeEditBtn');
        const filterPanel = document.getElementById('filterPanel');
        const editToolbar = document.getElementById('editToolbar');
        const listModuleShell = document.querySelector('[data-expense-page="list"]');

        if (modeFilterBtn && modeEditBtn) {
            modeFilterBtn.addEventListener('click', () => {
                if (state.isFilterMode) {
                    state.isFilterMode = false;
                    listModuleShell.classList.remove('filter-mode');
                    filterPanel.classList.remove('active');
                    modeFilterBtn.classList.remove('mode-btn-active');
                } else {
                    state.isFilterMode = true;
                    state.isEditMode = false;
                    
                    listModuleShell.classList.add('filter-mode');
                    listModuleShell.classList.remove('edit-mode');
                    
                    filterPanel.classList.add('active');
                    editToolbar.style.display = 'none';
                    
                    modeFilterBtn.classList.add('mode-btn-active');
                    modeEditBtn.classList.remove('mode-btn-active');
                }
            });

            modeEditBtn.addEventListener('click', () => {
                if (state.isEditMode) {
                    state.isEditMode = false;
                    listModuleShell.classList.remove('edit-mode');
                    editToolbar.style.display = 'none';
                    modeEditBtn.classList.remove('mode-btn-active');
                    clearSelectedExpenses();
                } else {
                    state.isEditMode = true;
                    state.isFilterMode = false;
                    
                    listModuleShell.classList.add('edit-mode');
                    listModuleShell.classList.remove('filter-mode');
                    
                    editToolbar.style.display = 'flex';
                    filterPanel.classList.remove('active');
                    
                    modeEditBtn.classList.add('mode-btn-active');
                    modeFilterBtn.classList.remove('mode-btn-active');
                }
            });
        }

        syncFilterGroupVisibility(filterMode?.value || 'single_day', true);

        if (filterMode) {
            filterMode.addEventListener('change', () => {
                syncFilterGroupVisibility(filterMode.value, true);
            });
        }

        if (filterForm) {
            filterForm.addEventListener('submit', (event) => {
                event.preventDefault();
                clearSelectedExpenses();
                renderCurrentList();
            });
        }

        if (resetButton) {
            resetButton.addEventListener('click', () => {
                filterForm?.reset();
                if (filterMode) {
                    filterMode.value = 'single_day';
                }
                syncFilterGroupVisibility('single_day', true);
                clearSelectedExpenses();
                renderCurrentList();
            });
        }

        [selectAllToolbar, selectAllHeader].forEach((checkbox) => {
            if (!checkbox) return;
            checkbox.addEventListener('change', () => {
                toggleVisibleSelection(checkbox.checked);
            });
        });

        if (bulkDeleteButton) {
            bulkDeleteButton.addEventListener('click', () => {
                const ids = Array.from(state.selectedIds);
                if (!ids.length) {
                    showPageStatus('expenseListStatus', 'Select one or more expenses before deleting.', 'error');
                    return;
                }

                openDeleteModal(ids, `Delete ${ids.length} selected expense${ids.length === 1 ? '' : 's'}?`);
            });
        }

        if (tableBody) {
            tableBody.addEventListener('change', (event) => {
                const target = event.target;
                if (target?.matches('.expense-row-checkbox')) {
                    const id = target.getAttribute('data-expense-id');
                    if (!id) return;

                    if (target.checked) {
                        state.selectedIds.add(String(id));
                    } else {
                        state.selectedIds.delete(String(id));
                    }

                    syncSelectionControls();
                }
            });

            tableBody.addEventListener('click', (event) => {
                const button = event.target.closest('[data-action]');
                if (!button) return;

                const expenseId = button.getAttribute('data-id');
                if (!expenseId) return;

                const action = button.getAttribute('data-action');
                if (action === 'edit') {
                    openEditModal(expenseId);
                } else if (action === 'delete') {
                    openDeleteModal([expenseId], 'Delete this expense?');
                }
            });
        }

        document.querySelectorAll('[data-close-edit-modal]').forEach((button) => {
            button.addEventListener('click', closeEditModal);
        });
        document.querySelectorAll('[data-close-delete-modal]').forEach((button) => {
            button.addEventListener('click', closeDeleteModal);
        });

        editModal?.addEventListener('click', (event) => {
            if (event.target === editModal) {
                closeEditModal();
            }
        });

        deleteModal?.addEventListener('click', (event) => {
            if (event.target === deleteModal) {
                closeDeleteModal();
            }
        });

        if (editForm) {
            editForm.addEventListener('submit', handleEditSubmit);
        }

        const deleteConfirmButton = document.getElementById('expenseDeleteConfirmBtn');
        if (deleteConfirmButton) {
            deleteConfirmButton.addEventListener('click', handleDeleteConfirm);
        }
    }

    function initExportPage() {
        const filterForm = document.getElementById('expenseExportForm');
        const filterMode = document.getElementById('expenseExportMode');
        const resetButton = document.getElementById('expenseExportReset');

        syncFilterGroupVisibility(filterMode?.value || 'date_range', false);

        if (filterMode) {
            filterMode.addEventListener('change', () => {
                syncFilterGroupVisibility(filterMode.value, false);
            });
        }

        if (filterForm) {
            filterForm.addEventListener('submit', handleExportSubmit);
        }

        if (resetButton) {
            resetButton.addEventListener('click', () => {
                filterForm?.reset();
                if (filterMode) {
                    filterMode.value = 'date_range';
                }
                syncFilterGroupVisibility('date_range', false);
                showPageStatus('expenseExportStatus', '');
            });
        }
    }

    async function handleManualSubmit(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const submitButton = document.getElementById('expenseManualSubmit');
        const statusId = 'manualExpenseStatus';

        const amount = Number(form.amount.value);
        const category = form.category.value.trim();
        const date = form.date.value;

        if (!Number.isFinite(amount) || amount <= 0) {
            showPageStatus(statusId, 'Please enter a valid amount greater than zero.', 'error');
            return;
        }

        if (!category) {
            showPageStatus(statusId, 'Please choose a category.', 'error');
            return;
        }

        if (!date) {
            showPageStatus(statusId, 'Please choose a date.', 'error');
            return;
        }

        setButtonLoading(submitButton, true, 'Save Expense');
        showPageStatus(statusId, 'Saving expense...');

        try {
            await API.request('/api/expense/add', {
                method: 'POST',
                body: JSON.stringify({
                    amount,
                    category,
                    date,
                }),
            });

            form.reset();
            setTodayValue(document.getElementById('expenseDate'));
            showPageStatus(statusId, 'Expense saved successfully.', 'success');

            if (page === 'list' || page === 'export') {
                await refreshExpenseCache();
            }
        } catch (error) {
            showPageStatus(statusId, error.message || 'Unable to save expense.', 'error');
        } finally {
            setButtonLoading(submitButton, false, 'Save Expense');
        }
    }

    async function handleImportSubmit(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const submitButton = document.getElementById('expenseImportSubmit');
        const statusId = 'importExpenseStatus';
        const fileInput = document.getElementById('expenseCsvFile');
        const file = fileInput?.files?.[0];

        if (!file) {
            showPageStatus(statusId, 'Please choose a CSV file before uploading.', 'error');
            return;
        }

        if (file.size === 0) {
            showPageStatus(statusId, 'The selected file is empty.', 'error');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.csv') && file.type !== 'text/csv') {
            showPageStatus(statusId, 'Please upload a CSV file.', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        setButtonLoading(submitButton, true, 'Upload CSV');
        showPageStatus(statusId, 'Uploading file...');

        try {
            const response = await API.request('/api/expense/upload', {
                method: 'POST',
                body: formData,
            });

            const message = response?.message || 'CSV uploaded successfully.';
            showPageStatus(statusId, message, 'success');
            form.reset();
            if (fileInput) {
                fileInput.value = '';
            }

            if (page === 'list' || page === 'export') {
                await refreshExpenseCache();
            }
        } catch (error) {
            showPageStatus(statusId, error.message || 'Unable to upload CSV.', 'error');
        } finally {
            setButtonLoading(submitButton, false, 'Upload CSV');
        }
    }

    async function handleEditSubmit(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const submitButton = document.getElementById('expenseEditSaveBtn');
        const statusId = 'expenseEditStatus';

        const payload = {
            expense_id: form.expense_id.value,
            amount: Number(form.amount.value),
            category: form.category.value,
            date: form.date.value,
        };

        if (!payload.expense_id) {
            showPageStatus(statusId, 'Missing expense ID.', 'error');
            return;
        }

        if (!Number.isFinite(payload.amount) || payload.amount <= 0) {
            showPageStatus(statusId, 'Please enter a valid amount greater than zero.', 'error');
            return;
        }

        if (!payload.date) {
            showPageStatus(statusId, 'Please choose a date.', 'error');
            return;
        }

        setButtonLoading(submitButton, true, 'Save Changes');
        showPageStatus(statusId, 'Saving changes...');

        try {
            await API.request('/api/expense/update', {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            showPageStatus(statusId, 'Expense updated successfully.', 'success');
            await refreshExpenseCache();
            closeEditModal();
            renderCurrentList();
        } catch (error) {
            showPageStatus(statusId, error.message || 'Unable to update expense.', 'error');
        } finally {
            setButtonLoading(submitButton, false, 'Save Changes');
        }
    }

    async function handleDeleteConfirm() {
        const ids = state.deleteTargetIds.slice();
        const confirmButton = document.getElementById('expenseDeleteConfirmBtn');

        if (!ids.length) {
            closeDeleteModal();
            return;
        }

        setButtonLoading(confirmButton, true, 'Delete');
        showPageStatus('expenseListStatus', 'Deleting expense(s)...');

        try {
            for (const id of ids) {
                await API.request('/api/expense/delete', {
                    method: 'DELETE',
                    body: JSON.stringify({ expense_id: id }),
                });
            }

            clearSelectedExpenses();
            closeDeleteModal();
            showPageStatus('expenseListStatus', `${ids.length} expense${ids.length === 1 ? '' : 's'} deleted.`, 'success');
            await refreshExpenseCache();
            renderCurrentList();
        } catch (error) {
            showPageStatus('expenseListStatus', error.message || 'Unable to delete expense(s).', 'error');
        } finally {
            setButtonLoading(confirmButton, false, 'Delete');
        }
    }

    async function handleExportSubmit(event) {
        event.preventDefault();
        const button = document.getElementById('expenseExportButton');
        const statusId = 'expenseExportStatus';
        const filters = collectFilters(document.getElementById('expenseExportForm'), false);
        const filteredExpenses = applyFilters(state.expenses, filters);

        if (!filteredExpenses.length) {
            showPageStatus(statusId, 'No expenses match the selected filters.', 'error');
            return;
        }

        setButtonLoading(button, true, 'Export CSV');
        showPageStatus(statusId, 'Preparing CSV file...');

        try {
            const csv = buildCsv(filteredExpenses);
            downloadTextFile(csv, buildExportFilename(filters));
            showPageStatus(statusId, `Exported ${filteredExpenses.length} expense${filteredExpenses.length === 1 ? '' : 's'}.`, 'success');
        } catch (error) {
            showPageStatus(statusId, error.message || 'Unable to export CSV.', 'error');
        } finally {
            setButtonLoading(button, false, 'Export CSV');
        }
    }

    async function refreshExpenseCache() {
        const data = await API.getExpenses();
        state.expenses = Array.isArray(data) ? normalizeExpenses(data) : [];
        return state.expenses;
    }

    function normalizeExpenses(expenses) {
        return expenses
            .map((expense) => ({
                ...expense,
                id: expense.id,
                amount: Number(expense.amount) || 0,
                category: expense.category || 'Other',
                date: String(expense.date || ''),
            }))
            .sort((left, right) => {
                const dateCompare = String(right.date || '').localeCompare(String(left.date || ''));
                if (dateCompare !== 0) {
                    return dateCompare;
                }

                return Number(right.id || 0) - Number(left.id || 0);
            });
    }

    function renderCurrentList() {
        const form = document.getElementById('expenseFilterForm');
        const filters = collectFilters(form, true);
        state.visibleExpenses = applyFilters(state.expenses, filters);
        renderExpenseRows(state.visibleExpenses);
        syncSelectionControls();
    }

    function renderExpenseRows(expenses) {
        const tableBody = document.getElementById('expenseTableBody');
        if (!tableBody) return;

        if (!expenses.length) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="expense-empty-state">No expenses match the current filters.</td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = expenses.map((expense) => {
            const id = String(expense.id);
            const checked = state.selectedIds.has(id) ? 'checked' : '';

            return `
                <tr data-expense-id="${escapeHtml(id)}">
                    <td class="edit-mode-cell">
                        <input class="expense-checkbox expense-row-checkbox" type="checkbox" data-expense-id="${escapeHtml(id)}" ${checked} aria-label="Select expense ${escapeHtml(id)}">
                    </td>
                    <td>${formatCurrency(expense.amount)}</td>
                    <td><span class="expense-badge">${escapeHtml(expense.category)}</span></td>
                    <td>${escapeHtml(expense.date)}</td>
                    <td class="edit-mode-cell">
                        <div class="expense-row-actions">
                            <button type="button" class="expense-button-secondary" data-action="edit" data-id="${escapeHtml(id)}">Edit</button>
                            <button type="button" class="expense-button-danger" data-action="delete" data-id="${escapeHtml(id)}">Delete</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function collectFilters(form, includeSingleDay) {
        if (!form) {
            return {};
        }

        const mode = form.querySelector('[name="filter_mode"]')?.value || (includeSingleDay ? 'single_day' : 'date_range');

        if (mode === 'single_day') {
            return { mode, single_day: form.querySelector('[name="single_day"]')?.value || '' };
        }

        if (mode === 'date_range') {
            return {
                mode,
                date_from: form.querySelector('[name="date_from"]')?.value || '',
                date_to: form.querySelector('[name="date_to"]')?.value || '',
            };
        }

        if (mode === 'month') {
            return { mode, month: form.querySelector('[name="month"]')?.value || '' };
        }

        if (mode === 'year') {
            return { mode, year: form.querySelector('[name="year"]')?.value || '' };
        }

        return {};
    }

    function applyFilters(expenses, filters) {
        const items = Array.isArray(expenses) ? expenses.slice() : [];

        return items.filter((expense) => {
            const date = String(expense.date || '');

            if (filters.mode === 'single_day') {
                return !filters.single_day || date === filters.single_day;
            }

            if (filters.mode === 'date_range') {
                if (filters.date_from && date < filters.date_from) {
                    return false;
                }

                if (filters.date_to && date > filters.date_to) {
                    return false;
                }

                return true;
            }

            if (filters.mode === 'month') {
                return !filters.month || date.startsWith(filters.month);
            }

            if (filters.mode === 'year') {
                return !filters.year || date.startsWith(String(filters.year));
            }

            return true;
        });
    }

    function syncFilterGroupVisibility(mode, includeSingleDay) {
        const filterGroups = document.querySelectorAll('[data-filter-group]');
        filterGroups.forEach((group) => {
            const groupName = group.getAttribute('data-filter-group');
            let visible = false;

            if (mode === 'single_day') {
                visible = includeSingleDay && groupName === 'single_day';
            } else if (mode === 'date_range') {
                visible = groupName === 'date_range';
            } else if (mode === 'month') {
                visible = groupName === 'month';
            } else if (mode === 'year') {
                visible = groupName === 'year';
            }

            group.hidden = !visible;
        });
    }

    function syncSelectionControls() {
        const selectedCount = document.getElementById('expenseSelectedCount');
        const bulkDeleteButton = document.getElementById('expenseBulkDeleteBtn');
        const selectAllToolbar = document.getElementById('expenseSelectAll');
        const selectAllHeader = document.getElementById('expenseSelectAllHeader');
        const visibleIds = state.visibleExpenses.map((expense) => String(expense.id));
        const selectedVisibleCount = visibleIds.filter((id) => state.selectedIds.has(id)).length;
        const allVisibleSelected = visibleIds.length > 0 && selectedVisibleCount === visibleIds.length;
        const someVisibleSelected = selectedVisibleCount > 0 && selectedVisibleCount < visibleIds.length;

        if (selectedCount) {
            selectedCount.textContent = `${state.selectedIds.size} selected`;
        }

        if (bulkDeleteButton) {
            bulkDeleteButton.disabled = state.selectedIds.size === 0;
        }

        [selectAllToolbar, selectAllHeader].forEach((checkbox) => {
            if (!checkbox) return;
            checkbox.checked = allVisibleSelected;
            checkbox.indeterminate = someVisibleSelected;
            checkbox.disabled = visibleIds.length === 0;
        });

        document.querySelectorAll('.expense-row-checkbox').forEach((checkbox) => {
            const id = checkbox.getAttribute('data-expense-id');
            checkbox.checked = id ? state.selectedIds.has(id) : false;
        });
    }

    function toggleVisibleSelection(checked) {
        const visibleIds = state.visibleExpenses.map((expense) => String(expense.id));

        visibleIds.forEach((id) => {
            if (checked) {
                state.selectedIds.add(id);
            } else {
                state.selectedIds.delete(id);
            }
        });

        syncSelectionControls();
    }

    function clearSelectedExpenses() {
        state.selectedIds.clear();
        syncSelectionControls();
    }

    function openEditModal(expenseId) {
        const modal = document.getElementById('expenseEditModal');
        const form = document.getElementById('expenseEditForm');
        const expense = state.expenses.find((item) => String(item.id) === String(expenseId));

        if (!modal || !form || !expense) {
            return;
        }

        form.expense_id.value = String(expense.id);
        form.amount.value = expense.amount;
        form.category.value = expense.category || 'Other';
        form.date.value = expense.date || '';
        showPageStatus('expenseEditStatus', '');
        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
    }

    function closeEditModal() {
        const modal = document.getElementById('expenseEditModal');
        const form = document.getElementById('expenseEditForm');

        if (form) {
            form.reset();
            form.expense_id.value = '';
        }

        showPageStatus('expenseEditStatus', '');

        if (modal) {
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
        }
    }

    function openDeleteModal(ids, message) {
        const modal = document.getElementById('expenseDeleteModal');
        const messageNode = document.getElementById('expenseDeleteModalMessage');

        state.deleteTargetIds = ids.map((id) => String(id));
        if (messageNode) {
            messageNode.textContent = message || 'This action cannot be undone.';
        }

        if (modal) {
            modal.classList.add('active');
            modal.setAttribute('aria-hidden', 'false');
        }
    }

    function closeDeleteModal() {
        const modal = document.getElementById('expenseDeleteModal');
        state.deleteTargetIds = [];

        if (modal) {
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
        }
    }

    function showPageStatus(elementId, message, type = 'info') {
        const element = document.getElementById(elementId);
        if (!element) return;

        element.textContent = message || '';
        element.style.color = type === 'success' ? '#15803d' : type === 'error' ? '#b91c1c' : '#64748b';
    }

    function setButtonLoading(button, loading, label) {
        if (!button) return;

        if (loading) {
            button.dataset.originalLabel = label;
            button.disabled = true;
            button.textContent = `${label}...`;
            return;
        }

        button.disabled = false;
        button.textContent = button.dataset.originalLabel || label;
    }

    function setTodayValue(input) {
        if (!input) return;

        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        input.value = `${year}-${month}-${day}`;
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(amount) || 0);
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function buildCsv(expenses) {
        const headers = ['amount', 'category', 'date'];
        const rows = expenses.map((expense) => [
            csvEscape(expense.amount),
            csvEscape(expense.category),
            csvEscape(expense.date),
        ].join(','));

        return [headers.join(','), ...rows].join('\n');
    }

    function csvEscape(value) {
        const text = String(value ?? '');
        if (/[",\n]/.test(text)) {
            return `"${text.replace(/"/g, '""')}"`;
        }
        return text;
    }

    function downloadTextFile(content, filename) {
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 250);
    }

    function buildExportFilename(filters) {
        const suffix = filters.mode === 'month'
            ? filters.month.replace('-', '')
            : filters.mode === 'year'
                ? String(filters.year || 'all')
                : 'filtered';

        return `smartvest-expenses-${suffix}.csv`;
    }
})();
