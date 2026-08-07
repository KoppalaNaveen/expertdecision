// =========================================================
// alternatives.js – Alternatives Overview Page
// =========================================================

let allAlternatives = [];
let currentPage     = 1;
const rowsPerPage   = 9;
let currentView     = "grid";

// Populated after decisions fetch
const decisionMap = {};

document.addEventListener("DOMContentLoaded", () => {
    loadAllAlternatives();
});

async function loadAllAlternatives() {
    try {
        // 1. Fetch all decisions
        const dRes = await fetch(`${API_URL}/decisions/`);
        if (!dRes.ok) throw new Error("Failed to load decisions");
        const decisions = await dRes.json();
        decisions.forEach(d => { decisionMap[d.id] = d; });

        // 2. Fetch alternatives for each decision in parallel
        const results = await Promise.allSettled(
            decisions.map(d => fetch(`${API_URL}/alternatives/decision/${d.id}`).then(r => r.ok ? r.json() : []))
        );

        allAlternatives = results
            .filter(r => r.status === "fulfilled")
            .flatMap(r => r.value)
            .map(alt => ({ ...alt, _decision: decisionMap[alt.decision_id] || null }));

        updateStats();
        renderView();
    } catch (err) {
        document.getElementById("altGridView").innerHTML = `
            <div class="col-12 text-center py-5 text-danger">
                <i data-lucide="alert-circle" style="width:24px;height:24px;" class="me-2"></i>${err.message}
            </div>`;
        if (window.lucide) lucide.createIcons();
    }
}

function updateStats() {
    document.getElementById("altStatTotal").innerText  = allAlternatives.length;
    document.getElementById("altStatLow").innerText    = allAlternatives.filter(a => a.risk_level === "Low").length;
    document.getElementById("altStatMedium").innerText = allAlternatives.filter(a => a.risk_level === "Medium").length;
    document.getElementById("altStatHigh").innerText   = allAlternatives.filter(a => a.risk_level === "High").length;
}

function filterAlts() {
    currentPage = 1;
    renderView();
}

function setView(view) {
    currentView = view;
    document.getElementById("viewGrid").className  = view === "grid"  ? "btn btn-primary px-3"          : "btn btn-outline-secondary px-3";
    document.getElementById("viewTable").className = view === "table" ? "btn btn-primary px-3"          : "btn btn-outline-secondary px-3";
    document.getElementById("altGridView").classList.toggle("d-none",  view !== "grid");
    document.getElementById("altTableView").classList.toggle("d-none", view !== "table");
    renderView();
}

function getFiltered() {
    const query = (document.getElementById("altSearch")?.value || "").toLowerCase();
    const risk  = document.getElementById("riskFilter")?.value || "";
    return allAlternatives.filter(a => {
        const matchRisk   = !risk || a.risk_level === risk;
        const decTitle    = a._decision?.title || "";
        const matchSearch = !query ||
            (a.title || "").toLowerCase().includes(query) ||
            (a.description || "").toLowerCase().includes(query) ||
            decTitle.toLowerCase().includes(query);
        return matchRisk && matchSearch;
    });
}

function renderView() {
    const filtered   = getFiltered();
    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;
    const start    = (currentPage - 1) * rowsPerPage;
    const pageData = filtered.slice(start, start + rowsPerPage);

    if (currentView === "grid") renderGrid(pageData);
    else                        renderTable(pageData);

    const info = filtered.length === 0 ? "No results" :
        `Showing ${start + 1}–${Math.min(start + rowsPerPage, filtered.length)} of ${filtered.length} alternatives`;
    document.getElementById("altPaginationInfo").innerText = info;
    document.getElementById("altBtnPrev").disabled = currentPage === 1;
    document.getElementById("altBtnNext").disabled = currentPage === totalPages;
}

function riskClass(risk) {
    const map = { Low: "risk-low", Medium: "risk-medium", High: "risk-high" };
    return map[risk] || "risk-unknown";
}

function renderGrid(items) {
    const grid = document.getElementById("altGridView");
    if (items.length === 0) {
        grid.innerHTML = `
            <div class="col-12" style="display:flex;flex-direction:column;align-items:center;padding:80px 0;text-align:center;">
                <i data-lucide="git-branch" style="width:48px;height:48px;color:#CBD5E1;" class="mb-3"></i>
                <h5 class="fw-semibold text-dark mb-1">No Alternatives Found</h5>
                <p class="text-muted">Adjust your filters or add alternatives to your decisions.</p>
            </div>`;
        if (window.lucide) lucide.createIcons();
        return;
    }

    grid.innerHTML = items.map(a => {
        let rawVal = parseFloat(a.feasibility_score);
        let feasPct = 0;
        if (!isNaN(rawVal) && rawVal > 0) {
            if (rawVal <= 1.0) feasPct = rawVal * 100;
            else if (rawVal <= 10.0) feasPct = rawVal * 10;
            else feasPct = rawVal;
            feasPct = Math.min(100, Math.max(0, Math.round(feasPct)));
        }
        const decisionTitle = a._decision?.title || `Decision #${a.decision_id}`;
        const decisionId    = a.decision_id;
        const cost   = a.cost != null ? `$${parseFloat(a.cost).toLocaleString("en-US", { minimumFractionDigits: 0 })}` : "—";
        const pros   = a.pros   ? a.pros.substring(0, 80)   : "";
        const cons   = a.cons   ? a.cons.substring(0, 80)   : "";
        return `
        <div class="col-md-6 col-lg-4">
            <div class="alt-card">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="fw-bold text-dark" style="font-size:14px;line-height:1.3;">${a.title || "Unnamed"}</span>
                    <span class="risk-pill ${riskClass(a.risk_level)}">${a.risk_level || "N/A"}</span>
                </div>
                ${a.description ? `<p class="text-muted mb-2" style="font-size:12px;">${a.description.substring(0,100)}${a.description.length > 100 ? "…" : ""}</p>` : ""}
                ${pros ? `<div class="mb-1" style="font-size:11px;"><span style="color:#059669;font-weight:700;">✓ Pros:</span> <span class="text-muted">${pros}${a.pros && a.pros.length > 80 ? "…" : ""}</span></div>` : ""}
                ${cons ? `<div class="mb-2" style="font-size:11px;"><span style="color:#DC2626;font-weight:700;">✗ Cons:</span> <span class="text-muted">${cons}${a.cons && a.cons.length > 80 ? "…" : ""}</span></div>` : ""}
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="cost-badge">${cost}</span>
                    <span class="text-muted" style="font-size:11px;">${a.feasibility_score != null ? `Feasibility: ${a.feasibility_score}/10` : ""}</span>
                </div>
                ${a.feasibility_score != null ? `<div class="feasibility-bar mb-3"><div class="feasibility-fill" style="width:${feasPct}%;"></div></div>` : ""}
                <div class="pt-2 border-top d-flex justify-content-between align-items-center">
                    <a href="/decision/${decisionId}" class="text-primary text-decoration-none" style="font-size:11px;font-weight:600;">
                        <i data-lucide="file-text" style="width:11px;height:11px;" class="me-1"></i>${decisionTitle.substring(0, 35)}${decisionTitle.length > 35 ? "…" : ""}
                    </a>
                    <a href="/decision/${decisionId}" class="btn btn-sm px-3" style="background:#EEF2FF;color:#4F46E5;font-size:11px;font-weight:600;border:none;">View Decision</a>
                </div>
            </div>
        </div>`;
    }).join("");
    if (window.lucide) lucide.createIcons();
}

function renderTable(items) {
    const tbody = document.getElementById("altTableBody");
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-5 text-muted">No alternatives found.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(a => {
        const cost        = a.cost != null ? `$${parseFloat(a.cost).toLocaleString()}` : "—";
        const feasibility = a.feasibility_score != null ? `${a.feasibility_score}/10` : "—";
        const decTitle    = a._decision?.title || `Decision #${a.decision_id}`;
        return `
        <tr>
            <td class="px-4 py-3">
                <div class="fw-semibold text-dark" style="font-size:13px;">${a.title || "Unnamed"}</div>
                ${a.description ? `<div class="text-muted" style="font-size:11px;">${a.description.substring(0,80)}…</div>` : ""}
            </td>
            <td class="px-4">
                <a href="/decision/${a.decision_id}" class="text-primary text-decoration-none fw-medium" style="font-size:12px;">
                    DEC-${a.decision_id}
                </a>
                <div class="text-muted" style="font-size:11px;">${decTitle.substring(0, 40)}${decTitle.length > 40 ? "…" : ""}</div>
            </td>
            <td class="px-4 fw-semibold text-dark" style="font-size:13px;">${cost}</td>
            <td class="px-4"><span class="risk-pill ${riskClass(a.risk_level)}">${a.risk_level || "N/A"}</span></td>
            <td class="px-4">
                <span class="fw-semibold text-dark" style="font-size:13px;">${feasibility}</span>
            </td>
            <td class="px-4 text-end">
                <a href="/decision/${a.decision_id}" class="btn btn-sm btn-outline-primary px-3" style="font-size:11px;">View Decision</a>
            </td>
        </tr>`;
    }).join("");
}

function prevPage() { if (currentPage > 1) { currentPage--; renderView(); } }
function nextPage() { currentPage++; renderView(); }
