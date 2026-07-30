// =========================================================
// audit.js – Audit Log Page
// =========================================================

let allLogs     = [];
let currentPage = 1;
const rowsPerPage = 15;

// Icons per action keyword
const ACTION_ICON = {
    create  : "plus-circle",
    update  : "edit-2",
    delete  : "trash-2",
    login   : "log-in",
    logout  : "log-out",
    approve : "check-circle",
    reject  : "x-circle",
    submit  : "send",
    view    : "eye",
    export  : "download",
};

function getIcon(action = "") {
    const key = action.toLowerCase().split("_")[0].split(" ")[0];
    return ACTION_ICON[key] || "activity";
}

const SEVERITY_STYLE = {
    Info     : { cls: "severity-info",     icon: "info" },
    Warning  : { cls: "severity-warning",  icon: "alert-triangle" },
    Critical : { cls: "severity-critical", icon: "alert-octagon" },
    Success  : { cls: "severity-success",  icon: "check-circle" },
};

document.addEventListener("DOMContentLoaded", () => {
    fetchAuditLogs();
    // Auto-refresh lively every 5 seconds to show live logins and events
    setInterval(fetchAuditLogs, 5000);
});

async function fetchAuditLogs() {
    try {
        let logs = [];
        const res = await fetch(`${API_URL}/audit/`);
        if (res.ok) {
            logs = await res.json();
        } else {
            const dRes = await fetch(`${API_URL}/dashboard/1`);
            if (dRes.ok) {
                const data = await dRes.json();
                logs = data.recent_audit_logs || [];
            }
        }

        // Supplement with decision events if logs are sparse
        if (logs.length < 5) {
            const dRes = await fetch(`${API_URL}/decisions/`);
            if (dRes.ok) {
                const decisions = await dRes.json();
                decisions.slice(0, 20).forEach(d => {
                    logs.push({
                        user_name : d.creator_name || "Unknown",
                        action    : `Created decision: ${d.title.substring(0, 40)}`,
                        module    : "Decisions",
                        time_ago  : new Date(d.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
                        severity  : "Info",
                    });
                    if (d.status === "Approved") {
                        logs.push({
                            user_name : "Reviewer",
                            action    : `Approved: ${d.title.substring(0, 40)}`,
                            module    : "Reviews",
                            time_ago  : "recently",
                            severity  : "Success",
                        });
                    }
                    if (d.status === "Rejected") {
                        logs.push({
                            user_name : "Reviewer",
                            action    : `Rejected: ${d.title.substring(0, 40)}`,
                            module    : "Reviews",
                            time_ago  : "recently",
                            severity  : "Warning",
                        });
                    }
                });
            }
        }

        allLogs = logs;
        buildModuleFilter();
        updateStats();
        renderTable();
    } catch (err) {
        document.getElementById("auditTableBody").innerHTML =
            `<tr><td colspan="5" class="text-center py-5 text-danger">Failed to load audit logs: ${err.message}</td></tr>`;
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
    document.getElementById("auditTotal").innerText    = allLogs.length;
    document.getElementById("auditInfo").innerText     = allLogs.filter(l => l.severity === "Info" || l.severity === "Success").length;
    document.getElementById("auditWarning").innerText  = allLogs.filter(l => l.severity === "Warning").length;
    document.getElementById("auditCritical").innerText = allLogs.filter(l => l.severity === "Critical").length;
}

function filterAudit() {
    currentPage = 1;
    renderTable();
}

function getFiltered() {
    const query    = (document.getElementById("auditSearch")?.value || "").toLowerCase();
    const severity = document.getElementById("severityFilter")?.value || "";
    const module   = document.getElementById("moduleFilter")?.value   || "";

    return allLogs.filter(l => {
        const matchSev    = !severity || l.severity === severity;
        const matchModule = !module   || l.module   === module;
        const matchSearch = !query    ||
            (l.user_name || "").toLowerCase().includes(query) ||
            (l.action    || "").toLowerCase().includes(query) ||
            (l.module    || "").toLowerCase().includes(query);
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
    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center py-5 text-muted">No audit logs match your filters.</td></tr>`;
    } else {
        tbody.innerHTML = pageData.map(l => {
            const sev   = SEVERITY_STYLE[l.severity] || SEVERITY_STYLE["Info"];
            const icon  = getIcon(l.action);
            const initials = (l.user_name || "SY").split(" ").map(p => p[0]).join("").substring(0, 2).toUpperCase();
            return `
            <tr class="audit-row">
                <td class="px-4 py-3" style="white-space:nowrap;">
                    <div class="fw-semibold text-dark" style="font-size:12px;">${l.time_ago || "Just now"}</div>
                    <div class="text-muted" style="font-size:10.5px;">${l.created_at_str || "—"}</div>
                </td>
                <td class="px-4">
                    <div class="d-flex align-items-center gap-2">
                        <div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#667EEA,#764BA2);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:white;">${initials}</div>
                        <span class="fw-medium text-dark" style="font-size:13px;">${l.user_name || "System"}</span>
                    </div>
                </td>
                <td class="px-4">
                    <div class="d-flex align-items-center gap-2">
                        <div class="audit-icon-wrap" style="background:#F1F5F9;">
                            <i data-lucide="${icon}" style="width:14px;height:14px;color:#64748B;"></i>
                        </div>
                        <span class="text-dark" style="font-size:13px;">${l.action}</span>
                    </div>
                </td>
                <td class="px-4">
                    <span style="background:#EEF2FF;color:#4F46E5;font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;">${l.module || "General"}</span>
                </td>
                <td class="px-4">
                    <span class="badge ${sev.cls}" style="font-size:11px;font-weight:700;">${l.severity}</span>
                </td>
            </tr>`;
        }).join("");
        if (window.lucide) lucide.createIcons();
    }

    document.getElementById("auditPaginationInfo").innerText =
        `Showing ${filtered.length === 0 ? 0 : start + 1}–${Math.min(start + rowsPerPage, filtered.length)} of ${filtered.length} events`;
    document.getElementById("auditBtnPrev").disabled = currentPage === 1;
    document.getElementById("auditBtnNext").disabled = currentPage === totalPages;
}

function prevPage() { if (currentPage > 1) { currentPage--; renderTable(); } }
function nextPage() { currentPage++; renderTable(); }

function exportCSV() {
    const filtered = getFiltered();
    const header   = ["Time", "User", "Action", "Module", "Severity"].join(",");
    const rows     = filtered.map(l =>
        [l.time_ago, l.user_name, `"${l.action}"`, l.module, l.severity].join(",")
    );
    const csv  = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "edrp_audit_log.csv";
    a.click();
    URL.revokeObjectURL(url);
}
