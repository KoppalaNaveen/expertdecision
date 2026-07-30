let allDecisions = [];
let currentStatusFilter = 'All';
let currentPage = 1;
const rowsPerPage = 5;

document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    if (tabParam) {
        currentStatusFilter = tabParam;
        const tabEl = document.getElementById(`${tabParam.toLowerCase()}-tab`);
        if (tabEl) {
            setFilter(tabParam, tabEl);
        }
    }

    fetchDecisions();

    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("input", function() {
            currentPage = 1;
            renderTable();
        });
    }
});

async function fetchDecisions() {
    try {
        const response = await fetch(`${API_URL}/decisions/`);
        if (!response.ok) throw new Error("Failed to load decisions");
        allDecisions = await response.json();
        renderTable();
    } catch (error) {
        showToast("Danger", error.message);
    }
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
        if (d.status === 'Archived') {
            counts['Archived']++;
        } else {
            counts['All']++;
            if (d.status === 'Draft') counts['Draft']++;
            else if (d.status === 'Pending') counts['Pending']++;
            else if (d.status === 'In Review' || d.status === 'Under Review') counts['In Review']++;
            else if (d.status === 'Approved') counts['Approved']++;
            else if (d.status === 'Rejected') counts['Rejected']++;
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
    const tbody = document.getElementById("decisionsTableBody");
    const searchInput = document.getElementById("searchInput");
    const searchQuery = searchInput ? searchInput.value.toLowerCase() : "";
    
    let filtered = allDecisions.filter(d => {
        const matchesSearch = 
            (d.title && d.title.toLowerCase().includes(searchQuery)) || 
            (d.description && d.description.toLowerCase().includes(searchQuery));
        
        let matchesStatus = false;
        if (currentStatusFilter === 'All') {
            matchesStatus = (d.status !== 'Archived');
        } else if (currentStatusFilter === 'In Review') {
            matchesStatus = (d.status === 'In Review' || d.status === 'Under Review');
        } else {
            matchesStatus = (d.status === currentStatusFilter);
        }
        
        return matchesSearch && matchesStatus;
    });

    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start = (currentPage - 1) * rowsPerPage;
    const paginated = filtered.slice(start, start + rowsPerPage);

    tbody.innerHTML = "";
    
    if (paginated.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">No decisions found.</td></tr>`;
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

            let draftActions = "";
            if (d.status === "Draft") {
                draftActions = `
                    <a href="/create_decision?edit=${d.id}" class="btn btn-sm btn-outline-secondary fw-semibold px-2 me-1" title="Edit Draft"><i class="bi bi-pencil me-1"></i>Edit</a>
                    <button onclick="submitDraftFromTable(${d.id})" class="btn btn-sm btn-success fw-semibold px-2 me-1" title="Submit Decision"><i class="bi bi-send me-1"></i>Submit</button>
                `;
            }

            tbody.innerHTML += `
                <tr>
                    <td class="ps-4 fw-semibold">
                        <a href="/decision/${d.id}" class="text-decoration-none fw-bold text-primary">DEC-${d.id}</a>
                        <div class="small text-muted text-truncate" style="max-width:200px;">${d.title}</div>
                    </td>
                    <td class="text-dark">${d.category_name || 'Uncategorized'}</td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div class="avatar-sm bg-light text-primary rounded-circle d-flex align-items-center justify-content-center" style="width:24px;height:24px;font-size:10px;font-weight:bold;">${d.creator_initials || 'U'}</div>
                            <span class="text-dark small fw-medium">${d.creator_name || 'Unknown User'}</span>
                        </div>
                    </td>
                    <td class="text-muted small">${dateStr}</td>
                    <td><span class="badge ${statusBadge}">${d.status}</span></td>
                    <td class="text-end pe-4">
                        <a href="/decision/${d.id}" class="btn btn-sm btn-outline-primary fw-semibold px-2 me-1">View</a>
                        ${draftActions}
                        ${canDelete ? `<button onclick="deleteDecision(${d.id})" class="btn btn-sm btn-outline-danger fw-semibold px-2" title="Delete Decision"><i class="bi bi-trash me-1"></i>Delete</button>` : ''}
                    </td>
                </tr>
            `;
        });
    }

    document.getElementById("paginationInfo").innerText = `Showing page ${currentPage} of ${totalPages} (${filtered.length} total)`;
    document.getElementById("btnPrev").disabled = currentPage === 1;
    document.getElementById("btnNext").disabled = currentPage === totalPages;
}

async function submitDraftFromTable(id) {
    if (!confirm("Are you sure you want to submit this draft decision for review?")) return;
    try {
        const response = await fetch(`${API_URL}/decisions/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "Pending" })
        });
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
    const url = id ? `${API_URL}/decisions/${id}` : `${API_URL}/decisions/`;

    try {
        const response = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

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
        const response = await fetch(`${API_URL}/decisions/${id}?user_id=${userParam}&role_name=${roleParam}`, { method: "DELETE" });
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
