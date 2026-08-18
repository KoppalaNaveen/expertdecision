const API = "/api/roles";

let allRoles = [];
let currentPage = 1;
const rowsPerPage = 5;

window.onload = function() {
    loadRoles();
};

document.addEventListener("DOMContentLoaded", function() {
    const addBtn = document.querySelector('button[data-bs-target="#roleModal"]');
    if(addBtn) {
        addBtn.addEventListener('click', openAddModal);
    }
});

function loadRoles() {
    fetch(API)
        .then(r => r.json())
        .then(data => {
            allRoles = data;
            renderTable();
        })
        .catch(err => {
            if(typeof showToast === 'function') showToast("Failed to load roles", "danger");
        });
}

function handleSearch() {
    currentPage = 1;
    renderTable();
}

function renderTable() {
    const searchInput = document.getElementById("roleSearch");
    const searchStr = searchInput ? searchInput.value.toLowerCase() : "";
    
    // Filter
    const filteredRoles = allRoles.filter(role => {
        return role.role_name.toLowerCase().includes(searchStr) || 
               (role.description && role.description.toLowerCase().includes(searchStr));
    });

    // Pagination
    const totalPages = Math.ceil(filteredRoles.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const pageInfo = document.getElementById("pageInfo");
    if(pageInfo) pageInfo.innerText = `Page ${currentPage} of ${totalPages}`;
    
    const prevBtn = document.getElementById("prevPageBtn");
    if(prevBtn) prevBtn.disabled = currentPage === 1;
    
    const nextBtn = document.getElementById("nextPageBtn");
    if(nextBtn) nextBtn.disabled = currentPage === totalPages;

    const startIdx = (currentPage - 1) * rowsPerPage;
    const paginatedRoles = filteredRoles.slice(startIdx, startIdx + rowsPerPage);

    let html = "";
    paginatedRoles.forEach(role => {
        html += `
        <tr>
            <td>${role.id}</td>
            <td>${role.role_name}</td>
            <td>${role.description ?? ""}</td>
            <td>
                <button class="btn btn-warning btn-sm" onclick="openEditModal(${role.id}, '${role.role_name.replace(/'/g, "\\'")}', '${(role.description ?? "").replace(/'/g, "\\'")}')">Edit</button>
                <button class="btn btn-danger btn-sm ms-2" onclick="deleteRole(${role.id})">Delete</button>
            </td>
        </tr>
        `;
    });

    const tbody = document.getElementById("roleTable");
    if(tbody) tbody.innerHTML = html;
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

function openAddModal() {
    document.getElementById("roleModalTitle").innerText = "Add Role";
    document.getElementById("roleId").value = "";
    document.getElementById("roleName").value = "";
    document.getElementById("roleDescription").value = "";
}

function openEditModal(id, name, desc) {
    document.getElementById("roleModalTitle").innerText = "Edit Role";
    document.getElementById("roleId").value = id;
    document.getElementById("roleName").value = name;
    document.getElementById("roleDescription").value = desc;
    
    const myModal = new bootstrap.Modal(document.getElementById('roleModal'));
    myModal.show();
}

function saveRole() {
    const id = document.getElementById("roleId").value;
    const name = document.getElementById("roleName").value;
    const desc = document.getElementById("roleDescription").value;

    if(!name) {
        if(typeof showToast === 'function') showToast("Role name is required", "warning");
        return;
    }

    const method = id ? "PUT" : "POST";
    const url = id ? `${API}/${id}` : API;

    fetch(url, {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role_name: name, description: desc })
    })
    .then(r => {
        if(!r.ok) throw new Error("API Error");
        return r.json();
    })
    .then(() => {
        if(typeof showToast === 'function') showToast(id ? "Role updated successfully" : "Role created successfully", "success");
        // hide modal
        const modalEl = document.getElementById('roleModal');
        const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        modal.hide();
        loadRoles();
    })
    .catch(err => {
        if(typeof showToast === 'function') showToast("Error saving role", "danger");
    });
}

function deleteRole(id) {
    if(!confirm("Delete this role?")) return;

    fetch(API + "/" + id, { method: "DELETE" })
    .then(r => {
        if(!r.ok) throw new Error("API Error");
        if(typeof showToast === 'function') showToast("Role deleted successfully", "info");
        loadRoles();
    })
    .catch(err => {
        if(typeof showToast === 'function') showToast("Error deleting role", "danger");
    });
}