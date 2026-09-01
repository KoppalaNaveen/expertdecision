// =========================================================
// dashboard.js – Reports & Analytics Page
// =========================================================

let statusChartInstance = null;
let trendChartInstance  = null;

document.addEventListener("DOMContentLoaded", () => {
    loadDashboardData();
});

let cachedDashboardData = null;

async function loadDashboardData() {
    try {
        const res = await fetch(`${API_URL}/dashboard/${USER_ID}`);
        if (!res.ok) throw new Error("Failed to load dashboard data");
        const data = await res.json();
        cachedDashboardData = data;
        renderStats(data);
        renderStatusChart(data);
        renderTrendChart(data);
        renderApprovalFlow(data);
        renderRecentDecisions(data);
    } catch (err) {
        console.error("Dashboard load error:", err.message);
    }
}

function exportReport() {
    exportReportAs('pdf');
}

function exportReportAs(format = 'pdf') {
    const data = cachedDashboardData || {};
    const total = data.total_decisions || 0;
    const approved = data.approved_decisions || 0;
    const pending = data.pending_reviews || 0;
    const rejected = data.rejected_decisions || 0;
    const draft = data.draft_decisions || 0;
    const approvalRate = total > 0 ? `${Math.round(approved / total * 100)}%` : '0%';
    const recents = data.recent_decisions || [];
    const dateStr = new Date().toISOString().slice(0, 10);
    const timeStr = new Date().toLocaleString();

    if (format === 'csv') {
        const headers = ["Metric / Field", "Value / Detail"];
        const summaryRows = [
            ["Platform", "Expert Decision Replay Platform (EDRP)"],
            ["Report Type", "Reports & Analytics Executive Summary"],
            ["Generated At", `"${timeStr}"`],
            ["Total Decisions", total],
            ["Approved Decisions", approved],
            ["Pending Review", pending],
            ["Rejected Decisions", rejected],
            ["Draft Decisions", draft],
            ["Overall Approval Rate", `"${approvalRate}"`],
            [],
            ["--- DECISION DATASET ---", ""],
            ["Decision ID", "Title", "Department", "Approver", "Created Date", "Status"]
        ];

        const dataRows = recents.map(d => [
            `DEC-${d.id}`,
            `"${(d.title || '').replace(/"/g, '""')}"`,
            `"${(d.department || '').replace(/"/g, '""')}"`,
            `"${(d.approver_name || '').replace(/"/g, '""')}"`,
            `"${d.created_at_str || ''}"`,
            `"${d.status || ''}"`
        ]);

        const csvContent = summaryRows.map(r => r.join(",")).join("\n") + "\n" + dataRows.map(r => r.join(",")).join("\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `EDRP_Reports_Analytics_${dateStr}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        if (typeof showCenterNotification === 'function') {
            showCenterNotification("Reports & Analytics CSV downloaded successfully!", "success", "Export Complete");
        }
    } 
    else if (format === 'excel') {
        if (typeof XLSX !== 'undefined') {
            const wb = XLSX.utils.book_new();

            // Sheet 1: Summary Metrics
            const summaryData = [
                ["Executive Metrics", "Values"],
                ["Platform", "Expert Decision Replay Platform (EDRP)"],
                ["Report Type", "Reports & Analytics Summary"],
                ["Generated Date", timeStr],
                ["Total Decisions", total],
                ["Approved Decisions", approved],
                ["Pending Decisions", pending],
                ["Rejected Decisions", rejected],
                ["Draft Decisions", draft],
                ["Approval Rate", approvalRate]
            ];
            const wsSummary = XLSX.utils.aoa_to_sheet(summaryData);
            XLSX.utils.book_append_sheet(wb, wsSummary, "Summary_KPIs");

            // Sheet 2: Recent Decisions List
            const decisionsData = [
                ["Decision ID", "Title", "Department", "Approver", "Date", "Status"]
            ];
            recents.forEach(d => {
                decisionsData.push([
                    `DEC-${d.id}`,
                    d.title || "",
                    d.department || "—",
                    d.approver_name || "—",
                    d.created_at_str || "—",
                    d.status || ""
                ]);
            });
            const wsDecisions = XLSX.utils.aoa_to_sheet(decisionsData);
            XLSX.utils.book_append_sheet(wb, wsDecisions, "Decisions_Data");

            XLSX.writeFile(wb, `EDRP_Reports_Analytics_${dateStr}.xlsx`);
            if (typeof showCenterNotification === 'function') {
                showCenterNotification("Reports & Analytics Excel spreadsheet downloaded successfully!", "success", "Export Complete");
            }
        } else {
            // Fallback to CSV if XLSX library is not yet loaded
            exportReportAs('csv');
        }
    } 
    else if (format === 'pdf') {
        // Build a dedicated print/PDF element for crystal clear layout
        const reportEl = document.createElement("div");
        reportEl.style.padding = "24px";
        reportEl.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
        reportEl.style.color = "#0f172a";
        reportEl.style.background = "#ffffff";

        let decisionsRowsHtml = recents.map(d => `
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 12px; font-weight: 700; color: #2563eb;">DEC-${d.id}</td>
                <td style="padding: 8px 12px; font-weight: 600;">${escapeHtml(d.title)}</td>
                <td style="padding: 8px 12px; color: #64748b;">${escapeHtml(d.department || "—")}</td>
                <td style="padding: 8px 12px; color: #64748b;">${escapeHtml(d.approver_name || "—")}</td>
                <td style="padding: 8px 12px; color: #64748b;">${escapeHtml(d.created_at_str || "—")}</td>
                <td style="padding: 8px 12px;"><span style="display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700; background:#f1f5f9;">${escapeHtml(d.status)}</span></td>
            </tr>
        `).join("");

        if (!decisionsRowsHtml) {
            decisionsRowsHtml = `<tr><td colspan="6" style="padding: 16px; text-align: center; color: #94a3b8;">No decisions available</td></tr>`;
        }

        reportEl.innerHTML = `
            <div style="border-bottom: 2px solid #2563eb; padding-bottom: 14px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: flex-end;">
                <div>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 800; color: #0f172a;">Expert Decision Replay Platform</h1>
                    <p style="margin: 4px 0 0; color: #64748b; font-size: 13px;">Executive Reports & Analytics Summary</p>
                </div>
                <div style="text-align: right; font-size: 11px; color: #64748b;">
                    <div><strong>Generated:</strong> ${timeStr}</div>
                    <div><strong>Status:</strong> Live Organizational Data</div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px;">
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #4f46e5;">${total}</div>
                    <div style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Total Decisions</div>
                </div>
                <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 12px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #059669;">${approved}</div>
                    <div style="font-size: 11px; color: #059669; font-weight: 600; text-transform: uppercase;">Approved (${approvalRate})</div>
                </div>
                <div style="background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; padding: 12px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #d97706;">${pending}</div>
                    <div style="font-size: 11px; color: #d97706; font-weight: 600; text-transform: uppercase;">Pending Review</div>
                </div>
                <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #dc2626;">${rejected}</div>
                    <div style="font-size: 11px; color: #dc2626; font-weight: 600; text-transform: uppercase;">Rejected</div>
                </div>
            </div>

            <div style="margin-bottom: 24px;">
                <h3 style="font-size: 15px; font-weight: 700; margin-bottom: 10px; color: #0f172a;">Decisions Dataset</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
                    <thead>
                        <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0; color: #475569; font-size: 11px; text-transform: uppercase;">
                            <th style="padding: 8px 12px;">ID</th>
                            <th style="padding: 8px 12px;">Title</th>
                            <th style="padding: 8px 12px;">Department</th>
                            <th style="padding: 8px 12px;">Approver</th>
                            <th style="padding: 8px 12px;">Date</th>
                            <th style="padding: 8px 12px;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${decisionsRowsHtml}
                    </tbody>
                </table>
            </div>

            <div style="border-top: 1px solid #e2e8f0; padding-top: 12px; font-size: 11px; color: #94a3b8; text-align: center;">
                &copy; 2026 Expert Decision Replay Platform (EDRP). Confidential Organizational Intelligence Report.
            </div>
        `;

        if (typeof html2pdf !== 'undefined') {
            const opt = {
                margin:       10,
                filename:     `EDRP_Reports_Analytics_${dateStr}.pdf`,
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2, useCORS: true },
                jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };
            html2pdf().from(reportEl).set(opt).save().then(() => {
                if (typeof showCenterNotification === 'function') {
                    showCenterNotification("Reports & Analytics PDF generated successfully!", "success", "Export Complete");
                }
            });
        } else {
            // Native print dialog fallback
            window.print();
        }
    }
}
