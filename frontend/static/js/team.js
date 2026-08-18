const API = "/api/teams";

let allTeams = [];
let currentPage = 1;
const rowsPerPage = 5;

window.onload = function() {
    loadTeams();
};

document.addEventListener("DOMContentLoaded", function() {
    const addBtn = document.querySelector('button[data-bs-target="#teamModal"]');
    if(addBtn) {
        addBtn.addEventListener('click', openAddModal);
    }
});

function loadTeams() {
    fetch(API)
        .then(r => r.json())
        .then(data => {
            allTeams = data;
            renderTable();
        })
        .catch(err => {
            if(typeof showToast === 'function') showToast("Failed to load teams", "danger");
        });
}

function handleSearch() {
    currentPage = 1;
    renderTable();
}

function renderTable() {
    const searchInput = document.getElementById("teamSearch");
    const searchStr = searchInput ? searchInput.value.toLowerCase() : "";
    
    // Filter
    const filteredTeams = allTeams.filter(team => {
        return team.team_name.toLowerCase().includes(searchStr) || 
               (team.description && team.description.toLowerCase().includes(searchStr));
    });

    // Pagination
    const totalPages = Math.ceil(filteredTeams.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const pageInfo = document.getElementById("pageInfo");
    if(pageInfo) pageInfo.innerText = `Page ${currentPage} of ${totalPages}`;
    
    const prevBtn = document.getElementById("prevPageBtn");
    if(prevBtn) prevBtn.disabled = currentPage === 1;
    
    const nextBtn = document.getElementById("nextPageBtn");
    if(nextBtn) nextBtn.disabled = currentPage === totalPages;

    const startIdx = (currentPage - 1) * rowsPerPage;
    const paginatedTeams = filteredTeams.slice(startIdx, startIdx + rowsPerPage);

    let html = "";
    paginatedTeams.forEach(team => {
        html += `
        <tr>
            <td>${team.id}</td>
            <td>${team.team_name}</td>
            <td>${team.description ?? ""}</td>
            <td>
                <button class="btn btn-warning btn-sm" onclick="openEditModal(${team.id}, '${team.team_name.replace(/'/g, "\\'")}', '${(team.description ?? "").replace(/'/g, "\\'")}')">Edit</button>
                <button class="btn btn-danger btn-sm ms-2" onclick="deleteTeam(${team.id})">Delete</button>
            </td>
        </tr>
        `;
    });

    const tbody = document.getElementById("teamTable");
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
    document.getElementById("teamModalTitle").innerText = "Add Team";
    document.getElementById("teamId").value = "";
    document.getElementById("teamName").value = "";
    document.getElementById("teamDescription").value = "";
}

function openEditModal(id, name, desc) {
    document.getElementById("teamModalTitle").innerText = "Edit Team";
    document.getElementById("teamId").value = id;
    document.getElementById("teamName").value = name;
    document.getElementById("teamDescription").value = desc;
    
    const myModal = new bootstrap.Modal(document.getElementById('teamModal'));
    myModal.show();
}

function saveTeam() {
    const id = document.getElementById("teamId").value;
    const name = document.getElementById("teamName").value;
    const desc = document.getElementById("teamDescription").value;

    if(!name) {
        if(typeof showToast === 'function') showToast("Team name is required", "warning");
        return;
    }

    const method = id ? "PUT" : "POST";
    const url = id ? `${API}/${id}` : API;

    fetch(url, {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team_name: name, description: desc })
    })
    .then(r => {
        if(!r.ok) throw new Error("API Error");
        return r.json();
    })
    .then(() => {
        if(typeof showToast === 'function') showToast(id ? "Team updated successfully" : "Team created successfully", "success");
        // hide modal
        const modalEl = document.getElementById('teamModal');
        const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        modal.hide();
        loadTeams();
    })
    .catch(err => {
        if(typeof showToast === 'function') showToast("Error saving team", "danger");
    });
}

function deleteTeam(id) {
    if(!confirm("Delete this team?")) return;

    fetch(API + "/" + id, { method: "DELETE" })
    .then(r => {
        if(!r.ok) throw new Error("API Error");
        if(typeof showToast === 'function') showToast("Team deleted successfully", "info");
        loadTeams();
    })
    .catch(err => {
        if(typeof showToast === 'function') showToast("Error deleting team", "danger");
    });
}