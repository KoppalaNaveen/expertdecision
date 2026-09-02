function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
window.escapeHtml = escapeHtml;

let allDecisions = [];
let currentStatusFilter = 'All';
let currentPage = 1;
let rowsPerPage = 5;

let isSelectModeActive = false;
let selectedDecisionIds = new Set();

function changeDecisionPageSize(size) {
    if (size === 'all') {
        rowsPerPage = 999999;
    } else {
        rowsPerPage = parseInt(size, 10) || 5;
    }
    currentPage = 1;
    renderTable();
}
window.changeDecisionPageSize = changeDecisionPageSize;

let filterState = {
    category: 'All',
    priority: 'All',
    department: 'All',
    ownership: 'All'
};

let dateRangeState = {
    type: 'all',
    label: 'All Time',
    startDate: null,
    endDate: null
};

function hydrateInstantData() {
    if (window.INITIAL_DECISIONS && Array.isArray(window.INITIAL_DECISIONS) && window.INITIAL_DECISIONS.length > 0) {
        allDecisions = window.INITIAL_DECISIONS;
        populateFilterDropdownOptions();
        renderTable();
        return true;
    }
    return false;
}

try {
    hydrateInstantData();
} catch (_) {}

function initDecisionPage() {
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    if (tabParam) {
        currentStatusFilter = tabParam;
        const tabEl = document.getElementById(`${tabParam.toLowerCase()}-tab`);
        if (tabEl) {
            setFilter(tabParam, tabEl);
        }
    }

    const wasHydrated = hydrateInstantData();
    if (!wasHydrated) {
        fetchDecisions();
    } else {
        setTimeout(() => { fetchDecisions(); }, 300);
    }

    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("input", function() {
            currentPage = 1;
            renderTable();
        });
    }

    if (typeof lucide !== 'undefined' && lucide.createIcons) {
        lucide.createIcons();
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDecisionPage);
} else {
    initDecisionPage();
}

async function fetchDecisions() {
    try {
        let userParam = (typeof USER_ID !== 'undefined' && USER_ID) ? USER_ID : '';
        let roleParam = (typeof CURRENT_USER_ROLE !== 'undefined' && CURRENT_USER_ROLE) ? CURRENT_USER_ROLE : '';
        let queryParams = [];
        if (userParam) queryParams.push(`user_id=${userParam}`);
        if (roleParam) queryParams.push(`role_name=${encodeURIComponent(roleParam)}`);
        let queryStr = queryParams.length > 0 ? `?${queryParams.join('&')}` : '';

        let response = await fetch(`/api/decisions${queryStr}`);
        if (!response.ok) {
            response = await fetch(`/api/decisions/${queryStr}`);
        }
        if (!response.ok && typeof API_URL !== 'undefined' && API_URL) {
            response = await fetch(`${API_URL}/decisions/${queryStr}`);
        }
        if (!response || !response.ok) throw new Error("Failed to load decisions");
        const data = await response.json();
        allDecisions = Array.isArray(data) ? data : [];

        populateFilterDropdownOptions();
        renderTable();
    } catch (error) {
        console.error("Error loading decisions:", error);
        if (typeof showToast === 'function') {
            showToast("Danger", error.message);
        }
    }
}

function populateFilterDropdownOptions() {
    const catSelect = document.getElementById("filterCategory");
    const deptSelect = document.getElementById("filterDepartment");

    if (catSelect) {
        const currentCatVal = catSelect.value || 'All';
        const categories = new Set();
        allDecisions.forEach(d => {
            if (d.category_name && d.category_name.trim()) categories.add(d.category_name.trim());
        });
        
        let catHtml = '<option value="All">All Categories</option>';
        Array.from(categories).sort().forEach(cat => {
            catHtml += `<option value="${escapeHtml(cat)}">${escapeHtml(cat)}</option>`;
        });
        catSelect.innerHTML = catHtml;
        catSelect.value = categories.has(currentCatVal) ? currentCatVal : 'All';
    }

    if (deptSelect) {
        const currentDeptVal = deptSelect.value || 'All';
        const departments = new Set();
        allDecisions.forEach(d => {
            if (d.department && d.department.trim()) departments.add(d.department.trim());
        });
        
        let deptHtml = '<option value="All">All Departments</option>';
        Array.from(departments).sort().forEach(dept => {
            deptHtml += `<option value="${escapeHtml(dept)}">${escapeHtml(dept)}</option>`;
        });
        deptSelect.innerHTML = deptHtml;
        deptSelect.value = departments.has(currentDeptVal) ? currentDeptVal : 'All';
    }
}

function applyAdvancedFilters() {
    const catSelect = document.getElementById("filterCategory");
    const prioSelect = document.getElementById("filterPriority");
    const deptSelect = document.getElementById("filterDepartment");
    const ownerSelect = document.getElementById("filterOwnership");

    filterState.category = catSelect ? catSelect.value : 'All';
    filterState.priority = prioSelect ? prioSelect.value : 'All';
    filterState.department = deptSelect ? deptSelect.value : 'All';
    filterState.ownership = ownerSelect ? ownerSelect.value : 'All';

    let activeFilterCount = 0;
    if (filterState.category !== 'All') activeFilterCount++;
    if (filterState.priority !== 'All') activeFilterCount++;
    if (filterState.department !== 'All') activeFilterCount++;
    if (filterState.ownership !== 'All') activeFilterCount++;

    const badge = document.getElementById("filterBadgeCount");
    const filterBtn = document.getElementById("filterDropdownBtn");
    if (badge) {
        if (activeFilterCount > 0) {
            badge.innerText = activeFilterCount;
            badge.classList.remove('d-none');
            if (filterBtn) {
                filterBtn.classList.add('border-primary', 'text-primary', 'bg-primary-subtle');
            }
        } else {
            badge.classList.add('d-none');
            if (filterBtn) {
                filterBtn.classList.remove('border-primary', 'text-primary', 'bg-primary-subtle');
            }
        }
    }

    // Close dropdown
    const dropdownEl = document.getElementById("filterDropdownBtn");
    if (dropdownEl && bootstrap.Dropdown.getInstance(dropdownEl)) {
        bootstrap.Dropdown.getInstance(dropdownEl).hide();
    }

    currentPage = 1;
    renderTable();
}
window.applyAdvancedFilters = applyAdvancedFilters;

function resetAdvancedFilters() {
    const catSelect = document.getElementById("filterCategory");
    const prioSelect = document.getElementById("filterPriority");
    const deptSelect = document.getElementById("filterDepartment");
    const ownerSelect = document.getElementById("filterOwnership");

    if (catSelect) catSelect.value = 'All';
    if (prioSelect) prioSelect.value = 'All';
    if (deptSelect) deptSelect.value = 'All';
    if (ownerSelect) ownerSelect.value = 'All';

    filterState = {
        category: 'All',
        priority: 'All',
        department: 'All',
        ownership: 'All'
    };

    const badge = document.getElementById("filterBadgeCount");
    const filterBtn = document.getElementById("filterDropdownBtn");
    if (badge) badge.classList.add('d-none');
    if (filterBtn) {
        filterBtn.classList.remove('border-primary', 'text-primary', 'bg-primary-subtle');
    }

    const dropdownEl = document.getElementById("filterDropdownBtn");
    if (dropdownEl && bootstrap.Dropdown.getInstance(dropdownEl)) {
        bootstrap.Dropdown.getInstance(dropdownEl).hide();
    }

    currentPage = 1;
    renderTable();
}
window.resetAdvancedFilters = resetAdvancedFilters;

function selectDatePreset(rangeKey, label) {
    dateRangeState.type = rangeKey;
    dateRangeState.label = label;
    dateRangeState.startDate = null;
    dateRangeState.endDate = null;

    // Update active style on preset buttons
    document.querySelectorAll('.date-preset-btn').forEach(btn => {
        const isMatch = btn.getAttribute('data-range') === rangeKey;
        btn.classList.toggle('active', isMatch);
        btn.classList.toggle('bg-primary-subtle', isMatch);
        btn.classList.toggle('text-primary', isMatch);
        const checkIcon = btn.querySelector('.preset-check');
        if (checkIcon) {
            checkIcon.classList.toggle('d-none', !isMatch);
        }
    });

    // Clear custom input fields
    const fromInput = document.getElementById('customDateFrom');
    const toInput = document.getElementById('customDateTo');
    if (fromInput) fromInput.value = '';
    if (toInput) toInput.value = '';

    updateDateRangeButtonUI();

    const dropdownEl = document.getElementById("dateRangeDropdownBtn");
    if (dropdownEl && bootstrap.Dropdown.getInstance(dropdownEl)) {
        bootstrap.Dropdown.getInstance(dropdownEl).hide();
    }

    currentPage = 1;
    renderTable();
}
window.selectDatePreset = selectDatePreset;

function applyCustomDateRange() {
    const fromInput = document.getElementById('customDateFrom');
    const toInput = document.getElementById('customDateTo');
    const fromVal = fromInput ? fromInput.value : '';
    const toVal = toInput ? toInput.value : '';

    if (!fromVal && !toVal) {
        if (typeof showToast === 'function') {
            showToast("Warning", "Please select at least a From or To date.");
        }
        return;
    }

    dateRangeState.type = 'custom';
    dateRangeState.startDate = fromVal || null;
    dateRangeState.endDate = toVal || null;

    let customLabel = '';
    if (fromVal && toVal) {
        customLabel = `${fromVal} to ${toVal}`;
    } else if (fromVal) {
        customLabel = `Since ${fromVal}`;
    } else {
        customLabel = `Until ${toVal}`;
    }
    dateRangeState.label = customLabel;

    // Deselect preset buttons
    document.querySelectorAll('.date-preset-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-primary-subtle', 'text-primary');
        const checkIcon = btn.querySelector('.preset-check');
        if (checkIcon) checkIcon.classList.add('d-none');
    });

    updateDateRangeButtonUI();

    const dropdownEl = document.getElementById("dateRangeDropdownBtn");
    if (dropdownEl && bootstrap.Dropdown.getInstance(dropdownEl)) {
        bootstrap.Dropdown.getInstance(dropdownEl).hide();
    }

    currentPage = 1;
    renderTable();
}
window.applyCustomDateRange = applyCustomDateRange;

function clearDateRange() {
    selectDatePreset('all', 'Date Range');
}
window.clearDateRange = clearDateRange;

function clearAllFiltersAndDate() {
    resetAdvancedFilters();
    clearDateRange();
}
window.clearAllFiltersAndDate = clearAllFiltersAndDate;

function updateDateRangeButtonUI() {
    const labelEl = document.getElementById("dateRangeLabel");
    const activeDot = document.getElementById("dateRangeActiveDot");
    const dateBtn = document.getElementById("dateRangeDropdownBtn");

    if (dateRangeState.type !== 'all') {
        if (labelEl) labelEl.innerText = dateRangeState.label;
        if (activeDot) activeDot.classList.remove('d-none');
        if (dateBtn) {
            dateBtn.classList.add('border-primary', 'text-primary', 'bg-primary-subtle');
        }
    } else {
        if (labelEl) labelEl.innerText = "Date Range";
        if (activeDot) activeDot.classList.add('d-none');
        if (dateBtn) {
            dateBtn.classList.remove('border-primary', 'text-primary', 'bg-primary-subtle');
        }
    }
}

function isDateWithinRange(itemDateVal, rangeState) {
    if (!rangeState || rangeState.type === 'all') return true;
    if (!itemDateVal) return false;

    const itemDate = new Date(itemDateVal);
    if (isNaN(itemDate.getTime())) return true;

    const now = new Date();
    
    if (rangeState.type === 'today') {
        const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
        return itemDate >= startOfDay && itemDate <= endOfDay;
    }
    
    if (rangeState.type === '7days') {
        const past7 = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        return itemDate >= past7 && itemDate <= now;
    }
    
    if (rangeState.type === '30days') {
        const past30 = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        return itemDate >= past30 && itemDate <= now;
    }
    
    if (rangeState.type === 'month') {
        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0);
        return itemDate >= startOfMonth && itemDate <= now;
    }
    
    if (rangeState.type === 'year') {
        const startOfYear = new Date(now.getFullYear(), 0, 1, 0, 0, 0);
        return itemDate >= startOfYear && itemDate <= now;
    }
    
    if (rangeState.type === 'custom') {
        if (rangeState.startDate) {
            const start = new Date(rangeState.startDate + 'T00:00:00');
            if (itemDate < start) return false;
        }
        if (rangeState.endDate) {
            const end = new Date(rangeState.endDate + 'T23:59:59.999');
            if (itemDate > end) return false;
        }
        return true;
    }
    
    return true;
}

function updateTabCounts() {
    let counts = {
        'All': 0,
        'Draft': 0,
        'Pending': 0,
        'In Review': 0,
        'Approved': 0,
        'Rejected': 0,
        'Archived': 0
    };

    allDecisions.forEach(d => {
        const st = (d.status || '').trim().toLowerCase();
        if (st === 'archived') {
            counts['Archived']++;
        } else {
            counts['All']++;
            if (st === 'draft') counts['Draft']++;
            else if (st === 'pending') counts['Pending']++;
            else if (st === 'in review' || st === 'under review' || st === 'review') counts['In Review']++;
            else if (st === 'approved') counts['Approved']++;
            else if (st === 'rejected') counts['Rejected']++;
        }
    });

    const mapping = {
        'count-all': 'All',
        'count-draft': 'Draft',
        'count-pending': 'Pending',
        'count-review': 'In Review',
        'count-approved': 'Approved',
        'count-rejected': 'Rejected',
        'count-archived': 'Archived'
    };

    for (let id in mapping) {
        const el = document.getElementById(id);
        if (el) {
            el.innerText = counts[mapping[id]];
        }
    }
}

function setFilter(status, btnElement) {
    currentStatusFilter = status;
    currentPage = 1;

    // Reset styles on all tabs
    const tabs = document.querySelectorAll('#decisionTabs .nav-link');
    tabs.forEach(tab => {
        tab.classList.remove('active', 'fw-bold', 'border-bottom', 'border-primary', 'border-3', 'text-primary');
        tab.classList.add('fw-medium', 'text-secondary');
        const badge = tab.querySelector('.badge');
        if (badge) {
            badge.className = 'badge bg-light text-secondary rounded-pill ms-1';
        }
    });

    // Set active styles on clicked tab
    if (btnElement) {
        btnElement.classList.add('active', 'fw-bold', 'border-bottom', 'border-primary', 'border-3', 'text-primary');
        btnElement.classList.remove('fw-medium', 'text-secondary');
        const badge = btnElement.querySelector('.badge');
        if (badge) {
            badge.className = 'badge bg-primary bg-opacity-10 text-primary rounded-pill ms-1';
        }
    }

    renderTable();
}

function renderTable() {
    updateTabCounts();
    updateActiveFilterChips();

    const tbody = document.getElementById("decisionsTableBody");
    const searchInput = document.getElementById("searchInput");
    const searchQuery = searchInput ? searchInput.value.toLowerCase().trim() : "";
    
    let filtered = allDecisions.filter(d => {
        // Search text
        const matchesSearch = !searchQuery || 
            (d.title && d.title.toLowerCase().includes(searchQuery)) || 
            (d.description && d.description.toLowerCase().includes(searchQuery)) ||
            (String(d.id).includes(searchQuery)) ||
            (d.creator_name && d.creator_name.toLowerCase().includes(searchQuery)) ||
            (d.tags && d.tags.toLowerCase().includes(searchQuery));
        
        // Status Tab
        const stLower = (d.status || '').trim().toLowerCase();
        const filterLower = (currentStatusFilter || 'All').trim().toLowerCase();

        let matchesStatus = false;
        if (filterLower === 'all') {
            matchesStatus = (stLower !== 'archived');
        } else if (filterLower === 'in review' || filterLower === 'review') {
            matchesStatus = (stLower === 'in review' || stLower === 'under review' || stLower === 'review');
        } else {
            matchesStatus = (stLower === filterLower);
        }

        // Category Filter
        let matchesCategory = true;
        if (filterState.category && filterState.category !== 'All') {
            matchesCategory = (d.category_name && d.category_name.trim().toLowerCase() === filterState.category.trim().toLowerCase());
        }

        // Priority Filter
        let matchesPriority = true;
        if (filterState.priority && filterState.priority !== 'All') {
            matchesPriority = (d.priority_level && d.priority_level.trim().toLowerCase() === filterState.priority.trim().toLowerCase());
        }

        // Department Filter
        let matchesDepartment = true;
        if (filterState.department && filterState.department !== 'All') {
            matchesDepartment = (d.department && d.department.trim().toLowerCase() === filterState.department.trim().toLowerCase());
        }

        // Ownership Filter
        let matchesOwnership = true;
        if (filterState.ownership === 'mine') {
            matchesOwnership = (typeof USER_ID !== 'undefined' && USER_ID && Number(d.created_by) === Number(USER_ID));
        } else if (filterState.ownership === 'others') {
            matchesOwnership = (typeof USER_ID !== 'undefined' && USER_ID && Number(d.created_by) !== Number(USER_ID));
        }

        // Date Range Filter
        let matchesDate = isDateWithinRange(d.created_at || d.decision_date, dateRangeState);
        
        return matchesSearch && matchesStatus && matchesCategory && matchesPriority && matchesDepartment && matchesOwnership && matchesDate;
    });

    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start = (currentPage - 1) * rowsPerPage;
    const paginated = filtered.slice(start, start + rowsPerPage);

    tbody.innerHTML = "";
    
    if (paginated.length === 0) {
        const colSpan = isSelectModeActive ? 7 : 6;
        tbody.innerHTML = `<tr><td colspan="${colSpan}" class="text-center py-4 text-muted">No decisions found.</td></tr>`;
    } else {
        paginated.forEach(d => {
            const dateStr = new Date(d.created_at).toLocaleDateString();
            let statusBadge = "bg-secondary";
            if (d.status === "Approved") statusBadge = "bg-success";
            if (d.status === "Rejected") statusBadge = "bg-danger";
            if (d.status === "Under Review" || d.status === "In Review") statusBadge = "bg-warning text-dark";
            if (d.status === "Archived") statusBadge = "bg-secondary text-white";

            const isAdmin = typeof CURRENT_USER_ROLE !== 'undefined' && CURRENT_USER_ROLE && String(CURRENT_USER_ROLE).toLowerCase().includes('admin');
            const canDelete = isAdmin || (d.status !== "Approved" && d.status !== "Rejected" && d.status !== "Archived");

            const isOwner = typeof USER_ID !== 'undefined' && USER_ID && Number(d.created_by) === Number(USER_ID);
            let actionButtons = "";

            if (d.status === "Draft" && isOwner) {
                actionButtons = `
                    <a href="/create_decision?edit=${d.id}" class="btn btn-sm btn-outline-secondary fw-semibold px-2 me-1" title="Edit Draft"><i class="bi bi-pencil me-1"></i>Edit</a>
                    <button onclick="submitDraftFromTable(${d.id})" class="btn btn-sm btn-success fw-semibold px-2 me-1" title="Submit Decision"><i class="bi bi-send me-1"></i>Submit</button>
                `;
            } else if (d.status === "Rejected" && isOwner) {
                actionButtons = `
                    <button onclick="openRejectionCommentsModal(${d.id})" class="btn btn-sm btn-outline-warning text-dark fw-semibold px-2 me-1" title="View Rejection Comments"><i class="bi bi-chat-left-text me-1"></i>View Comments</button>
                    <a href="/create_decision?edit=${d.id}&resubmit=true" class="btn btn-sm btn-primary fw-semibold px-2 me-1" title="Edit & Resubmit"><i class="bi bi-pencil-square me-1"></i>Edit & Resubmit</a>
                `;
            }

            const checkboxHtml = `
                <td class="ps-4 py-3 selection-col ${isSelectModeActive ? '' : 'd-none'}" style="width: 40px;">
                    <input type="checkbox" class="form-check-input decision-select-checkbox" value="${d.id}" ${selectedDecisionIds.has(Number(d.id)) ? 'checked' : ''} onchange="onDecisionCheckboxChange(${d.id})">
                </td>
            `;

            tbody.innerHTML += `
                <tr class="${selectedDecisionIds.has(Number(d.id)) ? 'table-danger bg-danger-subtle bg-opacity-10' : ''}">
                    ${checkboxHtml}
                    <td class="ps-4 fw-semibold">
                        <a href="/decision/${d.id}" class="text-decoration-none fw-bold text-primary">DEC-${d.id}</a>
                        <div class="small text-muted text-truncate" style="max-width:200px;">${escapeHtml(d.title)}</div>
                    </td>
                    <td class="text-dark">${escapeHtml(d.category_name || 'Uncategorized')}</td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div class="avatar-sm bg-light text-primary rounded-circle d-flex align-items-center justify-content-center" style="width:24px;height:24px;font-size:10px;font-weight:bold;">${escapeHtml(d.creator_initials || 'U')}</div>
                            <span class="text-dark small fw-medium">${escapeHtml(d.creator_name || 'Unknown User')}</span>
                        </div>
                    </td>
                    <td class="text-muted small">${dateStr}</td>
                    <td><span class="badge ${statusBadge}">${escapeHtml(d.status)}</span></td>
                    <td class="text-end pe-4">
                        <a href="/decision/${d.id}" class="btn btn-sm btn-outline-primary fw-semibold px-2 me-1">View</a>
                        ${actionButtons}
                        ${canDelete ? `<button onclick="deleteDecision(${d.id})" class="btn btn-sm btn-outline-danger fw-semibold px-2" title="Delete Decision"><i class="bi bi-trash me-1"></i>Delete</button>` : ''}
                    </td>
                </tr>
            `;
        });
    }

    document.getElementById("paginationInfo").innerText = `Showing page ${currentPage} of ${totalPages} (${filtered.length} total)`;
    document.getElementById("btnPrev").disabled = currentPage === 1;
    document.getElementById("btnNext").disabled = currentPage === totalPages;

    updateSelectedCountUI();
}

function toggleSelectDecisionsMode() {
    isSelectModeActive = !isSelectModeActive;
    if (!isSelectModeActive) {
        selectedDecisionIds.clear();
    }
    updateSelectModeUI();
    renderTable();
}
window.toggleSelectDecisionsMode = toggleSelectDecisionsMode;

function cancelSelectDecisionsMode() {
    isSelectModeActive = false;
    selectedDecisionIds.clear();
    updateSelectModeUI();
    renderTable();
}
window.cancelSelectDecisionsMode = cancelSelectDecisionsMode;

function updateSelectModeUI() {
    const actionBar = document.getElementById("bulkDeleteActionBar");
    const toggleBtn = document.getElementById("selectDecisionsToDeleteBtn");
    const btnText = document.getElementById("selectDecisionsBtnText");
    const selectAllTh = document.querySelectorAll(".selection-col");
    const headerDeleteBtn = document.getElementById("deleteSelectedHeaderBtn");

    if (isSelectModeActive) {
        if (actionBar) {
            actionBar.classList.remove("d-none");
            actionBar.classList.add("d-flex");
        }
        if (toggleBtn) {
            toggleBtn.classList.remove("btn-outline-danger");
            toggleBtn.classList.add("btn-danger");
        }
        if (btnText) {
            btnText.innerText = "Exit Selection";
        }
        selectAllTh.forEach(el => el.classList.remove("d-none"));
    } else {
        if (actionBar) {
            actionBar.classList.remove("d-flex");
            actionBar.classList.add("d-none");
        }
        if (toggleBtn) {
            toggleBtn.classList.remove("btn-danger");
            toggleBtn.classList.add("btn-outline-danger");
        }
        if (btnText) {
            btnText.innerText = "Select decisions to delete";
        }
        if (headerDeleteBtn) {
            headerDeleteBtn.classList.remove("d-flex");
            headerDeleteBtn.classList.add("d-none");
        }
        selectAllTh.forEach(el => el.classList.add("d-none"));
    }
    updateSelectedCountUI();
}

function updateSelectedCountUI() {
    const countBadge = document.getElementById("selectedDecisionsCountBadge");
    const deleteBtn = document.getElementById("confirmDeleteSelectedBtn");
    const headerDeleteBtn = document.getElementById("deleteSelectedHeaderBtn");
    const headerCountBadge = document.getElementById("headerSelectedCountBadge");
    const count = selectedDecisionIds.size;

    if (countBadge) {
        countBadge.innerText = `${count} selected`;
    }
    if (deleteBtn) {
        deleteBtn.disabled = count === 0;
        deleteBtn.innerHTML = `<i class="bi bi-trash3-fill"></i> Delete Selected (${count})`;
    }

    if (headerDeleteBtn) {
        if (isSelectModeActive && count > 0) {
            headerDeleteBtn.classList.remove("d-none");
            headerDeleteBtn.classList.add("d-flex");
            if (headerCountBadge) {
                headerCountBadge.innerText = count;
            }
        } else {
            headerDeleteBtn.classList.remove("d-flex");
            headerDeleteBtn.classList.add("d-none");
        }
    }

    // Update Select All Checkbox state
    const selectAllCheckbox = document.getElementById("selectAllDecisionsCheckbox");
    if (selectAllCheckbox) {
        const rowCheckboxes = document.querySelectorAll(".decision-select-checkbox");
        if (rowCheckboxes.length === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        } else {
            const allChecked = Array.from(rowCheckboxes).every(cb => cb.checked);
            const someChecked = Array.from(rowCheckboxes).some(cb => cb.checked);
            selectAllCheckbox.checked = allChecked;
            selectAllCheckbox.indeterminate = !allChecked && someChecked;
        }
    }
}

function toggleSelectAllDecisions(isChecked) {
    const rowCheckboxes = document.querySelectorAll(".decision-select-checkbox");
    rowCheckboxes.forEach(cb => {
        const id = parseInt(cb.value, 10);
        cb.checked = isChecked;
        if (isChecked) {
            selectedDecisionIds.add(id);
        } else {
            selectedDecisionIds.delete(id);
        }
    });
    renderTable();
}
window.toggleSelectAllDecisions = toggleSelectAllDecisions;

function onDecisionCheckboxChange(id) {
    id = parseInt(id, 10);
    if (selectedDecisionIds.has(id)) {
        selectedDecisionIds.delete(id);
    } else {
        selectedDecisionIds.add(id);
    }
    renderTable();
}
window.onDecisionCheckboxChange = onDecisionCheckboxChange;

function openBulkDeleteConfirmModal() {
    if (selectedDecisionIds.size === 0) {
        if (typeof showCenterNotification === 'function') {
            showCenterNotification("Please select at least one decision to delete.", "warning", "No Decisions Selected");
        } else if (typeof showToast === 'function') {
            showToast("Warning", "Please select at least one decision to delete.");
        }
        return;
    }

    const countBadge = document.getElementById("bulkDeleteModalCountBadge");
    if (countBadge) countBadge.innerText = selectedDecisionIds.size;

    const listContainer = document.getElementById("bulkDeleteSelectedItemsList");
    if (listContainer) {
        let html = '';
        selectedDecisionIds.forEach(id => {
            const dec = allDecisions.find(d => Number(d.id) === Number(id));
            const title = dec ? dec.title : `Decision #${id}`;
            const owner = dec ? (dec.creator_name || 'Unknown Owner') : '';
            const status = dec ? dec.status : '';
            html += `
                <div class="d-flex align-items-center justify-content-between py-1.5 px-2 border-bottom bg-white rounded mb-1 text-xs">
                    <div>
                        <strong class="text-primary me-1.5">DEC-${id}</strong>
                        <span class="text-dark fw-medium">${escapeHtml(title)}</span>
                    </div>
                    <div class="d-flex align-items-center gap-1.5">
                        <span class="text-muted text-xs">${escapeHtml(owner)}</span>
                        <span class="badge bg-secondary-subtle text-secondary border text-2xs">${escapeHtml(status)}</span>
                    </div>
                </div>
            `;
        });
        listContainer.innerHTML = html;
    }

    const modal = new bootstrap.Modal(document.getElementById('bulkDeleteConfirmModal'));
    modal.show();
}
window.openBulkDeleteConfirmModal = openBulkDeleteConfirmModal;

async function executeBulkDelete() {
    const btn = document.getElementById("executeBulkDeleteBtn");
    const originalText = btn ? btn.innerHTML : "Yes, Delete Decisions";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Deleting...`;
    }

    const decisionIds = Array.from(selectedDecisionIds);
    const payload = {
        decision_ids: decisionIds,
        user_id: typeof USER_ID !== 'undefined' ? USER_ID : 1,
        role_name: typeof CURRENT_USER_ROLE !== 'undefined' ? CURRENT_USER_ROLE : 'Administrator'
    };

    try {
        let res = await fetch("/api/decisions/bulk-delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok && typeof API_URL !== 'undefined' && API_URL) {
            res = await fetch(`${API_URL}/decisions/bulk-delete`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to delete decisions.");
        }

        const data = await res.json();
        
        // Hide modal
        const modalEl = document.getElementById('bulkDeleteConfirmModal');
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) modalInstance.hide();

        // Exit select mode and clear selections
        isSelectModeActive = false;
        selectedDecisionIds.clear();
        updateSelectModeUI();

        if (typeof showCenterNotification === 'function') {
            showCenterNotification(data.message || `Successfully deleted ${decisionIds.length} decision(s).`, "success", "Decisions Deleted");
        } else if (typeof showToast === 'function') {
            showToast("Success", data.message || "Decisions deleted successfully.");
        }

        await fetchDecisions();
    } catch (err) {
        console.error("Bulk delete error:", err);
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(err.message || "Failed to delete decisions.", "error", "Bulk Delete Failed");
        } else if (typeof showToast === 'function') {
            showToast("Danger", err.message || "Failed to delete decisions.");
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}
window.executeBulkDelete = executeBulkDelete;

function updateActiveFilterChips() {
    const container = document.getElementById("activeFiltersContainer");
    const pills = document.getElementById("activeFilterPills");
    if (!container || !pills) return;

    let chipsHtml = '';
    let hasActive = false;

    if (filterState.category && filterState.category !== 'All') {
        hasActive = true;
        chipsHtml += `
            <span class="badge bg-white text-dark border d-flex align-items-center gap-1.5 py-1 px-2.5 shadow-xs" style="font-size: 11.5px; border-radius: 6px;">
                Category: <strong class="ms-1">${escapeHtml(filterState.category)}</strong>
                <button type="button" class="btn-close p-0 ms-1.5" style="font-size: 7.5px;" onclick="clearSingleFilter('category')" title="Remove Category Filter"></button>
            </span>
        `;
    }

    if (filterState.priority && filterState.priority !== 'All') {
        hasActive = true;
        chipsHtml += `
            <span class="badge bg-white text-dark border d-flex align-items-center gap-1.5 py-1 px-2.5 shadow-xs" style="font-size: 11.5px; border-radius: 6px;">
                Priority: <strong class="ms-1">${escapeHtml(filterState.priority)}</strong>
                <button type="button" class="btn-close p-0 ms-1.5" style="font-size: 7.5px;" onclick="clearSingleFilter('priority')" title="Remove Priority Filter"></button>
            </span>
        `;
    }

    if (filterState.department && filterState.department !== 'All') {
        hasActive = true;
        chipsHtml += `
            <span class="badge bg-white text-dark border d-flex align-items-center gap-1.5 py-1 px-2.5 shadow-xs" style="font-size: 11.5px; border-radius: 6px;">
                Dept: <strong class="ms-1">${escapeHtml(filterState.department)}</strong>
                <button type="button" class="btn-close p-0 ms-1.5" style="font-size: 7.5px;" onclick="clearSingleFilter('department')" title="Remove Department Filter"></button>
            </span>
        `;
    }

    if (filterState.ownership && filterState.ownership !== 'All') {
        hasActive = true;
        const ownerLabel = filterState.ownership === 'mine' ? 'Created by Me' : 'Created by Others';
        chipsHtml += `
            <span class="badge bg-white text-dark border d-flex align-items-center gap-1.5 py-1 px-2.5 shadow-xs" style="font-size: 11.5px; border-radius: 6px;">
                Owner: <strong class="ms-1">${escapeHtml(ownerLabel)}</strong>
                <button type="button" class="btn-close p-0 ms-1.5" style="font-size: 7.5px;" onclick="clearSingleFilter('ownership')" title="Remove Ownership Filter"></button>
            </span>
        `;
    }

    if (dateRangeState.type !== 'all') {
        hasActive = true;
        chipsHtml += `
            <span class="badge bg-white text-dark border d-flex align-items-center gap-1.5 py-1 px-2.5 shadow-xs" style="font-size: 11.5px; border-radius: 6px;">
                <i class="bi bi-calendar-check text-primary me-1"></i> Date: <strong class="ms-1">${escapeHtml(dateRangeState.label)}</strong>
                <button type="button" class="btn-close p-0 ms-1.5" style="font-size: 7.5px;" onclick="clearDateRange()" title="Remove Date Filter"></button>
            </span>
        `;
    }

    pills.innerHTML = chipsHtml;
    if (hasActive) {
        container.classList.remove('d-none');
        container.classList.add('d-flex');
    } else {
        container.classList.remove('d-flex');
        container.classList.add('d-none');
    }
}

function clearSingleFilter(key) {
    if (key === 'category') {
        filterState.category = 'All';
        const el = document.getElementById("filterCategory");
        if (el) el.value = 'All';
    } else if (key === 'priority') {
        filterState.priority = 'All';
        const el = document.getElementById("filterPriority");
        if (el) el.value = 'All';
    } else if (key === 'department') {
        filterState.department = 'All';
        const el = document.getElementById("filterDepartment");
        if (el) el.value = 'All';
    } else if (key === 'ownership') {
        filterState.ownership = 'All';
        const el = document.getElementById("filterOwnership");
        if (el) el.value = 'All';
    }
    applyAdvancedFilters();
}
window.clearSingleFilter = clearSingleFilter;

async function submitDraftFromTable(id) {
    if (!confirm("Are you sure you want to submit this draft decision for review?")) return;
    try {
        let response = await fetch(`/api/decisions/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "Pending" })
        });
        if (!response.ok && typeof API_URL !== 'undefined' && API_URL) {
            response = await fetch(`${API_URL}/decisions/${id}/status`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: "Pending" })
            });
        }
        if (!response.ok) throw new Error("Failed to submit decision");
        
        if (typeof showCenterNotification === 'function') {
            showCenterNotification("Decision submitted for review successfully!", 'success', 'Decision Submitted');
        } else {
            showToast("Success", "Decision submitted for review");
        }
        fetchDecisions();
    } catch (error) {
        showToast("Danger", error.message);
    }
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        renderTable();
    }
}

function nextPage() {
    currentPage++;
    renderTable();
}

function openCreateModal() {
    document.getElementById("decisionId").value = "";
    document.getElementById("decisionTitle").value = "";
    document.getElementById("decisionDescription").value = "";
    document.getElementById("modalTitle").innerText = "Create Decision";
}

function openEditModal(id) {
    const d = allDecisions.find(x => x.id === id);
    if (!d) return;

    document.getElementById("decisionId").value = d.id;
    document.getElementById("decisionTitle").value = d.title;
    document.getElementById("decisionDescription").value = d.description;
    document.getElementById("modalTitle").innerText = "Edit Decision";
    
    const modal = new bootstrap.Modal(document.getElementById("decisionModal"));
    modal.show();
}

async function saveDecision() {
    const id = document.getElementById("decisionId").value;
    const title = document.getElementById("decisionTitle").value.trim();
    const description = document.getElementById("decisionDescription").value.trim();

    if (!title || !description) {
        showToast("Warning", "Title and description are required.");
        return;
    }

    const payload = id ? { title, description } : { title, description, created_by: USER_ID };
    const method = id ? "PUT" : "POST";
    const url = id ? `/api/decisions/${id}` : `/api/decisions/`;

    try {
        let response = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!response.ok && typeof API_URL !== 'undefined' && API_URL) {
            const fallbackUrl = id ? `${API_URL}/decisions/${id}` : `${API_URL}/decisions/`;
            response = await fetch(fallbackUrl, {
                method: method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (!response.ok) throw new Error("Failed to save decision");

        bootstrap.Modal.getInstance(document.getElementById("decisionModal")).hide();
        showToast("Success", id ? "Decision updated" : "Decision created");
        fetchDecisions();
    } catch (error) {
        showToast("Danger", error.message);
    }
}

async function deleteDecision(id) {
    if (!confirm("Are you sure you want to delete this decision?\nThis action cannot be undone.")) return;

    try {
        const roleParam = typeof CURRENT_USER_ROLE !== 'undefined' ? encodeURIComponent(CURRENT_USER_ROLE) : '';
        const userParam = typeof USER_ID !== 'undefined' ? USER_ID : 1;
        let response = await fetch(`/api/decisions/${id}?user_id=${userParam}&role_name=${roleParam}`, { method: "DELETE" });
        if (!response.ok && typeof API_URL !== 'undefined' && API_URL) {
            response = await fetch(`${API_URL}/decisions/${id}?user_id=${userParam}&role_name=${roleParam}`, { method: "DELETE" });
        }
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to delete decision");
        }
        
        if (typeof showCenterNotification === 'function') {
            showCenterNotification("Decision deleted successfully.", 'success', 'Decision Deleted');
        } else {
            showToast("Success", "Decision deleted successfully");
        }
        fetchDecisions();
    } catch (error) {
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(error.message || "Failed to delete decision", 'error', 'Error Deleting Decision');
        } else {
            showToast("Danger", error.message);
        }
    }
}

async function openRejectionCommentsModal(decisionId) {
    try {
        if (!decisionId || isNaN(parseInt(decisionId))) {
            throw new Error("Invalid Decision ID provided.");
        }

        const userParam = typeof USER_ID !== 'undefined' ? USER_ID : 1;
        let res = await fetch(`/api/decisions/${decisionId}?user_id=${userParam}`);
        if (!res.ok && typeof API_URL !== 'undefined' && API_URL) {
            res = await fetch(`${API_URL}/decisions/${decisionId}?user_id=${userParam}`);
        }

        if (!res.ok) {
            let errorDetail = "Failed to fetch decision comments.";
            try {
                const errJson = await res.json();
                if (errJson && errJson.detail) errorDetail = errJson.detail;
            } catch (_) {}
            throw new Error(errorDetail);
        }

        const dec = await res.json();

        const titleHeader = document.getElementById("modalDecisionTitleHeader");
        if (titleHeader) {
            titleHeader.innerText = `Review feedback for DEC-${dec.id || decisionId}: ${dec.title || 'Untitled'}`;
        }

        const editBtn = document.getElementById("modalEditResubmitBtn");
        if (editBtn) {
            editBtn.href = `/create_decision?edit=${dec.id || decisionId}&resubmit=true`;
        }

        const container = document.getElementById("modalCommentsContainer");
        if (!container) return;

        container.innerHTML = "";

        // Safe Datatype Validator & Formatter for comments
        function safeExtractString(val) {
            if (val == null || val === undefined) return "";
            if (typeof val === "string") return val.trim();
            if (typeof val === "number" || typeof val === "boolean") return String(val).trim();
            if (Array.isArray(val)) {
                return val.map(item => safeExtractString(item)).filter(Boolean).join("\n");
            }
            if (typeof val === "object") {
                if (val.content && typeof val.content === "string") return val.content.trim();
                if (val.comments && typeof val.comments === "string") return val.comments.trim();
                if (val.text && typeof val.text === "string") return val.text.trim();
                if (val.comment && typeof val.comment === "string") return val.comment.trim();
                if (val.message && typeof val.message === "string") return val.message.trim();
                try {
                    return JSON.stringify(val);
                } catch (_) {
                    return "";
                }
            }
            return "";
        }

        const reviews = Array.isArray(dec.reviews) ? dec.reviews : [];
        let validCommentsCount = 0;
        let reviewerBlock = "";
        let managerBlock = "";

        reviews.forEach(r => {
            if (!r) return;
            const commentStr = safeExtractString(r.comments);
            if (!commentStr) return;
            validCommentsCount++;

            const rRole = typeof r.reviewer_role === "string" ? r.reviewer_role.toLowerCase() : "";
            const rName = r.reviewer_name || `Reviewer #${r.reviewer_id || ''}`;
            const timeStr = r.reviewed_at ? new Date(r.reviewed_at).toLocaleString() : 'Recently';

            if (rRole.includes("manager") || rRole.includes("mn") || rRole.includes("lead")) {
                managerBlock += `
                    <div class="p-3 rounded-3 border bg-warning-subtle border-warning-subtle text-dark">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="fw-bold text-dark small"><i class="bi bi-person-badge me-1 text-warning fs-6"></i> Manager: ${rName}</span>
                            <span class="text-muted" style="font-size: 11px;">${timeStr}</span>
                        </div>
                        <div class="small text-dark mt-1">
                            • ${commentStr}
                        </div>
                    </div>
                `;
            } else {
                reviewerBlock += `
                    <div class="p-3 rounded-3 border bg-primary-subtle border-primary-subtle text-dark">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="fw-bold text-dark small"><i class="bi bi-person-check me-1 text-primary fs-6"></i> Reviewer: ${rName}</span>
                            <span class="text-muted" style="font-size: 11px;">${timeStr}</span>
                        </div>
                        <div class="small text-dark mt-1">
                            • ${commentStr}
                        </div>
                    </div>
                `;
            }
        });

        if (validCommentsCount === 0 && dec.comments) {
            const topCommentStr = safeExtractString(dec.comments);
            if (topCommentStr) {
                validCommentsCount++;
                reviewerBlock += `
                    <div class="p-3 rounded-3 border bg-primary-subtle border-primary-subtle text-dark">
                        <div class="small text-dark mt-1">• ${topCommentStr}</div>
                    </div>
                `;
            }
        }

        if (reviewerBlock) {
            container.innerHTML += `
                <div>
                    <h6 class="fw-bold text-primary mb-2" style="font-size:13px;">Reviewer Comments</h6>
                    ${reviewerBlock}
                </div>
            `;
        }

        if (managerBlock) {
            container.innerHTML += `
                <div>
                    <h6 class="fw-bold text-warning-emphasis mb-2" style="font-size:13px;">Manager Comments</h6>
                    ${managerBlock}
                </div>
            `;
        }

        if (validCommentsCount === 0) {
            container.innerHTML = `<div class="text-muted text-center py-4 fw-medium">No comments available for this decision.</div>`;
        }

        const modalEl = document.getElementById("rejectionCommentsModal");
        if (modalEl) {
            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
            modalInstance.show();
        }
    } catch (err) {
        console.error("View Comments Error:", err);
        if (typeof showGlobalErrorNotification === "function") {
            showGlobalErrorNotification(err.message || "Failed to fetch decision comments.");
        } else {
            alert(err.message || "Failed to fetch decision comments.");
        }
    }
}
