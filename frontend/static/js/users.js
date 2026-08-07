// =========================================================
// users.js – User Management Page
// =========================================================

let allUsers = [];
let currentPage = 1;
const rowsPerPage = 12;

// Role name lookup (by role_id) pre-populated with system defaults
const roleMap = {
    1: "Administrator",
    2: "Manager",
    3: "Employee",
    4: "Reviewer"
};

document.addEventListener("DOMContentLoaded", () => {
    Promise.all([fetchUsers(), fetchRoles()]);

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
});

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
        if (allUsers.length > 0) {
            renderTable();
        }
    } catch (_) {}
}

async function fetchUsers() {
    try {
        const res = await fetch(`${API_URL}/users/`);
        if (!res.ok) throw new Error("Failed to load users");
        allUsers = await res.json();
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
                statusBadge = `<span class="badge" style="background:#FEF3C7;color:#D97706;font-size:11px;font-weight:700;"><i data-lucide="clock" style="width:11px;height:11px;" class="me-1"></i>Pending Approval</span>`;
            } else if (u.status === "Rejected") {
                statusBadge = `<span class="badge" style="background:#FEF2F2;color:#DC2626;font-size:11px;font-weight:700;">Rejected</span>`;
            } else if (u.is_active) {
                statusBadge = `<span class="badge" style="background:#ECFDF5;color:#059669;font-size:11px;font-weight:700;">Active</span>`;
            } else {
                statusBadge = `<span class="badge" style="background:#FEF2F2;color:#DC2626;font-size:11px;font-weight:700;">Inactive</span>`;
            }
            
            const userEmail = (u.email_original || u.display_email || u.email || '').trim();
            const displayEmailStr = userEmail.includes('@') ? userEmail : `${u.full_name.toLowerCase().replace(/\s+/g, '.')}@corp.com`;
            const emailHtml = `<div class="text-muted d-flex align-items-center gap-1 mt-0.5" style="font-size:11px;" title="${displayEmailStr}">
                <i data-lucide="mail" style="width:12px;height:12px;color:#64748B;"></i>
                <span style="color:#475569;font-size:11.5px;font-weight:500;">${displayEmailStr}</span>
            </div>`;

            let approveBtn = "";
            if (isAdmin && (u.status === "Pending Approval" || u.approved === false)) {
                approveBtn = `<button class="btn btn-sm btn-success px-2 ms-1" style="font-size:12px; font-weight:700;" onclick="approveUserDirectly(${u.id}, '${u.full_name.replace(/'/g, "\\'")}')" title="Approve Account">
                    <i data-lucide="check-circle" style="width:13px;height:13px;" class="me-1"></i>Approve
                </button>`;
            }

            const deleteBtn = isAdmin
                ? `<button class="btn btn-sm btn-outline-danger px-2 ms-1" style="font-size:12px;" onclick="deleteUserPermanently(${u.id}, '${u.full_name.replace(/'/g, "\\'")}')" title="Delete account permanently">
                    <i data-lucide="trash-2" style="width:13px;height:13px;" class="me-1"></i>Delete
                   </button>`
                : ``;

            return `
            <tr>
                <td class="px-4 py-3">
                    <div class="d-flex align-items-center gap-3">
                        <div class="user-avatar-sm">${initials}</div>
                        <div>
                            <div class="fw-semibold text-dark">${u.full_name}</div>
                            ${emailHtml}
                        </div>
                    </div>
                </td>
                <td class="px-4">
                    <code style="background:#F1F5F9;color:#0F172A;padding:2px 8px;border-radius:4px;font-size:12px;">${u.employee_id || '—'}</code>
                </td>
                <td class="px-4">
                    <span class="role-badge ${roleClass}">${roleName}</span>
                </td>
                <td class="px-4 text-muted" style="font-size:13px;">${u.designation || '—'}</td>
                <td class="px-4 text-muted" style="font-size:13px;">${u.phone || '—'}</td>
                <td class="px-4">${statusBadge}</td>
                <td class="px-4 text-end">
                    ${approveBtn}
                    <button class="btn btn-sm btn-outline-primary px-2.5 ms-1" style="font-size:12px;" onclick="viewUserDetails(${u.id})" title="View user details">
                        <i data-lucide="eye" style="width:13px;height:13px;" class="me-1"></i>View
                    </button>
                    ${deleteBtn}
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

    const payload = {
        full_name: document.getElementById("addFullName").value.trim(),
        email: document.getElementById("addEmail").value.trim(),
        password: document.getElementById("addPassword").value,
        role_id: role_id,
        team_id: 1,
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

function viewUserDetails(userId) {
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

