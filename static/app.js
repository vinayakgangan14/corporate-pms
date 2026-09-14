/**
 * Single-Page Web Application Frontend Logic for Purechem PMS
 * Supports Administrator Configurable Section Weightages & 100% KRA Weightage Sum Enforcement.
 */

let allUsers = [];
let loggedInUserId = null;
let viewingUserId = null;
let currentPmsData = null;
let activeSettings = { section1_weightage: 70.0, section2_weightage: 30.0 };
let roleSettings = {};

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    await fetchRoleSettings();
    await fetchUsers();
    await fetchDepartments();
    lucide.createIcons();
}

async function fetchRoleSettings() {
    try {
        const res = await fetch("/api/settings/roles");
        roleSettings = await res.json();
        renderRoleSettingsTable();
    } catch (err) {
        console.error("Error loading role settings:", err);
    }
}

function renderRoleSettingsTable() {
    const tbody = document.getElementById("roleWeightagesTableBody");
    if (!tbody) return;

    const roleLabels = {
        "MD": "Managing Director (MD)",
        "GM": "General Manager (GM)",
        "HOD": "Head of Department (HOD)",
        "MANAGER": "Manager",
        "SUPERVISOR": "Supervisor",
        "EMPLOYEE": "Staff / Individual Contributor",
        "ADMIN": "System Administrator"
    };

    const rolesOrder = ["MD", "GM", "HOD", "MANAGER", "SUPERVISOR", "EMPLOYEE", "ADMIN"];

    tbody.innerHTML = rolesOrder.map(r => {
        const setting = roleSettings[r] || { section1_weight: 70.0, section2_weight: 30.0 };
        const sec1 = setting.section1_weight;
        const sec2 = setting.section2_weight;
        const total = sec1 + sec2;
        const isValid = Math.abs(total - 100.0) < 0.1;

        return `
            <tr class="hover:bg-slate-800/50 transition">
                <td class="py-2.5 px-3 font-bold text-white">${roleLabels[r] || r}</td>
                <td class="py-2.5 px-3">
                    <input type="number" step="1" min="1" max="99" id="role_sec1_${r}" value="${sec1}"
                        onchange="validateRoleWeightInputs('${r}')"
                        class="w-20 text-xs p-1.5 bg-slate-950 text-sky-300 font-bold border border-slate-700 rounded focus:ring-2 focus:ring-sky-500 focus:outline-none">
                </td>
                <td class="py-2.5 px-3">
                    <input type="number" step="1" min="1" max="99" id="role_sec2_${r}" value="${sec2}"
                        onchange="validateRoleWeightInputs('${r}')"
                        class="w-20 text-xs p-1.5 bg-slate-950 text-indigo-300 font-bold border border-slate-700 rounded focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </td>
                <td class="py-2.5 px-3" id="role_status_${r}">
                    ${isValid ? 
                        '<span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-900/80 text-emerald-300 border border-emerald-700">100% ✓</span>' : 
                        '<span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-rose-900/80 text-rose-300 border border-rose-700">Error ⚠</span>'}
                </td>
                <td class="py-2.5 px-3 text-right">
                    <button onclick="handleSaveRoleWeightage('${r}')" class="px-3 py-1 bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs rounded-lg shadow transition inline-flex items-center gap-1">
                        <i data-lucide="save" class="w-3.5 h-3.5"></i> Save
                    </button>
                </td>
            </tr>
        `;
    }).join("");
    lucide.createIcons();
}

function validateRoleWeightInputs(role) {
    const sec1 = parseFloat(document.getElementById(`role_sec1_${role}`).value) || 0;
    const sec2 = parseFloat(document.getElementById(`role_sec2_${role}`).value) || 0;
    const statusCell = document.getElementById(`role_status_${role}`);
    const total = sec1 + sec2;
    if (Math.abs(total - 100.0) < 0.1) {
        statusCell.innerHTML = '<span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-900/80 text-emerald-300 border border-emerald-700">100% ✓</span>';
    } else {
        statusCell.innerHTML = `<span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-rose-900/80 text-rose-300 border border-rose-700">${total}% ⚠</span>`;
    }
}

async function handleSaveRoleWeightage(role) {
    const sec1 = parseFloat(document.getElementById(`role_sec1_${role}`).value) || 0;
    const sec2 = parseFloat(document.getElementById(`role_sec2_${role}`).value) || 0;
    if (Math.abs(sec1 + sec2 - 100.0) >= 0.1) {
        alert(`Error: Section 1 (${sec1}%) and Section 2 (${sec2}%) for position '${role}' must sum to exactly 100%!`);
        return;
    }

    try {
        const res = await fetch("/api/settings/roles", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role: role, section1_weight: sec1, section2_weight: sec2 })
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            await fetchRoleSettings();
            if (viewingUserId) await loadUserDashboard(viewingUserId);
        } else {
            alert("Error: " + data.detail);
        }
    } catch (err) {
        console.error("Error saving role weightage:", err);
    }
}

async function fetchUsers() {
    try {
        const res = await fetch("/api/users");
        allUsers = await res.json();
        populateUserSelector();
        populateManagerDropdown();
        populateAdminPersonaDropdown();
        renderAllUsersPersonaTable();

        if (!loggedInUserId && allUsers.length > 0) {
            const mdUser = allUsers.find(u => u.role === "MD") || allUsers[0];
            loggedInUserId = mdUser.id;
        }

        if (!viewingUserId) {
            viewingUserId = loggedInUserId;
        }

        if (loggedInUserId) {
            document.getElementById("userSelector").value = loggedInUserId;
            await loadUserDashboard(viewingUserId);
        }
    } catch (err) {
        console.error("Error loading users:", err);
    }
}

function populateAdminPersonaDropdown() {
    const select = document.getElementById("adminPersonaSelect");
    if (!select) return;
    select.innerHTML = allUsers.map(u => 
        `<option value="${u.id}">${u.name} [${u.role}] - ${u.designation}</option>`
    ).join("");

    if (allUsers.length > 0) {
        handleAdminPersonaSelectChange(select.value || allUsers[0].id);
    }
}

function handleAdminPersonaSelectChange(userId) {
    const u = allUsers.find(usr => usr.id === parseInt(userId));
    if (!u) return;
    const sec1Input = document.getElementById("personaSec1WeightInput");
    const sec2Input = document.getElementById("personaSec2WeightInput");
    if (sec1Input && sec2Input) {
        sec1Input.value = u.effective_section1_weight;
        sec2Input.value = u.effective_section2_weight;
    }
}

async function handleSavePersonaFormWeightages(e) {
    e.preventDefault();
    const select = document.getElementById("adminPersonaSelect");
    const userId = parseInt(select.value);
    const sec1 = parseFloat(document.getElementById("personaSec1WeightInput").value) || 0;
    const sec2 = parseFloat(document.getElementById("personaSec2WeightInput").value) || 0;

    if (Math.abs(sec1 + sec2 - 100.0) >= 0.1) {
        alert(`Error: Section 1 (${sec1}%) and Section 2 (${sec2}%) for the selected persona must sum to exactly 100%!`);
        return;
    }

    try {
        const res = await fetch(`/api/users/${userId}/weightages`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ section1_weight: sec1, section2_weight: sec2 })
        });
        const result = await res.json();
        if (res.ok) {
            alert(result.message);
            await fetchUsers();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (err) {
        console.error("Error saving persona weightages:", err);
    }
}

function renderAllUsersPersonaTable() {
    const tbody = document.getElementById("allUsersPersonaTableBody");
    if (!tbody) return;

    tbody.innerHTML = allUsers.map(u => {
        const isOverride = u.weightage_source === "custom_override";
        const badge = isOverride ? 
            `<span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-amber-900/80 text-amber-300 border border-amber-700">Custom Override</span>` : 
            `<span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-slate-800 text-slate-300 border border-slate-700">Inherited (${u.role})</span>`;

        return `
            <tr class="hover:bg-slate-800/50 transition">
                <td class="py-2.5 px-3 font-bold text-white">${u.name}</td>
                <td class="py-2.5 px-3 text-sky-400 font-semibold">${u.role}</td>
                <td class="py-2.5 px-3 text-slate-300">${u.designation}</td>
                <td class="py-2.5 px-3 text-center text-sky-300 font-bold">${u.effective_section1_weight}% / ${u.effective_section2_weight}%</td>
                <td class="py-2.5 px-3 text-center">${badge}</td>
                <td class="py-2.5 px-3 text-right">
                    ${isOverride ? `
                        <button onclick="handleResetUserWeightages(${u.id})" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 text-[11px] font-semibold rounded-lg transition inline-flex items-center gap-1">
                            Reset Default
                        </button>
                    ` : '<span class="text-slate-600 text-xs">--</span>'}
                </td>
            </tr>
        `;
    }).join("");
}

async function handleResetUserWeightages(userId) {
    try {
        const res = await fetch(`/api/users/${userId}/weightages`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ section1_weight: -1, section2_weight: -1 })
        });
        const result = await res.json();
        if (res.ok) {
            alert(result.message);
            await fetchUsers();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (err) {
        console.error("Error resetting weightages:", err);
    }
}

async function handleDeleteUser(userId) {
    if (!confirm(`Are you sure you want to remove employee #${userId} from the organization? This will delete their KRAs and update downline reporting lines.`)) return;

    try {
        const res = await fetch(`/api/users/${userId}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            await fetchUsers();
            if ((loggedInUserId === userId || viewingUserId === userId) && allUsers.length > 0) {
                handleUserSelectorChange(allUsers[0].id);
            }
        } else {
            alert("Delete Error: " + data.detail);
        }
    } catch (err) {
        console.error("Error deleting user:", err);
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

async function handleUserSelectorChange(userId) {
    loggedInUserId = parseInt(userId);
    viewingUserId = loggedInUserId;
    await loadUserDashboard(viewingUserId);
}

async function reviewReportKRA(userId) {
    viewingUserId = parseInt(userId);
    switchTab("appraisalTab");
    await loadUserDashboard(viewingUserId);
    const sel = document.getElementById("userSelector");
    if (sel) sel.value = loggedInUserId;
}

async function returnToMyDashboard() {
    viewingUserId = loggedInUserId;
    await loadUserDashboard(viewingUserId);
    const sel = document.getElementById("userSelector");
    if (sel) sel.value = loggedInUserId;
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

    const statusBadgeMap = {
        DRAFT: '<span class="px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-800 border border-amber-300">DRAFT</span>',
        SUBMITTED_SELF: '<span class="px-2 py-0.5 text-xs font-bold rounded bg-sky-100 text-sky-800 border border-sky-300">SUBMITTED TO MANAGER 🔒</span>',
        MANAGER_APPROVED: '<span class="px-2 py-0.5 text-xs font-bold rounded bg-indigo-100 text-indigo-800 border border-indigo-300">MANAGER APPROVED — PENDING MD APPROVAL ⏳</span>',
        APPROVED: '<span class="px-2 py-0.5 text-xs font-bold rounded bg-emerald-100 text-emerald-800 border border-emerald-300">FULLY APPROVED BY MD ✓</span>',
        REJECTED: '<span class="px-2 py-0.5 text-xs font-bold rounded bg-rose-100 text-rose-800 border border-rose-300">DISAPPROVED / RETURNED ⚠️</span>'
    };
    document.getElementById("statAppraisalStatus").innerHTML = statusBadgeMap[appMeta.status] || `<span class="px-2 py-0.5 text-xs font-bold rounded bg-slate-100 text-slate-800 border border-slate-300">${appMeta.status}</span>`;

    document.getElementById("statDownchainCount").innerText = `${currentPmsData.downchain_total_count} Reports`;

    document.getElementById("selfCommentsInput").value = appMeta.self_comments || "";
    document.getElementById("managerCommentsInput").value = appMeta.manager_comments || "";
    const mdInput = document.getElementById("mdCommentsInput");
    if (mdInput) mdInput.value = appMeta.md_comments || "";
}

function renderKraTables() {
    if (!currentPmsData) return;
    const u = currentPmsData.user;
    const pms = currentPmsData.pms;
    const sec1Weight = pms.section_settings ? pms.section_settings.section1_weightage_percent : 70.0;
    const sec2Weight = pms.section_settings ? pms.section_settings.section2_weightage_percent : 30.0;

    const appStatus = currentPmsData.appraisal_status ? currentPmsData.appraisal_status.status : "DRAFT";
    const isFreezed = appStatus === "SUBMITTED_SELF" || appStatus === "MANAGER_APPROVED" || appStatus === "APPROVED";
    const isRejected = appStatus === "REJECTED";

    const isViewingSelf = loggedInUserId === u.id;
    const loggedInUser = allUsers.find(usr => usr.id === loggedInUserId);
    const mgrName = u.manager_name || "Reporting Manager";
    const mdUser = allUsers.find(usr => usr.role === "MD");
    const mdName = mdUser ? mdUser.name : "Managing Director";

    // Reviewing Downline Report Context Banner
    const contextBanner = document.getElementById("reviewingReportContextBanner");
    if (contextBanner) {
        if (!isViewingSelf && loggedInUser) {
            contextBanner.innerHTML = `
                <div class="bg-amber-50 border border-amber-300 text-amber-900 rounded-xl p-3 sm:p-4 mb-3 sm:mb-4 flex items-center justify-between gap-3 shadow-xs">
                    <div class="flex items-center gap-2.5">
                        <i data-lucide="eye" class="w-5 h-5 text-amber-600 flex-shrink-0"></i>
                        <div>
                            <div class="font-extrabold text-xs sm:text-sm text-amber-950">
                                Reviewing KRA Sheet for Downline Report: <span class="text-sky-900 font-black underline">${u.name}</span>
                                <span class="text-[11px] font-normal text-amber-800 ml-1">(${u.role} - ${u.designation})</span>
                            </div>
                            <div class="text-[11px] text-amber-800 font-medium">Logged in Evaluator Persona: <strong>${loggedInUser.name}</strong> [${loggedInUser.role}]</div>
                        </div>
                    </div>
                    <button onclick="returnToMyDashboard()" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-lg shadow transition inline-flex items-center gap-1 flex-shrink-0">
                        <i data-lucide="arrow-left" class="w-3.5 h-3.5"></i> Back to My Appraisal
                    </button>
                </div>
            `;
        } else {
            contextBanner.innerHTML = "";
        }
    }

    // Freeze / Unfreeze Notice Banners
    const freezeAlertContainer = document.getElementById("appraisalFreezeAlertContainer");
    if (freezeAlertContainer) {
        if (appStatus === "SUBMITTED_SELF") {
            freezeAlertContainer.innerHTML = `
                <div class="bg-sky-50 border border-sky-200 text-sky-900 rounded-xl p-3 sm:p-4 mb-3 sm:mb-4 flex items-center justify-between gap-3 shadow-xs">
                    <div class="flex items-center gap-2">
                        <i data-lucide="lock" class="w-5 h-5 text-sky-600 flex-shrink-0"></i>
                        <div>
                            <div class="font-bold text-xs sm:text-sm">🔒 Submitted to Reporting Manager (${mgrName})</div>
                            <p class="text-[11px] text-sky-700">Section 1 & Section 2 KRAs have been submitted and are locked for changes pending review by ${mgrName}.</p>
                        </div>
                    </div>
                    <span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-sky-600 text-white shadow-xs whitespace-nowrap">Locked 🔒</span>
                </div>
            `;
        } else if (appStatus === "MANAGER_APPROVED") {
            freezeAlertContainer.innerHTML = `
                <div class="bg-indigo-50 border border-indigo-200 text-indigo-900 rounded-xl p-3 sm:p-4 mb-3 sm:mb-4 flex items-center justify-between gap-3 shadow-xs">
                    <div class="flex items-center gap-2">
                        <i data-lucide="shield-check" class="w-5 h-5 text-indigo-600 flex-shrink-0"></i>
                        <div>
                            <div class="font-bold text-xs sm:text-sm">⏳ Approved by Manager (${mgrName}) — Submitted to Managing Director (${mdName})</div>
                            <p class="text-[11px] text-indigo-700">Approved by ${mgrName}. Section 1 & Section 2 KRAs are locked pending final sign-off by Managing Director (${mdName}).</p>
                        </div>
                    </div>
                    <span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-indigo-600 text-white shadow-xs whitespace-nowrap">Pending MD ⏳</span>
                </div>
            `;
        } else if (appStatus === "APPROVED") {
            freezeAlertContainer.innerHTML = `
                <div class="bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-xl p-3 sm:p-4 mb-3 sm:mb-4 flex items-center justify-between gap-3 shadow-xs">
                    <div class="flex items-center gap-2">
                        <i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-600 flex-shrink-0"></i>
                        <div>
                            <div class="font-bold text-xs sm:text-sm">✓ Fully Approved & Signed Off by Managing Director (${mdName})</div>
                            <p class="text-[11px] text-emerald-700">This appraisal has completed all approval tiers and is finalized.</p>
                        </div>
                    </div>
                    <span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-600 text-white shadow-xs whitespace-nowrap">Approved ✓</span>
                </div>
            `;
        } else if (isRejected) {
            freezeAlertContainer.innerHTML = `
                <div class="bg-rose-50 border border-rose-200 text-rose-900 rounded-xl p-3 sm:p-4 mb-3 sm:mb-4 flex items-center justify-between gap-3 shadow-xs">
                    <div class="flex items-center gap-2">
                        <i data-lucide="alert-triangle" class="w-5 h-5 text-rose-600 flex-shrink-0"></i>
                        <div>
                            <div class="font-bold text-xs sm:text-sm">⚠️ Appraisal Disapproved / Returned for Edits</div>
                            <p class="text-[11px] text-rose-700">The appraisal was returned for modifications. Section 1 & Section 2 KRAs have been unfrozen. Please revise outcomes/ratings and click "Submit Self Appraisal" again.</p>
                        </div>
                    </div>
                    <span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-rose-600 text-white shadow-xs whitespace-nowrap">Unfrozen ⚠️</span>
                </div>
            `;
        } else {
            freezeAlertContainer.innerHTML = "";
        }
    }

    // Toggle Add KRA Buttons Visibility when freezed or when reviewing downline report
    const addSec1Btn = document.getElementById("addSec1Btn");
    const addSec2Btn = document.getElementById("addSec2Btn");
    if (addSec1Btn) addSec1Btn.style.display = (isFreezed || !isViewingSelf) ? "none" : "inline-flex";
    if (addSec2Btn) addSec2Btn.style.display = (isFreezed || !isViewingSelf) ? "none" : "inline-flex";

    // Dynamic Action Buttons
    const actionBox = document.getElementById("appraisalActionButtonsBox");

    if (actionBox) {
        if (isViewingSelf) {
            // Employee viewing their own appraisal sheet
            if (appStatus === "DRAFT" || appStatus === "REJECTED") {
                actionBox.innerHTML = `
                    <button onclick="submitAppraisalForm('DRAFT')" class="w-full sm:w-auto px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold text-xs rounded-xl transition text-center">
                        Save Draft
                    </button>
                    <button onclick="submitAppraisalForm('SUBMITTED_SELF')" class="w-full sm:w-auto px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white font-bold text-xs rounded-xl shadow transition flex items-center justify-center gap-1.5">
                        <i data-lucide="send" class="w-4 h-4"></i> Submit Self Appraisal
                    </button>
                `;
            } else if (appStatus === "SUBMITTED_SELF") {
                actionBox.innerHTML = `
                    <div class="px-4 py-2 bg-sky-50 text-sky-800 border border-sky-200 font-bold text-xs rounded-xl flex items-center gap-1.5 shadow-xs">
                        <i data-lucide="clock" class="w-4 h-4 text-sky-600"></i> Submitted to Reporting Manager (${mgrName}) — Pending Evaluation 🔒
                    </div>
                `;
            } else if (appStatus === "MANAGER_APPROVED") {
                actionBox.innerHTML = `
                    <div class="px-4 py-2 bg-indigo-50 text-indigo-800 border border-indigo-200 font-bold text-xs rounded-xl flex items-center gap-1.5 shadow-xs">
                        <i data-lucide="shield-check" class="w-4 h-4 text-indigo-600"></i> Approved by Reporting Manager (${mgrName}) — Pending MD (${mdName}) Final Sign-Off ⏳
                    </div>
                `;
            } else if (appStatus === "APPROVED") {
                actionBox.innerHTML = `
                    <div class="px-4 py-2 bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold text-xs rounded-xl flex items-center gap-1.5 shadow-xs">
                        <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-600"></i> Fully Approved & Finalized by Managing Director (${mdName}) ✓
                    </div>
                `;
            }
        } else {
            // Manager or MD reviewing downline report's appraisal sheet
            const evaluatorName = loggedInUser ? loggedInUser.name : "Evaluator";
            const evaluatorRole = loggedInUser ? loggedInUser.role : "";

            if (appStatus === "SUBMITTED_SELF") {
                actionBox.innerHTML = `
                    <button onclick="submitAppraisalForm('MANAGER_APPROVED')" class="w-full sm:w-auto px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow transition flex items-center justify-center gap-1.5">
                        <i data-lucide="check-circle" class="w-4 h-4"></i> Level 1 Approve (${evaluatorName})
                    </button>
                    <button onclick="submitAppraisalForm('REJECTED')" class="w-full sm:w-auto px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-xl shadow transition flex items-center justify-center gap-1.5">
                        <i data-lucide="x-circle" class="w-4 h-4"></i> Disapprove / Reject (Return to Employee)
                    </button>
                `;
            } else if (appStatus === "MANAGER_APPROVED") {
                if (evaluatorRole === "MD" || evaluatorRole === "ADMIN") {
                    actionBox.innerHTML = `
                        <button onclick="submitAppraisalForm('APPROVED')" class="w-full sm:w-auto px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs rounded-xl shadow transition flex items-center justify-center gap-1.5">
                            <i data-lucide="crown" class="w-4 h-4"></i> MD Final Approve (${evaluatorName})
                        </button>
                        <button onclick="submitAppraisalForm('REJECTED')" class="w-full sm:w-auto px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-xl shadow transition flex items-center justify-center gap-1.5">
                            <i data-lucide="x-circle" class="w-4 h-4"></i> MD Disapprove / Reject (Return to Employee)
                        </button>
                    `;
                } else {
                    actionBox.innerHTML = `
                        <div class="px-4 py-2 bg-indigo-50 text-indigo-800 border border-indigo-200 font-bold text-xs rounded-xl flex items-center gap-1.5 shadow-xs">
                            <i data-lucide="shield-check" class="w-4 h-4 text-indigo-600"></i> Approved by Reporting Manager (${mgrName}) — Sent to Managing Director (${mdName}) for Final Sign-Off ⏳
                        </div>
                    `;
                }
            } else if (appStatus === "APPROVED") {
                actionBox.innerHTML = `
                    <div class="px-4 py-2 bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold text-xs rounded-xl flex items-center gap-1.5 shadow-xs">
                        <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-600"></i> Appraisal Fully Approved & Signed Off by Managing Director (${mdName})
                    </div>
                `;
            } else if (appStatus === "REJECTED") {
                actionBox.innerHTML = `
                    <div class="px-4 py-2 bg-rose-50 text-rose-800 border border-rose-200 font-bold text-xs rounded-xl flex items-center gap-1.5 shadow-xs">
                        <i data-lucide="alert-triangle" class="w-4 h-4 text-rose-600"></i> Disapproved & Returned to Employee for Edits ⚠️
                    </div>
                `;
            } else {
                actionBox.innerHTML = `
                    <div class="px-4 py-2 bg-slate-100 text-slate-700 border border-slate-200 font-bold text-xs rounded-xl">
                        Draft Mode (Employee has not submitted self appraisal yet)
                    </div>
                `;
            }
        }
    }

    // Dynamic Banner & Labels
    document.getElementById("bannerFormulaTitle").innerText = `${sec1Weight}% Section 1 (Current EVA) + ${sec2Weight}% Section 2 (Future EVA)`;
    document.getElementById("bannerSec1Text").innerText = `${sec1Weight}% weightage`;
    document.getElementById("bannerSec2Text").innerText = `${sec2Weight}% weightage`;
    document.getElementById("labelSec1Badge").innerText = `Section 1 (${sec1Weight}%)`;
    document.getElementById("labelSec2Badge").innerText = `Section 2 (${sec2Weight}%)`;
    document.getElementById("sec1PillBadge").innerText = `${sec1Weight}%`;
    document.getElementById("sec2PillBadge").innerText = `${sec2Weight}%`;

    const sec1Pms = pms.present_year;
    document.getElementById("summaryPresent70Score").innerText = sec1Pms.raw_score.toFixed(1) + "%";
    document.getElementById("summaryPresentWeightSum").innerText = `Sum: ${sec1Pms.total_kra_weight_sum}%`;
    
    const sec1Badge = document.getElementById("sec1WeightStatusBadge");
    sec1Badge.innerText = sec1Pms.is_valid_100_percent ? `Sum: ${sec1Pms.total_kra_weight_sum}% ✓` : `Sum: ${sec1Pms.total_kra_weight_sum}% Error ⚠️`;
    sec1Badge.className = `px-2 py-0.5 text-[9px] sm:text-[10px] font-bold rounded-full ${sec1Pms.is_valid_100_percent ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-rose-100 text-rose-800 border border-rose-300'}`;

    const sec1ErrBanner = document.getElementById("sec1ErrorBanner");
    if (sec1ErrBanner) {
        if (!sec1Pms.is_valid_100_percent && sec1Pms.kras.length > 0) {
            document.getElementById("sec1ErrorMessageText").innerText = sec1Pms.weightage_error;
            sec1ErrBanner.classList.remove("hidden");
        } else {
            sec1ErrBanner.classList.add("hidden");
        }
    }

    renderKraSectionRows("presentKraMobileCards", "presentKraTableBody", sec1Pms.kras, isFreezed || !isViewingSelf, isViewingSelf);

    const sec2Pms = pms.upcoming_year;
    document.getElementById("summaryUpcoming30Score").innerText = sec2Pms.raw_score.toFixed(1) + "%";
    document.getElementById("summaryUpcomingWeightSum").innerText = `Sum: ${sec2Pms.total_kra_weight_sum}%`;

    const sec2Badge = document.getElementById("sec2WeightStatusBadge");
    sec2Badge.innerText = sec2Pms.is_valid_100_percent ? `Sum: ${sec2Pms.total_kra_weight_sum}% ✓` : `Sum: ${sec2Pms.total_kra_weight_sum}% Error ⚠️`;
    sec2Badge.className = `px-2 py-0.5 text-[9px] sm:text-[10px] font-bold rounded-full ${sec2Pms.is_valid_100_percent ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-rose-100 text-rose-800 border border-rose-300'}`;

    const sec2ErrBanner = document.getElementById("sec2ErrorBanner");
    if (sec2ErrBanner) {
        if (!sec2Pms.is_valid_100_percent && sec2Pms.kras.length > 0) {
            document.getElementById("sec2ErrorMessageText").innerText = sec2Pms.weightage_error;
            sec2ErrBanner.classList.remove("hidden");
        } else {
            sec2ErrBanner.classList.add("hidden");
        }
    }

    renderKraSectionRows("upcomingKraMobileCards", "upcomingKraTableBody", sec2Pms.kras, isFreezed || !isViewingSelf, isViewingSelf);

    document.getElementById("summaryCompositeScore").innerText = pms.composite_score.toFixed(1) + "%";
    document.getElementById("summaryGrade").innerText = "Grade " + pms.grade;

    // Freeze & Control Comment Textareas based on status & role
    const selfInput = document.getElementById("selfCommentsInput");
    const mgrInput = document.getElementById("managerCommentsInput");
    const mdInput = document.getElementById("mdCommentsInput");

    if (selfInput) {
        const canEditSelf = isViewingSelf && !isFreezed;
        selfInput.disabled = !canEditSelf;
        selfInput.className = `w-full text-xs p-2 sm:p-3 border rounded-xl focus:ring-2 focus:ring-sky-500 focus:outline-none ${canEditSelf ? 'bg-white border-slate-300' : 'bg-slate-100 border-slate-200 text-slate-600 cursor-not-allowed'}`;
    }

    if (mgrInput) {
        const canEditMgr = !isViewingSelf && (appStatus === "SUBMITTED_SELF");
        mgrInput.disabled = !canEditMgr;
        mgrInput.className = `w-full text-xs p-2 sm:p-3 border rounded-xl focus:ring-2 focus:ring-sky-500 focus:outline-none ${canEditMgr ? 'bg-white border-slate-300' : 'bg-slate-100 border-slate-200 text-slate-600 cursor-not-allowed'}`;
    }

    if (mdInput) {
        const isMdRole = loggedInUser && (loggedInUser.role === 'MD' || loggedInUser.role === 'ADMIN');
        const canEditMd = !isViewingSelf && isMdRole && (appStatus === "MANAGER_APPROVED");
        mdInput.disabled = !canEditMd;
        mdInput.className = `w-full text-xs p-2 sm:p-3 border rounded-xl focus:ring-2 focus:ring-purple-500 focus:outline-none ${canEditMd ? 'bg-purple-50/50 border-purple-300' : 'bg-slate-100 border-slate-200 text-slate-600 cursor-not-allowed'}`;
    }

    if (window.lucide) lucide.createIcons();
}

function renderKraSectionRows(mobileId, desktopId, kras, isFreezed, isViewingSelf) {
    const mobileContainer = document.getElementById(mobileId);
    const desktopContainer = document.getElementById(desktopId);

    if (!mobileContainer || !desktopContainer) return;

    if (kras.length === 0) {
        mobileContainer.innerHTML = `<div class="text-center py-4 text-xs text-slate-400 italic">No KRAs added yet to this section.</div>`;
        desktopContainer.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-xs text-slate-400 italic">No KRAs added yet to this section.</td></tr>`;
        return;
    }

    mobileContainer.innerHTML = kras.map(kra => `
        <div class="bg-slate-50 p-2.5 rounded-xl border border-slate-200 space-y-2">
            <div class="flex justify-between items-start">
                <div>
                    <h4 class="font-bold text-xs text-slate-900">${kra.lever_name}</h4>
                    <p class="text-[10px] text-slate-500 line-clamp-2">${kra.description || ''}</p>
                </div>
                <span class="px-2 py-0.5 bg-sky-100 text-sky-800 text-[10px] font-bold rounded-full">${kra.weightage_percent}% Weight</span>
            </div>
            
            <div class="grid grid-cols-2 gap-2 text-[10px]">
                <div class="bg-white p-1.5 rounded border border-slate-200">
                    <span class="text-slate-400 block">Target Value:</span>
                    <span class="font-bold text-slate-800">${kra.target_value} ${kra.metric_unit}</span>
                </div>
                <div class="bg-white p-1.5 rounded border border-slate-200">
                    <span class="text-slate-400 block">Actual Outcome:</span>
                    ${!isFreezed && isViewingSelf ? `
                        <input type="number" step="0.1" value="${kra.actual_outcome}" 
                            onchange="updateKraOutcome(${kra.id}, this.value, ${kra.self_rating_percent}, ${kra.manager_rating_percent})"
                            class="w-full text-xs p-1 bg-slate-50 font-bold border border-slate-300 rounded focus:ring-1 focus:ring-sky-500 focus:outline-none">
                    ` : `<span class="font-bold text-slate-900">${kra.actual_outcome} ${kra.metric_unit}</span>`}
                </div>
            </div>

            <div class="flex justify-between items-center pt-1 border-t border-slate-200 text-[10px]">
                <div>
                    <span class="text-slate-500">Achieved: </span>
                    <span class="font-bold ${kra.achievement_percent >= 100 ? 'text-emerald-600' : 'text-slate-800'}">${kra.achievement_percent}%</span>
                </div>
                <div>
                    <span class="text-slate-500">Contribution: </span>
                    <span class="font-black text-sky-700">${kra.weighted_contribution}%</span>
                </div>
                ${!isFreezed && isViewingSelf ? `
                    <button onclick="deleteKra(${kra.id})" class="p-1 text-rose-500 hover:text-rose-700">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>
                ` : ''}
            </div>
        </div>
    `).join("");

    desktopContainer.innerHTML = kras.map(kra => `
        <tr class="hover:bg-slate-50/80 transition">
            <td class="p-3">
                <div class="font-bold text-slate-900 text-xs">${kra.lever_name}</div>
                <div class="text-[11px] text-slate-500">${kra.description || ''}</div>
            </td>
            <td class="p-3 font-medium text-slate-600">${kra.metric_unit}</td>
            <td class="p-3 font-semibold text-slate-800 text-right">${kra.target_value}</td>
            <td class="p-3 font-bold text-slate-900 text-right">
                ${!isFreezed && isViewingSelf ? `
                    <input type="number" step="0.1" value="${kra.actual_outcome}" 
                        onchange="updateKraOutcome(${kra.id}, this.value, ${kra.self_rating_percent}, ${kra.manager_rating_percent})"
                        class="w-20 text-xs p-1.5 bg-slate-50 font-bold border border-slate-300 rounded focus:ring-2 focus:ring-sky-500 focus:outline-none text-right">
                ` : `<span class="font-bold text-slate-900">${kra.actual_outcome}</span>`}
            </td>
            <td class="p-3 font-bold text-right ${kra.achievement_percent >= 100 ? 'text-emerald-600' : 'text-slate-800'}">${kra.achievement_percent}%</td>
            <td class="p-3 font-extrabold text-sky-700 text-right">${kra.weightage_percent}%</td>
            <td class="p-3 font-semibold text-slate-700 text-right">${kra.self_rating_percent}%</td>
            <td class="p-3 text-right font-black text-xs text-sky-900">${kra.weighted_contribution}%</td>
            <td class="p-3 text-center">
                ${!isFreezed && isViewingSelf ? `
                    <button onclick="deleteKra(${kra.id})" class="p-1 text-slate-400 hover:text-rose-600 transition" title="Delete KRA">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                ` : ''}
            </td>
        </tr>
    `).join("");

    if (window.lucide) lucide.createIcons();
}

async function handleUpdateSectionWeightages(e) {
    e.preventDefault();
    const sec1 = parseFloat(document.getElementById("adminSec1WeightInput").value) || 0;
    const sec2 = parseFloat(document.getElementById("adminSec2WeightInput").value) || 0;

    if (roundTo1Decimal(sec1 + sec2) !== 100.0) {
        alert(`Error: Section 1 (${sec1}%) + Section 2 (${sec2}%) sum to ${sec1 + sec2}%, but must equal exactly 100%!`);
        return;
    }

    try {
        const res = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                section1_weightage: sec1,
                section2_weightage: sec2
            })
        });
        const result = await res.json();
        if (res.ok) {
            alert(result.message);
            await fetchSettings();
            await loadUserDashboard(viewingUserId);
        } else {
            alert("Error: " + result.detail);
        }
    } catch (err) {
        console.error("Error updating settings:", err);
    }
}

function roundTo1Decimal(num) {
    return Math.round(num * 10) / 10;
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
        await loadUserDashboard(viewingUserId);
    } catch (err) {
        console.error("Error updating KRA outcome:", err);
    }
}

async function deleteKra(kraId) {
    if (!confirm("Are you sure you want to delete this KRA lever?")) return;
    try {
        await fetch(`/api/kras/${kraId}`, { method: "DELETE" });
        await loadUserDashboard(viewingUserId);
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
            <div class="bg-white p-2 sm:p-3 rounded-xl border border-slate-200 hover:border-sky-400 shadow-xs flex flex-row items-center justify-between gap-1 transition cursor-pointer" onclick="reviewReportKRA(${node.id})">
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
                        View KRA
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
        tbody.innerHTML = `<tr><td colspan="7" class="p-4 text-center text-slate-400 italic text-xs">No direct reports or pending submissions under current persona. Switch persona using top dropdown selector.</td></tr>`;
        return;
    }

    const statusBadgeMap = {
        DRAFT: '<span class="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-100 text-amber-800 border border-amber-300">DRAFT</span>',
        SUBMITTED_SELF: '<span class="px-2 py-0.5 text-[10px] font-bold rounded bg-sky-100 text-sky-800 border border-sky-300">SUBMITTED TO MANAGER 🔒</span>',
        MANAGER_APPROVED: '<span class="px-2 py-0.5 text-[10px] font-bold rounded bg-indigo-100 text-indigo-800 border border-indigo-300">MANAGER APPROVED ⏳</span>',
        APPROVED: '<span class="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800 border border-emerald-300">FULLY APPROVED ✓</span>',
        REJECTED: '<span class="px-2 py-0.5 text-[10px] font-bold rounded bg-rose-100 text-rose-800 border border-rose-300">DISAPPROVED ⚠️</span>'
    };

    tbody.innerHTML = reports.map(r => {
        const stBadge = statusBadgeMap[r.appraisal_status] || `<span class="px-2 py-0.5 text-[10px] font-bold rounded bg-slate-100 text-slate-700">${r.appraisal_status}</span>`;
        
        return `
            <tr class="hover:bg-slate-50 transition">
                <td class="p-2.5 font-bold text-slate-900">${r.name}</td>
                <td class="p-2.5 font-semibold text-sky-700">${r.role}</td>
                <td class="p-2.5 text-slate-600">${r.designation}</td>
                <td class="p-2.5 text-center">${stBadge}</td>
                <td class="p-2.5 text-right font-extrabold text-slate-900">${r.composite_score.toFixed(1)}%</td>
                <td class="p-2.5 text-center">
                    <span class="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800">Grade ${r.grade}</span>
                </td>
                <td class="p-2.5 text-center">
                    <button onclick="reviewReportKRA(${r.id})" class="px-3 py-1 bg-sky-600 hover:bg-sky-700 text-white font-semibold text-[11px] rounded-lg transition shadow-xs inline-flex items-center gap-1">
                        <i data-lucide="eye" class="w-3.5 h-3.5"></i> Review KRA Sheet
                    </button>
                </td>
            </tr>
        `;
    }).join("");
    lucide.createIcons();
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
        "Add KRA to Section 1: Key Deliverables impact Current EVA" : "Add KRA to Section 2: Key Deliverables impact Future EVA";
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
        user_id: viewingUserId,
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
        await loadUserDashboard(viewingUserId);
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
    if (!currentPmsData) return;
    const pms = currentPmsData.pms;

    // Strict 100% Weightage Sum Validation Check before submission
    if (status === "SUBMITTED_SELF" || status === "APPROVED") {
        if (!pms.is_overall_weightage_valid) {
            const errs = pms.errors.join("\n\n");
            alert(`⚠️ SUBMISSION BLOCKED: KRA Weightage Sum Error\n\n${errs}\n\nPlease adjust individual KRA weightages so that Section 1 sums to 100% and Section 2 sums to 100% before submitting.`);
            return;
        }
    }

    try {
        const mdInput = document.getElementById("mdCommentsInput");
        const mdComments = mdInput ? mdInput.value : "";

        const res = await fetch("/api/appraisals/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: viewingUserId,
                year: 2026,
                status: status,
                self_comments: document.getElementById("selfCommentsInput").value,
                manager_comments: document.getElementById("managerCommentsInput").value,
                md_comments: mdComments
            })
        });
        const result = await res.json();
        if (res.ok) {
            alert(`Appraisal status updated to ${status}!`);
            await loadUserDashboard(viewingUserId);
        } else {
            alert("Submission Error: " + result.detail);
        }
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

    const menu = document.getElementById("mobileNavMenu");
    if (menu && !menu.classList.contains("hidden")) {
        menu.classList.add("hidden");
    }
}
