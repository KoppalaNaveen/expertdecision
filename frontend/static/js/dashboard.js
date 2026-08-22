// =========================================================
// dashboard.js – Reports & Analytics Page
// =========================================================

let statusChartInstance = null;
let trendChartInstance  = null;

document.addEventListener("DOMContentLoaded", () => {
    loadDashboardData();
});

async function loadDashboardData() {
    try {
        const res = await fetch(`${API_URL}/dashboard/${USER_ID}`);
        if (!res.ok) throw new Error("Failed to load dashboard data");
        const data = await res.json();
        renderStats(data);
        renderStatusChart(data);
        renderTrendChart(data);
        renderApprovalFlow(data);
        renderRecentDecisions(data);
    } catch (err) {
        console.error("Dashboard load error:", err.message);
    }
}

function renderStats(data) {
    const total    = data.total_decisions    || 0;
    const approved = data.approved_decisions || 0;
    const pending  = data.pending_reviews    || 0;
    const rejected = data.rejected_decisions || 0;

    document.getElementById("rptTotal").innerText    = total;
    document.getElementById("rptApproved").innerText = approved;
    document.getElementById("rptPending").innerText  = pending;
    document.getElementById("rptRejected").innerText = rejected;

    const pct = total > 0 ? Math.round(approved / total * 100) : 0;
    const el  = document.getElementById("rptApprovedPct");
    if (el) el.innerText = `↑ ${pct}% approval rate`;
}

function renderStatusChart(data) {
    const approved = data.approved_decisions || 0;
    const pending  = data.pending_reviews    || 0;
    const rejected = data.rejected_decisions || 0;
    const draft    = data.draft_decisions    || 0;

    if (statusChartInstance) statusChartInstance.destroy();

    const ctx = document.getElementById("statusChart")?.getContext("2d");
    if (!ctx) return;

    statusChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels  : ["Approved", "Pending Review", "Rejected", "Draft"],
            datasets: [{
                data           : [approved, pending, rejected, draft],
                backgroundColor: ["#059669", "#D97706", "#DC2626", "#94A3B8"],
                borderWidth    : 0,
                hoverOffset    : 6,
            }]
        },
        options: {
            cutout  : "72%",
            plugins : { legend: { display: false } },
            animation: { animateScale: true }
        }
    });

    const colors = ["#059669", "#D97706", "#DC2626", "#94A3B8"];
    const labels = ["Approved", "Pending", "Rejected", "Draft"];
    const vals   = [approved, pending, rejected, draft];
    document.getElementById("statusLegend").innerHTML = labels.map((l, i) => `
        <div class="d-flex align-items-center gap-1">
            <div style="width:10px;height:10px;border-radius:50%;background:${colors[i]};"></div>
            <span class="text-muted">${l}: <strong>${vals[i]}</strong></span>
        </div>`).join("");
}

function renderTrendChart(data) {
    if (trendChartInstance) trendChartInstance.destroy();

    const ctx = document.getElementById("trendChart")?.getContext("2d");
    if (!ctx) return;

    // Use live decision trends directly from backend database
    const trends = data.decision_trends || {};
    const labels = trends.labels && trends.labels.length > 0 ? trends.labels : ["Mar", "Apr", "May", "Jun", "Jul", "Aug"];
    const created  = trends.submitted || [0, 0, 0, 0, 0, 0];
    const approved = trends.approved  || [0, 0, 0, 0, 0, 0];
    const pending  = trends.pending   || [0, 0, 0, 0, 0, 0];

    trendChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [
                { label: "Created",  data: created,  backgroundColor: "#93C5FD", borderRadius: 6, borderSkipped: false },
                { label: "Approved", data: approved, backgroundColor: "#34D399", borderRadius: 6, borderSkipped: false },
                { label: "Pending",  data: pending,  backgroundColor: "#FBBF24", borderRadius: 6, borderSkipped: false },
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
                tooltip: { mode: "index", intersect: false }
            },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: "#F1F5F9" }, ticks: { precision: 0, stepSize: 1, beginAtZero: true } }
            }
        }
    });
}

function renderApprovalFlow(data) {
    const container = document.getElementById("approvalFlowContainer");
    const flow = data.approval_flow || [];

    if (flow.length === 0) {
        container.innerHTML = `<p class="text-muted" style="font-size:13px;">No approval flow data available.</p>`;
        return;
    }

    container.innerHTML = flow.map(f => `
        <div class="mb-3">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-semibold text-dark" style="font-size:13px;">${f.stage}</span>
                <span class="text-muted" style="font-size:12px;">${f.count} decisions (${f.pct}%)</span>
            </div>
            <div style="height:8px;border-radius:4px;background:#F1F5F9;overflow:hidden;">
                <div style="height:100%;width:${f.pct}%;background:${f.color || "#2563EB"};border-radius:4px;transition:width 0.6s ease;"></div>
            </div>
        </div>`).join("");
}

function renderRecentDecisions(data) {
    const tbody    = document.getElementById("recentDecisionsBody");
    const recents  = data.recent_decisions || [];

    if (recents.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">No recent decisions.</td></tr>`;
        return;
    }

    tbody.innerHTML = recents.map(d => {
        let badgeStyle;
        if (d.status === "Approved")      badgeStyle = "background:#ECFDF5;color:#059669;";
        else if (d.status === "Rejected") badgeStyle = "background:#FEF2F2;color:#DC2626;";
        else if (d.status === "Draft")    badgeStyle = "background:#F1F5F9;color:#64748B;";
        else                              badgeStyle = "background:#FFF7ED;color:#D97706;";
        return `
        <tr>
            <td class="px-3 py-2">
                <a href="/decision/${d.id}" class="fw-bold text-primary text-decoration-none" style="font-size:12px;">DEC-${d.id}</a>
            </td>
            <td class="px-3 text-dark fw-medium" style="font-size:13px;max-width:200px;">
                <div class="text-truncate">${d.title}</div>
            </td>
            <td class="px-3 text-muted" style="font-size:12px;">${d.department || "—"}</td>
            <td class="px-3 text-muted" style="font-size:12px;">${d.approver_name || "—"}</td>
            <td class="px-3 text-muted" style="font-size:12px;">${d.created_at_str || "—"}</td>
            <td class="px-3">
                <span class="badge" style="${badgeStyle}font-size:10px;font-weight:700;">${d.status}</span>
            </td>
        </tr>`;
    }).join("");
}

function exportReport() {
    window.print();
}
