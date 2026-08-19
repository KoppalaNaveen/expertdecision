// =========================================================
// review.js – Reviews / Pending Approvals Page
// =========================================================

let allReviews = [];
let currentFilter = "all";
let currentPage = 1;
const rowsPerPage = 8;

// Decision title cache
const decisionCache = {};

document.addEventListener("DOMContentLoaded", () => {
    fetchReviews();
});

async function fetchReviews() {
    try {
        const userParam = typeof USER_ID !== 'undefined' && USER_ID ? `?user_id=${USER_ID}` : '';
        const res = await fetch(`${API_URL}/reviews/${userParam}`);
        if (!res.ok) throw new Error("Failed to load reviews");
        allReviews = await res.json();
        updateStats();
        renderTable();
    } catch (err) {
        document.getElementById("reviewsTableBody").innerHTML =
            `<tr><td colspan="7" class="text-center py-5 text-danger">
                <i data-lucide="alert-circle" style="width:18px;height:18px;" class="me-2"></i>${err.message}
             </td></tr>`;
        if (window.lucide) lucide.createIcons();
    }
}

async function getDecisionTitle(id) {
    if (decisionCache[id]) return decisionCache[id];
    try {
        const res = await fetch(`${API_URL}/decisions/${id}`);
        if (!res.ok) return `DEC-${id}`;
        const d = await res.json();
        decisionCache[id] = d.title || `DEC-${id}`;
        return decisionCache[id];
    } catch (_) {
        return `DEC-${id}`;
    }
}

function updateStats() {
    const total    = allReviews.length;
    const pending  = allReviews.filter(r => r.status === "Pending" || r.status === "Queued").length;
    const approved = allReviews.filter(r => r.status === "Approved").length;
    const rejected = allReviews.filter(r => r.status === "Rejected").length;

    document.getElementById("statAll").innerText     = total;
    document.getElementById("statPending").innerText  = pending;
    document.getElementById("statApproved").innerText = approved;
    document.getElementById("statRejected").innerText = rejected;

    document.getElementById("tabAll").innerText     = total;
    document.getElementById("tabPending").innerText  = pending;
    document.getElementById("tabApproved").innerText = approved;
    document.getElementById("tabRejected").innerText = rejected;
}

function setFilter(filter, btn) {
    currentFilter = filter;
    currentPage = 1;
    document.querySelectorAll(".nav-link").forEach(el => {
        el.classList.remove("active", "fw-bold", "text-primary", "border-primary");
        el.classList.add("text-secondary");
        el.style.borderBottom = "";
    });
    btn.classList.add("active", "fw-bold", "text-primary");
    btn.classList.remove("text-secondary");
    renderTable();
}

function filterReviews() {
    currentPage = 1;
    renderTable();
}

function getFilteredReviews() {
    const query = (document.getElementById("reviewSearch")?.value || "").toLowerCase();
    return allReviews.filter(r => {
        let matchStatus = false;
        if (currentFilter === "all") matchStatus = true;
        else if (currentFilter === "Pending") matchStatus = (r.status === "Pending" || r.status === "Queued");
        else matchStatus = (r.status === currentFilter);
        
        const matchSearch = !query ||
            (r.reviewer_name || "").toLowerCase().includes(query) ||
            (`DEC-${r.decision_id}`).toLowerCase().includes(query) ||
            (r.comments || "").toLowerCase().includes(query) ||
            (r.approval_type || "").toLowerCase().includes(query);
        return matchStatus && matchSearch;
    });
}

function renderTable() {
    const filtered   = getFilteredReviews();
    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start    = (currentPage - 1) * rowsPerPage;
    const pageData = filtered.slice(start, start + rowsPerPage);

    const tbody = document.getElementById("reviewsTableBody");

    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted">
            No ${currentFilter === "all" ? "" : currentFilter.toLowerCase()} reviews found.
        </td></tr>`;
        if (window.lucide) lucide.createIcons();
    } else {
        tbody.innerHTML = pageData.map(r => {
            const date = r.reviewed_at ? new Date(r.reviewed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";
            const initials = (r.reviewer_initials || (r.reviewer_name || "U").substring(0, 2)).toUpperCase();

            let statusBadge, statusStyle;
            if (r.status === "Approved") {
                statusBadge = "Approved";
                statusStyle = "background:#ECFDF5;color:#059669;";
            } else if (r.status === "Rejected") {
                statusBadge = "Rejected";
                statusStyle = "background:#FEF2F2;color:#DC2626;";
            } else if (r.status === "Queued") {
                statusBadge = "Queued (Step 1 Pending)";
                statusStyle = "background:#F1F5F9;color:#64748B;";
            } else {
                statusBadge = "Pending Action";
                statusStyle = "background:#FFF7ED;color:#D97706;";
            }

            const approvalType = r.approval_type || "Review";
            const commentsText = r.comments ? r.comments.substring(0, 60) + (r.comments.length > 60 ? "…" : "") : "<span class='text-muted fst-italic'>No comments</span>";

            const isApprover = typeof CURRENT_USER_ROLE !== 'undefined' && ['Manager', 'Administrator', 'Admin', 'Reviewer', 'Team Lead'].includes(CURRENT_USER_ROLE);
            const actionButtons = (r.status === "Pending" && isApprover) ? `
                <div class="d-flex gap-1 justify-content-end align-items-center">
                    <button class="btn btn-sm btn-success px-2 py-1 fw-semibold d-flex align-items-center" style="font-size:11px;" onclick="openApprovalWorkflowModal(${r.decision_id}, 'DEC-${r.decision_id}', ${r.reviewer_id}, 'Approved', '${(r.reviewer_name || 'Author').replace(/'/g, "\\'")}', '${r.approval_type || 'General'}')">
                        <i data-lucide="check-circle" style="width:12px;height:12px;" class="me-1"></i>Accept
                    </button>
                    <button class="btn btn-sm btn-danger px-2 py-1 fw-semibold d-flex align-items-center" style="font-size:11px;" onclick="openApprovalWorkflowModal(${r.decision_id}, 'DEC-${r.decision_id}', ${r.reviewer_id}, 'Rejected', '${(r.reviewer_name || 'Author').replace(/'/g, "\\'")}', '${r.approval_type || 'General'}')">
                        <i data-lucide="x-circle" style="width:12px;height:12px;" class="me-1"></i>Reject
                    </button>
                    <a href="/decision/${r.decision_id}" class="btn btn-sm btn-outline-secondary px-2 py-1" style="font-size:11px;">View</a>
                </div>
            ` : `
                <a href="/decision/${r.decision_id}" class="btn btn-sm btn-outline-primary px-3" style="font-size:12px;">View Decision</a>
            `;

            return `
            <tr>
                <td class="px-4 py-3">
                    <a href="/decision/${r.decision_id}" class="fw-bold text-primary text-decoration-none" style="font-size:13px;">DEC-${r.decision_id}</a>
                    <div class="text-muted" style="font-size:11px;">Decision #${r.decision_id}</div>
                </td>
                <td class="px-4">
                    <div class="d-flex align-items-center gap-2">
                        <div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#667EEA,#764BA2);display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:white;">${initials}</div>
                        <span class="fw-medium" style="font-size:13px;">${r.reviewer_name || `Reviewer #${r.reviewer_id}`}</span>
                    </div>
                </td>
                <td class="px-4">
                    <span style="background:#EEF2FF;color:#4F46E5;font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;">${approvalType}</span>
                </td>
                <td class="px-4 text-muted" style="font-size:12px;max-width:180px;">${commentsText}</td>
                <td class="px-4 text-muted" style="font-size:12px;">${date}</td>
                <td class="px-4">
                    <span class="badge" style="${statusStyle}font-size:11px;font-weight:700;">${statusBadge}</span>
                </td>
                <td class="px-4 text-end">
                    ${actionButtons}
                </td>
            </tr>`;
        }).join("");
        if (window.lucide) lucide.createIcons();
    }

    document.getElementById("reviewPaginationInfo").innerText =
        `Showing ${filtered.length === 0 ? 0 : start + 1}–${Math.min(start + rowsPerPage, filtered.length)} of ${filtered.length}`;
    document.getElementById("reviewPageIndicator").innerText = `${currentPage} / ${totalPages}`;
    document.getElementById("reviewBtnPrev").disabled = currentPage === 1;
    document.getElementById("reviewBtnNext").disabled = currentPage === totalPages;
}

async function submitReviewAction(decisionId, reviewerId, status) {
    const comments = prompt(`Enter comments for marking this decision as ${status} (optional):`) || "";
    try {
        const res = await fetch(`${API_URL}/reviews/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                decision_id: decisionId,
                reviewer_id: reviewerId,
                status: status,
                comments: comments
            })
        });
        if (res.ok) {
            alert(`Review decision marked as ${status}!`);
            fetchReviews();
        } else {
            alert("Failed to submit review action.");
        }
    } catch (e) {
        console.error("Error submitting review action:", e);
        alert("Network error occurred.");
    }
}

function prevPage() { if (currentPage > 1) { currentPage--; renderTable(); } }
function nextPage() { currentPage++; renderTable(); }
