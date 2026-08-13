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
        let userParam = (typeof USER_ID !== 'undefined' && USER_ID) ? USER_ID : '';
        let roleParam = (typeof CURRENT_USER_ROLE !== 'undefined' && CURRENT_USER_ROLE) ? CURRENT_USER_ROLE : '';
        let queryParams = [];
        if (userParam) queryParams.push(`user_id=${userParam}`);
        if (roleParam) queryParams.push(`role_name=${encodeURIComponent(roleParam)}`);
        let queryStr = queryParams.length > 0 ? `?${queryParams.join('&')}` : '';

        let response;
        try {
            response = await fetch(`/api/decisions${queryStr}`);
            if (!response.ok) {
                response = await fetch(`${API_URL}/decisions/${queryStr}`);
            }
        } catch (_) {
            response = await fetch(`${API_URL}/decisions/${queryStr}`);
        }
        if (!response || !response.ok) throw new Error("Failed to load decisions");
        const data = await response.json();
        allDecisions = Array.isArray(data) ? data : [];

        renderTable();
    } catch (error) {
        console.error("Error loading decisions:", error);
        if (typeof showToast === 'function') {
            showToast("Danger", error.message);
        }
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
    const tbody = document.getElementById("decisionsTableBody");
    const searchInput = document.getElementById("searchInput");
    const searchQuery = searchInput ? searchInput.value.toLowerCase() : "";
    
    let filtered = allDecisions.filter(d => {
        const matchesSearch = 
            (d.title && d.title.toLowerCase().includes(searchQuery)) || 
            (d.description && d.description.toLowerCase().includes(searchQuery));
        
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

async function openRejectionCommentsModal(decisionId) {
    try {
        if (!decisionId || isNaN(parseInt(decisionId))) {
            throw new Error("Invalid Decision ID provided.");
        }

        const userParam = typeof USER_ID !== 'undefined' ? USER_ID : 1;
        let res;
        try {
            res = await fetch(`${API_URL}/decisions/${decisionId}?user_id=${userParam}`);
        } catch (fetchErr) {
            throw new Error("Failed to fetch decision comments.");
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
