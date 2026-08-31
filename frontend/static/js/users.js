// =========================================================
// users.js – User Management Page
// =========================================================

let allUsers = [];
let currentPage = 1;
let rowsPerPage = 12;

function changePageSize(size) {
    if (size === 'all') {
        rowsPerPage = 999999;
    } else {
        rowsPerPage = parseInt(size, 10) || 12;
    }
    currentPage = 1;
    renderTable();
}
window.changePageSize = changePageSize;

// Role name lookup (by role_id) pre-populated with system defaults
const roleMap = {
    1: "Administrator",
    2: "Manager",
    3: "Employee",
    4: "Reviewer"
};

let allTeamsList = [];


document.addEventListener("DOMContentLoaded", () => {
    Promise.all([fetchUsers(), fetchRoles(), fetchTeams()]);

    const btnSubmit = document.getElementById("btnAddUserSubmit");
    if (btnSubmit) {
        btnSubmit.addEventListener("click", (e) => {
            submitAddUserForm(e);
        });
    }
    const form = document.getElementById("addUserForm");
    if (form) {
        form.addEventListener("submit", (e) => {
            submitAddUserForm(e);
        });
    }

    const editForm = document.getElementById("editUserForm");
    if (editForm) {
        editForm.addEventListener("submit", (e) => {
            submitEditUserForm(e);
        });
    }

    const promoteForm = document.getElementById("promoteUserForm");
    if (promoteForm) {
        promoteForm.addEventListener("submit", (e) => {
            submitPromoteUser(e);
        });
    }
});

async function fetchTeams() {
    try {
        const res = await fetch(`${API_URL}/teams/`);
        if (!res.ok) return;
        allTeamsList = await res.json();
        const select = document.getElementById("addTeamId");
        if (select && Array.isArray(allTeamsList) && allTeamsList.length > 0) {
            select.innerHTML = `<option value="">-- Unassigned --</option>` + 
                allTeamsList.map(t => `<option value="${t.id}">${t.team_name}</option>`).join('');
        }
        const editSelect = document.getElementById("editTeamId");
        if (editSelect && Array.isArray(allTeamsList) && allTeamsList.length > 0) {
            editSelect.innerHTML = `<option value="">-- Unassigned --</option>` + 
                allTeamsList.map(t => `<option value="${t.id}">${t.team_name}</option>`).join('');
        }
    } catch (_) {}
}

async function fetchRoles() {
    try {
        const res = await fetch(`${API_URL}/roles`);
        if (!res.ok) return;
        const roles = await res.json();
        roles.forEach(r => { roleMap[r.id] = r.role_name; });
        const select = document.getElementById("addRoleId");
        if (select && roles.length > 0) {
            select.innerHTML = roles.map(r => `<option value="${r.id}">${r.role_name}</option>`).join('');
        }
        const editRoleSelect = document.getElementById("editRoleId");
        if (editRoleSelect && roles.length > 0) {
            editRoleSelect.innerHTML = roles.map(r => `<option value="${r.id}">${r.role_name}</option>`).join('');
        }
        if (allUsers.length > 0) {
            renderTable();
        }
    } catch (_) {}
}


async function fetchUsers() {
    try {
        const res = await fetch(`${API_URL}/users/`);
        if (!res.ok) throw new Error("Failed to load users");

        const rawUsers = await res.json();
        const seenIds = new Set();
        allUsers = [];
        (Array.isArray(rawUsers) ? rawUsers : []).forEach(u => {
            if (!u || !u.id || seenIds.has(u.id)) return;
            seenIds.add(u.id);
            allUsers.push(u);
        });

        updateStats();
        renderTable();
    } catch (err) {

        document.getElementById("usersTableBody").innerHTML =
            `<tr><td colspan="7" class="text-center py-5 text-danger">
                <i data-lucide="alert-circle" style="width:18px;height:18px;" class="me-2"></i>${err.message}
             </td></tr>`;
        if (window.lucide) lucide.createIcons();
    }
}

function updateStats() {
    const total    = allUsers.length;
    const active   = allUsers.filter(u => u.is_active).length;
    const inactive = total - active;
    const admins   = allUsers.filter(u => {
        const roleName = (roleMap[u.role_id] || "").toLowerCase();
        return roleName === "administrator" || roleName === "admin";
    }).length;

    document.getElementById("statTotal").innerText    = total;
    document.getElementById("statActive").innerText   = active;
    document.getElementById("statInactive").innerText = inactive;
    document.getElementById("statAdmins").innerText   = admins;
}

function handleSearch() {
    currentPage = 1;
    renderTable();
}

function renderTable() {
    const query      = (document.getElementById("userSearch")?.value || "").toLowerCase();
    const roleFilter = (document.getElementById("roleFilter")?.value || "").toLowerCase();
    const isAdmin    = typeof CURRENT_USER_ROLE !== 'undefined' && ['Administrator', 'Admin', 'System Administrator'].includes(CURRENT_USER_ROLE);

    const filtered = allUsers.filter(u => {
        const roleName = (roleMap[u.role_id] || "").toLowerCase();
        const matchSearch = !query ||
            u.full_name.toLowerCase().includes(query) ||
            (u.email || "").toLowerCase().includes(query) ||
            (u.employee_id || "").toLowerCase().includes(query) ||
            (u.designation || "").toLowerCase().includes(query);
        const matchRole = !roleFilter || roleName.includes(roleFilter);
        return matchSearch && matchRole;
    });

    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start    = (currentPage - 1) * rowsPerPage;
    const pageData = filtered.slice(start, start + rowsPerPage);

    const tbody = document.getElementById("usersTableBody");
    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted">
            <i data-lucide="search-x" style="width:20px;height:20px;" class="me-2"></i>No users found.
        </td></tr>`;
        if (window.lucide) lucide.createIcons();
    } else {
        tbody.innerHTML = pageData.map(u => {
            const roleName   = roleMap[u.role_id] || "Unknown";
            const initials   = u.full_name.split(" ").map(p => p[0]).join("").substring(0, 2).toUpperCase();
            const roleClass  = "role-" + roleName.toLowerCase().replace(/\s/g, "");
            let statusBadge = "";
            if (u.status === "Pending Approval" || u.approved === false) {
                statusBadge = `<span class="status-pill status-pending" title="Pending Approval"><span class="status-dot"></span>Pending</span>`;
            } else if (u.status === "Rejected") {
                statusBadge = `<span class="status-pill status-inactive" title="Rejected"><span class="status-dot"></span>Rejected</span>`;
            } else if (u.is_active) {
                statusBadge = `<span class="status-pill status-active" title="Active Account"><span class="status-dot"></span>Active</span>`;
            } else {
                statusBadge = `<span class="status-pill status-inactive" title="Inactive Account"><span class="status-dot"></span>Inactive</span>`;
            }
            
            const userEmail = (u.email_original || u.display_email || u.email || '').trim();
            const displayEmailStr = userEmail.includes('@') ? userEmail : `${u.full_name.toLowerCase().replace(/\s+/g, '.')}@corp.com`;
            const emailHtml = `<div class="text-muted d-flex align-items-center gap-1 mt-0.5" style="font-size:11px;" title="${displayEmailStr}">
                <i data-lucide="mail" style="width:11px;height:11px;color:#94A3B8;"></i>
                <span style="color:#64748B;font-size:11px;font-weight:500;" class="text-truncate">${displayEmailStr}</span>
            </div>`;

            let approveBtn = "";
            if (isAdmin && (u.status === "Pending Approval" || u.approved === false)) {
                approveBtn = `<button class="btn btn-sm btn-success px-2 py-1" onclick="approveUserDirectly(${u.id}, '${u.full_name.replace(/'/g, "\\'")}')" title="Approve Account">
                    <i data-lucide="check-circle" style="width:11px;height:11px;"></i>Approve
                </button>`;
            }

            const isTargetAdmin = roleName.toLowerCase().includes('admin') || ['administrator', 'admin', 'system administrator'].includes(roleName.toLowerCase()) || u.role_id === 1;

            const promoteBtn = (isAdmin && !isTargetAdmin)
                ? `<button class="btn btn-sm btn-outline-info px-2 py-1" style="color:#6D28D9; border-color:#DDD6FE; background:#F5F3FF;" onclick="openPromoteModal(${u.id})" title="Promote / Change Role">
                    <i data-lucide="shield-check" style="width:11px;height:11px;"></i>Promote
                   </button>`
                : ``;

            const viewBtn = `<button class="btn btn-sm btn-outline-primary px-2 py-1" onclick="viewUserDetails(${u.id})" title="View Details">
                <i data-lucide="eye" style="width:11px;height:11px;"></i>View
            </button>`;

            const editBtn = isAdmin
                ? `<button class="btn btn-sm btn-outline-success px-2 py-1" onclick="openEditUserModal(${u.id})" title="Edit Credentials & Profile">
                    <i data-lucide="edit-3" style="width:11px;height:11px;"></i>Edit
                   </button>`
                : ``;

            const deleteBtn = isAdmin
                ? `<button class="btn btn-sm btn-outline-danger px-2 py-1" onclick="deleteUserPermanently(${u.id}, '${u.full_name.replace(/'/g, "\\'")}')" title="Delete User">
                    <i data-lucide="trash-2" style="width:11px;height:11px;"></i>Delete
                   </button>`
                : ``;

            return `
            <tr>
                <td class="ps-3 pe-2 py-2">
                    <div class="d-flex align-items-center gap-2.5">
                        <div class="user-avatar-sm">${initials}</div>
                        <div style="min-width:0;">
                            <div class="fw-bold text-dark text-truncate" style="font-size:12.5px;" title="${u.full_name}">${u.full_name}</div>
                            ${emailHtml}
                        </div>
                    </div>
                </td>
                <td class="px-2 py-2">
                    <span class="emp-id-badge">${u.employee_id || '—'}</span>
                </td>
                <td class="px-2 py-2">
                    <span class="role-badge ${roleClass}">${roleName}</span>
                </td>
                <td class="px-2 py-2">
                    <span class="badge bg-light text-dark border px-2 py-1" style="font-size:10.5px; font-weight:600;" title="${u.team_name || 'Not Assigned'}">
                        <i data-lucide="users" style="width:10.5px;height:10.5px;" class="me-1 text-primary"></i>${u.team_name || 'Not Assigned'}
                    </span>
                </td>
                <td class="px-2 py-2 text-muted text-truncate" style="font-size:11.5px;" title="${u.designation || ''}">${u.designation || '—'}</td>
                <td class="px-2 py-2 text-muted" style="font-size:11.5px; white-space: nowrap;">${u.phone || '—'}</td>
                <td class="px-2 py-2 text-center">${statusBadge}</td>
                <td class="pe-3 ps-2 py-2 text-end" style="white-space: nowrap;">
                    <div class="action-btn-group">
                        ${approveBtn}
                        ${promoteBtn}
                        ${viewBtn}
                        ${editBtn}
                        ${deleteBtn}
                    </div>
                </td>
            </tr>`;





        }).join("");
        if (window.lucide) lucide.createIcons();
    }

    document.getElementById("paginationInfo").innerText =
        `Showing ${start + 1}–${Math.min(start + rowsPerPage, filtered.length)} of ${filtered.length} users`;
    document.getElementById("pageIndicator").innerText = `${currentPage} / ${totalPages}`;
    document.getElementById("btnPrev").disabled = currentPage === 1;
    document.getElementById("btnNext").disabled = currentPage === totalPages;
}

function prevPage() {
    if (currentPage > 1) { currentPage--; renderTable(); }
}
function nextPage() {
    currentPage++;
    renderTable();
}

async function deleteUserPermanently(userId, userName) {
    if (!confirm(`Are you sure you want to permanently delete user "${userName}"?\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/users/${userId}`, { method: "DELETE" });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to delete user");
        }

        allUsers = allUsers.filter(u => u.id !== userId);
        updateStats();
        renderTable();

        if (typeof showCenterNotification === 'function') {
            showCenterNotification("The account has been deleted successfully.", 'delete', '🗑 Account Deleted');
        }

        await fetchUsers();
    } catch (err) {
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(err.message || "Failed to delete user", 'error', 'Error Deleting Account');
        }
    }
}

let isSubmittingUser = false;

async function submitAddUserForm(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    if (isSubmittingUser) return;

    const form = document.getElementById("addUserForm");
    const alertBox = document.getElementById("addUserAlert");
    const submitBtn = document.getElementById("btnAddUserSubmit");

    if (form && !form.checkValidity()) {
        form.reportValidity();
        return;
    }

    isSubmittingUser = true;
    if (alertBox) alertBox.classList.add("d-none");
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = "Creating...";
    }

    let rawRoleId = document.getElementById("addRoleId")?.value || "3";
    let role_id = parseInt(rawRoleId);
    if (isNaN(role_id)) {
        const valLower = String(rawRoleId).toLowerCase();
        if (valLower.includes("admin")) role_id = 1;
        else if (valLower.includes("manager") || valLower.includes("lead")) role_id = 2;
        else if (valLower.includes("reviewer")) role_id = 4;
        else role_id = 3;
    }

    const teamVal = document.getElementById("addTeamId")?.value;
    const team_id = teamVal ? parseInt(teamVal) : null;

    const payload = {
        full_name: document.getElementById("addFullName").value.trim(),
        email: document.getElementById("addEmail").value.trim(),
        password: document.getElementById("addPassword").value,
        role_id: role_id,
        team_id: team_id,
        employee_id: document.getElementById("addEmployeeId").value.trim() || null,
        designation: document.getElementById("addDesignation").value.trim() || null,
        phone: document.getElementById("addPhone").value.trim() || null
    };


    try {
        let res;
        try {
            res = await fetch(`/api/admin-create-user`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.status === 404) {
                res = await fetch(`${API_URL}/users/admin_create`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
            }
        } catch (_) {
            res = await fetch(`${API_URL}/users/admin_create`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            let msg = "Failed to create user";
            if (typeof errData.detail === "string") {
                msg = errData.detail;
            } else if (Array.isArray(errData.detail) && errData.detail.length > 0) {
                msg = errData.detail.map(e => e.msg || e.detail || JSON.stringify(e)).join(", ");
            }
            throw new Error(msg);
        }

        const newUser = await res.json();

        // Close modal reliably
        const modalEl = document.getElementById("addUserModal");
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        if (modal) modal.hide();

        // Cleanup modal backdrop if leftover
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';

        document.getElementById("addUserForm").reset();
        showCenterNotification(`User "${newUser.full_name}" created successfully with Employee ID: ${newUser.employee_id}`, 'success', 'User Created');
        fetchUsers();
    } catch (err) {
        console.error("User creation error:", err);
        alertBox.innerText = err.message || "Failed to create user";
        alertBox.classList.remove("d-none");
        showCenterNotification(err.message || "Failed to create user", 'error', 'Error Creating User');
    } finally {
        isSubmittingUser = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = "Create User";
        }
    }
}

// Bind to window for global access
window.submitAddUserForm = submitAddUserForm;
window.deleteUserPermanently = deleteUserPermanently;

async function approveUserDirectly(userId, userName) {
    if (!confirm(`Are you sure you want to approve the account for "${userName}"?`)) return;

    try {
        const res = await fetch(`${API_URL}/users/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, action: "approve", actor_name: CURRENT_USER_ROLE || "Administrator" })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to approve user");
        }
        if (typeof showCenterNotification === 'function') {
            showCenterNotification("The account has been approved successfully.", "success", "✅ Account Approved");
        }
        fetchUsers();
    } catch (err) {
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(err.message || "Failed to approve user", "error", "Error Approving Account");
        }
    }
}
window.approveUserDirectly = approveUserDirectly;

let currentlyViewingUserId = null;

function viewUserDetails(userId) {
    currentlyViewingUserId = userId;
    const u = allUsers.find(user => user.id === userId);
    if (!u) {
        alert("User details not found.");
        return;
    }


    const roleName = roleMap[u.role_id] || "User";
    const initials = u.full_name.split(" ").map(p => p[0]).join("").substring(0, 2).toUpperCase();
    
    const avatarEl = document.getElementById("viewUserAvatar");
    if (avatarEl) avatarEl.innerText = initials;
    
    const nameEl = document.getElementById("viewFullName");
    if (nameEl) nameEl.innerText = u.full_name;
    
    const roleBadge = document.getElementById("viewRoleBadge");
    if (roleBadge) {
        roleBadge.innerText = roleName;
        roleBadge.className = "role-badge role-" + roleName.toLowerCase().replace(/\s/g, "");
    }
    
    const empIdEl = document.getElementById("viewEmployeeId");
    if (empIdEl) empIdEl.innerText = u.employee_id || "N/A";
    
    const statusEl = document.getElementById("viewStatus");
    if (statusEl) statusEl.innerText = u.status || (u.is_active ? "Active" : "Inactive");
    
    const emailEl = document.getElementById("viewEmail");
    const userEmailVal = (u.email_original || u.display_email || u.email || '').trim();
    const readableEmail = userEmailVal.includes('@') ? userEmailVal : `${u.full_name.toLowerCase().replace(/\s+/g, '.')}@corp.com`;
    if (emailEl) emailEl.innerHTML = `<div class="d-flex align-items-center justify-content-between"><span class="fw-semibold text-dark" style="font-size:12.5px;">${readableEmail}</span><span class="badge bg-light text-primary border ms-2" style="font-size:10px;"><i data-lucide="mail" style="width:11px;height:11px;" class="me-1"></i>Verified Email</span></div>`;
    
    const teamEl = document.getElementById("viewTeam");
    if (teamEl) teamEl.innerText = u.team_name || "Not Assigned";

    const desigEl = document.getElementById("viewDesignation");
    if (desigEl) desigEl.innerText = u.designation || "N/A";
    
    const phoneEl = document.getElementById("viewPhone");
    if (phoneEl) phoneEl.innerText = u.phone || "N/A";
    
    const verifiedEl = document.getElementById("viewEmailVerified");
    if (verifiedEl) verifiedEl.innerText = u.email_verified ? "Yes (Verified)" : "No";
    
    const approvedEl = document.getElementById("viewApproved");
    if (approvedEl) approvedEl.innerText = u.approved ? "Yes (Approved)" : "Pending/No";

    const modalEl = document.getElementById("viewUserModal");
    if (modalEl) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }
}
window.viewUserDetails = viewUserDetails;

// =========================================================
// Role Promotion & ID Transformation Handlers
// =========================================================

const rolePrefixMap = {
    1: "AD",
    2: "MN",
    3: "EMP",
    4: "RW"
};

function calculateNewEmpId(oldEmpId, targetRoleId) {
    const rawId = (oldEmpId || "").trim();
    const digitsMatch = rawId.match(/\d+/);
    const digits = digitsMatch ? digitsMatch[0] : "123456";
    const prefix = rolePrefixMap[targetRoleId] || "EMP";
    return `${prefix}${digits}`;
}

function updatePromotePreview() {
    const userId = parseInt(document.getElementById("promoteUserId")?.value, 10);
    const targetRoleId = parseInt(document.getElementById("promoteNewRoleId")?.value, 10);
    const u = allUsers.find(user => user.id === userId);
    if (!u) return;

    const oldId = u.employee_id || "EMP123456";
    const newId = calculateNewEmpId(oldId, targetRoleId);

    const prevEl = document.getElementById("previewOldId");
    const nextEl = document.getElementById("previewNewId");
    if (prevEl) prevEl.innerText = oldId;
    if (nextEl) nextEl.innerText = newId;
}
window.updatePromotePreview = updatePromotePreview;

function openPromoteModal(userId) {
    const u = allUsers.find(user => user.id === userId);
    if (!u) {
        alert("User details not found.");
        return;
    }

    const currentRoleName = roleMap[u.role_id] || "Employee";
    const isTargetAdmin = currentRoleName.toLowerCase().includes('admin') || ['administrator', 'admin', 'system administrator'].includes(currentRoleName.toLowerCase()) || u.role_id === 1;
    if (isTargetAdmin) {
        if (typeof showCenterNotification === 'function') {
            showCenterNotification("Administrator is already the highest role and cannot be promoted.", 'warning', 'Action Not Allowed');
        } else {
            alert("Administrator is already the highest role and cannot be promoted.");
        }
        return;
    }

    const roleClass = "role-" + currentRoleName.toLowerCase().replace(/\s/g, "");

    document.getElementById("promoteUserId").value = u.id;
    document.getElementById("promoteUserName").innerText = u.full_name;
    
    const roleBadge = document.getElementById("promoteCurrentRoleBadge");
    if (roleBadge) {
        roleBadge.innerText = currentRoleName;
        roleBadge.className = `role-badge ${roleClass}`;
    }

    const empIdEl = document.getElementById("promoteCurrentEmpId");
    if (empIdEl) empIdEl.innerText = u.employee_id || "N/A";

    const selectEl = document.getElementById("promoteNewRoleId");
    if (selectEl) {
        // Suggest next role in promotion path if available
        let nextRoleId = 4; // default reviewer
        if (u.role_id === 3) nextRoleId = 4; // Employee -> Reviewer
        else if (u.role_id === 4) nextRoleId = 2; // Reviewer -> Manager
        else if (u.role_id === 2) nextRoleId = 4; // Manager -> Reviewer
        else nextRoleId = 3;
        selectEl.value = String(nextRoleId);
    }

    const alertBox = document.getElementById("promoteAlert");
    if (alertBox) alertBox.classList.add("d-none");

    updatePromotePreview();

    const modalEl = document.getElementById("promoteUserModal");
    if (modalEl) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }
}
window.openPromoteModal = openPromoteModal;

let isPromotingUser = false;

async function submitPromoteUser(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    if (isPromotingUser) return;

    const userId = parseInt(document.getElementById("promoteUserId")?.value, 10);
    const newRoleId = parseInt(document.getElementById("promoteNewRoleId")?.value, 10);
    const alertBox = document.getElementById("promoteAlert");
    const submitBtn = document.getElementById("btnPromoteSubmit");

    if (!userId || !newRoleId) return;

    isPromotingUser = true;
    if (alertBox) alertBox.classList.add("d-none");
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = "Applying Promotion...";
    }

    const payload = {
        role_id: newRoleId,
        actor_role: typeof CURRENT_USER_ROLE !== 'undefined' ? CURRENT_USER_ROLE : "Administrator",
        actor_name: "Administrator"
    };

    try {
        let res;
        try {
            res = await fetch(`/api/users/${userId}/promote`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.status === 404) {
                res = await fetch(`/api/users/${userId}/role`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
            }
        } catch (_) {
            res = await fetch(`/api/users/${userId}/role`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to promote user");
        }

        const data = await res.json();

        // Close modal
        const modalEl = document.getElementById("promoteUserModal");
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.hide();
        }

        // Cleanup any leftover modal backdrop
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';

        const successMsg = `User "${data.full_name}" promoted to ${data.new_role}! Employee ID updated: ${data.prev_employee_id} &rarr; ${data.new_employee_id}. Mail dispatched to Gmail.`;
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(successMsg, 'success', '🚀 User Promoted Successfully');
        } else {
            alert(successMsg);
        }

        await fetchUsers();
    } catch (err) {
        console.error("Promotion error:", err);
        if (alertBox) {
            alertBox.innerText = err.message || "Failed to promote user";
            alertBox.classList.remove("d-none");
        }
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(err.message || "Failed to promote user", 'error', 'Promotion Error');
        }
    } finally {
        isPromotingUser = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = "Apply Promotion & Send Mail";
        }
    }
}
window.submitPromoteUser = submitPromoteUser;

// =========================================================
// Edit User Credentials & Access Handlers (Admin Only)
// =========================================================

function openEditUserFromView() {
    if (!currentlyViewingUserId) return;
    const viewModalEl = document.getElementById("viewUserModal");
    if (viewModalEl) {
        const viewModal = bootstrap.Modal.getInstance(viewModalEl);
        if (viewModal) viewModal.hide();
    }
    openEditUserModal(currentlyViewingUserId);
}
window.openEditUserFromView = openEditUserFromView;

function openEditUserModal(userId) {
    const u = allUsers.find(user => user.id === userId);
    if (!u) {
        alert("User details not found.");
        return;
    }

    const alertBox = document.getElementById("editUserAlert");
    if (alertBox) alertBox.classList.add("d-none");

    const idInput = document.getElementById("editUserId");
    if (idInput) idInput.value = u.id;

    const empIdInput = document.getElementById("editEmployeeId");
    if (empIdInput) empIdInput.value = u.employee_id || `EMP-${u.id}`;

    const nameInput = document.getElementById("editFullName");
    if (nameInput) nameInput.value = u.full_name || "";

    const userEmailVal = (u.email_original || u.display_email || u.email || "").trim();
    const origEmailInput = document.getElementById("editOriginalEmail");
    if (origEmailInput) origEmailInput.value = userEmailVal;

    const emailInput = document.getElementById("editEmail");
    if (emailInput) emailInput.value = userEmailVal;

    const passInput = document.getElementById("editPassword");
    if (passInput) {
        passInput.value = "";
        passInput.type = "password";
    }

    const passIcon = document.getElementById("toggleEditPassIcon");
    if (passIcon) passIcon.setAttribute("data-lucide", "eye");

    const roleSelect = document.getElementById("editRoleId");
    if (roleSelect) roleSelect.value = u.role_id || "3";

    const teamSelect = document.getElementById("editTeamId");
    if (teamSelect) teamSelect.value = u.team_id || "";

    const desigInput = document.getElementById("editDesignation");
    if (desigInput) {
        const val = (u.designation || "").trim();
        if (val) {
            let exists = false;
            for (let i = 0; i < desigInput.options.length; i++) {
                if (desigInput.options[i].value.toLowerCase() === val.toLowerCase()) {
                    desigInput.selectedIndex = i;
                    exists = true;
                    break;
                }
            }
            if (!exists) {
                const opt = document.createElement("option");
                opt.value = val;
                opt.text = val;
                desigInput.appendChild(opt);
                desigInput.value = val;
            }
        } else {
            desigInput.value = "";
        }
    }

    const phoneInput = document.getElementById("editPhone");
    if (phoneInput) phoneInput.value = u.phone || "";

    const notifyCheck = document.getElementById("editNotifyUser");
    if (notifyCheck) notifyCheck.checked = true;

    const modalEl = document.getElementById("editUserModal");
    if (modalEl) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
        if (window.lucide) lucide.createIcons();
    }
}
window.openEditUserModal = openEditUserModal;

function toggleEditPasswordVisibility() {
    const passInput = document.getElementById("editPassword");
    const passIcon = document.getElementById("toggleEditPassIcon");
    if (!passInput) return;

    if (passInput.type === "password") {
        passInput.type = "text";
        if (passIcon) passIcon.setAttribute("data-lucide", "eye-off");
    } else {
        passInput.type = "password";
        if (passIcon) passIcon.setAttribute("data-lucide", "eye");
    }
    if (window.lucide) lucide.createIcons();
}
window.toggleEditPasswordVisibility = toggleEditPasswordVisibility;

function generateRandomPasswordForEdit() {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%";
    let randomPass = "";
    for (let i = 0; i < 10; i++) {
        randomPass += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    const passInput = document.getElementById("editPassword");
    if (passInput) {
        passInput.value = randomPass;
        passInput.type = "text";
    }
    const passIcon = document.getElementById("toggleEditPassIcon");
    if (passIcon) passIcon.setAttribute("data-lucide", "eye-off");
    if (window.lucide) lucide.createIcons();
}
window.generateRandomPasswordForEdit = generateRandomPasswordForEdit;

let isUpdatingCredentials = false;
async function submitEditUserForm(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (isUpdatingCredentials) return;

    const alertBox = document.getElementById("editUserAlert");
    const submitBtn = document.getElementById("btnEditUserSubmit");

    const userId = parseInt(document.getElementById("editUserId")?.value, 10);
    const fullName = document.getElementById("editFullName")?.value.trim();
    const email = document.getElementById("editEmail")?.value.trim().toLowerCase();
    const password = document.getElementById("editPassword")?.value;
    const roleId = parseInt(document.getElementById("editRoleId")?.value, 10) || 3;
    const teamVal = document.getElementById("editTeamId")?.value;
    const teamId = teamVal ? parseInt(teamVal, 10) : null;
    const designation = document.getElementById("editDesignation")?.value.trim() || null;
    const phone = document.getElementById("editPhone")?.value.trim() || null;
    const notifyUser = document.getElementById("editNotifyUser")?.checked ?? true;

    if (!userId || !fullName || !email) {
        if (alertBox) {
            alertBox.innerText = "Please fill in all required fields (Full Name and Email Address).";
            alertBox.classList.remove("d-none");
        }
        return;
    }

    if (password && password.length < 6) {
        if (alertBox) {
            alertBox.innerText = "Password must be at least 6 characters long.";
            alertBox.classList.remove("d-none");
        }
        return;
    }

    isUpdatingCredentials = true;
    if (alertBox) alertBox.classList.add("d-none");
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = "Saving Changes...";
    }

    const payload = {
        user_id: userId,
        full_name: fullName,
        email: email,
        password: password ? password : null,
        role_id: roleId,
        team_id: teamId,
        designation: designation,
        phone: phone,
        notify_user: notifyUser
    };

    try {
        let res = await fetch("/api/users/admin_update_credentials", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (res.status === 404) {
            res = await fetch(`/api/users/${userId}/credentials`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to update user credentials.");
        }

        const data = await res.json();

        // Close modal
        const modalEl = document.getElementById("editUserModal");
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.hide();
        }

        let notifyDetails = "";
        if (data.email_changed && data.password_changed) {
            notifyDetails = `Email & Password updated. Security notices dispatched to both ${data.old_email} and ${data.new_email}.`;
        } else if (data.email_changed) {
            notifyDetails = `Email updated (${data.old_email} &rarr; ${data.new_email}). Notification dispatched to both inboxes.`;
        } else if (data.password_changed) {
            notifyDetails = `Password has been reset. Confirmation dispatched to ${data.email}.`;
        } else {
            notifyDetails = `User profile details updated successfully.`;
        }

        if (typeof showCenterNotification === 'function') {
            showCenterNotification(notifyDetails, 'success', '👤 Account Updated');
        } else {
            alert(notifyDetails);
        }

        await fetchUsers();
    } catch (err) {
        console.error("Update credentials error:", err);
        if (alertBox) {
            alertBox.innerText = err.message || "Failed to update user credentials.";
            alertBox.classList.remove("d-none");
        }
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(err.message || "Failed to update user credentials.", 'error', 'Update Failed');
        }
    } finally {
        isUpdatingCredentials = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = "Save Changes";
        }
    }
}
window.submitEditUserForm = submitEditUserForm;

let isCreatingUser = false;
async function submitAddUserForm(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (isCreatingUser) return;

    const alertBox = document.getElementById("addUserAlert");
    const submitBtn = document.getElementById("btnAddUserSubmit");

    const fullName = document.getElementById("addFullName")?.value.trim();
    const email = document.getElementById("addEmail")?.value.trim().toLowerCase();
    const roleId = parseInt(document.getElementById("addRoleId")?.value, 10) || 3;
    const employeeId = document.getElementById("addEmployeeId")?.value.trim() || null;
    const password = document.getElementById("addPassword")?.value;
    const designation = document.getElementById("addDesignation")?.value.trim() || null;
    const teamVal = document.getElementById("addTeamId")?.value;
    const teamId = teamVal ? parseInt(teamVal, 10) : 1;
    const phone = document.getElementById("addPhone")?.value.trim() || null;

    if (!fullName || !email || !password) {
        if (alertBox) {
            alertBox.innerText = "Please provide Full Name, Email, and Password.";
            alertBox.classList.remove("d-none");
        }
        return;
    }

    if (password.length < 6) {
        if (alertBox) {
            alertBox.innerText = "Password must be at least 6 characters long.";
            alertBox.classList.remove("d-none");
        }
        return;
    }

    isCreatingUser = true;
    if (alertBox) alertBox.classList.add("d-none");
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = "Creating User...";
    }

    const payload = {
        full_name: fullName,
        email: email,
        password: password,
        role_id: roleId,
        team_id: teamId,
        employee_id: employeeId,
        designation: designation,
        phone: phone
    };

    try {
        const res = await fetch("/api/users/admin_create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to create user.");
        }

        const newUser = await res.json();

        // Close modal and reset form
        const modalEl = document.getElementById("addUserModal");
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.hide();
        }
        const form = document.getElementById("addUserForm");
        if (form) form.reset();

        const successMsg = `User "${newUser.full_name}" created with designation "${newUser.designation || designation || 'Team Member'}"! (ID: ${newUser.employee_id})`;
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(successMsg, 'success', '✅ User Created');
        } else {
            alert(successMsg);
        }

        await fetchUsers();
    } catch (err) {
        console.error("Create user error:", err);
        if (alertBox) {
            alertBox.innerText = err.message || "Failed to create user.";
            alertBox.classList.remove("d-none");
        }
        if (typeof showCenterNotification === 'function') {
            showCenterNotification(err.message || "Failed to create user.", 'error', 'Creation Error');
        }
    } finally {
        isCreatingUser = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = "Create User";
        }
    }
}
window.submitAddUserForm = submitAddUserForm;


