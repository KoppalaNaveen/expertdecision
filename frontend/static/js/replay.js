// =========================================================
// replay.js – Decision Replays Page
// =========================================================

let allReplays  = [];
let currentPage = 1;
let rowsPerPage = 12;

function changeReplayPageSize(size) {
    if (size === 'all') {
        rowsPerPage = 999999;
    } else {
        rowsPerPage = parseInt(size, 10) || 12;
    }
    currentPage = 1;
    renderReplays();
}
window.changeReplayPageSize = changeReplayPageSize;

const ACTION_COLORS = {
    "view"    : { bg: "#EEF2FF", color: "#4F46E5", icon: "eye" },
    "create"  : { bg: "#ECFDF5", color: "#059669", icon: "plus-circle" },
    "update"  : { bg: "#FFF7ED", color: "#D97706", icon: "edit-2" },
    "delete"  : { bg: "#FEF2F2", color: "#DC2626", icon: "trash-2" },
    "approve" : { bg: "#ECFDF5", color: "#059669", icon: "check-circle" },
    "reject"  : { bg: "#FEF2F2", color: "#DC2626", icon: "x-circle" },
    "submit"  : { bg: "#EFF6FF", color: "#2563EB", icon: "send" },
    "replay"  : { bg: "#F5F3FF", color: "#7C3AED", icon: "play-circle" },
};

function getActionStyle(action = "") {
    const key = action.toLowerCase().split("_")[0];
    return ACTION_COLORS[key] || { bg: "#F1F5F9", color: "#64748B", icon: "activity" };
}

document.addEventListener("DOMContentLoaded", () => {
    fetchReplays();
});

async function fetchReplays() {
    try {
        const res = await fetch(`${API_URL}/replays/`);
        if (!res.ok) throw new Error("Failed to load replays");
        allReplays = await res.json();
        populateActionFilter();
        updateStats();
        renderCards();
    } catch (err) {
        document.getElementById("replayContainer").innerHTML = `
            <div class="col-12 empty-state">
                <i data-lucide="alert-circle" style="width:40px;height:40px;color:#EF4444;" class="mb-3"></i>
                <h5 class="fw-semibold text-dark mb-1">Failed to Load Replays</h5>
                <p class="text-muted">${err.message}</p>
                <button class="btn btn-primary btn-sm mt-2" onclick="fetchReplays()">
                    <i data-lucide="refresh-cw" style="width:14px;height:14px;" class="me-1"></i>Retry
                </button>
            </div>`;
        if (window.lucide) lucide.createIcons();
    }
}

function populateActionFilter() {
    const uniqueActions = [...new Set(allReplays.map(r => r.action))].sort();
    const select = document.getElementById("actionFilter");
    uniqueActions.forEach(a => {
        const opt = document.createElement("option");
        opt.value = a;
        opt.textContent = a.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
        select.appendChild(opt);
    });
}

function updateStats() {
    document.getElementById("statTotalReplays").innerText     = allReplays.length;
    document.getElementById("statUniqueDecisions").innerText  = new Set(allReplays.map(r => r.decision_id)).size;
    document.getElementById("statActionTypes").innerText      = new Set(allReplays.map(r => r.action)).size;
}

function filterReplays() {
    currentPage = 1;
    renderCards();
}

function getFilteredReplays() {
    const query  = (document.getElementById("replaySearch")?.value || "").toLowerCase();
    const action = document.getElementById("actionFilter")?.value || "";
    return allReplays.filter(r => {
        const matchAction = !action || r.action === action;
        const matchSearch = !query ||
            r.action.toLowerCase().includes(query) ||
            (`DEC-${r.decision_id}`).includes(query) ||
            (`#${r.performed_by}`).includes(query);
        return matchAction && matchSearch;
    });
}

function renderCards() {
    const filtered   = getFilteredReplays();
    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start    = (currentPage - 1) * rowsPerPage;
    const pageData = filtered.slice(start, start + rowsPerPage);

    const container = document.getElementById("replayContainer");

    if (pageData.length === 0) {
        container.innerHTML = `
            <div class="col-12 empty-state">
                <i data-lucide="play-circle" style="width:48px;height:48px;color:#CBD5E1;" class="mb-3"></i>
                <h5 class="fw-semibold text-dark mb-1">No Replays Found</h5>
                <p class="text-muted">No replay records match your current filters.</p>
            </div>`;
        if (window.lucide) lucide.createIcons();
    } else {
        container.innerHTML = pageData.map(r => {
            const style  = getActionStyle(r.action);
            const label  = r.action.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
            return `
            <div class="col-md-6 col-lg-4">
                <div class="replay-card">
                    <div class="d-flex align-items-start gap-3">
                        <div class="replay-icon-wrap" style="background:${style.bg};">
                            <i data-lucide="${style.icon}" style="width:20px;height:20px;color:${style.color};"></i>
                        </div>
                        <div class="flex-grow-1 min-w-0">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <span class="replay-action-pill" style="background:${style.bg};color:${style.color};">${label}</span>
                                <a href="/decision/${r.decision_id}" class="text-muted text-decoration-none" style="font-size:11px;font-weight:600;">
                                    DEC-${r.decision_id}
                                </a>
                            </div>
                            <div class="d-flex align-items-center gap-2 mt-2">
                                <div style="width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#667EEA,#764BA2);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:white;">U${r.performed_by}</div>
                                <span class="text-muted" style="font-size:12px;">User #${r.performed_by}</span>
                            </div>
                            <div class="mt-2">
                                <a href="/decision/${r.decision_id}" class="btn btn-sm px-3 fw-semibold" style="font-size:11px;background:#EEF2FF;color:#4F46E5;border:none;">
                                    <i data-lucide="external-link" style="width:11px;height:11px;" class="me-1"></i>View Decision
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join("");
        if (window.lucide) lucide.createIcons();
    }

    const info = filtered.length === 0 ? "No results" :
        `Showing ${start + 1}–${Math.min(start + rowsPerPage, filtered.length)} of ${filtered.length} replays`;
    document.getElementById("replayPaginationInfo").innerText = info;
    document.getElementById("replayBtnPrev").disabled = currentPage === 1;
    document.getElementById("replayBtnNext").disabled = currentPage === totalPages;
}

function prevPage() { if (currentPage > 1) { currentPage--; renderCards(); } }
function nextPage() { currentPage++; renderCards(); }
