// =========================================================
// repository.js – Knowledge Repository Page with Tag Search
// =========================================================

let allDecisions = [];
let currentCat   = "";
let currentTag   = "";
let currentPage  = 1;
let rowsPerPage  = 9;

function changeRepoPageSize(size) {
    if (size === 'all') {
        rowsPerPage = 999999;
    } else {
        rowsPerPage = parseInt(size, 10) || 9;
    }
    currentPage = 1;
    renderCards();
}
window.changeRepoPageSize = changeRepoPageSize;

function hydrateRepoInstantData() {
    if (window.INITIAL_APPROVED_DECISIONS && Array.isArray(window.INITIAL_APPROVED_DECISIONS) && window.INITIAL_APPROVED_DECISIONS.length > 0) {
        allDecisions = window.INITIAL_APPROVED_DECISIONS.filter(d => d && (!d.status || d.status.toLowerCase() === "approved"));
        buildCategoryFilters();
        buildTagFilters();
        updateStats();
        renderCards();
        return true;
    }
    return false;
}

try {
    hydrateRepoInstantData();
} catch (_) {}

function initRepoPage() {
    const wasHydrated = hydrateRepoInstantData();
    if (wasHydrated) {
        setTimeout(() => { fetchApprovedDecisions(); }, 300);
    } else {
        fetchApprovedDecisions();
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRepoPage);
} else {
    initRepoPage();
}

async function fetchApprovedDecisions() {
    try {
        const res = await fetch(`${API_URL}/decisions/?scope=repository&status=Approved`);
        if (!res.ok) throw new Error("Failed to load decisions");
        const all  = await res.json();
        allDecisions = (Array.isArray(all) ? all : []).filter(d => d && (!d.status || d.status.toLowerCase() === "approved"));
        buildCategoryFilters();
        buildTagFilters();
        updateStats();
        renderCards();
    } catch (err) {
        if (allDecisions.length === 0) {
            document.getElementById("repoGrid").innerHTML = `
                <div class="col-12 text-center py-5 text-danger">
                    <i data-lucide="alert-circle" style="width:24px;height:24px;" class="me-2"></i>${err.message}
                </div>`;
            if (window.lucide) lucide.createIcons();
        }
    }
}

function parseTags(tagStr) {
    if (!tagStr) return [];
    return tagStr.split(",")
        .map(t => t.trim())
        .filter(t => t.length > 0);
}

function buildCategoryFilters() {
    const cats = [...new Set(allDecisions.map(d => d.category_name).filter(Boolean))].sort();
    const container = document.getElementById("categoryBtns");
    if (!container) return;
    container.innerHTML = cats.map(c => `
        <button class="btn btn-sm px-3 fw-semibold"
            style="background:rgba(255,255,255,0.1);color:#CBD5E1;font-size:11px;border-radius:20px;border:1px solid rgba(255,255,255,0.15);transition:all 0.2s;"
            onclick="setCat('${c}', this)">${c}</button>`).join("");
}

function buildTagFilters() {
    const tagCountMap = {};
    
    // Aggregate tags across approved decisions
    allDecisions.forEach(d => {
        const tags = parseTags(d.tags);
        tags.forEach(t => {
            tagCountMap[t] = (tagCountMap[t] || 0) + 1;
        });
    });

    // Default tag fallbacks if few tags exist
    const defaultTagPool = ["Technology", "Budget", "Cloud", "Security", "Operations", "AI", "Q4", "Policy", "Infrastructure", "Optimization"];
    defaultTagPool.forEach(dt => {
        if (!tagCountMap[dt]) {
            tagCountMap[dt] = 0;
        }
    });

    // Sort by count descending, then alphabetical
    const sortedTags = Object.keys(tagCountMap).sort((a, b) => {
        if (tagCountMap[b] !== tagCountMap[a]) {
            return tagCountMap[b] - tagCountMap[a];
        }
        return a.localeCompare(b);
    });

    const container = document.getElementById("tagFilterButtons");
    if (!container) return;

    // Filter tags relevant to current category if selected
    let tagsToRender = sortedTags;
    if (currentCat) {
        tagsToRender = sortedTags.filter(t => {
            return allDecisions.some(d => d.category_name === currentCat && (d.tags || "").toLowerCase().includes(t.toLowerCase())) ||
                   t.toLowerCase().includes(currentCat.toLowerCase()) ||
                   currentCat.toLowerCase().includes(t.toLowerCase());
        });
        if (tagsToRender.length === 0) tagsToRender = sortedTags.slice(0, 8);
    }

    container.innerHTML = `
        <span class="tag-filter-pill ${currentTag === '' ? 'active' : ''}" onclick="setTag('', this)">
            All Tags
        </span>
        ${tagsToRender.map(tag => {
            const count = tagCountMap[tag] || 0;
            const isActive = currentTag.toLowerCase() === tag.toLowerCase();
            return `
                <span class="tag-filter-pill ${isActive ? 'active' : ''}" onclick="setTag('${tag}', this)">
                    #${tag} ${count > 0 ? `<span class="badge bg-white text-dark rounded-pill px-1.5 py-0.5" style="font-size:9.5px; margin-left:2px;">${count}</span>` : ''}
                </span>
            `;
        }).join("")}
    `;

    const clearTagBtn = document.getElementById("btnClearTag");
    if (clearTagBtn) {
        clearTagBtn.style.display = currentTag ? "inline-block" : "none";
    }
}

function setCat(cat, btn) {
    currentCat  = cat;
    currentPage = 1;
    
    // Reset category styles
    const catAll = document.getElementById("catAll");
    if (catAll) {
        catAll.style.background = cat === "" ? "#2563EB" : "rgba(255,255,255,0.1)";
        catAll.style.color      = cat === "" ? "white"   : "#CBD5E1";
    }
    document.querySelectorAll("#categoryBtns button").forEach(b => {
        const isActive = b.textContent.trim() === cat;
        b.style.background = isActive ? "#2563EB" : "rgba(255,255,255,0.1)";
        b.style.color      = isActive ? "white"   : "#CBD5E1";
    });

    buildTagFilters();
    updateActiveFilterBadges();
    renderCards();
}

function setTag(tag, target) {
    if (currentTag.toLowerCase() === tag.toLowerCase()) {
        currentTag = ""; // Toggle off
    } else {
        currentTag = tag;
    }
    currentPage = 1;
    
    buildTagFilters();
    updateActiveFilterBadges();
    renderCards();
}

function filterRepo() {
    currentPage = 1;
    const input = document.getElementById("repoSearch");
    const clearBtn = document.getElementById("btnClearSearch");
    if (clearBtn && input) {
        clearBtn.style.display = input.value.trim() ? "inline-block" : "none";
    }
    updateActiveFilterBadges();
    renderCards();
}

function clearSearch() {
    const input = document.getElementById("repoSearch");
    if (input) {
        input.value = "";
    }
    const clearBtn = document.getElementById("btnClearSearch");
    if (clearBtn) {
        clearBtn.style.display = "none";
    }
    filterRepo();
}

function updateActiveFilterBadges() {
    const container = document.getElementById("activeFilterBadgeContainer");
    if (!container) return;

    let badgesHtml = "";
    if (currentCat) {
        badgesHtml += `
            <span class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill px-2.5 py-1 d-inline-flex align-items-center gap-1" style="font-size:11.5px;">
                Category: ${currentCat}
                <i class="bi bi-x cursor-pointer" onclick="setCat('', null)"></i>
            </span>
        `;
    }
    if (currentTag) {
        badgesHtml += `
            <span class="badge bg-info-subtle text-info-emphasis border border-info-subtle rounded-pill px-2.5 py-1 d-inline-flex align-items-center gap-1" style="font-size:11.5px;">
                Tag: #${currentTag}
                <i class="bi bi-x cursor-pointer" onclick="setTag('', null)"></i>
            </span>
        `;
    }
    const searchVal = document.getElementById("repoSearch")?.value?.trim();
    if (searchVal) {
        badgesHtml += `
            <span class="badge bg-secondary-subtle text-secondary border rounded-pill px-2.5 py-1 d-inline-flex align-items-center gap-1" style="font-size:11.5px;">
                Search: "${searchVal}"
                <i class="bi bi-x cursor-pointer" onclick="clearSearch()"></i>
            </span>
        `;
    }
    if (badgesHtml) {
        badgesHtml = `<span class="text-muted small me-1" style="font-size:11.5px;">Active Filters:</span>` + badgesHtml;
    }
    container.innerHTML = badgesHtml;
}

function updateStats() {
    const repoCountEl = document.getElementById("repoCount");
    if (repoCountEl) {
        repoCountEl.innerText = allDecisions.length;
    }
    const repoCatCountEl = document.getElementById("repoCategoryCount");
    if (repoCatCountEl) {
        repoCatCountEl.innerText = new Set(allDecisions.map(d => d.category_name).filter(Boolean)).size;
    }
}

function getFiltered() {
    let query = (document.getElementById("repoSearch")?.value || "").toLowerCase().trim();
    if (query.startsWith("#")) {
        query = query.substring(1).trim();
    }

    return allDecisions.filter(d => {
        // 1. Category Filter
        const matchCat = !currentCat || d.category_name === currentCat;
        
        // 2. Tag Filter
        const tags = parseTags(d.tags).map(t => t.toLowerCase());
        const matchTag = !currentTag || 
            tags.some(t => t.includes(currentTag.toLowerCase()) || currentTag.toLowerCase().includes(t)) ||
            (d.category_name || "").toLowerCase().includes(currentTag.toLowerCase()) ||
            (d.title || "").toLowerCase().includes(currentTag.toLowerCase());

        // 3. Search Query Filter (Title, Description, Category, Tags, Creator, DEC ID)
        const decIdStr = `dec-${d.id}`.toLowerCase();
        const rawIdStr = `${d.id}`;
        const matchSearch = !query ||
            d.title.toLowerCase().includes(query) ||
            (d.description || "").toLowerCase().includes(query) ||
            (d.category_name || "").toLowerCase().includes(query) ||
            tags.some(t => t.includes(query)) ||
            (d.creator_name || "").toLowerCase().includes(query) ||
            decIdStr.includes(query) ||
            rawIdStr === query;

        return matchCat && matchTag && matchSearch;
    });
}

function renderCards() {
    const filtered   = getFiltered();
    const totalPages = Math.ceil(filtered.length / rowsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;

    const start    = (currentPage - 1) * rowsPerPage;
    const pageData = filtered.slice(start, start + rowsPerPage);

    const grid = document.getElementById("repoGrid");
    const countDisplay = document.getElementById("repoCount");
    if (countDisplay) {
        countDisplay.innerText = filtered.length;
    }

    if (pageData.length === 0) {
        grid.innerHTML = `
            <div class="col-12" style="display:flex;flex-direction:column;align-items:center;padding:70px 0;color:#94A3B8;text-align:center;">
                <i data-lucide="book-open" style="width:48px;height:48px;color:#CBD5E1;" class="mb-3"></i>
                <h5 class="fw-semibold text-dark mb-1">No Approved Decisions Found</h5>
                <p class="text-muted mb-3" style="font-size:13.5px;">No decisions match your current search criteria or tag filters.</p>
                <button class="btn btn-sm btn-outline-primary rounded-pill px-3 py-1.5" onclick="clearAllFilters()">
                    Reset All Filters
                </button>
            </div>`;
        if (window.lucide) lucide.createIcons();
    } else {
        grid.innerHTML = pageData.map(d => {
            const date     = new Date(d.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
            const initials = d.creator_initials || (d.creator_name || "U").substring(0, 2).toUpperCase();
            const desc     = (d.description || "No description provided.").substring(0, 120);
            const cat      = d.category_name || "Uncategorized";
            
            // Format decision tags
            const tags = parseTags(d.tags);
            let tagsHtml = "";
            if (tags.length > 0) {
                tagsHtml = tags.map(t => `
                    <span class="tag-badge" title="Filter by #${t}" onclick="setTag('${t}', event); event.stopPropagation();">
                        #${t}
                    </span>
                `).join(" ");
            } else {
                tagsHtml = `
                    <span class="tag-badge" title="Filter by #${cat}" onclick="setTag('${cat}', event); event.stopPropagation();">
                        #${cat}
                    </span>
                `;
            }

            // Determine whether to show owner info: Only shown for Administrator accounts
            const isAdminUser = (typeof IS_ADMIN !== 'undefined' && IS_ADMIN === true) ||
                                (typeof CURRENT_USER_ROLE !== 'undefined' && CURRENT_USER_ROLE.toLowerCase().includes('admin')) ||
                                (localStorage.getItem('role_name') || '').toLowerCase().includes('admin');

            let footerHtml = '';
            if (isAdminUser) {
                footerHtml = `
                    <div class="d-flex justify-content-between align-items-center mt-auto pt-2 border-top">
                        <div class="d-flex align-items-center gap-2">
                            <div style="width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,#667EEA,#764BA2);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:white;">${initials}</div>
                            <span class="text-muted" style="font-size:11.5px;font-weight:500;">${d.creator_name || "Unknown"}</span>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <span class="text-muted" style="font-size:11px;">${date}</span>
                            <a href="/decision/${d.id}" class="btn btn-sm px-3 rounded-pill" style="background:#EEF2FF;color:#4F46E5;font-size:11px;font-weight:600;border:none;">View →</a>
                        </div>
                    </div>
                `;
            } else {
                footerHtml = `
                    <div class="d-flex justify-content-between align-items-center mt-auto pt-2 border-top">
                        <div class="d-flex align-items-center gap-1.5 text-muted" style="font-size:11.5px;">
                            <i data-lucide="calendar" style="width: 14px; height: 14px;" class="text-secondary"></i>
                            <span>${date}</span>
                        </div>
                        <a href="/decision/${d.id}" class="btn btn-sm px-3 rounded-pill" style="background:#EEF2FF;color:#4F46E5;font-size:11.5px;font-weight:600;border:none;">View Details →</a>
                    </div>
                `;
            }

            return `
            <div class="col-md-6 col-lg-4">
                <div class="repo-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="d-flex align-items-center gap-1.5">
                            <span style="background:#ECFDF5;color:#059669;font-size:10.5px;font-weight:700;padding:3px 9px;border-radius:20px;">✓ Approved</span>
                            <span class="badge bg-light text-secondary border rounded-pill px-2 py-0.5" style="font-size: 10px;">DEC-${d.id}</span>
                        </div>
                        <span style="background:#EEF2FF;color:#4F46E5;font-size:10.5px;font-weight:700;padding:3px 9px;border-radius:20px;">${cat}</span>
                    </div>
                    <div class="repo-card-title">${d.title}</div>
                    <div class="repo-card-desc">${desc}${d.description && d.description.length > 120 ? "…" : ""}</div>
                    
                    <!-- Decision Tags List -->
                    <div class="d-flex flex-wrap gap-1.5 mb-3">
                        ${tagsHtml}
                    </div>

                    ${footerHtml}
                </div>
            </div>`;
        }).join("");
        if (window.lucide) lucide.createIcons();
    }

    const info = filtered.length === 0 ? "" :
        `Showing ${start + 1}–${Math.min(start + rowsPerPage, filtered.length)} of ${filtered.length} results`;
    const pagInfo = document.getElementById("repoPaginationInfo");
    if (pagInfo) pagInfo.innerText = info;
    const btnPrev = document.getElementById("repoBtnPrev");
    if (btnPrev) btnPrev.disabled = (currentPage === 1);
    const btnNext = document.getElementById("repoBtnNext");
    if (btnNext) btnNext.disabled = (currentPage >= totalPages);
}

function clearAllFilters() {
    currentCat = "";
    currentTag = "";
    const input = document.getElementById("repoSearch");
    if (input) input.value = "";
    const clearBtn = document.getElementById("btnClearSearch");
    if (clearBtn) clearBtn.style.display = "none";
    
    setCat("", null);
}

function prevPage() { if (currentPage > 1) { currentPage--; renderCards(); } }
function nextPage() { currentPage++; renderCards(); }
