/**
 * Single-Page Web Application Frontend Logic for PMS
 * Handles 70/30 score engine rendering, responsive mobile cards, hierarchy tree, and persona switching.
 */

let allUsers = [];
let currentUserId = null;
let currentPmsData = null;

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    await fetchUsers();
    await fetchDepartments();
    lucide.createIcons();
}

async function fetchUsers() {
    try {
        const res = await fetch("/api/users");
        allUsers = await res.json();
        populateUserSelector();
        populateManagerDropdown();

        if (!currentUserId && allUsers.length > 0) {
            const mdUser = allUsers.find(u => u.role === "MD") || allUsers[0];
            currentUserId = mdUser.id;
        }

        if (currentUserId) {
            document.getElementById("userSelector").value = currentUserId;
            await loadUserDashboard(currentUserId);
        }
    } catch (err) {
        console.error("Error loading users:", err);
    }
}

async function fetchDepartments() {
    try {
        const res = await fetch("/api/departments");
        const depts = await res.json();
        const select = document.getElementById("newUserDepartment");
        select.innerHTML = depts.map(d => `<option value="${d.id}">${d.name} (${d.code})</option>`).join("");
    } catch (err) {
        console.error("Error loading departments:", err);
    }
}

function populateUserSelector() {
    const select = document.getElementById("userSelector");
    select.innerHTML = allUsers.map(u => 
        `<option value="${u.id}">${u.name} [${u.role}] - ${u.designation}</option>`
    ).join("");
}

function populateManagerDropdown() {
    const select = document.getElementById("newUserManager");
    select.innerHTML = `<option value="">None (Top Level / MD)</option>` + 
        allUsers.map(u => `<option value="${u.id}">${u.name} (${u.role} - ${u.designation})</option>`).join("");
}

async function switchActiveUser(userId) {
    currentUserId = parseInt(userId);
    await loadUserDashboard(currentUserId);
}

async function loadUserDashboard(userId) {
    try {
        const res = await fetch(`/api/users/${userId}/pms`);
        currentPmsData = await res.json();
        renderHeaderStats();
        renderKraTables();
        renderHierarchyTree();
        renderTeamMembersTable();
        fetchAnalytics();
        lucide.createIcons();
    } catch (err) {
        console.error("Error loading PMS dashboard:", err);
    }
}

function renderHeaderStats() {
    if (!currentPmsData) return;
    const u = currentPmsData.user;
    const pms = currentPmsData.pms;
    const appMeta = currentPmsData.appraisal_status;

    document.getElementById("statUserName").innerText = u.name;
    document.getElementById("statUserDesignation").innerText = u.designation + " | " + (u.department_name || "Executive");
    document.getElementById("statUserManager").innerText = u.manager_name ? u.manager_name : "Board of Directors";
    document.getElementById("statUserRole").innerText = u.role + " Persona";

    document.getElementById("statCompositeScore").innerText = pms.composite_score.toFixed(1) + "%";
    
    const badge = document.getElementById("statGradeBadge");
    badge.innerText = "Grade " + pms.grade;
    badge.className = `px-1.5 py-0.5 text-[10px] sm:text-xs font-bold rounded ${
        pms.grade === 'A+' ? 'bg-emerald-100 text-emerald-800' :
        pms.grade === 'A' ? 'bg-sky-100 text-sky-800' :
        pms.grade === 'B' ? 'bg-indigo-100 text-indigo-800' :
        pms.grade === 'C' ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'
    }`;

    document.getElementById("statBandName").innerText = pms.performance_band;
    document.getElementById("statAppraisalStatus").innerText = appMeta.status;
    document.getElementById("statDownchainCount").innerText = `${currentPmsData.downchain_total_count} Reports`;

    document.getElementById("selfCommentsInput").value = appMeta.self_comments || "";
    document.getElementById("managerCommentsInput").value = appMeta.manager_comments || "";
}

function renderKraTables() {
    if (!currentPmsData) return;
    const pms = currentPmsData.pms;

    // Summary numbers
    document.getElementById("summaryPresent70Score").innerText = pms.present_year.raw_score.toFixed(1) + "%";
    document.getElementById("summaryPresentWeightSum").innerText = `Weight: ${pms.present_year.total_kra_weight_sum}%`;
    document.getElementById("summaryUpcoming30Score").innerText = pms.upcoming_year.raw_score.toFixed(1) + "%";
    document.getElementById("summaryUpcomingWeightSum").innerText = `Weight: ${pms.upcoming_year.total_kra_weight_sum}%`;
    document.getElementById("summaryCompositeScore").innerText = pms.composite_score.toFixed(1) + "%";
    document.getElementById("summaryGrade").innerText = `Grade ${pms.grade} (${pms.performance_band.split('/')[0]})`;

    // PRESENT YEAR - Desktop Table
    const presentTbody = document.getElementById("presentKraTableBody");
    const presentCardsContainer = document.getElementById("presentKraMobileCards");

    if (pms.present_year.kras.length === 0) {
        const emptyHtml = `<div class="p-4 text-center text-slate-400 italic text-xs">No Present Year EVA KRAs defined. Click "+ Add KRA" above to add.</div>`;
        if (presentTbody) presentTbody.innerHTML = `<tr><td colspan="9" class="p-4 text-center text-slate-400 italic">No Present Year KRAs defined.</td></tr>`;
        if (presentCardsContainer) presentCardsContainer.innerHTML = emptyHtml;
    } else {
        if (presentTbody) {
            presentTbody.innerHTML = pms.present_year.kras.map(kra => `
                <tr class="hover:bg-slate-50 transition">
                    <td class="p-3">
                        <div class="font-bold text-slate-900">${kra.lever_name}</div>
                        <div class="text-[11px] text-slate-500">${kra.description || ''}</div>
                    </td>
                    <td class="p-3 font-medium text-slate-600">${kra.metric_unit}</td>
                    <td class="p-3 text-right font-semibold text-slate-700">${kra.target_value}</td>
                    <td class="p-3 text-right">
                        <input type="number" step="0.01" value="${kra.actual_outcome}" 
                            onchange="updateKraOutcome(${kra.id}, this.value, ${kra.self_rating_percent}, ${kra.manager_rating_percent})"
                            class="w-20 text-right text-xs p-1 border border-slate-300 rounded focus:ring-1 focus:ring-sky-500">
                    </td>
                    <td class="p-3 text-right font-bold ${kra.achievement_percent >= 100 ? 'text-emerald-600' : 'text-amber-600'}">
                        ${kra.achievement_percent}%
                    </td>
                    <td class="p-3 text-right font-medium text-slate-600">${kra.weightage_percent}%</td>
                    <td class="p-3 text-right">
                        <span class="px-2 py-0.5 bg-sky-50 text-sky-700 font-bold rounded">${kra.computed_self_rating.toFixed(1)}%</span>
                    </td>
                    <td class="p-3 text-right font-extrabold text-sky-900">${kra.weighted_contribution}%</td>
                    <td class="p-3 text-center">
                        <button onclick="deleteKra(${kra.id})" class="text-rose-500 hover:text-rose-700 p-1">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </td>
                </tr>
            `).join("");
        }

        if (presentCardsContainer) {
            presentCardsContainer.innerHTML = pms.present_year.kras.map(kra => `
                <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-xs space-y-2">
                    <div class="flex justify-between items-start">
                        <div>
                            <span class="text-[9px] font-bold text-sky-700 bg-sky-50 px-1.5 py-0.5 rounded border border-sky-200 uppercase">${kra.metric_unit}</span>
                            <h4 class="text-xs font-bold text-slate-900 mt-1">${kra.lever_name}</h4>
                            ${kra.description ? `<p class="text-[10px] text-slate-500">${kra.description}</p>` : ''}
                        </div>
                        <button onclick="deleteKra(${kra.id})" class="text-rose-500 p-1">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>

                    <div class="grid grid-cols-2 gap-2 bg-slate-50 p-2 rounded-lg border border-slate-100 text-xs">
                        <div>
                            <span class="text-[10px] text-slate-500 block">Target Value</span>
                            <span class="font-bold text-slate-800">${kra.target_value}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-500 block">Actual Outcome</span>
                            <input type="number" step="0.01" value="${kra.actual_outcome}" 
                                onchange="updateKraOutcome(${kra.id}, this.value, ${kra.self_rating_percent}, ${kra.manager_rating_percent})"
                                class="w-full text-right font-bold text-xs p-1 border border-slate-300 rounded bg-white focus:ring-1 focus:ring-sky-500">
                        </div>
                    </div>

                    <div class="flex items-center justify-between text-[11px] pt-1">
                        <div>
                            <span class="text-slate-500">Achievement: </span>
                            <span class="font-bold ${kra.achievement_percent >= 100 ? 'text-emerald-600' : 'text-amber-600'}">${kra.achievement_percent}%</span>
                        </div>
                        <div>
                            <span class="text-slate-500">Weight: </span>
                            <span class="font-bold text-slate-700">${kra.weightage_percent}%</span>
                        </div>
                        <div>
                            <span class="text-slate-500">Score: </span>
                            <span class="font-extrabold text-sky-900">${kra.weighted_contribution}%</span>
                        </div>
                    </div>
                </div>
            `).join("");
        }
    }

    // UPCOMING YEAR - Desktop Table & Mobile Cards
    const upcomingTbody = document.getElementById("upcomingKraTableBody");
    const upcomingCardsContainer = document.getElementById("upcomingKraMobileCards");

    if (pms.upcoming_year.kras.length === 0) {
        const emptyHtml = `<div class="p-4 text-center text-slate-400 italic text-xs">No Upcoming Year Objectives defined. Click "+ Add Objective" above to add.</div>`;
        if (upcomingTbody) upcomingTbody.innerHTML = `<tr><td colspan="9" class="p-4 text-center text-slate-400 italic">No Upcoming Objectives defined.</td></tr>`;
        if (upcomingCardsContainer) upcomingCardsContainer.innerHTML = emptyHtml;
    } else {
        if (upcomingTbody) {
            upcomingTbody.innerHTML = pms.upcoming_year.kras.map(kra => `
                <tr class="hover:bg-slate-50 transition">
                    <td class="p-3">
                        <div class="font-bold text-slate-900">${kra.lever_name}</div>
                        <div class="text-[11px] text-slate-500">${kra.description || ''}</div>
                    </td>
                    <td class="p-3 font-medium text-slate-600">${kra.metric_unit}</td>
                    <td class="p-3 text-right font-semibold text-slate-700">${kra.target_value}</td>
                    <td class="p-3 text-right">
                        <input type="number" step="0.01" value="${kra.actual_outcome}" 
                            onchange="updateKraOutcome(${kra.id}, this.value, ${kra.self_rating_percent}, ${kra.manager_rating_percent})"
                            class="w-20 text-right text-xs p-1 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500">
                    </td>
                    <td class="p-3 text-right font-bold ${kra.achievement_percent >= 100 ? 'text-emerald-600' : 'text-amber-600'}">
                        ${kra.achievement_percent}%
                    </td>
                    <td class="p-3 text-right font-medium text-slate-600">${kra.weightage_percent}%</td>
                    <td class="p-3 text-right">
                        <span class="px-2 py-0.5 bg-indigo-50 text-indigo-700 font-bold rounded">${kra.computed_self_rating.toFixed(1)}%</span>
                    </td>
                    <td class="p-3 text-right font-extrabold text-indigo-900">${kra.weighted_contribution}%</td>
                    <td class="p-3 text-center">
                        <button onclick="deleteKra(${kra.id})" class="text-rose-500 hover:text-rose-700 p-1">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </td>
                </tr>
            `).join("");
        }

        if (upcomingCardsContainer) {
            upcomingCardsContainer.innerHTML = pms.upcoming_year.kras.map(kra => `
                <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-xs space-y-2">
                    <div class="flex justify-between items-start">
                        <div>
                            <span class="text-[9px] font-bold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200 uppercase">${kra.metric_unit}</span>
                            <h4 class="text-xs font-bold text-slate-900 mt-1">${kra.lever_name}</h4>
                            ${kra.description ? `<p class="text-[10px] text-slate-500">${kra.description}</p>` : ''}
                        </div>
                        <button onclick="deleteKra(${kra.id})" class="text-rose-500 p-1">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>

                    <div class="grid grid-cols-2 gap-2 bg-slate-50 p-2 rounded-lg border border-slate-100 text-xs">
                        <div>
                            <span class="text-[10px] text-slate-500 block">Target Value</span>
                            <span class="font-bold text-slate-800">${kra.target_value}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-500 block">Actual Outcome</span>
                            <input type="number" step="0.01" value="${kra.actual_outcome}" 
                                onchange="updateKraOutcome(${kra.id}, this.value, ${kra.self_rating_percent}, ${kra.manager_rating_percent})"
                                class="w-full text-right font-bold text-xs p-1 border border-slate-300 rounded bg-white focus:ring-1 focus:ring-indigo-500">
                        </div>
                    </div>

                    <div class="flex items-center justify-between text-[11px] pt-1">
                        <div>
                            <span class="text-slate-500">Progress: </span>
                            <span class="font-bold ${kra.achievement_percent >= 100 ? 'text-emerald-600' : 'text-amber-600'}">${kra.achievement_percent}%</span>
                        </div>
                        <div>
                            <span class="text-slate-500">Weight: </span>
                            <span class="font-bold text-slate-700">${kra.weightage_percent}%</span>
                        </div>
                        <div>
                            <span class="text-slate-500">Score: </span>
                            <span class="font-extrabold text-indigo-900">${kra.weighted_contribution}%</span>
                        </div>
                    </div>
                </div>
            `).join("");
        }
    }
}

async function updateKraOutcome(kraId, outcome, selfRating, mgrRating) {
    try {
        await fetch(`/api/kras/${kraId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                actual_outcome: parseFloat(outcome) || 0,
                self_rating_percent: parseFloat(selfRating) || 0,
                manager_rating_percent: parseFloat(mgrRating) || 0
            })
        });
        await loadUserDashboard(currentUserId);
    } catch (err) {
        console.error("Error updating KRA outcome:", err);
    }
}

async function deleteKra(kraId) {
    if (!confirm("Are you sure you want to delete this KRA lever?")) return;
    try {
        await fetch(`/api/kras/${kraId}`, { method: "DELETE" });
        await loadUserDashboard(currentUserId);
    } catch (err) {
        console.error("Error deleting KRA:", err);
    }
}

async function renderHierarchyTree() {
    try {
        const res = await fetch("/api/hierarchy");
        const treeData = await res.json();
        const container = document.getElementById("hierarchyTreeContainer");
        container.innerHTML = treeData.map(node => renderTreeNode(node)).join("");
        lucide.createIcons();
    } catch (err) {
        console.error("Error rendering hierarchy tree:", err);
    }
}

function toggleMobileNav() {
    const menu = document.getElementById("mobileNavMenu");
    menu.classList.toggle("hidden");
}

function renderTreeNode(node, level = 0) {
    const roleColors = {
        ADMIN: "bg-purple-100 text-purple-800 border-purple-200",
        MD: "bg-sky-100 text-sky-900 border-sky-300 font-extrabold",
        GM: "bg-indigo-100 text-indigo-800 border-indigo-200",
        HOD: "bg-blue-100 text-blue-800 border-blue-200",
        MANAGER: "bg-emerald-100 text-emerald-800 border-emerald-200",
        SUPERVISOR: "bg-amber-100 text-amber-800 border-amber-200",
        EMPLOYEE: "bg-slate-100 text-slate-800 border-slate-200"
    };

    const badgeStyle = roleColors[node.role] || "bg-slate-100 text-slate-800";
    const indentClass = level === 0 ? "" : level === 1 ? "ml-1.5 sm:ml-6 border-l-2 border-sky-200 pl-1.5 sm:pl-4" : "ml-3 sm:ml-12 border-l-2 border-slate-200 pl-1.5 sm:pl-4";

    let reportsHtml = "";
    if (node.reports && node.reports.length > 0) {
        reportsHtml = `<div class="mt-1.5 space-y-1.5">${node.reports.map(child => renderTreeNode(child, level + 1)).join("")}</div>`;
    }

    return `
        <div class="${indentClass} my-1.5">
            <div class="bg-white p-2 sm:p-3 rounded-xl border border-slate-200 hover:border-sky-400 shadow-xs flex flex-row items-center justify-between gap-1 transition cursor-pointer" onclick="switchActiveUser(${node.id})">
                <div class="flex items-center space-x-2 min-w-0">
                    <div class="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-slate-900 text-white font-bold text-[9px] sm:text-xs flex items-center justify-center flex-shrink-0">
                        ${node.name.split(' ').map(n=>n[0]).join('')}
                    </div>
                    <div class="min-w-0">
                        <div class="flex items-center space-x-1 flex-wrap">
                            <span class="font-bold text-[11px] sm:text-xs text-slate-900 truncate">${node.name}</span>
                            <span class="px-1 py-0.2 text-[8px] sm:text-[10px] rounded font-bold border ${badgeStyle}">${node.role}</span>
                        </div>
                        <p class="text-[9px] sm:text-[11px] text-slate-500 truncate">${node.designation}</p>
                    </div>
                </div>

                <div class="flex items-center space-x-2 flex-shrink-0">
                    <div class="text-right">
                        <div class="text-[11px] sm:text-xs font-black text-slate-900">${node.composite_score.toFixed(1)}%</div>
                        <div class="text-[8px] sm:text-[10px] font-bold text-emerald-600">Grade ${node.grade}</div>
                    </div>
                    <button class="px-1.5 py-0.5 bg-slate-100 hover:bg-sky-50 text-slate-600 text-[10px] font-semibold rounded border transition">
                        View
                    </button>
                </div>
            </div>
            ${reportsHtml}
        </div>
    `;
}

function renderTeamMembersTable() {
    if (!currentPmsData) return;
    const tbody = document.getElementById("teamMembersTableBody");
    const reports = currentPmsData.direct_reports || [];

    if (reports.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-slate-400 italic text-xs">No direct reports under current persona. Switch persona to Manager, HOD, GM, or MD.</td></tr>`;
        return;
    }

    tbody.innerHTML = reports.map(r => `
        <tr class="hover:bg-slate-50 transition">
            <td class="p-2.5 font-bold text-slate-900">${r.name}</td>
            <td class="p-2.5 font-semibold text-sky-700">${r.role}</td>
            <td class="p-2.5 text-slate-600">${r.designation}</td>
            <td class="p-2.5 text-right font-extrabold text-slate-900">${r.composite_score.toFixed(1)}%</td>
            <td class="p-2.5 text-center">
                <span class="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800">Grade ${r.grade}</span>
            </td>
            <td class="p-2.5 text-center">
                <button onclick="switchActiveUser(${r.id})" class="px-2.5 py-1 bg-sky-600 hover:bg-sky-700 text-white font-semibold text-[11px] rounded-lg transition">
                    Inspect
                </button>
            </td>
        </tr>
    `).join("");
}

async function fetchAnalytics() {
    try {
        const res = await fetch("/api/analytics");
        const data = await res.json();
        const container = document.getElementById("analyticsContainer");

        const bandColors = {
            "Outstanding / Exceptional": "bg-emerald-50 text-emerald-800 border-emerald-200",
            "Exceeds Expectations": "bg-sky-50 text-sky-800 border-sky-200",
            "Meets Expectations": "bg-indigo-50 text-indigo-800 border-indigo-200",
            "Needs Improvement": "bg-amber-50 text-amber-800 border-amber-200",
            "Unsatisfactory": "bg-rose-50 text-rose-800 border-rose-200"
        };

        container.innerHTML = Object.entries(data.performance_band_distribution).map(([band, count]) => `
            <div class="p-2 sm:p-3 rounded-xl border ${bandColors[band] || 'bg-slate-50'} text-center shadow-xs">
                <div class="text-[9px] sm:text-xs font-bold uppercase tracking-wider opacity-80">${band.split('/')[0]}</div>
                <div class="text-lg sm:text-2xl font-black mt-0.5">${count}</div>
                <div class="text-[8px] sm:text-[10px] opacity-75">Staff</div>
            </div>
        `).join("");
    } catch (err) {
        console.error("Error fetching analytics:", err);
    }
}

function openAddKRAModal(section) {
    document.getElementById("kraSectionInput").value = section;
    document.getElementById("modalTitle").innerText = section === "PRESENT_YEAR_70" ? 
        "Add KRA to Section 1: Key Deliverables impact Current EVA (70%)" : "Add KRA to Section 2: Key Deliverables impact Future EVA (30%)";
    document.getElementById("addKraModal").classList.remove("hidden");
    document.getElementById("addKraModal").classList.add("flex");
}

function closeAddKRAModal() {
    document.getElementById("addKraModal").classList.add("hidden");
    document.getElementById("addKraModal").classList.remove("flex");
}

async function handleSaveKRA(e) {
    e.preventDefault();
    const section = document.getElementById("kraSectionInput").value;
    const kraData = {
        user_id: currentUserId,
        year: 2026,
        section: section,
        lever_name: document.getElementById("kraLeverName").value,
        description: document.getElementById("kraDescription").value,
        metric_unit: document.getElementById("kraMetricUnit").value,
        target_value: parseFloat(document.getElementById("kraTargetValue").value) || 0,
        actual_outcome: parseFloat(document.getElementById("kraActualOutcome").value) || 0,
        weightage_percent: parseFloat(document.getElementById("kraWeightage").value) || 0,
    };

    try {
        await fetch("/api/kras", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(kraData)
        });
        closeAddKRAModal();
        document.getElementById("kraForm").reset();
        await loadUserDashboard(currentUserId);
    } catch (err) {
        console.error("Error saving KRA:", err);
    }
}

async function handleCreateUser(e) {
    e.preventDefault();
    const userData = {
        name: document.getElementById("newUserName").value,
        email: document.getElementById("newUserEmail").value,
        role: document.getElementById("newUserRole").value,
        designation: document.getElementById("newUserDesignation").value,
        department_id: parseInt(document.getElementById("newUserDepartment").value) || 1,
        manager_id: document.getElementById("newUserManager").value ? parseInt(document.getElementById("newUserManager").value) : null
    };

    try {
        const res = await fetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(userData)
        });
        const result = await res.json();
        if (res.ok) {
            alert(result.message);
            document.getElementById("addUserForm").reset();
            await fetchUsers();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (err) {
        console.error("Error creating user:", err);
    }
}

async function submitAppraisalForm(status) {
    try {
        await fetch("/api/appraisals/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: currentUserId,
                year: 2026,
                status: status,
                self_comments: document.getElementById("selfCommentsInput").value,
                manager_comments: document.getElementById("managerCommentsInput").value
            })
        });
        alert(`Appraisal status updated to ${status}!`);
        await loadUserDashboard(currentUserId);
    } catch (err) {
        console.error("Error submitting appraisal:", err);
    }
}

function switchTab(tabId) {
    const tabs = ["appraisalTab", "hierarchyTab", "teamTab", "adminTab"];
    tabs.forEach(t => {
        document.getElementById(t).classList.add("hidden");
    });
    document.getElementById(tabId).classList.remove("hidden");

    const btnMap = {
        appraisalTab: "tabBtnAppraisal",
        hierarchyTab: "tabBtnHierarchy",
        teamTab: "tabBtnTeam",
        adminTab: "tabBtnAdmin"
    };

    Object.values(btnMap).forEach(bId => {
        const btn = document.getElementById(bId);
        btn.className = "py-3 text-xs sm:text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center gap-2 whitespace-nowrap";
    });

    document.getElementById(btnMap[tabId]).className = "py-3 text-xs sm:text-sm font-semibold border-b-2 border-sky-600 text-sky-600 flex items-center gap-2 whitespace-nowrap";

    // Close mobile menu if open
    const menu = document.getElementById("mobileNavMenu");
    if (menu && !menu.classList.contains("hidden")) {
        menu.classList.add("hidden");
    }
}
