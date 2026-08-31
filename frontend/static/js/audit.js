// =========================================================
// audit.js – Real-Time Admin Audit Logs
// =========================================================

let allLogs         = [];
let currentPage     = 1;
const rowsPerPage   = 15;
let isFetchingAudit = false;
let autoRefreshTimer = null;

// Action keywords to Icons
const ACTION_ICON = {
    create   : "plus-circle",
    update   : "edit-2",
    delete   : "trash-2",
    login    : "log-in",
    logout   : "log-out",
    approve  : "check-circle",
    reject   : "x-circle",
    submit   : "send",
    view     : "eye",
    export   : "download",
    access   : "shield-check",
    password : "key",
    otp      : "lock",
    role     : "award",
    backup   : "archive",
    restore  : "rotate-ccw",
    team     : "users",
    thread   : "message-square",
    comment  : "message-circle",
};

function getIcon(action = "") {
    const key = action.toLowerCase().split("_")[0].split(" ")[0].replace(/[^a-z]/g, "");
    return ACTION_ICON[key] || "activity";
}

const SEVERITY_STYLE = {
    Info     : { cls: "severity-info",     icon: "info" },
    Warning  : { cls: "severity-warning",  icon: "alert-triangle" },
    Critical : { cls: "severity-critical", icon: "alert-octagon" },
    Success  : { cls: "severity-success",  icon: "check-circle" },
};

document.addEventListener("DOMContentLoaded", () => {
    fetchAuditLogs(true);
    // Real-time live polling every 3 seconds when the browser tab is focused
    autoRefreshTimer = setInterval(() => {
        if (!document.hidden) {
            fetchAuditLogs(false);
        }
    }, 15000);
});

async function fetchAuditLogs(showSpinner = false) {
    if (isFetchingAudit) return;
    isFetchingAudit = true;

    const refreshIcon = document.getElementById("auditRefreshIcon");
    if (refreshIcon && showSpinner) {
        refreshIcon.style.animation = "spin 1s linear infinite";
    }

    try {
        const res = await fetch(`${API_URL}/audit/?limit=500`);
        if (!res.ok) {
            throw new Error(`Server returned ${res.status}`);
        }
        const data = await res.json();
        
        // Only re-render if data has changed
        const currentFirstId = allLogs.length > 0 ? allLogs[0].id : null;
        const newFirstId = data.length > 0 ? data[0].id : null;
        
        allLogs = Array.isArray(data) ? data : [];
        buildModuleFilter();
        updateStats();
        
        if (showSpinner || currentFirstId !== newFirstId || allLogs.length === 0) {
            renderTable();
        }

        const lastUpdatedEl = document.getElementById("auditLastUpdated");
        if (lastUpdatedEl) {
            lastUpdatedEl.innerText = `Last updated: ${new Date().toLocaleTimeString()}`;
        }
    } catch (err) {
        if (allLogs.length === 0) {
            document.getElementById("auditTableBody").innerHTML =
                `<tr><td colspan="5" class="text-center py-5 text-danger">
                    <i data-lucide="alert-circle" class="mb-2" style="width:28px;height:28px;"></i>
                    <div class="fw-bold">Failed to load live audit logs</div>
                    <div class="small text-muted">${err.message}</div>
                </td></tr>`;
            if (window.lucide) lucide.createIcons();
        }
    } finally {
        isFetchingAudit = false;
        if (refreshIcon) {
            refreshIcon.style.animation = "";
        }
    }
}

function buildModuleFilter() {
    const sel = document.getElementById("moduleFilter");
    if (!sel) return;
    const currentVal = sel.value;
    const modules = [...new Set(allLogs.map(l => l.module).filter(Boolean))].sort();
    
    sel.innerHTML = '<option value="">All Modules</option>';
    modules.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (m === currentVal) opt.selected = true;
        sel.appendChild(opt);
    });
}

function updateStats() {
    const total = allLogs.length;
    const info = allLogs.filter(l => l.severity === "Info" || l.severity === "Success").length;
    const warning = allLogs.filter(l => l.severity === "Warning").length;
    const critical = allLogs.filter(l => l.severity === "Critical").length;

    const totalEl = document.getElementById("auditTotal");
    const infoEl = document.getElementById("auditInfo");
    const warnEl = document.getElementById("auditWarning");
    const critEl = document.getElementById("auditCritical");

    if (totalEl) totalEl.innerText = total;
    if (infoEl) infoEl.innerText = info;
    if (warnEl) warnEl.innerText = warning;
    if (critEl) critEl.innerText = critical;
}

function filterAudit() {
    currentPage = 1;
    renderTable();
}

function getFiltered() {
    const query    = (document.getElementById("auditSearch")?.value || "").toLowerCase().trim();
    const severity = document.getElementById("severityFilter")?.value || "";
    const module   = document.getElementById("moduleFilter")?.value   || "";

    return allLogs.filter(l => {
        const matchSev    = !severity || l.severity === severity;
        const matchModule = !module   || l.module   === module;
        const matchSearch = !query    ||
            (l.user_name        || "").toLowerCase().includes(query) ||
            (l.user_role        || "").toLowerCase().includes(query) ||
            (l.employee_id      || "").toLowerCase().includes(query) ||
            (l.action           || "").toLowerCase().includes(query) ||
            (l.details          || "").toLowerCase().includes(query) ||
            (l.module           || "").toLowerCase().includes(query) ||
            (l.exact_timestamp  || "").toLowerCase().includes(query);
        return matchSev && matchModule && matchSearch;
    });
}

function renderTable() {
    const filtered   = getFiltered();
    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start    = (currentPage - 1) * rowsPerPage;
    const pageData = filtered.slice(start, start + rowsPerPage);

    const tbody = document.getElementById("auditTableBody");
    if (!tbody) return;

    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center py-5 text-muted">No audit logs match your search filters.</td></tr>`;
    } else {
        tbody.innerHTML = pageData.map((l, index) => {
            const sev   = SEVERITY_STYLE[l.severity] || SEVERITY_STYLE["Info"];
            const icon  = getIcon(l.action);
            const initials = (l.user_name || "SY").split(" ").map(p => p[0]).join("").substring(0, 2).toUpperCase();
            const timeAgo = l.time_ago || "Just now";
            const exactTime = l.exact_timestamp || l.created_at_str || "—";
            const empId = l.employee_id ? `<span class="badge bg-light text-secondary border ms-1" style="font-size:10px;">${l.employee_id}</span>` : "";

            return `
            <tr class="audit-row" style="cursor: pointer;" onclick="openLogDetails(${start + index})">
                <td class="px-4 py-3" style="white-space:nowrap;">
                    <div class="fw-bold text-dark" style="font-size:12px;">${timeAgo}</div>
                    <div class="text-muted font-monospace" style="font-size:10.5px;" title="${exactTime}">${exactTime}</div>
                </td>
                <td class="px-4">
                    <div class="d-flex align-items-center gap-2">
                        <div style="width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#4F46E5,#7C3AED);display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:white;flex-shrink:0;">${initials}</div>
                        <div>
                            <div class="fw-semibold text-dark d-flex align-items-center" style="font-size:13px;">${l.user_name || "System"} ${empId}</div>
                            <div class="text-muted" style="font-size:11px;">${l.user_role || "Administrator"}</div>
                        </div>
                    </div>
                </td>
                <td class="px-4">
                    <div class="d-flex align-items-center gap-2.5">
                        <div class="audit-icon-wrap" style="background:#F1F5F9;">
                            <i data-lucide="${icon}" style="width:15px;height:15px;color:#475569;"></i>
                        </div>
                        <div style="min-width:0;">
                            <div class="text-dark fw-medium" style="font-size:13px;">${l.action}</div>
                            ${l.details && l.details !== "—" ? `<div class="text-muted text-truncate" style="font-size:11px; max-width: 380px;">${l.details}</div>` : ""}
                        </div>
                    </div>
                </td>
                <td class="px-4">
                    <span style="background:#EEF2FF;color:#4F46E5;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;border:1px solid #E0E7FF;">${l.module || "General"}</span>
                </td>
                <td class="px-4">
                    <span class="badge ${sev.cls}" style="font-size:11px;font-weight:700;padding:4px 8px;">${l.severity}</span>
                </td>
            </tr>`;
        }).join("");
        if (window.lucide) lucide.createIcons();
    }

    const paginationEl = document.getElementById("auditPaginationInfo");
    if (paginationEl) {
        paginationEl.innerText =
            `Showing ${filtered.length === 0 ? 0 : start + 1}–${Math.min(start + rowsPerPage, filtered.length)} of ${filtered.length} live events`;
    }
    const prevBtn = document.getElementById("auditBtnPrev");
    const nextBtn = document.getElementById("auditBtnNext");
    if (prevBtn) prevBtn.disabled = currentPage === 1;
    if (nextBtn) nextBtn.disabled = currentPage === totalPages;
}

function openLogDetails(index) {
    const filtered = getFiltered();
    const log = filtered[index];
    if (!log) return;

    document.getElementById("detailModalAction").innerText = log.action || "—";
    document.getElementById("detailModalUser").innerText = `${log.user_name || "System"} (${log.user_role || "Administrator"} · ${log.employee_id || "SYS"})`;
    document.getElementById("detailModalModule").innerText = log.module || "System";
    document.getElementById("detailModalTime").innerText = log.exact_timestamp || log.created_at_str || "—";
    
    const sev = SEVERITY_STYLE[log.severity] || SEVERITY_STYLE["Info"];
    document.getElementById("detailModalSeverity").innerHTML = `<span class="badge ${sev.cls}">${log.severity}</span>`;
    document.getElementById("detailModalPayload").innerText = log.details || "No additional payload details recorded.";

    const modal = new bootstrap.Modal(document.getElementById("auditDetailModal"));
    modal.show();
}

function prevPage() { if (currentPage > 1) { currentPage--; renderTable(); } }
function nextPage() { currentPage++; renderTable(); }

function exportCSV() {
    const filtered = getFiltered();
    const header   = ["Log ID", "Exact Time (UTC)", "Time Ago", "User", "Employee ID", "Role", "Module", "Action", "Severity", "Details"].join(",");
    const rows     = filtered.map(l =>
        [
            l.id,
            `"${l.exact_timestamp || ""}"`,
            `"${l.time_ago || ""}"`,
            `"${l.user_name || ""}"`,
            `"${l.employee_id || ""}"`,
            `"${l.user_role || ""}"`,
            `"${l.module || ""}"`,
            `"${(l.action || "").replace(/"/g, '""')}"`,
            `"${l.severity || ""}"`,
            `"${(l.details || "").replace(/"/g, '""')}"`
        ].join(",")
    );
    const csv  = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `edrp_live_audit_logs_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
