let currentDecision = null;
let currentAlternatives = [];
let livePollInterval = null;

document.addEventListener("DOMContentLoaded", () => {
    fetchDecisionDetails();
    fetchAlternatives();

    if (!livePollInterval) {
        livePollInterval = setInterval(fetchDecisionDetailsSilent, 3000);
    }
});

async function fetchDecisionDetails() {
    try {
        const userIdParam = typeof USER_ID !== 'undefined' ? USER_ID : 1;
        let response = await fetch(`/api/decisions/${DECISION_ID}?user_id=${userIdParam}`);
        if (!response.ok && typeof API_URL !== 'undefined' && API_URL) {
            response = await fetch(`${API_URL}/decisions/${DECISION_ID}?user_id=${userIdParam}`);
        }
        if (!response.ok) throw new Error("Failed to load decision");
        
        currentDecision = await response.json();
        renderDecisionDetails();
        loadHistory();
    } catch (error) {
        showToast("Danger", error.message);
    }
}

async function fetchDecisionDetailsSilent() {
    try {
        const userIdParam = typeof USER_ID !== 'undefined' ? USER_ID : 1;
        let response = await fetch(`/api/decisions/${DECISION_ID}?user_id=${userIdParam}`);
        if (!response.ok && typeof API_URL !== 'undefined' && API_URL) {
            response = await fetch(`${API_URL}/decisions/${DECISION_ID}?user_id=${userIdParam}`);
        }
        if (!response.ok) return;
        const newData = await response.json();
        
        const hasChanged = JSON.stringify(newData.reviews) !== JSON.stringify(currentDecision?.reviews) || newData.status !== currentDecision?.status;
        currentDecision = newData;
        if (hasChanged) {
            renderDecisionDetails();
        }
    } catch (_) {}
}

function renderDecisionDetails() {
    document.getElementById("detailTitle").innerText = currentDecision.title;
    document.getElementById("detailDescription").innerText = currentDecision.description;
    
    // Update owner info using new fields
    const creatorName = currentDecision.creator_name || `User #${currentDecision.created_by}`;
    const creatorInitials = currentDecision.creator_initials || 'U';
    
    // Select the avatar and name elements
    const creatorContainer = document.getElementById("detailCreator").parentElement;
    if (creatorContainer) {
        const avatar = creatorContainer.querySelector('.avatar-sm');
        if (avatar) avatar.innerText = creatorInitials;
        document.getElementById("detailCreator").innerText = creatorName;
    }
    
    document.getElementById("detailDate").innerText = new Date(currentDecision.created_at).toLocaleDateString();
    
    const badge = document.getElementById("decisionStatusBadge");
    if (badge) {
        badge.innerText = currentDecision.status;
        badge.className = "badge " + getStatusBadgeClass(currentDecision.status);
    }

    const isOwner = (currentDecision.created_by === USER_ID);
    const isAdmin = typeof CURRENT_USER_ROLE !== 'undefined' && CURRENT_USER_ROLE && String(CURRENT_USER_ROLE).toLowerCase().includes('admin');
    const canDelete = isAdmin || (isOwner && currentDecision.status !== "Approved" && currentDecision.status !== "Rejected");
    const btnDelete = document.getElementById("btnDeleteDecision");
    if (btnDelete) {
        if (canDelete) {
            btnDelete.classList.remove("d-none");
        } else {
            btnDelete.classList.add("d-none");
        }
    }

    // Edit button: ONLY decision owner can edit
    const btnEdit = document.getElementById("btnEditDecision");
    if (btnEdit) {
        if (isOwner && currentDecision.status === "Draft") {
            btnEdit.classList.remove("d-none");
        } else if (isOwner) {
            btnEdit.classList.remove("d-none");
        } else {
            btnEdit.classList.add("d-none");
        }
    }

    // Submit Draft button: ONLY decision owner can submit
    const btnSubmitDraft = document.getElementById("btnSubmitDraft");
    if (btnSubmitDraft) {
        if (isOwner && currentDecision.status === "Draft") {
            btnSubmitDraft.classList.remove("d-none");
        } else {
            btnSubmitDraft.classList.add("d-none");
        }
    }

    const statusSel = document.getElementById("statusSelect");
    if (statusSel) statusSel.value = currentDecision.status;

    const updateStatusContainer = document.getElementById("updateStatusContainer");
    if (updateStatusContainer) {
        const userRole = typeof CURRENT_USER_ROLE !== 'undefined' ? CURRENT_USER_ROLE : '';
        if (['Administrator', 'Admin', 'System Administrator'].includes(userRole)) {
            updateStatusContainer.classList.remove('d-none');
        } else {
            updateStatusContainer.classList.add('d-none');
        }
    }

    // Check if current user is the FIRST pending reviewer in sequential sequence
    const pendingReviews = currentDecision.reviews ? currentDecision.reviews.filter(r => r.status === "Pending") : [];
    const firstPending = pendingReviews.length > 0 ? pendingReviews[0] : null;
    const curName = (typeof CURRENT_USER_NAME !== 'undefined' ? CURRENT_USER_NAME : '').trim().toLowerCase();
    const revName = (firstPending && firstPending.reviewer_name ? firstPending.reviewer_name : '').trim().toLowerCase();
    const isUserTurn = firstPending && (firstPending.reviewer_id === USER_ID || (revName && curName && revName === curName) || isAdmin);

    const actionCard = document.getElementById("pendingReviewActionCard");
    if (isUserTurn && actionCard) {
        actionCard.classList.remove("d-none");
    } else if (actionCard) {
        actionCard.classList.add("d-none");
    }
    
    renderApprovalChain();
}

function submitDetailReviewAction(status) {
    const title = currentDecision ? currentDecision.title : `Decision #${DECISION_ID}`;
    const creator = currentDecision ? (currentDecision.creator_name || 'Author') : 'Author';
    const category = currentDecision ? (currentDecision.category || 'General') : 'General';
    const pendingReviews = currentDecision.reviews ? currentDecision.reviews.filter(r => r.status === "Pending") : [];
    const firstPending = pendingReviews.length > 0 ? pendingReviews[0] : null;
    const reviewerIdToUse = firstPending ? firstPending.reviewer_id : USER_ID;
    openApprovalWorkflowModal(DECISION_ID, title, reviewerIdToUse, status, creator, category);
}

function renderApprovalChain() {
    const container = document.getElementById("approvalChainContainer");
    if (!container) return;
    
    container.innerHTML = "";
    
    // First step: Draft Created (always completed)
    const dateStr = new Date(currentDecision.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const creatorName = currentDecision.creator_name || `User #${currentDecision.created_by}`;
    
    let html = `
        <div class="timeline-item completed">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h6 class="fw-bold mb-0 text-sm">Draft Created</h6>
                    <p class="text-muted mb-0" style="font-size: 12px;">${creatorName}</p>
                </div>
                <small class="text-muted" style="font-size: 11px;">${dateStr}</small>
            </div>
        </div>
    `;
    
    // Find index of first pending review in sequential flow
    const firstPendingIdx = currentDecision.reviews ? currentDecision.reviews.findIndex(r => r.status === "Pending") : -1;

    // Add reviews
    if (currentDecision.reviews && currentDecision.reviews.length > 0) {
        currentDecision.reviews.forEach((review, idx) => {
            let itemClass = "timeline-item";
            let titleClass = "fw-semibold text-secondary";
            let timeLabel = "";

            const revName = review.reviewer_name || `User #${review.reviewer_id}`;
            const empIdStr = review.employee_id ? ` (${review.employee_id})` : '';
            const roleStr = idx === 0 ? 'Reviewer' : 'Manager';
            const reviewerDisplay = `${escapeHtml(revName)}${empIdStr}`;
            
            let statusText = `Pending: ${reviewerDisplay}`;
            
            if (review.status === "Approved") {
                itemClass = "timeline-item completed";
                titleClass = "fw-bold text-success";
                statusText = `<span class="fw-bold text-dark">${reviewerDisplay}</span> <span class="badge bg-success-subtle text-success border border-success-subtle ms-1"><i class="bi bi-check-circle-fill me-1"></i>Approved / Accepted</span>`;
                if (review.comments) {
                    statusText += `<div class="text-muted small mt-1">"${escapeHtml(review.comments)}"</div>`;
                }
                timeLabel = review.reviewed_at ? new Date(review.reviewed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Approved';
            } else if (review.status === "Rejected") {
                itemClass = "timeline-item completed";
                titleClass = "fw-bold text-danger";
                statusText = `<span class="fw-bold text-dark">${reviewerDisplay}</span> <span class="badge bg-danger-subtle text-danger border border-danger-subtle ms-1"><i class="bi bi-x-circle-fill me-1"></i>Rejected</span>`;
                if (review.comments) {
                    statusText += `<div class="text-danger small mt-1">Reason: "${escapeHtml(review.comments)}"</div>`;
                }
                timeLabel = review.reviewed_at ? new Date(review.reviewed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Rejected';
            } else if (review.status === "Pending") {
                if (idx === firstPendingIdx) {
                    itemClass = "timeline-item active";
                    titleClass = "fw-bold text-primary";
                    statusText = `Pending: <span class="fw-bold text-dark">${reviewerDisplay}</span>`;
                    timeLabel = `<span class="badge bg-primary bg-opacity-10 text-primary fw-bold" style="font-size: 11px;">Current</span>`;
                } else {
                    itemClass = "timeline-item";
                    titleClass = "fw-medium text-secondary";
                    statusText = `Queued (Awaiting Step 1): <span class="fw-medium text-dark">${reviewerDisplay}</span>`;
                    timeLabel = `<span class="badge bg-light text-muted border" style="font-size: 10px;">Queued</span>`;
                }
            }
            
            let approvalTypeLabel = `Review Step ${idx + 1} (${roleStr})`;
            
            html += `
                <div class="${itemClass}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="${titleClass} mb-1 text-sm">${approvalTypeLabel}</h6>
                            <p class="text-muted mb-0" style="font-size: 12px;">${statusText}</p>
                        </div>
                        <small class="text-muted" style="font-size: 11px;">${timeLabel}</small>
                    </div>
                </div>
            `;
        });
    } else {
        html += `
            <div class="timeline-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="fw-semibold text-secondary mb-0 text-sm">No Reviewers Assigned</h6>
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function getStatusBadgeClass(status) {
    if (status === "Approved") return "bg-success text-white";
    if (status === "Rejected") return "bg-danger text-white";
    if (status === "Under Review" || status === "Pending") return "bg-warning text-dark";
    if (status === "Draft") return "bg-secondary text-white";
    if (status === "Archived") return "bg-dark text-white";
    return "bg-secondary text-white";
}

async function archiveCurrentDecision() {
    if (!confirm("Are you sure you want to move this decision to Archive?")) return;
    try {
        const res = await fetch(`${API_URL}/decisions/${DECISION_ID}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "Archived" })
        });
        if (!res.ok) throw new Error("Failed to archive decision");
        showToast("Success", "Decision status updated to Archived.");
        fetchDecisionDetails();
    } catch (e) {
        showToast("Danger", e.message || "Error archiving decision");
    }
}
window.archiveCurrentDecision = archiveCurrentDecision;

async function submitDraftForReview() {
    if (!confirm("Submit this draft decision for review?")) return;
    try {
        const res = await fetch(`${API_URL}/decisions/${DECISION_ID}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "Pending" })
        });
        if (!res.ok) throw new Error("Failed to submit draft decision for review");
        showToast("Success", "Draft decision submitted for review!");
        fetchDecisionDetails();
    } catch (e) {
        showToast("Danger", e.message || "Error submitting draft decision");
    }
}
window.submitDraftForReview = submitDraftForReview;

async function updateStatus() {
    const newStatus = document.getElementById("statusSelect").value;
    try {
        const response = await fetch(`${API_URL}/decisions/${DECISION_ID}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus })
        });
        if (!response.ok) throw new Error("Failed to update status");
        
        showToast("Success", "Status updated successfully");
        fetchDecisionDetails();
    } catch (error) {
        showToast("Danger", error.message);
    }
}

// ================= ALTERNATIVES =================

async function fetchAlternatives() {
    try {
        const response = await fetch(`${API_URL}/alternatives/decision/${DECISION_ID}`);
        if (!response.ok) throw new Error("Failed to load alternatives");
        
        currentAlternatives = await response.json();
        renderAlternativesTable();
    } catch (error) {
        showToast("Danger", error.message);
    }
}

function renderAlternativesTable() {
    const listContainer = document.getElementById("alternativesEvaluatorList");
    const tbody = document.getElementById("alternativesTableBody");

    if (listContainer) {
        listContainer.innerHTML = "";
        if (!currentAlternatives || currentAlternatives.length === 0) {
            listContainer.innerHTML = `<div class="text-center py-4 text-muted">No alternatives added yet.</div>`;
        } else {
            currentAlternatives.forEach((alt, idx) => {
                let riskBadge = "bg-secondary-subtle text-secondary";
                if (alt.risk_level === "Low") riskBadge = "bg-success-subtle text-success border border-success-subtle";
                if (alt.risk_level === "Medium") riskBadge = "bg-warning-subtle text-warning-emphasis border border-warning-subtle";
                if (alt.risk_level === "High") riskBadge = "bg-danger-subtle text-danger border border-danger-subtle";

                const score = (alt.feasibility_score !== null && alt.feasibility_score !== undefined) ? Number(alt.feasibility_score) : 5;
                const scorePercent = Math.min(Math.max(score * 10, 0), 100);
                let scoreColor = "bg-primary";
                if (score >= 8) scoreColor = "bg-success";
                else if (score < 5) scoreColor = "bg-warning";

                const costDisplay = (alt.cost !== null && alt.cost !== undefined) ? `$${Number(alt.cost).toLocaleString()}` : '$0.00';

                listContainer.innerHTML += `
                    <div class="border rounded-3 p-3 mb-3 bg-light bg-opacity-50">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div class="d-flex align-items-center gap-2">
                                <span class="badge bg-primary bg-opacity-10 text-primary rounded-circle p-2" style="width: 28px; height: 28px; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold;">
                                    ${idx + 1}
                                </span>
                                <h6 class="fw-bold text-dark mb-0">${alt.title}</h6>
                            </div>
                            <div class="d-flex align-items-center gap-1">
                                <button class="btn btn-sm btn-outline-primary border-0" onclick="openAlternativeModal(${alt.id})" title="Edit Option"><i class="bi bi-pencil"></i></button>
                                <button class="btn btn-sm btn-outline-danger border-0" onclick="deleteAlternative(${alt.id})" title="Delete Option"><i class="bi bi-trash"></i></button>
                            </div>
                        </div>
                        <p class="text-muted text-sm mb-3">${alt.description || 'No description provided.'}</p>
                        
                        <div class="row g-3 text-xs align-items-center">
                            <div class="col-md-4">
                                <span class="text-muted d-block mb-1">Estimated Cost</span>
                                <span class="fw-bold text-dark fs-6">${costDisplay}</span>
                            </div>
                            <div class="col-md-4">
                                <span class="text-muted d-block mb-1">Risk Level</span>
                                <span class="badge ${riskBadge} rounded-pill">${alt.risk_level || 'Medium'}</span>
                            </div>
                            <div class="col-md-4">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="text-muted">Feasibility</span>
                                    <span class="fw-bold text-dark">${score} / 10</span>
                                </div>
                                <div class="alt-progress-bar">
                                    <div class="alt-progress-fill ${scoreColor}" style="width: ${scorePercent}%;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
    }

    if (tbody) {
        tbody.innerHTML = "";
        if (!currentAlternatives || currentAlternatives.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-muted">No alternatives added yet.</td></tr>`;
            return;
        }

        currentAlternatives.forEach(alt => {
            let riskBadge = "bg-secondary";
            if (alt.risk_level === "Low") riskBadge = "bg-success";
            if (alt.risk_level === "Medium") riskBadge = "bg-warning text-dark";
            if (alt.risk_level === "High") riskBadge = "bg-danger";

            tbody.innerHTML += `
                <tr>
                    <td class="ps-4">
                        <div class="fw-bold text-primary">${alt.title}</div>
                        <div class="small text-muted text-truncate" style="max-width:200px;">${alt.description || 'N/A'}</div>
                    </td>
                    <td>$${alt.cost || '0.00'}</td>
                    <td><span class="badge ${riskBadge}">${alt.risk_level || 'N/A'}</span></td>
                    <td><span class="badge bg-info text-dark">${alt.feasibility_score || '-'} / 10</span></td>
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-outline-primary me-1" onclick="openAlternativeModal(${alt.id})"><i class="bi bi-pencil"></i></button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteAlternative(${alt.id})"><i class="bi bi-trash"></i></button>
                    </td>
                </tr>
            `;
        });
    }
}

function openAlternativeModal(id = null) {
    if (id) {
        const alt = currentAlternatives.find(x => x.id === id);
        if (!alt) return;
        document.getElementById("altModalTitle").innerText = "Edit Alternative";
        document.getElementById("altId").value = alt.id;
        document.getElementById("altTitle").value = alt.title;
        document.getElementById("altDescription").value = alt.description || "";
        document.getElementById("altPros").value = alt.pros || "";
        document.getElementById("altCons").value = alt.cons || "";
        document.getElementById("altCost").value = alt.cost || "";
        document.getElementById("altRisk").value = alt.risk_level || "Medium";
        document.getElementById("altFeasibility").value = alt.feasibility_score || "";
    } else {
        document.getElementById("altModalTitle").innerText = "Add Alternative";
        document.getElementById("altId").value = "";
        document.getElementById("altTitle").value = "";
        document.getElementById("altDescription").value = "";
        document.getElementById("altPros").value = "";
        document.getElementById("altCons").value = "";
        document.getElementById("altCost").value = "";
        document.getElementById("altRisk").value = "Medium";
        document.getElementById("altFeasibility").value = "";
    }
    
    new bootstrap.Modal(document.getElementById("alternativeModal")).show();
}

async function saveAlternative() {
    const id = document.getElementById("altId").value;
    const payload = {
        title: document.getElementById("altTitle").value.trim(),
        description: document.getElementById("altDescription").value.trim(),
        pros: document.getElementById("altPros").value.trim(),
        cons: document.getElementById("altCons").value.trim(),
        cost: parseFloat(document.getElementById("altCost").value) || null,
        risk_level: document.getElementById("altRisk").value,
        feasibility_score: parseInt(document.getElementById("altFeasibility").value) || null,
    };

    if (!payload.title) {
        showToast("Warning", "Title is required");
        return;
    }

    try {
        let response;
        if (id) {
            response = await fetch(`${API_URL}/alternatives/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            payload.decision_id = DECISION_ID;
            response = await fetch(`${API_URL}/alternatives/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (!response.ok) throw new Error("Failed to save alternative");

        bootstrap.Modal.getInstance(document.getElementById("alternativeModal")).hide();
        showToast("Success", id ? "Alternative updated" : "Alternative added");
        fetchAlternatives();
    } catch (error) {
        showToast("Danger", error.message);
    }
}

async function deleteAlternative(id) {
    if (!confirm("Delete this alternative?")) return;

    try {
        const response = await fetch(`${API_URL}/alternatives/${id}`, { method: "DELETE" });
        if (!response.ok) throw new Error("Failed to delete alternative");
        
        showToast("Success", "Alternative deleted");
        fetchAlternatives();
    } catch (error) {
        showToast("Danger", error.message);
    }
}

// ==========================================
// TAB NAVIGATION LOGIC (Workflow 3 and 3b)
// ==========================================

let activeTab = 'overview';
let activeThreadId = null;

function switchTab(tabName) {
    activeTab = tabName;
    
    // Reset tabs UI
    const tabNames = ['overview', 'rationale', 'discussions', 'meeting_notes', 'documents', 'history'];
    tabNames.forEach(t => {
        const link = document.getElementById(`tab-link-${t}`);
        const pane = document.getElementById(`tab-pane-${t}`);
        if (link) {
            link.classList.remove('active', 'fw-bold');
            link.classList.add('text-secondary', 'fw-semibold');
        }
        if (pane) {
            pane.classList.add('d-none');
        }
    });

    // Set active tab UI
    const activeLink = document.getElementById(`tab-link-${tabName}`);
    const activePane = document.getElementById(`tab-pane-${tabName}`);
    if (activeLink) {
        activeLink.classList.add('active', 'fw-bold');
        activeLink.classList.remove('text-secondary', 'fw-semibold');
    }
    if (activePane) {
        activePane.classList.remove('d-none');
    }

    // Trigger tab-specific loaders
    if (tabName === 'rationale') {
        renderRationale();
    } else if (tabName === 'discussions') {
        loadThreads();
    } else if (tabName === 'meeting_notes') {
        loadMeetingNotes();
    } else if (tabName === 'documents') {
        loadDocuments();
    } else if (tabName === 'history') {
        loadHistory();
    }
}

// Check URL query parameters for default tab
window.addEventListener('load', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    const threadParam = urlParams.get('thread');
    
    if (tabParam) {
        switchTab(tabParam);
        if (tabParam === 'discussions' && threadParam) {
            activeThreadId = parseInt(threadParam);
            setTimeout(() => selectThread(activeThreadId), 500);
        }
    } else {
        switchTab('overview');
    }
    // Preload discussion threads so they are available immediately
    loadThreads();
});

// ==========================================
// RATIONALE LOGIC
// ==========================================

function renderRationale() {
    // Populate Pros/Cons
    const prosConsList = document.getElementById('rationaleProsCons');
    const riskTable = document.getElementById('rationaleRiskTable');
    
    if (prosConsList) {
        prosConsList.innerHTML = '';
        if (currentAlternatives.length === 0) {
            prosConsList.innerHTML = '<div class="col-12 text-muted text-center">No alternatives available to draw Pros & Cons.</div>';
        } else {
            currentAlternatives.forEach(alt => {
                const pros = alt.pros ? alt.pros.split('\n').map(p => `<li>${p}</li>`).join('') : '<li>No pros documented</li>';
                const cons = alt.cons ? alt.cons.split('\n').map(c => `<li>${c}</li>`).join('') : '<li>No cons documented</li>';
                
                prosConsList.innerHTML += `
                    <div class="col-md-6">
                        <div class="border rounded p-3 h-100 bg-light">
                            <h6 class="fw-bold mb-2 text-dark">${alt.title}</h6>
                            <div class="row">
                                <div class="col-6">
                                    <small class="text-success fw-bold d-block mb-1">PROS</small>
                                    <ul class="ps-3 text-muted text-xs mb-0">${pros}</ul>
                                </div>
                                <div class="col-6">
                                    <small class="text-danger fw-bold d-block mb-1">CONS</small>
                                    <ul class="ps-3 text-muted text-xs mb-0">${cons}</ul>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
    }

    if (riskTable) {
        riskTable.innerHTML = '';
        if (currentAlternatives.length === 0) {
            riskTable.innerHTML = '<tr><td colspan="3" class="text-center text-muted">No options analyzed.</td></tr>';
        } else {
            currentAlternatives.forEach(alt => {
                let mitigation = 'Standard rollout and verification';
                if (alt.risk_level === 'High') {
                    mitigation = 'Parallel deployment with full rollback capabilities; automated integration checks.';
                } else if (alt.risk_level === 'Medium') {
                    mitigation = 'Phased migration rollout, training resources allocation.';
                }
                
                let badgeClass = alt.risk_level === 'High' ? 'danger' : (alt.risk_level === 'Medium' ? 'warning' : 'success');

                riskTable.innerHTML += `
                    <tr>
                        <td class="fw-semibold text-dark">${alt.title} - Implementation Risk</td>
                        <td><span class="badge bg-${badgeClass}-subtle text-${badgeClass} border border-${badgeClass}-subtle">${alt.risk_level || 'Low'}</span></td>
                        <td class="text-muted">${mitigation}</td>
                    </tr>
                `;
            });
        }
    }
}

// ==========================================
// DISCUSSIONS & COMMENTS LOGIC
// ==========================================

let threadsCache = [];

async function loadThreads() {
    try {
        const res = await fetch(`${API_URL}/decisions/${DECISION_ID}/threads`);
        if (!res.ok) throw new Error("Failed to load threads");
        threadsCache = await res.json();
        renderThreadsList();
    } catch (err) {
        showToast("Danger", err.message);
    }
}

function renderThreadsList() {
    const container = document.getElementById('threadsListContainer');
    const query = document.getElementById('threadSearch').value.toLowerCase();
    
    if (!container) return;
    container.innerHTML = '';
    
    const filtered = threadsCache.filter(t => t.topic.toLowerCase().includes(query));
    
    if (filtered.length === 0) {
        container.innerHTML = '<div class="text-center text-muted py-4 small">No discussion threads found.</div>';
        return;
    }
    
    filtered.forEach(t => {
        const isActive = activeThreadId === t.id;
        const badgeClass = t.status === 'Open' ? 'bg-primary-subtle text-primary border-primary-subtle' : 'bg-success-subtle text-success border-success-subtle';
        const escapedTopic = String(t.topic || '').replace(/'/g, "\\'").replace(/"/g, "&quot;");

        container.innerHTML += `
            <div class="border rounded p-3 hover-shadow transition position-relative" style="cursor: pointer; background: ${isActive ? '#f8fafc' : '#fff'}; border-color: ${isActive ? '#3b82f6 !important' : '#e2e8f0'};" onclick="selectThread(${t.id})">
                <div class="d-flex justify-content-between align-items-start mb-1 gap-2">
                    <span class="fw-bold text-sm text-dark flex-grow-1 text-truncate">${t.topic}</span>
                    <div class="d-flex align-items-center gap-1.5 flex-shrink-0">
                        <span class="badge ${badgeClass} border rounded-pill" style="font-size: 9px;">${t.status}</span>
                        <button class="btn btn-sm text-muted p-0 text-hover-danger ms-1" style="line-height:1;" onclick="event.stopPropagation(); deleteDiscussionThread(${t.id}, '${escapedTopic}')" title="Delete Thread">
                            <i class="bi bi-trash text-secondary"></i>
                        </button>
                    </div>
                </div>
                <div class="d-flex justify-content-between text-muted mt-2" style="font-size: 10px;">
                    <span>${t.comments ? t.comments.length : 0} comments</span>
                    <span>${new Date(t.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        `;
    });

    document.getElementById('threadSearch').addEventListener('input', renderThreadsList);
}

function openNewThreadModal() {
    document.getElementById('newThreadTopicInput').value = '';
    const modalEl = document.getElementById('newThreadModal');
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();
}

async function submitNewThread() {
    const topicInput = document.getElementById('newThreadTopicInput');
    const topic = topicInput ? topicInput.value.trim() : '';
    if (!topic) {
        showToast("Warning", "Topic is required");
        return;
    }

    try {
        const res = await fetch(`${API_URL}/decisions/${DECISION_ID}/threads`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                topic: topic,
                created_by: USER_ID
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to start thread");
        }
        
        const data = await res.json();
        const modalEl = document.getElementById('newThreadModal');
        if (modalEl) {
            const instance = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
            instance.hide();
        }
        if (topicInput) topicInput.value = '';
        showToast("Success", "Discussion thread started");
        
        activeThreadId = data.id;
        loadThreads().then(() => selectThread(data.id));
    } catch (err) {
        showToast("Danger", err.message);
    }
}

let cachedUsersForMentions = [];

async function fetchUsersForMentions() {
    if (cachedUsersForMentions.length > 0) return cachedUsersForMentions;
    try {
        const res = await fetch(`${API_URL}/users/`);
        if (res.ok) {
            cachedUsersForMentions = await res.json();
        }
    } catch (_) {}
    return cachedUsersForMentions;
}

function formatMentionsInContent(content, usersList = []) {
    if (!content) return "";

    let safeContent = String(content)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Replace @Name (EMP123) or @[Name](EMP123) or @EMP123
    safeContent = safeContent.replace(/@([^\(\n\r<]+?)\s*\(([^)]+)\)/g, (match, name, empId) => {
        return `<span class="mention-pill"><i class="bi bi-at"></i> ${name.trim()} <span class="mention-empid">${empId.trim()}</span></span>`;
    });

    safeContent = safeContent.replace(/@\[([^\]]+)\]\(([^\)]+)\)/g, (match, name, empId) => {
        return `<span class="mention-pill"><i class="bi bi-at"></i> ${name.trim()} <span class="mention-empid">${empId.trim()}</span></span>`;
    });

    usersList.forEach(u => {
        if (u.employee_id) {
            const empRegex = new RegExp(`@${u.employee_id}\\b`, 'gi');
            safeContent = safeContent.replace(empRegex, `<span class="mention-pill"><i class="bi bi-at"></i> ${u.full_name} <span class="mention-empid">${u.employee_id}</span></span>`);
        }
    });

    return safeContent;
}

let mentionAutocompleteInitialized = false;
function setupMentionAutocomplete() {
    const textarea = document.getElementById("newCommentContent");
    const dropdown = document.getElementById("mentionDropdown");
    if (!textarea || !dropdown || mentionAutocompleteInitialized) return;
    
    mentionAutocompleteInitialized = true;

    let selectedIndex = 0;
    let matchStart = -1;

    fetchUsersForMentions();

    textarea.addEventListener("input", handleInput);
    textarea.addEventListener("keydown", handleKeydown);

    async function handleInput() {
        const text = textarea.value;
        const cursorPos = textarea.selectionStart;
        const textBeforeCursor = text.substring(0, cursorPos);
        const atIndex = textBeforeCursor.lastIndexOf("@");

        if (atIndex !== -1) {
            const query = textBeforeCursor.substring(atIndex + 1);
            const charBeforeAt = atIndex > 0 ? textBeforeCursor[atIndex - 1] : " ";
            if (/[\s\n]/.test(charBeforeAt) || atIndex === 0) {
                if (!/\s\s/.test(query) && query.length <= 30) {
                    matchStart = atIndex;
                    await renderMentionDropdown(query.toLowerCase());
                    return;
                }
            }
        }
        hideMentionDropdown();
    }

    async function renderMentionDropdown(query) {
        const users = await fetchUsersForMentions();
        const filtered = users.filter(u => {
            // Exclude current user's own account from mention suggestions
            if (u.id === USER_ID) return false;
            const nameMatch = (u.full_name || "").toLowerCase().includes(query);
            const empMatch = (u.employee_id || "").toLowerCase().includes(query);
            return nameMatch || empMatch;
        });

        if (filtered.length === 0) {
            hideMentionDropdown();
            return;
        }

        selectedIndex = 0;
        dropdown.innerHTML = filtered.map((u, idx) => {
            const initials = (u.full_name || 'U').split(' ').map(n=>n[0]).join('').substring(0,2).toUpperCase();
            return `
                <div class="mention-dropdown-item ${idx === 0 ? 'active' : ''}" data-idx="${idx}" data-fullname="${u.full_name}" data-empid="${u.employee_id || ''}">
                    <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold text-xs" style="width: 28px; height: 28px; flex-shrink: 0;">
                        ${initials}
                    </div>
                    <div class="flex-grow-1 min-w-0">
                        <div class="fw-bold text-dark text-xs d-flex align-items-center justify-content-between">
                            <span>${u.full_name}</span>
                            ${u.employee_id ? `<span class="employee-id-badge">${u.employee_id}</span>` : ''}
                        </div>
                        <div class="text-muted" style="font-size: 10.5px;">${u.role_name || 'Team Member'}</div>
                    </div>
                </div>
            `;
        }).join("");

        dropdown.style.display = "block";

        dropdown.querySelectorAll(".mention-dropdown-item").forEach(item => {
            item.addEventListener("click", () => {
                selectMentionUser(item.getAttribute("data-fullname"), item.getAttribute("data-empid"));
            });
        });
    }

    function selectMentionUser(fullName, empId) {
        const text = textarea.value;
        const beforeAt = text.substring(0, matchStart);
        const cursorPos = textarea.selectionStart;
        const afterCursor = text.substring(cursorPos);

        const mentionText = empId ? `@${fullName} (${empId}) ` : `@${fullName} `;
        textarea.value = beforeAt + mentionText + afterCursor;
        textarea.focus();
        const newCursorPos = matchStart + mentionText.length;
        textarea.setSelectionRange(newCursorPos, newCursorPos);
        hideMentionDropdown();
    }

    function hideMentionDropdown() {
        dropdown.style.display = "none";
    }

    function handleKeydown(e) {
        if (dropdown.style.display === "block") {
            const items = dropdown.querySelectorAll(".mention-dropdown-item");
            if (items.length === 0) return;

            if (e.key === "ArrowDown") {
                e.preventDefault();
                selectedIndex = (selectedIndex + 1) % items.length;
                updateActiveItem(items);
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                selectedIndex = (selectedIndex - 1 + items.length) % items.length;
                updateActiveItem(items);
            } else if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                const activeItem = items[selectedIndex];
                if (activeItem) {
                    selectMentionUser(activeItem.getAttribute("data-fullname"), activeItem.getAttribute("data-empid"));
                }
            } else if (e.key === "Escape") {
                hideMentionDropdown();
            }
        } else if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submitComment();
        }
    }

    function updateActiveItem(items) {
        items.forEach((item, idx) => {
            if (idx === selectedIndex) {
                item.classList.add("active");
                item.scrollIntoView({ block: "nearest" });
            } else {
                item.classList.remove("active");
            }
        });
    }
}

async function selectThread(threadId) {
    activeThreadId = threadId;
    renderThreadsList();

    const thread = threadsCache.find(t => t.id === threadId);
    if (!thread) return;

    document.getElementById('currentThreadTopic').innerText = thread.topic;
    
    const statusBadge = document.getElementById('currentThreadStatus');
    if (statusBadge) {
        statusBadge.innerText = thread.status;
        statusBadge.style.display = 'inline-block';
        statusBadge.className = `badge ${thread.status === 'Open' ? 'bg-primary-subtle text-primary border border-primary-subtle' : 'bg-success-subtle text-success border border-success-subtle'} rounded-pill text-xs`;
    }

    const subtext = document.getElementById('currentThreadSubtext');
    if (subtext) {
        const count = thread.comments ? thread.comments.length : 0;
        subtext.innerText = `${count} message${count === 1 ? '' : 's'} in discussion`;
    }

    const feed = document.getElementById('commentsFeedContainer');
    feed.innerHTML = '';

    const users = await fetchUsersForMentions();
    const userMap = {};
    users.forEach(u => { userMap[u.id] = u; });

    if (!thread.comments || thread.comments.length === 0) {
        feed.innerHTML = `
            <div class="text-center text-muted py-5 my-auto">
                <div class="rounded-circle bg-white border d-inline-flex align-items-center justify-content-center p-3 mb-3 shadow-sm">
                    <i class="bi bi-chat-dots text-primary fs-2"></i>
                </div>
                <h6 class="fw-bold text-dark">No Messages Yet</h6>
                <p class="small text-muted mb-0">Start the conversation by sending a message below.</p>
            </div>
        `;
    } else {
        thread.comments.forEach(c => {
            const isOwn = c.user_id === USER_ID;
            const author = userMap[c.user_id] || { full_name: "Team Member", employee_id: "" };
            const initials = (author.full_name || "TM").split(' ').map(n => n[0]).join('').substring(0,2).toUpperCase();
            
            const timeStr = c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
            const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : '';
            const fullTime = `${dateStr} at ${timeStr}`;

            const isDeleted = c.is_deleted || c.content === "This message was deleted.";
            let formattedContent = isDeleted ? '<span class="fst-italic text-muted opacity-75">This message was deleted.</span>' : formatMentionsInContent(c.content, users);
            if (c.is_edited && !isDeleted) {
                formattedContent += ' <small class="text-muted opacity-75" style="font-size: 10px;">(edited)</small>';
            }

            const safeContent = (c.content || '').replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\${/g, '\\${');
            const editDeleteButtons = (isOwn && !isDeleted) ? `
                <div class="d-inline-flex gap-2 ms-2 opacity-75">
                    <button type="button" class="btn btn-link p-0 text-primary text-xs text-decoration-none" onclick="editChatMessage(${c.id}, \`${safeContent}\`, false)" title="Edit Message">
                        <i class="bi bi-pencil-fill" style="font-size: 11px;"></i> Edit
                    </button>
                    <button type="button" class="btn btn-link p-0 text-danger text-xs text-decoration-none" onclick="deleteChatMessage(${c.id}, false)" title="Delete Message">
                        <i class="bi bi-trash-fill" style="font-size: 11px;"></i> Delete
                    </button>
                </div>
            ` : '';

            feed.innerHTML += `
                <div class="chat-msg-row ${isOwn ? 'own-msg' : 'other-msg'}">
                    <div class="chat-avatar ${isOwn ? 'bg-primary text-white' : 'bg-white text-primary border'}">
                        ${initials}
                    </div>
                    <div class="chat-bubble-wrap">
                        <div class="chat-msg-header d-flex align-items-center">
                            <span class="chat-msg-author">${isOwn ? 'You' : author.full_name}</span>
                            ${(!isOwn && author.employee_id) ? `<span class="chat-msg-empid">${author.employee_id}</span>` : ''}
                            <span class="chat-msg-time me-auto">${fullTime}</span>
                            ${editDeleteButtons}
                        </div>
                        <div class="chat-bubble">
                            ${formattedContent}
                        </div>
                    </div>
                </div>
            `;
        });
    }

    const deleteBtn = document.getElementById('btnDeleteActiveThread');
    if (deleteBtn) {
        deleteBtn.classList.remove('d-none');
        deleteBtn.classList.add('d-flex');
    }

    const formBox = document.getElementById('addCommentFormBox');
    if (formBox) {
        formBox.style.display = 'block';
    }
    
    setupMentionAutocomplete();
    
    // Auto-scroll chat feed to latest message
    setTimeout(() => {
        feed.scrollTop = feed.scrollHeight;
    }, 50);
}

async function submitComment() {
    const contentInput = document.getElementById('newCommentContent');
    if (!contentInput) return;
    const content = contentInput.value.trim();
    if (!content) {
        showToast("Warning", "Message cannot be empty");
        return;
    }

    try {
        const res = await fetch(`${API_URL}/decisions/threads/${activeThreadId}/comments`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                content: content,
                user_id: USER_ID
            })
        });

        if (!res.ok) throw new Error("Failed to post message");
        
        contentInput.value = '';
        showToast("Success", "Message sent");
        loadThreads().then(() => selectThread(activeThreadId));
    } catch (err) {
        showToast("Danger", err.message);
    }
}

async function deleteDiscussionThread(threadId, topicTitle) {
    if (!confirm(`Are you sure you want to delete thread "${topicTitle}"?`)) return;

    try {
        const res = await fetch(`${API_URL}/decisions/threads/${threadId}?user_id=${USER_ID}`, {
            method: "DELETE"
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to delete thread");
        }

        showToast("Danger", "Thread deleted");

        if (activeThreadId === threadId) {
            activeThreadId = null;
            document.getElementById('currentThreadTopic').innerText = "Select a Thread";
            const statusBadge = document.getElementById('currentThreadStatus');
            if (statusBadge) statusBadge.style.display = 'none';
            const deleteBtn = document.getElementById('btnDeleteActiveThread');
            if (deleteBtn) {
                deleteBtn.classList.remove('d-flex');
                deleteBtn.classList.add('d-none');
            }
            const feed = document.getElementById('commentsFeedContainer');
            if (feed) {
                feed.innerHTML = `
                    <div class="text-center text-muted py-5 my-auto">
                        <div class="rounded-circle bg-white border d-inline-flex align-items-center justify-content-center p-3 mb-3 shadow-sm">
                            <i class="bi bi-chat-dots text-primary fs-2"></i>
                        </div>
                        <h6 class="fw-bold text-dark">No Thread Selected</h6>
                        <p class="small text-muted mb-0">Select a thread from the panel on the left to view conversation messages.</p>
                    </div>
                `;
            }
            const formBox = document.getElementById('addCommentFormBox');
            if (formBox) formBox.style.display = 'none';
        }

        loadThreads();
    } catch (err) {
        showToast("Danger", err.message);
    }
}

function deleteActiveThread() {
    if (!activeThreadId) return;
    const thread = threadsCache.find(t => t.id === activeThreadId);
    const title = thread ? thread.topic : "this thread";
    deleteDiscussionThread(activeThreadId, title);
}

// ==========================================
// MEETING NOTES LOGIC
// ==========================================

let meetingNotesCache = [];

async function loadMeetingNotes() {
    try {
        const res = await fetch(`${API_URL}/decisions/${DECISION_ID}/meeting_notes`);
        if (!res.ok) throw new Error("Failed to load meeting notes");
        meetingNotesCache = await res.json();
        renderMeetingNotesList();
    } catch (err) {
        showToast("Danger", err.message);
    }
}

function getMeetingStatusInfo(note) {
    if (!note) {
        return { label: "Not Scheduled", badgeClass: "bg-secondary-subtle text-secondary border border-secondary-subtle" };
    }

    const rawStatus = (note.status || "").trim().toLowerCase();

    if (rawStatus === "cancelled" || rawStatus === "canceled") {
        return { label: "Cancelled", badgeClass: "bg-danger-subtle text-danger border border-danger-subtle" };
    }
    if (rawStatus === "scheduled") {
        return { label: "Scheduled", badgeClass: "bg-primary-subtle text-primary border border-primary-subtle" };
    }
    if (rawStatus === "in progress" || rawStatus === "inprogress" || rawStatus === "active") {
        return { label: "In Progress", badgeClass: "bg-warning-subtle text-warning-emphasis border border-warning-subtle" };
    }
    if (rawStatus === "completed" || rawStatus === "finished") {
        return { label: "Completed", badgeClass: "bg-success-subtle text-success border border-success-subtle" };
    }
    if (rawStatus === "not scheduled") {
        return { label: "Not Scheduled", badgeClass: "bg-secondary-subtle text-secondary border border-secondary-subtle" };
    }

    if (!note.meeting_date) {
        return { label: "Not Scheduled", badgeClass: "bg-secondary-subtle text-secondary border border-secondary-subtle" };
    }

    const now = new Date();
    const meetingStart = new Date(note.meeting_date);

    if (isNaN(meetingStart.getTime())) {
        return { label: "Not Scheduled", badgeClass: "bg-secondary-subtle text-secondary border border-secondary-subtle" };
    }

    const meetingEnd = new Date(meetingStart.getTime() + 60 * 60 * 1000);

    if (now < meetingStart) {
        return { label: "Scheduled", badgeClass: "bg-primary-subtle text-primary border border-primary-subtle" };
    } else if (now >= meetingStart && now <= meetingEnd) {
        return { label: "In Progress", badgeClass: "bg-warning-subtle text-warning-emphasis border border-warning-subtle" };
    } else {
        return { label: "Completed", badgeClass: "bg-success-subtle text-success border border-success-subtle" };
    }
}

let activeMeetingNoteId = null;

function setupGenericMentionAutocomplete(inputId, dropdownId) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    if (!input || !dropdown) return;
    if (input.dataset.mentionAttached) return;
    input.dataset.mentionAttached = "true";

    let selectedIndex = 0;
    let matchStart = -1;

    fetchUsersForMentions();

    input.addEventListener("input", handleInput);
    input.addEventListener("focus", handleFocus);
    input.addEventListener("keydown", handleKeydown);

    function handleFocus() {
        if (inputId === 'newMeetingParticipants' && (!input.value || input.value.trim() === '')) {
            matchStart = 0;
            renderDropdown("");
        }
    }

    async function handleInput() {
        const text = input.value;
        const cursorPos = input.selectionStart;
        const textBeforeCursor = text.substring(0, cursorPos);
        const atIndex = textBeforeCursor.lastIndexOf("@");

        if (atIndex !== -1) {
            const query = textBeforeCursor.substring(atIndex + 1);
            const charBeforeAt = atIndex > 0 ? textBeforeCursor[atIndex - 1] : " ";
            if (/[\s\n]/.test(charBeforeAt) || atIndex === 0) {
                if (!/\s\s/.test(query) && query.length <= 30) {
                    matchStart = atIndex;
                    await renderDropdown(query.toLowerCase());
                    return;
                }
            }
        } else if (inputId === 'newMeetingParticipants') {
            matchStart = 0;
            await renderDropdown(text.trim().toLowerCase());
            return;
        }
        hideDropdown();
    }

    async function renderDropdown(query) {
        const users = await fetchUsersForMentions();
        const filtered = users.filter(u => {
            if (u.id === USER_ID) return false;
            const nameMatch = (u.full_name || "").toLowerCase().includes(query);
            const empMatch = (u.employee_id || "").toLowerCase().includes(query);
            return nameMatch || empMatch;
        });

        if (filtered.length === 0) {
            dropdown.innerHTML = `<div class="p-2 text-center text-muted text-xs">No employees found matching "${query}"</div>`;
            dropdown.style.display = "block";
            return;
        }

        selectedIndex = 0;
        const itemsHtml = filtered.map((u, idx) => {
            const initials = (u.full_name || 'U').split(' ').map(n=>n[0]).join('').substring(0,2).toUpperCase();
            return `
                <div class="mention-dropdown-item ${idx === 0 ? 'active' : ''}" data-idx="${idx}" data-fullname="${u.full_name}" data-empid="${u.employee_id || ''}">
                    <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold text-xs" style="width: 28px; height: 28px; flex-shrink: 0;">
                        ${initials}
                    </div>
                    <div class="flex-grow-1 min-w-0">
                        <div class="fw-bold text-dark text-xs d-flex align-items-center justify-content-between">
                            <span>${u.full_name}</span>
                            ${u.employee_id ? `<span class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill text-xs px-2">${u.employee_id}</span>` : ''}
                        </div>
                        <div class="text-muted text-xs" style="font-size: 10px;">ID: ${u.employee_id || 'N/A'} · ${u.role_name || 'Employee'}</div>
                    </div>
                </div>
            `;
        }).join("");

        dropdown.innerHTML = `
            <div class="p-1 border-bottom bg-light">
                <input type="text" class="form-control form-control-sm mention-search-input text-xs rounded-2" placeholder="🔍 Search employee by Name or ID..." id="${dropdownId}_search" value="${query}">
            </div>
            <div class="mention-items-list" style="max-height: 180px; overflow-y: auto;">
                ${itemsHtml}
            </div>
        `;

        dropdown.style.display = "block";

        const searchInput = document.getElementById(`${dropdownId}_search`);
        if (searchInput) {
            searchInput.focus();
            searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
            searchInput.addEventListener("input", (e) => {
                const subQuery = e.target.value.toLowerCase().trim();
                renderDropdown(subQuery);
            });
        }

        dropdown.querySelectorAll(".mention-dropdown-item").forEach(item => {
            item.addEventListener("click", () => {
                selectMentionUser(item.getAttribute("data-fullname"), item.getAttribute("data-empid"));
            });
        });
    }

    function selectMentionUser(fullName, empId) {
        const text = input.value;
        const beforeAt = text.substring(0, matchStart);
        const cursorPos = input.selectionStart;
        const afterCursor = text.substring(cursorPos);

        const mentionText = empId ? `@${fullName} (${empId}) ` : `@${fullName} `;
        input.value = beforeAt + mentionText + afterCursor;
        input.focus();
        const newCursorPos = matchStart + mentionText.length;
        input.setSelectionRange(newCursorPos, newCursorPos);
        hideDropdown();
    }

    function hideDropdown() {
        dropdown.style.display = "none";
    }

    function handleKeydown(e) {
        if (dropdown.style.display === "block") {
            const items = dropdown.querySelectorAll(".mention-dropdown-item");
            if (items.length === 0) return;

            if (e.key === "ArrowDown") {
                e.preventDefault();
                selectedIndex = (selectedIndex + 1) % items.length;
                updateActiveItem(items);
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                selectedIndex = (selectedIndex - 1 + items.length) % items.length;
                updateActiveItem(items);
            } else if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                const activeItem = items[selectedIndex];
                if (activeItem) {
                    selectMentionUser(activeItem.getAttribute("data-fullname"), activeItem.getAttribute("data-empid"));
                }
            } else if (e.key === "Escape") {
                hideDropdown();
            }
        }
    }

    function updateActiveItem(items) {
        items.forEach((item, idx) => {
            if (idx === selectedIndex) {
                item.classList.add("active");
                item.scrollIntoView({ block: "nearest" });
            } else {
                item.classList.remove("active");
            }
        });
    }
}

let currentMeetingFilter = 'all';

function filterMeetingNotes(statusFilter) {
    currentMeetingFilter = statusFilter;

    ['all', 'scheduled', 'in_progress', 'completed'].forEach(f => {
        const btn = document.getElementById(`filter-btn-${f}`);
        if (btn) {
            if (f === statusFilter) {
                btn.className = "btn btn-sm filter-pill-btn btn-primary text-white fw-bold px-3 py-1.5 rounded-2 shadow-2xs";
                const badge = btn.querySelector('.badge');
                if (badge) badge.className = "badge bg-white text-primary rounded-pill ms-1";
            } else {
                btn.className = "btn btn-sm filter-pill-btn text-secondary fw-semibold px-3 py-1.5 rounded-2";
                const badge = btn.querySelector('.badge');
                if (badge) {
                    if (f === 'scheduled') badge.className = "badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill ms-1";
                    else if (f === 'in_progress') badge.className = "badge bg-warning-subtle text-warning-emphasis border border-warning-subtle rounded-pill ms-1";
                    else if (f === 'completed') badge.className = "badge bg-success-subtle text-success border border-success-subtle rounded-pill ms-1";
                    else badge.className = "badge bg-secondary text-white rounded-pill ms-1";
                }
            }
        }
    });

    renderMeetingNotesList();
}

function renderMeetingNotesList() {
    const container = document.getElementById('meetingNotesContainer');
    const partContainer = document.getElementById('meetingParticipantsContainer');
    const nextSessionContainer = document.getElementById('nextScheduledSessionContainer');
    
    if (!container) return;
    container.innerHTML = '';
    
    if (meetingNotesCache.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-calendar-x fs-2 d-block mb-2"></i>
                No meeting notes recorded.
            </div>
        `;
        if (nextSessionContainer) {
            nextSessionContainer.innerHTML = '<div class="text-muted text-xs py-2 text-center">No upcoming meeting scheduled.</div>';
        }
        if (partContainer) {
            partContainer.innerHTML = '<span class="text-muted text-xs">No active participants.</span>';
        }
        return;
    }

    // Calculate Counts for Status Badges
    let countAll = meetingNotesCache.length;
    let countScheduled = 0;
    let countInProgress = 0;
    let countCompleted = 0;

    meetingNotesCache.forEach(n => {
        const statusInfo = getMeetingStatusInfo(n);
        const st = statusInfo.label.toLowerCase();
        if (st === 'scheduled') countScheduled++;
        else if (st === 'in progress' || st === 'inprogress' || st === 'active') countInProgress++;
        else if (st === 'completed' || st === 'finished') countCompleted++;
    });

    if (document.getElementById('count-all')) document.getElementById('count-all').innerText = countAll;
    if (document.getElementById('count-scheduled')) document.getElementById('count-scheduled').innerText = countScheduled;
    if (document.getElementById('count-in_progress')) document.getElementById('count-in_progress').innerText = countInProgress;
    if (document.getElementById('count-completed')) document.getElementById('count-completed').innerText = countCompleted;

    const now = new Date();
    let upcomingNote = null;

    // Filter next scheduled upcoming meeting (where meeting_date > now)
    const sortedNotes = [...meetingNotesCache].sort((a, b) => new Date(a.meeting_date || 0) - new Date(b.meeting_date || 0));
    for (let n of sortedNotes) {
        if (n.meeting_date && new Date(n.meeting_date) > now) {
            upcomingNote = n;
            break;
        }
    }

    // Dynamic Next Scheduled Session Panel
    if (nextSessionContainer) {
        if (upcomingNote) {
            const mDate = new Date(upcomingNote.meeting_date);
            const dateStr = mDate.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
            const timeStr = mDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const hasLink = upcomingNote.meeting_link && upcomingNote.meeting_link.trim().startsWith('http');
            const joinBtn = hasLink ? `<a href="${upcomingNote.meeting_link.trim()}" target="_blank" class="btn btn-primary btn-sm rounded-pill text-xs fw-bold px-3 shadow-2xs mt-2 d-inline-flex align-items-center gap-1.5"><i class="bi bi-camera-video-fill"></i> Join Google Meet</a>` : '';

            nextSessionContainer.innerHTML = `
                <div class="d-flex align-items-start gap-3">
                    <div class="rounded-3 bg-primary-subtle text-primary d-flex align-items-center justify-content-center flex-shrink-0" style="width: 44px; height: 44px;">
                        <i class="bi bi-calendar-event fs-4"></i>
                    </div>
                    <div class="flex-grow-1 min-w-0">
                        <h6 class="fw-bold mb-1 text-dark text-sm text-truncate">${upcomingNote.title}</h6>
                        <div class="text-muted text-xs"><i class="bi bi-clock me-1"></i>${dateStr} at ${timeStr}</div>
                        ${joinBtn}
                    </div>
                </div>
            `;
        } else {
            nextSessionContainer.innerHTML = `
                <div class="text-center py-2 text-muted text-xs">
                    <i class="bi bi-calendar-check me-1"></i> No upcoming meeting scheduled.
                </div>
            `;
        }
    }

    // Filter Meetings according to currentMeetingFilter
    const filteredNotes = meetingNotesCache.filter(n => {
        if (currentMeetingFilter === 'all') return true;
        const statusInfo = getMeetingStatusInfo(n);
        const st = statusInfo.label.toLowerCase();
        if (currentMeetingFilter === 'scheduled') return st === 'scheduled';
        if (currentMeetingFilter === 'in_progress') return st === 'in progress' || st === 'inprogress' || st === 'active';
        if (currentMeetingFilter === 'completed') return st === 'completed' || st === 'finished';
        return true;
    });

    if (filteredNotes.length === 0) {
        const filterName = currentMeetingFilter === 'all' ? '' : currentMeetingFilter.replace('_', ' ');
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-funnel fs-2 d-block mb-2 text-secondary opacity-50"></i>
                No ${filterName} meetings found.
            </div>
        `;
        return;
    }

    filteredNotes.forEach(n => {
        const date = n.meeting_date ? new Date(n.meeting_date).toLocaleDateString() : 'N/A';
        const time = n.meeting_date ? new Date(n.meeting_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
        const statusInfo = getMeetingStatusInfo(n);
        const hasMeet = n.meeting_link && n.meeting_link.trim().startsWith('http');
        const meetBadge = hasMeet ? `<span class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill text-xs ms-2"><i class="bi bi-camera-video-fill me-1"></i>Google Meet</span>` : '';
        
        container.innerHTML += `
            <div class="border rounded p-3 mb-3 hover-shadow transition" style="cursor: pointer;" onclick="viewMeetingNoteDetail(${n.id})">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div class="d-flex align-items-center gap-1">
                        <h6 class="fw-bold text-dark mb-0">${n.title}</h6>
                        ${meetBadge}
                    </div>
                    <span class="badge ${statusInfo.badgeClass} rounded-pill text-xs">${statusInfo.label}</span>
                </div>
                <p class="text-muted text-sm mb-2 text-truncate" style="max-width: 600px;">${n.notes}</p>
                <div class="d-flex align-items-center justify-content-between text-muted text-xs">
                    <span><i class="bi bi-calendar me-1"></i> ${date} ${time ? '· ' + time : ''}</span>
                    <span class="fw-semibold text-primary">View Note Details & Chat <i class="bi bi-chevron-right"></i></span>
                </div>
            </div>
        `;
    });

    // Populate Participants List
    if (partContainer) {
        partContainer.innerHTML = '';
        const allParticipantsText = meetingNotesCache.map(n => (n.participants || '') + ' ' + (n.author_name || '')).join(' ');
        
        fetchUsersForMentions().then(users => {
            const matchedUsers = users.filter(u => {
                if (!u.employee_id && !u.full_name) return false;
                return (u.employee_id && allParticipantsText.includes(u.employee_id)) || (u.full_name && allParticipantsText.includes(u.full_name));
            });

            if (matchedUsers.length === 0) {
                partContainer.innerHTML = '<span class="text-muted text-xs">No active tagged participants.</span>';
            } else {
                matchedUsers.forEach(u => {
                    const initials = (u.full_name || 'U').split(' ').map(n=>n[0]).join('').substring(0,2).toUpperCase();
                    partContainer.innerHTML += `
                        <div class="d-flex align-items-center gap-2 p-1.5 rounded bg-light border mb-1">
                            <div class="avatar-sm bg-primary text-white flex-shrink-0" style="width: 24px; height: 24px; font-size: 10px;">${initials}</div>
                            <div class="flex-grow-1 min-w-0">
                                <div class="text-dark fw-bold text-xs d-flex align-items-center justify-content-between">
                                    <span>${u.full_name}</span>
                                    ${u.employee_id ? `<span class="employee-id-badge">${u.employee_id}</span>` : ''}
                                </div>
                            </div>
                        </div>
                    `;
                });
            }
        });
    }
}

function openNewMeetingNoteModal() {
    if (document.getElementById('newMeetingTitle')) document.getElementById('newMeetingTitle').value = '';
    if (document.getElementById('newMeetingNotes')) document.getElementById('newMeetingNotes').value = '';
    if (document.getElementById('newMeetingDate')) document.getElementById('newMeetingDate').value = '';
    if (document.getElementById('newMeetingParticipants')) document.getElementById('newMeetingParticipants').value = '';
    if (document.getElementById('newMeetingLink')) document.getElementById('newMeetingLink').value = '';

    setupGenericMentionAutocomplete('newMeetingParticipants', 'mentionDropdownParticipants');
    setupGenericMentionAutocomplete('newMeetingNotes', 'mentionDropdownNotes');

    const modalEl = document.getElementById('newMeetingNoteModal');
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();
}

async function submitNewMeetingNote() {
    const title = document.getElementById('newMeetingTitle').value.trim();
    const notes = document.getElementById('newMeetingNotes').value.trim();
    const dateInput = document.getElementById('newMeetingDate').value;
    const participants = document.getElementById('newMeetingParticipants') ? document.getElementById('newMeetingParticipants').value.trim() : '';
    const meetingLink = document.getElementById('newMeetingLink') ? document.getElementById('newMeetingLink').value.trim() : '';

    if (!title || !notes) {
        showToast("Warning", "Title and Notes are required");
        return;
    }

    let dateIso = null;
    if (dateInput) {
        try {
            dateIso = new Date(dateInput).toISOString();
        } catch (_) {
            dateIso = null;
        }
    }

    try {
        const res = await fetch(`${API_URL}/decisions/${DECISION_ID}/meeting_notes`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title: title,
                notes: notes,
                meeting_date: dateIso,
                participants: participants,
                meeting_link: meetingLink,
                created_by: USER_ID
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to record meeting notes");
        }
        
        const modalEl = document.getElementById('newMeetingNoteModal');
        if (modalEl) {
            const instance = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
            instance.hide();
        }
        showToast("Success", "Meeting scheduled and tagged teammates notified");
        loadMeetingNotes();
    } catch (err) {
        showToast("Danger", err.message);
    }
}

async function viewMeetingNoteDetail(noteId) {
    activeMeetingNoteId = noteId;
    const note = meetingNotesCache.find(n => n.id === noteId);
    if (!note) return;

    const statusInfo = getMeetingStatusInfo(note);
    const users = await fetchUsersForMentions();

    document.getElementById('detailNoteTitle').innerText = note.title;
    document.getElementById('detailNoteDate').innerText = note.meeting_date ? new Date(note.meeting_date).toLocaleString() : 'N/A';
    document.getElementById('detailNoteContent').innerHTML = formatMentionsInContent(note.notes, users);
    if (document.getElementById('detailNoteAuthor')) document.getElementById('detailNoteAuthor').innerText = note.author_name || 'User';

    const statusEl = document.getElementById('detailNoteStatus');
    if (statusEl) {
        statusEl.className = `badge ${statusInfo.badgeClass} rounded-pill text-xs ms-2`;
        statusEl.innerText = statusInfo.label;
    }

    // Join Google Meet Button
    const meetContainer = document.getElementById('detailJoinMeetBtnContainer');
    if (meetContainer) {
        if (note.meeting_link && note.meeting_link.trim().startsWith('http')) {
            meetContainer.innerHTML = `
                <a href="${note.meeting_link.trim()}" target="_blank" class="btn btn-primary btn-sm rounded-pill px-3 fw-bold text-xs shadow-2xs d-inline-flex align-items-center gap-1.5">
                    <i class="bi bi-camera-video-fill"></i> Join Google Meet
                </a>
            `;
        } else {
            meetContainer.innerHTML = '';
        }
    }

    // Tagged Participants list
    const partEl = document.getElementById('detailNoteParticipants');
    if (partEl) {
        if (note.participants) {
            partEl.innerHTML = formatMentionsInContent(note.participants, users);
        } else {
            partEl.innerHTML = '<span class="text-muted text-xs">No specific participants tagged.</span>';
        }
    }

    // Fetch and render Live Meeting Chat
    fetchMeetingNoteComments(noteId);
    setupGenericMentionAutocomplete('meetingChatInputText', 'mentionDropdownMeetingChat');

    const modalEl = document.getElementById('meetingNoteDetailModal');
    const bsModal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    bsModal.show();
}

async function fetchMeetingNoteComments(noteId) {
    const feed = document.getElementById('meetingChatFeedContainer');
    if (!feed) return;

    try {
        const res = await fetch(`${API_URL}/decisions/meeting_notes/${noteId}/comments`);
        if (!res.ok) return;
        const comments = await res.json();

        feed.innerHTML = '';
        const users = await fetchUsersForMentions();

        if (comments.length === 0) {
            feed.innerHTML = `
                <div class="text-center text-muted py-5 my-auto">
                    <i class="bi bi-chat-text text-secondary fs-3 d-block mb-1"></i>
                    <span class="small">No chat messages yet. Send Google Meet links or updates below!</span>
                </div>
            `;
            return;
        }

        comments.forEach(c => {
            const isOwn = c.user_id === USER_ID;
            const author = users.find(u => u.id === c.user_id) || { full_name: c.author_name || "Teammate", employee_id: "" };
            const initials = (author.full_name || "TM").split(' ').map(n=>n[0]).join('').substring(0,2).toUpperCase();
            const timeStr = c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

            const isDeleted = c.is_deleted || c.content === "This message was deleted.";
            let formattedBody = isDeleted ? '<span class="fst-italic text-muted opacity-75">This message was deleted.</span>' : formatMentionsInContent(c.content, users);

            if (!isDeleted) {
                if (c.is_edited) {
                    formattedBody += ' <small class="text-muted opacity-75" style="font-size: 10px;">(edited)</small>';
                }
                // Detect URLs & Google Meet links
                formattedBody = formattedBody.replace(/(https?:\/\/[^\s<]+)/gi, (url) => {
                    if (url.includes('meet.google.com') || url.includes('zoom.us') || url.includes('teams.microsoft.com')) {
                        return `<a href="${url}" target="_blank" class="btn btn-sm btn-light border text-primary fw-bold rounded-pill my-1 px-3 d-inline-flex align-items-center gap-1.5 shadow-2xs text-xs"><i class="bi bi-camera-video-fill text-primary"></i> Join Meeting Link</a>`;
                    }
                    return `<a href="${url}" target="_blank" class="text-decoration-underline fw-bold">${url}</a>`;
                });
            }

            const safeContent = (c.content || '').replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\${/g, '\\${');
            const editDeleteButtons = (isOwn && !isDeleted) ? `
                <div class="d-inline-flex gap-2 ms-2 opacity-75">
                    <button type="button" class="btn btn-link p-0 text-primary text-xs text-decoration-none" onclick="editChatMessage(${c.id}, \`${safeContent}\`, true)" title="Edit Message">
                        <i class="bi bi-pencil-fill" style="font-size: 11px;"></i> Edit
                    </button>
                    <button type="button" class="btn btn-link p-0 text-danger text-xs text-decoration-none" onclick="deleteChatMessage(${c.id}, true)" title="Delete Message">
                        <i class="bi bi-trash-fill" style="font-size: 11px;"></i> Delete
                    </button>
                </div>
            ` : '';

            feed.innerHTML += `
                <div class="chat-msg-row ${isOwn ? 'own-msg' : 'other-msg'}">
                    <div class="chat-avatar ${isOwn ? 'bg-primary text-white' : 'bg-white text-primary border'}">
                        ${initials}
                    </div>
                    <div class="chat-bubble-wrap">
                        <div class="chat-msg-header d-flex align-items-center">
                            <span class="chat-msg-author">${isOwn ? 'You' : author.full_name}</span>
                            ${(!isOwn && author.employee_id) ? `<span class="chat-msg-empid">${author.employee_id}</span>` : ''}
                            <span class="chat-msg-time me-auto">${timeStr}</span>
                            ${editDeleteButtons}
                        </div>
                        <div class="chat-bubble">
                            ${formattedBody}
                        </div>
                    </div>
                </div>
            `;
        });

        setTimeout(() => { feed.scrollTop = feed.scrollHeight; }, 50);
    } catch (e) {
        console.error("Error loading meeting note comments:", e);
    }
}

async function submitMeetingNoteComment() {
    if (!activeMeetingNoteId) return;
    const input = document.getElementById('meetingChatInputText');
    if (!input) return;
    const content = input.value.trim();
    if (!content) return;

    try {
        const res = await fetch(`${API_URL}/decisions/meeting_notes/${activeMeetingNoteId}/comments`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                content: content,
                user_id: USER_ID
            })
        });

        if (!res.ok) throw new Error("Failed to send chat message");
        input.value = '';
        fetchMeetingNoteComments(activeMeetingNoteId);
    } catch (err) {
        showToast("Danger", err.message);
    }
}

async function editChatMessage(commentId, currentContent, isMeetingNote = false) {
    const newContent = prompt("Edit your message:", currentContent);
    if (newContent === null || newContent.trim() === "" || newContent.trim() === currentContent) return;

    try {
        const res = await fetch(`${API_URL}/decisions/comments/${commentId}?content=${encodeURIComponent(newContent.trim())}&user_id=${USER_ID}`, {
            method: "PUT"
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to edit message");
        }

        showToast("Success", "Message updated");
        if (isMeetingNote && activeMeetingNoteId) {
            fetchMeetingNoteComments(activeMeetingNoteId);
        } else if (activeThreadId) {
            loadThreads().then(() => selectThread(activeThreadId));
        }
    } catch (err) {
        showToast("Danger", err.message);
    }
}

async function deleteChatMessage(commentId, isMeetingNote = false) {
    if (!confirm("Are you sure you want to delete this message?")) return;

    try {
        const res = await fetch(`${API_URL}/decisions/comments/${commentId}?user_id=${USER_ID}`, {
            method: "DELETE"
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to delete message");
        }

        showToast("Danger", "Message deleted");
        if (isMeetingNote && activeMeetingNoteId) {
            fetchMeetingNoteComments(activeMeetingNoteId);
        } else if (activeThreadId) {
            loadThreads().then(() => selectThread(activeThreadId));
        }
    } catch (err) {
        showToast("Danger", err.message);
    }
}

// ==========================================
// SUPPORTING DOCUMENTS LOGIC
// ==========================================

async function loadDocuments() {
    try {
        const res = await fetch(`${API_URL}/decisions/${DECISION_ID}`);
        if (!res.ok) throw new Error("Failed to load documents");
        const dec = await res.json();
        
        const tbody = document.getElementById('documentsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        const attachments = dec.attachments || [];

        if (attachments.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-5">No files uploaded yet.</td></tr>`;
            return;
        }

        // Fetch users mapping
        const uRes = await fetch(`${API_URL}/users/`);
        const users = uRes.ok ? await uRes.json() : [];
        const userMap = {};
        users.forEach(u => { userMap[u.id] = u; });

        attachments.forEach(att => {
            const size = (att.file_size / (1024 * 1024)).toFixed(2) + ' MB';
            const date = new Date(att.uploaded_at).toLocaleDateString();
            const u = userMap[att.uploaded_by] || { full_name: "Anonymous uploader" };
            
            // Render file type icon based on extension
            let extIcon = 'bi-file-earmark';
            if (att.filename.endsWith('.pdf')) extIcon = 'bi-file-pdf text-danger';
            else if (att.filename.endsWith('.xlsx') || att.filename.endsWith('.xls')) extIcon = 'bi-file-spreadsheet text-success';
            else if (att.filename.endsWith('.docx') || att.filename.endsWith('.doc')) extIcon = 'bi-file-word text-primary';
            else if (att.filename.endsWith('.pptx') || att.filename.endsWith('.ppt')) extIcon = 'bi-file-slides text-warning';

            tbody.innerHTML += `
                <tr>
                    <td class="ps-4">
                        <div class="d-flex align-items-center gap-2">
                            <i class="bi ${extIcon} fs-5"></i>
                            <span class="fw-bold text-dark">${att.filename}</span>
                        </div>
                    </td>
                    <td>${size}</td>
                    <td>${u.full_name}</td>
                    <td>${date}</td>
                    <td class="text-end pe-4">
                        <a href="${API_URL}/upload/${att.id}" target="_blank" class="btn btn-sm btn-outline-secondary me-2" title="View Document"><i class="bi bi-eye"></i> View</a>
                        <a href="${API_URL}/upload/${att.id}" class="btn btn-sm btn-outline-primary" download><i class="bi bi-download"></i> Download</a>
                    </td>
                </tr>
            `;
        });

    } catch (err) {
        showToast("Danger", err.message);
    }
}

// Drag & drop file uploads handler
window.addEventListener('load', () => {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');

    if (dropzone && fileInput) {
        dropzone.addEventListener('click', () => fileInput.click());
        
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('bg-primary-subtle');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('bg-primary-subtle');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('bg-primary-subtle');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileUpload(files);
            }
        });

        fileInput.addEventListener('change', () => {
            const files = fileInput.files;
            if (files.length > 0) {
                handleFileUpload(files);
            }
        });
    }
});

async function handleFileUpload(files) {
    const formData = new FormData();
    formData.append('file', files[0]);
    formData.append('user_id', USER_ID);
    formData.append('decision_id', DECISION_ID);

    try {
        const res = await fetch(`${API_URL}/upload/`, {
            method: "POST",
            body: formData
        });

        if (!res.ok) throw new Error("Failed to upload file");
        
        showToast("Success", "File uploaded and linked successfully");
        loadDocuments();
    } catch (err) {
        showToast("Danger", err.message);
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function logUserAction(action, details) {
    if (typeof DECISION_ID === 'undefined' || !USER_ID) return;
    try {
        await fetch(`${API_URL}/audit/log`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: USER_ID,
                action: action,
                details: details
            })
        });
    } catch (_) {}
}
window.logUserAction = logUserAction;

function switchTab(tabName) {
    if (window.event) {
        window.event.preventDefault();
    }
    const panes = document.querySelectorAll('.tab-pane-content');
    panes.forEach(p => p.classList.add('d-none'));

    const links = document.querySelectorAll('#decisionTabs .nav-link');
    links.forEach(l => {
        l.classList.remove('active', 'fw-bold', 'text-primary', 'text-white', 'bg-primary');
        l.classList.add('fw-semibold', 'text-secondary');
    });

    const targetPane = document.getElementById(`tab-pane-${tabName}`);
    if (targetPane) {
        targetPane.classList.remove('d-none');
    }

    const targetLink = document.getElementById(`tab-link-${tabName}`);
    if (targetLink) {
        targetLink.classList.add('active', 'fw-bold', 'text-white', 'bg-primary');
        targetLink.classList.remove('fw-semibold', 'text-secondary', 'text-primary');
    }

    if (tabName !== 'overview') {
        logUserAction(
            `Viewed ${tabName.replace('_', ' ')} section for DEC-${DECISION_ID}`,
            `User opened ${tabName.replace('_', ' ')} tab`
        );
    }

    if (tabName === 'history') {
        loadHistory();
    } else if (tabName === 'discussions') {
        loadThreads();
        if (typeof loadDiscussions === 'function') loadDiscussions();
    } else if (tabName === 'meeting_notes') {
        if (typeof loadMeetingNotes === 'function') loadMeetingNotes();
    } else if (tabName === 'documents') {
        if (typeof loadDocuments === 'function') loadDocuments();
    } else if (tabName === 'rationale') {
        if (typeof fetchAlternatives === 'function') fetchAlternatives();
    }
}
window.switchTab = switchTab;

// ==========================================
// HISTORY LOGIC
// ==========================================

async function loadHistory() {
    const container = document.getElementById('versionHistoryContainer');
    if (!container) return;

    const decisionId = typeof DECISION_ID !== 'undefined' ? DECISION_ID : (typeof CURRENT_DECISION_ID !== 'undefined' ? CURRENT_DECISION_ID : 1);
    const userIdParam = typeof USER_ID !== 'undefined' ? USER_ID : 1;

    let versions = [];
    try {
        const vRes = await fetch(`${API_URL}/decisions/${decisionId}/versions?user_id=${userIdParam}`);
        if (vRes.ok) {
            versions = await vRes.json();
        }
    } catch (_) {}

    if (!versions || versions.length === 0) {
        container.innerHTML = '<div class="text-center py-4 text-muted small">No version history available.</div>';
        return;
    }

    container.innerHTML = '';

    versions.forEach((v, index) => {
        const dateStr = v.created_at ? new Date(v.created_at).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'medium' }) : 'Recent';
        const changer = v.changed_by_name || 'System';

        if (v.event_type === 'VERSION_UPDATE') {
            const isLatest = index === 0;
            const itemClass = isLatest ? "timeline-item active border-start border-4 border-success bg-white shadow-sm p-3 mb-3 rounded" : "timeline-item completed bg-light border p-3 mb-3 rounded";
            const activeBadgeHtml = `
                <span class="badge px-3 py-1 text-white ms-1 fw-bold shadow-sm" style="background-color: #10B981 !important; color: #FFFFFF !important; font-size: 11px; border-radius: 6px; display: inline-flex; align-items: center; gap: 4px;">
                    <i class="bi bi-check-circle-fill"></i> Current Active Version
                </span>
            `;

            container.innerHTML += `
                <div class="${itemClass}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1 me-3">
                            <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
                                <span class="badge bg-primary px-2.5 py-1 fw-bold" style="font-size: 11px;">Version ${v.version_number}</span>
                                <span class="badge bg-primary-subtle text-primary border border-primary-subtle fw-semibold px-2.5 py-1" style="font-size: 11px;">${escapeHtml(v.status || 'Pending')}</span>
                                ${isLatest ? activeBadgeHtml : ''}
                            </div>
                            <div class="fw-bold text-dark text-md mb-1" style="font-size: 16px;">${escapeHtml(v.title || "Decision Record")}</div>
                            ${v.description ? `<p class="text-secondary small mb-2 text-truncate" style="max-width: 550px;">${escapeHtml(v.description)}</p>` : ''}
                            <div class="p-2.5 rounded bg-light border mb-2">
                                <small class="text-dark d-block"><strong>Change Summary:</strong> ${escapeHtml(v.change_reason || "Version Snapshot Saved")}</small>
                            </div>
                            <p class="text-muted mb-0 small" style="font-size: 12px;"><i class="bi bi-person-circle me-1 text-primary"></i> Changed by: <strong>${escapeHtml(changer)}</strong></p>
                        </div>
                        <div class="text-end">
                            <small class="text-muted d-block mb-3" style="font-size: 11px;"><i class="bi bi-clock me-1"></i>${dateStr}</small>
                            ${(!isLatest && v.version_number > 0) ? `
                                <button class="btn btn-outline-primary btn-sm py-1 px-3 fw-semibold shadow-sm" onclick="restoreVersion(${v.version_number})">
                                    <i class="bi bi-arrow-counterclockwise me-1"></i> Restore Version ${v.version_number}
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        } else if (v.event_type === 'REVIEW_EVENT') {
            const isApproved = (v.status || '').toLowerCase().includes('approved');
            const badgeClass = isApproved ? 'success' : 'danger';
            const iconClass = isApproved ? 'bi-check-circle-fill' : 'bi-x-circle-fill';

            container.innerHTML += `
                <div class="timeline-item bg-white border border-${badgeClass}-subtle p-3 mb-3 rounded shadow-sm" style="border-left: 4px solid ${isApproved ? '#10B981' : '#EF4444'} !important;">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1 me-3">
                            <div class="d-flex align-items-center gap-2 mb-1">
                                <span class="badge bg-${badgeClass}-subtle text-${badgeClass} border border-${badgeClass}-subtle px-2.5 py-1" style="font-size: 11px;"><i class="bi ${iconClass} me-1"></i>Review ${v.status}</span>
                            </div>
                            <div class="fw-bold text-dark text-sm mb-1"><i class="bi bi-person-badge-fill me-1 text-primary"></i><strong>${escapeHtml(changer)}</strong> (${escapeHtml(v.title || 'Review Action')})</div>
                            <div class="text-muted small">${escapeHtml(v.change_reason || "Review status updated")}</div>
                        </div>
                        <div class="text-end">
                            <small class="text-muted d-block" style="font-size: 11px;"><i class="bi bi-clock me-1"></i>${dateStr}</small>
                        </div>
                    </div>
                </div>
            `;
        } else {
            // DOC_ACCESS, DISCUSSION_EVENT, NOTE_EVENT, TAB_VIEW, ACCESS_EVENT
            let bClass = v.badge_color || 'info';
            let bIcon = v.badge_icon || 'bi-eye-fill';
            let bLabel = v.badge_label || 'Activity Log';
            let actionTitle = v.title || `${changer} performed action`;

            container.innerHTML += `
                <div class="timeline-item bg-white border border-${bClass}-subtle p-3 mb-3 rounded shadow-sm" style="border-left: 4px solid var(--bs-${bClass}, #0EA5E9) !important;">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1 me-3">
                            <div class="d-flex align-items-center gap-2 mb-1">
                                <span class="badge bg-${bClass}-subtle text-${bClass} border border-${bClass}-subtle px-2.5 py-1" style="font-size: 11px;"><i class="bi ${bIcon} me-1"></i>${escapeHtml(bLabel)}</span>
                            </div>
                            <div class="fw-bold text-dark text-sm mb-1"><i class="bi bi-person-check-fill text-primary me-1"></i><strong>${escapeHtml(changer)}</strong>: ${escapeHtml(actionTitle)}</div>
                            <div class="text-muted small">${escapeHtml(v.description || v.change_reason || "Activity recorded")}</div>
                        </div>
                        <div class="text-end">
                            <small class="text-muted d-block" style="font-size: 11px;"><i class="bi bi-clock me-1"></i>${dateStr}</small>
                        </div>
                    </div>
                </div>
            `;
        }
    });
}

async function restoreVersion(versionNumber) {
    if (!confirm(`Are you sure you want to restore decision to Version ${versionNumber}?`)) {
        return;
    }
    const decisionId = typeof DECISION_ID !== 'undefined' ? DECISION_ID : (typeof CURRENT_DECISION_ID !== 'undefined' ? CURRENT_DECISION_ID : 1);
    try {
        const res = await fetch(`${API_URL}/decisions/${decisionId}/versions/${versionNumber}/restore`, {
            method: "POST"
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to restore version");
        }
        showCenterNotification(`Decision restored to Version ${versionNumber} successfully!`, 'success', 'Version Restored');
        if (typeof fetchDecisionDetails === 'function') {
            fetchDecisionDetails();
        } else {
            window.location.reload();
        }
    } catch (e) {
        showCenterNotification(e.message || "Failed to restore version", 'error', 'Restore Error');
    }
}
window.restoreVersion = restoreVersion;

async function deleteCurrentDecision() {
    const decisionId = typeof DECISION_ID !== 'undefined' ? DECISION_ID : (typeof CURRENT_DECISION_ID !== 'undefined' ? CURRENT_DECISION_ID : 1);
    if (!confirm(`Are you sure you want to delete this decision (DEC-${decisionId})?\nThis action cannot be undone.`)) {
        return;
    }
    try {
        const roleParam = typeof CURRENT_USER_ROLE !== 'undefined' ? encodeURIComponent(CURRENT_USER_ROLE) : '';
        const userParam = typeof USER_ID !== 'undefined' ? USER_ID : 1;
        const res = await fetch(`${API_URL}/decisions/${decisionId}?user_id=${userParam}&role_name=${roleParam}`, {
            method: "DELETE"
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to delete decision");
        }
        showCenterNotification("Decision deleted successfully.", 'success', 'Decision Deleted');
        setTimeout(() => {
            window.location.href = "/decisions";
        }, 1200);
    } catch (e) {
        showCenterNotification(e.message || "Failed to delete decision", 'error', 'Error Deleting Decision');
    }
}
window.deleteCurrentDecision = deleteCurrentDecision;
