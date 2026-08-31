// =========================================================
// team.js – Production-Level Enterprise Team Management UI
// =========================================================

const API = "/api/teams";

let allTeams = [];
let allAssignableEmployees = [];
let selectedEmployeeIds = new Set();
let currentEmpFilter = "all"; // 'all', 'unassigned', 'selected'
let currentPage = 1;
let rowsPerPage = 6;

function changeTeamPageSize(size) {
    if (size === 'all') {
        rowsPerPage = 999999;
    } else {
        rowsPerPage = parseInt(size, 10) || 6;
    }
    currentPage = 1;
    renderTeamTable();
}
window.changeTeamPageSize = changeTeamPageSize;

window.onload = function() {
    loadTeams();
    loadAssignableEmployees();
};

document.addEventListener("DOMContentLoaded", function() {
    const addBtn = document.querySelector('button[data-bs-target="#teamModal"]');
    if(addBtn) {
        addBtn.addEventListener('click', openAddModal);
    }
});

// -------------------------------------------------------------
// 1. DATA LOADING & KPI STATS
// -------------------------------------------------------------
function loadTeams() {
    fetch(API)
        .then(r => {
            if(!r.ok) throw new Error("Failed to load teams");
            return r.json();
        })
        .then(data => {
            allTeams = Array.isArray(data) ? data : [];
            updateKpiStats();
            renderTable();
        })
        .catch(err => {
            console.error("Team load error:", err);
            const tbody = document.getElementById("teamTable");
            if(tbody) {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center py-5 text-danger">Failed to load teams from server.</td></tr>`;
            }
            if(typeof showToast === 'function') showToast("Failed to load teams", "danger");
        });
}

function loadAssignableEmployees() {
    fetch(`${API}/assignable-employees`)
        .then(r => {
            if(!r.ok) throw new Error("Failed to fetch assignable employees");
            return r.json();
        })
        .then(data => {
            allAssignableEmployees = Array.isArray(data) ? data : [];
            updateKpiStats();
            if(document.getElementById("teamModal") && document.getElementById("teamModal").classList.contains("show")) {
                renderEmployeeSelectionList();
            }
        })
        .catch(err => {
            console.warn("Could not pre-load assignable employees:", err);
        });
}

function updateKpiStats() {
    const totalTeams = allTeams.length;
    
    // Calculate assigned and unassigned counts
    let totalAssigned = 0;
    allTeams.forEach(t => {
        totalAssigned += (t.employees ? t.employees.length : (t.employee_count || 0));
    });

    let totalActiveEmps = allAssignableEmployees.length;
    let unassignedCount = 0;
    if (totalActiveEmps > 0) {
        unassignedCount = allAssignableEmployees.filter(e => !e.team_id).length;
    } else {
        unassignedCount = Math.max(0, totalActiveEmps - totalAssigned);
    }

    const avgSize = totalTeams > 0 ? (totalAssigned / totalTeams).toFixed(1) : "0";

    const elTotal = document.getElementById("statTotalTeams");
    const elAssigned = document.getElementById("statAssignedMembers");
    const elUnassigned = document.getElementById("statUnassignedMembers");
    const elAvg = document.getElementById("statAvgTeamSize");

    if (elTotal) elTotal.innerText = totalTeams;
    if (elAssigned) elAssigned.innerText = totalAssigned;
    if (elUnassigned) elUnassigned.innerText = unassignedCount;
    if (elAvg) elAvg.innerText = avgSize;
}

// -------------------------------------------------------------
// 2. MAIN TABLE RENDERING & SEARCH
// -------------------------------------------------------------
function handleSearch() {
    currentPage = 1;
    renderTable();
}

function renderTable() {
    const searchInput = document.getElementById("teamSearch");
    const searchStr = searchInput ? searchInput.value.toLowerCase().trim() : "";
    
    // Filter by team name, description, or assigned employee name/id
    const filteredTeams = allTeams.filter(team => {
        const nameMatch = team.team_name && team.team_name.toLowerCase().includes(searchStr);
        const descMatch = team.description && team.description.toLowerCase().includes(searchStr);
        const empMatch = team.employees && team.employees.some(e => 
            (e.full_name && e.full_name.toLowerCase().includes(searchStr)) || 
            (e.employee_id && e.employee_id.toLowerCase().includes(searchStr))
        );
        return nameMatch || descMatch || empMatch;
    });

    // Pagination
    const totalPages = Math.ceil(filteredTeams.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const pageInfo = document.getElementById("pageInfo");
    if(pageInfo) pageInfo.innerText = `Showing page ${currentPage} of ${totalPages} (${filteredTeams.length} total teams)`;
    
    const prevBtn = document.getElementById("prevPageBtn");
    if(prevBtn) prevBtn.disabled = currentPage === 1;
    
    const nextBtn = document.getElementById("nextPageBtn");
    if(nextBtn) nextBtn.disabled = currentPage === totalPages;

    const startIdx = (currentPage - 1) * rowsPerPage;
    const paginatedTeams = filteredTeams.slice(startIdx, startIdx + rowsPerPage);

    let html = "";
    if (paginatedTeams.length === 0) {
        html = `
        <tr>
            <td colspan="5" class="text-center py-5 text-muted">
                <div class="d-flex flex-column align-items-center justify-content-center">
                    <i data-lucide="search-x" style="width: 36px; height: 36px; color: #94a3b8; margin-bottom: 8px;"></i>
                    <div class="fw-semibold" style="font-size: 14px;">No matching teams found</div>
                    <div class="small text-muted">Try adjusting your search criteria</div>
                </div>
            </td>
        </tr>`;
    } else {
        paginatedTeams.forEach(team => {
            const employees = team.employees || [];
            const empCount = team.employee_count !== undefined ? team.employee_count : employees.length;
            
            // Build assigned employees preview with dropdown trigger
            let empPreviewHtml = "";
            let drawerMembersHtml = "";

            if (employees.length === 0) {
                empPreviewHtml = `
                    <div class="d-flex align-items-center gap-2">
                        <span class="text-muted small fst-italic">No members assigned</span>
                        <button class="btn btn-xs btn-outline-primary py-0.5 px-2" style="font-size: 11px; border-radius: 6px;" onclick="openEditModal(${team.id})">
                            <i data-lucide="user-plus" style="width: 11px; height: 11px; margin-right: 2px;"></i> Add
                        </button>
                    </div>
                `;
            } else {
                const visibleEmps = employees.slice(0, 2);
                const pills = visibleEmps.map(e => {
                    const roleClass = (e.role_name || '').toLowerCase().includes('admin') ? 'admin' : 
                                      (e.role_name || '').toLowerCase().includes('manager') ? 'manager' :
                                      (e.role_name || '').toLowerCase().includes('reviewer') ? 'reviewer' : '';
                    return `
                    <span class="member-pill" title="${e.full_name} (${e.role_name || 'Member'})">
                        <span class="member-pill-id ${roleClass}">${escapeHtml(e.employee_id || 'EMP')}</span>
                        <span class="member-pill-name">${escapeHtml(e.full_name)}</span>
                    </span>
                    `;
                }).join("");
                
                empPreviewHtml = `
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        <div class="member-pill-group">
                            ${pills}
                        </div>
                        <button class="btn btn-sm team-dropdown-btn d-inline-flex align-items-center gap-1.5 px-2.5 py-1" onclick="toggleTeamMembersDrawer(${team.id}, event)" id="btnToggleDrawer_${team.id}" title="Click to expand and view all assigned members">
                            <i data-lucide="users" style="width: 12.5px; height: 12.5px;" class="text-primary"></i>
                            <span style="font-size: 11.5px; font-weight: 600;">${empCount} Members</span>
                            <i data-lucide="chevron-down" class="dropdown-arrow-icon" style="width: 12px; height: 12px;"></i>
                        </button>
                    </div>
                `;

                drawerMembersHtml = employees.map(e => {
                    const initials = (e.full_name || 'U').split(" ").map(n => n[0]).slice(0, 2).join("").toUpperCase();
                    const roleClass = (e.role_name || '').toLowerCase().includes('admin') ? 'bg-danger-subtle text-danger border-danger-subtle' :
                                      (e.role_name || '').toLowerCase().includes('manager') ? 'bg-primary-subtle text-primary border-primary-subtle' :
                                      (e.role_name || '').toLowerCase().includes('reviewer') ? 'bg-warning-subtle text-warning-emphasis border-warning-subtle' :
                                      'bg-secondary-subtle text-secondary border-secondary-subtle';
                    
                    return `
                    <div class="col-md-4 col-sm-6">
                        <div class="drawer-member-card">
                            <div class="drawer-member-avatar">${initials}</div>
                            <div style="min-width: 0; flex: 1;">
                                <div class="d-flex align-items-center gap-1.5">
                                    <span class="fw-bold text-dark text-truncate" style="font-size: 12.5px;">${escapeHtml(e.full_name)}</span>
                                    <span class="badge bg-primary text-white" style="font-size: 9.5px; font-family: monospace; border-radius: 4px;">${escapeHtml(e.employee_id || '—')}</span>
                                </div>
                                <div class="d-flex align-items-center gap-1.5 mt-0.5">
                                    <span class="badge border ${roleClass}" style="font-size: 9px; font-weight: 700;">${escapeHtml(e.role_name || 'Employee')}</span>
                                    <span class="text-muted small text-truncate" style="font-size: 11px;">${escapeHtml(e.designation || 'Team Member')}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    `;
                }).join("");
            }

            html += `
            <tr>
                <td class="ps-4">
                    <span class="badge bg-light text-secondary border fw-bold" style="font-size: 11.5px; font-family: monospace;">#${team.id}</span>
                </td>
                <td>
                    <div class="fw-bold text-dark" style="font-size: 14px;">${escapeHtml(team.team_name)}</div>
                    <span class="badge bg-success-subtle text-success border border-success-subtle mt-0.5" style="font-size: 10px; font-weight: 700;">Active Team</span>
                </td>
                <td class="text-secondary" style="max-width: 260px;">
                    <div style="font-size: 12.5px; line-height: 1.45; color: #475569;">
                        ${team.description ? escapeHtml(team.description) : '<span class="text-muted fst-italic">No description provided</span>'}
                    </div>
                </td>
                <td>
                    ${empPreviewHtml}
                </td>
                <td class="text-end pe-4" style="white-space: nowrap;">
                    <div class="d-inline-flex align-items-center justify-content-end gap-1.5" style="white-space: nowrap;">
                        <button class="btn btn-sm btn-outline-primary px-2.5 py-1 d-inline-flex align-items-center gap-1" style="font-size: 12px; font-weight: 600;" onclick="openEditModal(${team.id})" title="Edit Team & Members">
                            <i data-lucide="edit-3" style="width: 13px; height: 13px;"></i> Edit
                        </button>
                        <button class="btn btn-sm btn-outline-danger px-2.5 py-1 d-inline-flex align-items-center gap-1" style="font-size: 12px; font-weight: 600;" onclick="deleteTeam(${team.id}, '${team.team_name.replace(/'/g, "\\'")}')" title="Delete Team">
                            <i data-lucide="trash-2" style="width: 13px; height: 13px;"></i> Delete
                        </button>
                    </div>
                </td>
            </tr>
            ${employees.length > 0 ? `
            <tr id="teamMembersDrawer_${team.id}" class="team-members-drawer-row d-none">
                <td colspan="5" class="p-0 border-0">
                    <div class="team-drawer-card p-3 mx-4 my-2">
                        <div class="d-flex justify-content-between align-items-center mb-2.5 pb-2 border-bottom">
                            <div class="d-flex align-items-center gap-2">
                                <div style="width:26px; height:26px; border-radius:6px; background:#EEF2FF; color:#4F46E5; display:flex; align-items:center; justify-content:center;">
                                    <i data-lucide="users" style="width:14px; height:14px;"></i>
                                </div>
                                <div>
                                    <span class="fw-bold text-dark" style="font-size: 13px;">Assigned Employees in ${escapeHtml(team.team_name)}</span>
                                    <span class="badge bg-primary text-white ms-1" style="font-size: 10px; border-radius: 10px;">${empCount} Members</span>
                                </div>
                            </div>
                            <div class="d-flex align-items-center gap-2">
                                <button class="btn btn-xs btn-outline-primary px-2.5 py-1 d-inline-flex align-items-center gap-1" style="font-size: 11.5px; font-weight: 600;" onclick="openEditModal(${team.id})">
                                    <i data-lucide="user-plus" style="width: 11px; height: 11px;"></i> Manage Members
                                </button>
                                <button class="btn btn-xs btn-light border px-2 py-1 text-muted d-inline-flex align-items-center gap-1" style="font-size: 11px;" onclick="toggleTeamMembersDrawer(${team.id})" title="Close Drawer">
                                    <i data-lucide="chevron-up" style="width: 12px; height: 12px;"></i> Hide
                                </button>
                            </div>
                        </div>
                        <div class="row g-2">
                            ${drawerMembersHtml}
                        </div>
                    </div>
                </td>
            </tr>
            ` : ''}
            `;
        });
    }

    const tbody = document.getElementById("teamTable");
    if(tbody) {
        tbody.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

function toggleTeamMembersDrawer(teamId, evt) {
    if (evt) evt.stopPropagation();
    const drawer = document.getElementById(`teamMembersDrawer_${teamId}`);
    const btn = document.getElementById(`btnToggleDrawer_${teamId}`);
    if (!drawer) return;

    if (drawer.classList.contains("d-none")) {
        // Close any other open drawer
        document.querySelectorAll(".team-members-drawer-row").forEach(d => {
            if (d.id !== `teamMembersDrawer_${teamId}`) d.classList.add("d-none");
        });
        document.querySelectorAll(".team-dropdown-btn").forEach(b => {
            if (b.id !== `btnToggleDrawer_${teamId}`) b.classList.remove("open");
        });

        drawer.classList.remove("d-none");
        if (btn) btn.classList.add("open");
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } else {
        drawer.classList.add("d-none");
        if (btn) btn.classList.remove("open");
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

function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// -------------------------------------------------------------
// 3. EMPLOYEE MULTI-SELECT & REAL-TIME SEARCH (MODAL)
// -------------------------------------------------------------
function setEmpFilter(filterType) {
    currentEmpFilter = filterType;
    document.querySelectorAll(".filter-tab-pill").forEach(p => p.classList.remove("active"));
    
    if (filterType === "all") document.getElementById("tabAllEmps")?.classList.add("active");
    if (filterType === "unassigned") document.getElementById("tabUnassignedEmps")?.classList.add("active");
    if (filterType === "selected") document.getElementById("tabSelectedEmps")?.classList.add("active");

    renderEmployeeSelectionList();
}

function filterEmployeeList() {
    renderEmployeeSelectionList();
}

function renderEmployeeSelectionList() {
    const container = document.getElementById("employeeSelectionContainer");
    if(!container) return;

    const currentTeamId = parseInt(document.getElementById("teamId")?.value) || null;
    const searchVal = (document.getElementById("employeeSearchInput")?.value || "").toLowerCase().trim();

    // Base Eligible Pool:
    // - When creating a new team (!currentTeamId): Only employees with NO team assigned (!e.team_id) are eligible.
    // - When editing an existing team (currentTeamId): Only unassigned employees (!e.team_id) OR members already in this team (e.team_id === currentTeamId) are eligible.
    // Employees who belong to other teams are completely excluded and never shown in the list.
    const eligibleEmployees = allAssignableEmployees.filter(e => {
        if (!currentTeamId) {
            return !e.team_id;
        } else {
            return !e.team_id || e.team_id === currentTeamId;
        }
    });

    // Update Counts
    const countAll = eligibleEmployees.length;
    const countSelected = selectedEmployeeIds.size;
    const countUnassigned = eligibleEmployees.filter(e => !selectedEmployeeIds.has(e.id)).length;

    if (document.getElementById("countAllEmps")) document.getElementById("countAllEmps").innerText = countAll;
    if (document.getElementById("countUnassignedEmps")) document.getElementById("countUnassignedEmps").innerText = countUnassigned;
    if (document.getElementById("countSelectedEmps")) document.getElementById("countSelectedEmps").innerText = countSelected;

    // Filter employees based on search query and current tab
    const filteredEmployees = eligibleEmployees.filter(e => {
        // Tab filter
        if (currentEmpFilter === "unassigned") {
            const isUnassigned = !selectedEmployeeIds.has(e.id);
            if (!isUnassigned) return false;
        } else if (currentEmpFilter === "selected") {
            if (!selectedEmployeeIds.has(e.id)) return false;
        }

        // Search query: match Name OR Employee ID OR Role OR Designation
        if (searchVal) {
            const nameMatch = e.full_name && e.full_name.toLowerCase().includes(searchVal);
            const idMatch = e.employee_id && e.employee_id.toLowerCase().includes(searchVal);
            const roleMatch = e.role_name && e.role_name.toLowerCase().includes(searchVal);
            const desigMatch = e.designation && e.designation.toLowerCase().includes(searchVal);
            return nameMatch || idMatch || roleMatch || desigMatch;
        }

        return true;
    });

    // Render Selection Cards
    if (filteredEmployees.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i data-lucide="user-x" style="width: 28px; height: 28px; color: #94a3b8; margin-bottom: 6px;"></i>
                <div class="small fw-semibold">No employees found matching this filter</div>
                <button type="button" class="btn btn-link btn-xs text-decoration-none mt-1" onclick="clearEmpSearchAndFilter()">Reset Search</button>
            </div>
        `;
    } else {
        container.innerHTML = filteredEmployees.map(emp => {
            const isSelected = selectedEmployeeIds.has(emp.id);

            // Assignment status badge
            let teamStatusBadge = "";
            if (isSelected) {
                teamStatusBadge = `<span class="badge bg-primary-subtle text-primary border border-primary-subtle" style="font-size: 10px;"><i data-lucide="check" style="width: 10px; height: 10px; display: inline;"></i> Selected</span>`;
            } else {
                teamStatusBadge = `<span class="badge bg-light text-muted border" style="font-size: 10px;">Unassigned</span>`;
            }


            // Role badge color
            const roleClass = (emp.role_name || '').toLowerCase().includes('admin') ? 'bg-danger-subtle text-danger border-danger-subtle' :
                              (emp.role_name || '').toLowerCase().includes('manager') ? 'bg-primary-subtle text-primary border-primary-subtle' :
                              (emp.role_name || '').toLowerCase().includes('reviewer') ? 'bg-warning-subtle text-warning-emphasis border-warning-subtle' :
                              'bg-secondary-subtle text-secondary border-secondary-subtle';

            const initials = (emp.full_name || 'U').split(" ").map(n => n[0]).slice(0, 2).join("").toUpperCase();

            return `
            <div class="emp-select-card ${isSelected ? 'selected' : ''}" onclick="toggleEmployeeSelection(${emp.id})">
                <div class="emp-checkbox-wrapper">
                    ${isSelected ? '<i data-lucide="check" style="width: 14px; height: 14px; stroke-width: 3;"></i>' : ''}
                </div>
                <div class="emp-avatar">${initials}</div>
                <div style="flex: 1; min-width: 0;">
                    <div class="d-flex align-items-center gap-2 mb-0.5">
                        <span class="fw-bold text-dark text-truncate" style="font-size: 13px;">${escapeHtml(emp.full_name)}</span>
                        <span class="badge bg-primary text-white" style="font-size: 10px; font-family: monospace; letter-spacing: 0.03em; border-radius: 4px;">${escapeHtml(emp.employee_id)}</span>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge border ${roleClass}" style="font-size: 9.5px; font-weight: 700;">${escapeHtml(emp.role_name || 'Employee')}</span>
                        <span class="text-muted small text-truncate" style="font-size: 11px;">${escapeHtml(emp.designation || 'Team Member')}</span>
                    </div>
                </div>
                <div class="text-end">
                    ${teamStatusBadge}
                </div>
            </div>
            `;
        }).join("");
    }

    renderSelectedTray();
    updateCountBadge();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}


function renderSelectedTray() {
    const tray = document.getElementById("selectedEmployeesTray");
    if (!tray) return;

    if (selectedEmployeeIds.size === 0) {
        tray.innerHTML = `<span class="text-muted small fst-italic" style="font-size: 11.5px;">No employees currently selected. Click cards below to assign.</span>`;
        return;
    }

    const selectedList = allAssignableEmployees.filter(e => selectedEmployeeIds.has(e.id));
    tray.innerHTML = selectedList.map(emp => `
        <span class="selected-tray-chip" title="${emp.full_name} (${emp.role_name})">
            <span class="badge bg-primary text-white p-0 px-1" style="font-size: 9.5px; font-family: monospace; border-radius: 3px;">${escapeHtml(emp.employee_id)}</span>
            <span>${escapeHtml(emp.full_name)}</span>
            <button type="button" class="btn-remove-chip" onclick="removeEmployeeFromSelection(${emp.id}, event)" title="Remove">✕</button>
        </span>
    `).join("");
}

function clearEmpSearchAndFilter() {
    const searchInput = document.getElementById("employeeSearchInput");
    if (searchInput) searchInput.value = "";
    setEmpFilter("all");
}

function toggleEmployeeSelection(empId) {
    if (selectedEmployeeIds.has(empId)) {
        selectedEmployeeIds.delete(empId);
    } else {
        selectedEmployeeIds.add(empId);
    }
    renderEmployeeSelectionList();
}

function removeEmployeeFromSelection(empId, evt) {
    if (evt) evt.stopPropagation();
    selectedEmployeeIds.delete(empId);
    renderEmployeeSelectionList();
}

function selectAllEmployees() {
    const searchVal = (document.getElementById("employeeSearchInput")?.value || "").toLowerCase().trim();
    const currentTeamId = parseInt(document.getElementById("teamId")?.value) || null;

    const eligibleEmployees = allAssignableEmployees.filter(e => {
        if (!currentTeamId) {
            return !e.team_id;
        } else {
            return !e.team_id || e.team_id === currentTeamId;
        }
    });

    eligibleEmployees.forEach(e => {
        let match = true;
        if (currentEmpFilter === "unassigned") {
            match = !e.team_id;
        }
        if (match && searchVal) {
            const nameMatch = e.full_name && e.full_name.toLowerCase().includes(searchVal);
            const idMatch = e.employee_id && e.employee_id.toLowerCase().includes(searchVal);
            const roleMatch = e.role_name && e.role_name.toLowerCase().includes(searchVal);
            const desigMatch = e.designation && e.designation.toLowerCase().includes(searchVal);
            match = nameMatch || idMatch || roleMatch || desigMatch;
        }
        if (match) selectedEmployeeIds.add(e.id);
    });

    renderEmployeeSelectionList();
}

function clearAllEmployeeSelections() {
    selectedEmployeeIds.clear();
    renderEmployeeSelectionList();
}

function updateCountBadge() {
    const badge = document.getElementById("selectedEmployeeCountBadge");
    if (badge) {
        badge.innerText = `${selectedEmployeeIds.size} Selected`;
    }
}

// -------------------------------------------------------------
// 4. ADD / EDIT / SAVE / DELETE TEAM
// -------------------------------------------------------------
function openAddModal() {
    document.getElementById("teamModalTitle").innerText = "Add Enterprise Team";
    document.getElementById("teamId").value = "";
    document.getElementById("teamName").value = "";
    document.getElementById("teamDescription").value = "";
    
    if (document.getElementById("employeeSearchInput")) {
        document.getElementById("employeeSearchInput").value = "";
    }
    
    selectedEmployeeIds.clear();
    currentEmpFilter = "all";

    fetch(`${API}/assignable-employees`)
        .then(r => r.json())
        .then(data => {
            allAssignableEmployees = data || [];
            renderEmployeeSelectionList();
        })
        .catch(() => renderEmployeeSelectionList());

    const modalEl = document.getElementById('teamModal');
    const myModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    myModal.show();
}

function openEditModal(id) {
    const team = allTeams.find(t => t.id === id);
    if (!team) return;

    document.getElementById("teamModalTitle").innerText = `Edit Team: ${team.team_name}`;
    document.getElementById("teamId").value = team.id;
    document.getElementById("teamName").value = team.team_name || "";
    document.getElementById("teamDescription").value = team.description || "";

    if (document.getElementById("employeeSearchInput")) {
        document.getElementById("employeeSearchInput").value = "";
    }

    selectedEmployeeIds.clear();
    currentEmpFilter = "all";

    if (team.employees && Array.isArray(team.employees)) {
        team.employees.forEach(e => selectedEmployeeIds.add(e.id));
    }

    fetch(`${API}/assignable-employees`)
        .then(r => r.json())
        .then(data => {
            allAssignableEmployees = data || [];
            renderEmployeeSelectionList();
        })
        .catch(() => renderEmployeeSelectionList());
    
    // Dismiss view modal if open
    const viewModalEl = document.getElementById('viewMembersModal');
    if (viewModalEl) {
        const viewModal = bootstrap.Modal.getInstance(viewModalEl);
        if (viewModal) viewModal.hide();
    }


    const modalEl = document.getElementById('teamModal');
    const myModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    myModal.show();
}

function saveTeam() {
    const id = document.getElementById("teamId").value;
    const name = document.getElementById("teamName").value.trim();
    const desc = document.getElementById("teamDescription").value.trim();

    if(!name) {
        if(typeof showToast === 'function') showToast("Team name is required", "warning");
        else alert("Team name is required");
        return;
    }

    const employeeIdsArray = Array.from(selectedEmployeeIds);
    const method = id ? "PUT" : "POST";
    const url = id ? `${API}/${id}` : API;

    const payload = {
        team_name: name,
        description: desc,
        employee_ids: employeeIdsArray
    };

    fetch(url, {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(r => {
        if(!r.ok) {
            return r.json().then(errData => {
                throw new Error(errData.detail || "Error saving team");
            });
        }
        return r.json();
    })
    .then(() => {
        if(typeof showToast === 'function') {
            showToast(id ? "Team and employee assignments updated successfully" : "Team created with employees successfully", "success");
        }
        
        // Hide modal
        const modalEl = document.getElementById('teamModal');
        const modal = bootstrap.Modal.getInstance(modalEl) || bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.hide();
        
        // Reload teams and employees
        loadTeams();
        loadAssignableEmployees();
    })
    .catch(err => {
        console.error("Save team error:", err);
        if(typeof showToast === 'function') showToast(err.message || "Error saving team", "danger");
        else alert(err.message || "Error saving team");
    });
}

function deleteTeam(id, teamName) {
    const displayName = teamName || `ID #${id}`;
    if(!confirm(`Are you sure you want to delete "${displayName}"?\nAll assigned employees will be unassigned to "Not Assigned".`)) return;

    fetch(API + "/" + id, { method: "DELETE" })
    .then(r => {
        if(!r.ok) throw new Error("API Error deleting team");
        return r.json();
    })
    .then(() => {
        if(typeof showToast === 'function') showToast("Team deleted successfully", "info");
        loadTeams();
        loadAssignableEmployees();
    })
    .catch(err => {
        if(typeof showToast === 'function') showToast("Error deleting team", "danger");
    });
}

// -------------------------------------------------------------
// 5. VIEW TEAM MEMBERS MODAL
// -------------------------------------------------------------
function viewTeamMembersModal(teamId) {
    const team = allTeams.find(t => t.id === teamId);
    if (!team) return;

    document.getElementById("viewMembersModalTitle").innerText = `${team.team_name} — Members`;
    document.getElementById("viewMembersModalSubtitle").innerText = `${team.employees ? team.employees.length : 0} members assigned to this team`;

    const container = document.getElementById("viewMembersListContainer");
    const employees = team.employees || [];

    const btnQuickEdit = document.getElementById("btnQuickEditFromView");
    if (btnQuickEdit) {
        btnQuickEdit.onclick = () => openEditModal(team.id);
    }

    if (employees.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i data-lucide="users" style="width: 36px; height: 36px; color: #94a3b8; margin-bottom: 8px;"></i>
                <div class="fw-semibold">No members assigned to this team yet</div>
                <p class="small text-muted mb-3">Click below to assign employees to this team.</p>
                <button class="btn btn-sm btn-primary px-3" onclick="openEditModal(${team.id})">
                    <i data-lucide="user-plus" style="width: 14px; height: 14px; margin-right: 4px;"></i> Assign Employees
                </button>
            </div>
        `;
    } else {
        container.innerHTML = `
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0" style="font-size: 13px;">
                    <thead class="table-light text-secondary" style="font-size: 11px; text-transform: uppercase;">
                        <tr>
                            <th class="ps-3">Employee</th>
                            <th>Employee ID</th>
                            <th>Role</th>
                            <th>Designation</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${employees.map(e => {
                            const initials = (e.full_name || 'U').split(" ").map(n => n[0]).slice(0, 2).join("").toUpperCase();
                            const roleClass = (e.role_name || '').toLowerCase().includes('admin') ? 'bg-danger-subtle text-danger border-danger-subtle' :
                                              (e.role_name || '').toLowerCase().includes('manager') ? 'bg-primary-subtle text-primary border-primary-subtle' :
                                              (e.role_name || '').toLowerCase().includes('reviewer') ? 'bg-warning-subtle text-warning-emphasis border-warning-subtle' :
                                              'bg-secondary-subtle text-secondary border-secondary-subtle';
                            return `
                            <tr>
                                <td class="ps-3">
                                    <div class="d-flex align-items-center gap-2.5">
                                        <div class="emp-avatar" style="width: 32px; height: 32px; font-size: 11px;">${initials}</div>
                                        <div class="fw-bold text-dark">${escapeHtml(e.full_name)}</div>
                                    </div>
                                </td>
                                <td>
                                    <span class="badge bg-primary text-white" style="font-size: 11px; font-family: monospace;">${escapeHtml(e.employee_id || '—')}</span>
                                </td>
                                <td>
                                    <span class="badge border ${roleClass}" style="font-size: 10.5px; font-weight: 700;">${escapeHtml(e.role_name || 'Member')}</span>
                                </td>
                                <td class="text-muted" style="font-size: 12.5px;">${escapeHtml(e.designation || 'Team Member')}</td>
                            </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }

    const modalEl = document.getElementById('viewMembersModal');
    const myModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    myModal.show();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}