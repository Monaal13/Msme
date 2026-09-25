const api = {
    async request(path, options = {}) {
        const baseUrl = window.API_BASE_URL !== undefined
            ? window.API_BASE_URL
            : (window.location.port === "5000" ? "" : "http://127.0.0.1:5000");

        const url = (path.startsWith("http://") || path.startsWith("https://"))
            ? path
            : baseUrl + (path.startsWith("/") ? path : "/" + path);

        const response = await fetch(url, {
            credentials: "include",
            headers: { "Content-Type": "application/json", ...(options.headers || {}) },
            ...options,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "Request failed");
        return data;
    },
};

function formatMoney(value) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
}

function animateValue(element, end, duration = 600, isMoney = false) {
    if (!element) return;
    const endNum = Number(end) || 0;
    if (duration <= 0) {
        element.textContent = isMoney ? formatMoney(endNum) : endNum.toLocaleString("en-IN");
        return;
    }
    const start = 0;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const current = Math.floor(progress * (endNum - start) + start);
        element.textContent = isMoney ? formatMoney(current) : current.toLocaleString("en-IN");
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            element.textContent = isMoney ? formatMoney(endNum) : endNum.toLocaleString("en-IN");
        }
    };
    window.requestAnimationFrame(step);
}

function formatDate(value) {
    if (!value) return "";
    return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

function formatDateTime(value) {
    if (!value) return "-";
    const d = new Date(value);
    if (isNaN(d.getTime())) return value;
    const dateStr = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(d);
    const timeStr = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", hour12: true }).format(d);
    return `${dateStr}, ${timeStr}`;
}

function renderActiveBadge(status) {
    const isAct = (status || "active").toString().toLowerCase() === "active";
    if (isAct) {
        return `<span class="badge-status active" title="Currently Available"><span class="badge-status-icon">✓</span> Active</span>`;
    } else {
        return `<span class="badge-status inactive" title="Currently Disabled"><span class="badge-status-icon">✕</span> Inactive</span>`;
    }
}

function renderPaymentBadge(status, overdueDays = 0) {
    const st = (status || "unpaid").toString().toLowerCase();
    if (st === "paid") {
        return `<span class="badge-pay paid" title="Payment Received">✓ Paid</span>`;
    } else if (st === "overdue" || overdueDays > 0) {
        const text = overdueDays > 0 ? `Overdue by ${overdueDays} day${overdueDays > 1 ? 's' : ''}` : "Overdue";
        return `<span class="badge-pay overdue" title="Overdue Payment">⚠️ ${text}</span>`;
    } else {
        return `<span class="badge-pay unpaid" title="Payment Pending">⏳ Unpaid</span>`;
    }
}

function renderStageBadge(stage) {
    const st = (stage || "New").toString();
    let cssClass = "stage-new";
    if (st === "Cutting") cssClass = "stage-cutting";
    else if (st === "Stitching") cssClass = "stage-stitching";
    else if (st === "Finishing") cssClass = "stage-finishing";
    else if (st === "Quality Check") cssClass = "stage-quality";
    else if (st === "Packing") cssClass = "stage-packing";
    else if (st === "Ready for Dispatch") cssClass = "stage-ready";
    else if (st === "Completed" || st === "Dispatched") cssClass = "stage-completed";

    return `<span class="stage-badge ${cssClass}">${st}</span>`;
}

function renderStageProgressStepper(currentStage) {
    const stages = ["Cutting", "Stitching", "Finishing", "Quality Check", "Packing", "Ready for Dispatch"];
    const curIndex = stages.indexOf(currentStage);

    let html = '<div class="stepper-wrap">';
    stages.forEach((st, idx) => {
        let isDone = idx < curIndex || currentStage === "Completed";
        let isActive = idx === curIndex;
        let cls = isDone ? "completed" : isActive ? "active" : "";
        let icon = isDone ? "✓" : idx + 1;

        html += `
            <div class="step-node ${cls}">
                <div class="step-circle">${icon}</div>
                <span>${st}</span>
            </div>
        `;
    });
    html += '</div>';
    return html;
}

function showToast(message, type = "success", title = "") {
    let container = document.getElementById("toastContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "toastContainer";
        document.body.appendChild(container);
    }

    const icons = {
        success: "✓",
        error: "✕",
        warning: "⚠",
        info: "ℹ",
    };

    const toast = document.createElement("div");
    toast.className = `toast-item ${type}`;
    toast.innerHTML = `
        <div style="display:flex; align-items:flex-start; gap:10px;">
            <span style="font-weight:bold; font-size:16px;">${icons[type] || "•"}</span>
            <div>
                ${title ? `<strong style="display:block; margin-bottom:2px;">${title}</strong>` : ""}
                <span>${message}</span>
            </div>
        </div>
        <button class="toast-close" onclick="this.closest('.toast-item').remove()">✕</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 200);
    }, 4000);
}

function setStatus(message, type = "") {
    const box = document.querySelector("[data-status]");
    if (box) {
        box.textContent = message;
        box.className = `status ${type}`;
    }
    if (message && (type === "error" || type === "success" || type === "warning" || type === "info")) {
        showToast(message, type);
    }
}

async function requireLogin() {
    try {
        const res = await api.request("/api/auth/me");
        window.currentUser = res.user;
        const userBrand = document.querySelector("[data-user-name]");
        if (userBrand) userBrand.textContent = res.user.name || "User";
        const bizBrand = document.querySelector("[data-business-name]");
        if (bizBrand && res.user.business_name) bizBrand.textContent = res.user.business_name;
        return res.user;
    } catch {
        window.location.href = "/";
    }
}

async function logout() {
    try {
        await api.request("/api/auth/logout", { method: "POST" });
    } catch (e) {
        console.error(e);
    }
    window.location.href = "/";
}

function collectForm(form) {
    return Object.fromEntries(new FormData(form).entries());
}

function setBtnLoading(btn, isLoading, text = "Saving...") {
    if (!btn) return;
    if (isLoading) {
        btn.dataset.originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span> ${text}`;
    } else {
        btn.disabled = false;
        btn.innerHTML = btn.dataset.originalText || "Submit";
    }
}

async function handleAuth(formId, endpoint) {
    const form = document.getElementById(formId);
    if (!form) return;
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitBtn = form.querySelector("button[type='submit']");
        setBtnLoading(submitBtn, true, "Authenticating...");
        try {
            const res = await api.request(endpoint, { method: "POST", body: JSON.stringify(collectForm(form)) });
            showToast("Login successful! Redirecting...", "success", "Welcome");
            setTimeout(() => {
                window.location.href = res.redirect || "/pages/dashboard.html";
            }, 400);
        } catch (error) {
            setBtnLoading(submitBtn, false);
            setStatus(error.message, "error");
        }
    });
}

function initThemeToggle() {
    const savedTheme = localStorage.getItem("theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);

    const topbar = document.querySelector(".topbar");
    if (topbar && !topbar.querySelector(".theme-toggle-btn")) {
        const rightGroup = topbar.querySelector(".topbar-right") || topbar;
        const toggleBtn = document.createElement("button");
        toggleBtn.className = "icon-btn theme-toggle-btn";
        toggleBtn.title = "Toggle Light/Night Mode";
        toggleBtn.innerHTML = savedTheme === "dark" ? "☀️" : "🌙";
        toggleBtn.onclick = () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("theme", next);
            toggleBtn.innerHTML = next === "dark" ? "☀️" : "🌙";
            showToast(`Switched to ${next === "dark" ? "Night" : "Light"} Mode`, "info");
            window.dispatchEvent(new CustomEvent("themeChanged", { detail: { theme: next } }));
        };
        rightGroup.insertBefore(toggleBtn, rightGroup.firstChild);
    }
}

function initSidebar() {
    const shell = document.querySelector(".app-shell");
    const sidebar = document.querySelector(".sidebar");
    const topbar = document.querySelector(".topbar");

    if (!sidebar || !shell) return;

    if (topbar && !topbar.querySelector(".sidebar-toggle-btn")) {
        const leftGroup = topbar.querySelector(".topbar-left") || topbar;
        const toggleBtn = document.createElement("button");
        toggleBtn.className = "icon-btn sidebar-toggle-btn";
        toggleBtn.title = "Toggle Sidebar";
        toggleBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
        `;
        toggleBtn.onclick = () => {
            if (window.innerWidth <= 768) {
                shell.classList.toggle("sidebar-mobile-open");
            } else {
                shell.classList.toggle("sidebar-collapsed");
                const isCollapsed = shell.classList.contains("sidebar-collapsed");
                localStorage.setItem("sidebarCollapsed", isCollapsed ? "true" : "false");
            }
        };
        leftGroup.insertBefore(toggleBtn, leftGroup.firstChild);
    }

    if (localStorage.getItem("sidebarCollapsed") === "true" && window.innerWidth > 768) {
        shell.classList.add("sidebar-collapsed");
    }

    if (!document.querySelector(".mobile-overlay")) {
        const overlay = document.createElement("div");
        overlay.className = "mobile-overlay";
        overlay.onclick = () => shell.classList.remove("sidebar-mobile-open");
        document.body.appendChild(overlay);
    }

    const currentPath = window.location.pathname;
    const links = sidebar.querySelectorAll(".nav-link");
    links.forEach((link) => {
        const href = link.getAttribute("href");
        if (href && (href === currentPath || (currentPath === "/" && href.includes("dashboard")))) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });
}

function injectLiveIndicators() {
    const topbar = document.querySelector(".topbar");
    if (topbar && !topbar.querySelector(".live-badge")) {
        const badge = document.createElement("div");
        badge.className = "live-badge";
        badge.innerHTML = '<span class="pulse-dot"></span> System Active';
        const rightGroup = topbar.querySelector(".topbar-right") || topbar;
        rightGroup.insertBefore(badge, rightGroup.firstChild);
    }
}

function renderRows(tableBody, rows, columns, emptyText) {
    if (!rows.length) {
        tableBody.innerHTML = `<tr><td colspan="${columns.length}"><div class="empty-state"><span class="empty-icon">📂</span><span>${emptyText}</span></div></td></tr>`;
        return;
    }
    tableBody.innerHTML = rows
        .map(
            (row) =>
                `<tr>${columns.map((column) => `<td>${column.render ? column.render(row) : row[column.key] !== undefined && row[column.key] !== null ? row[column.key] : ""}</td>`).join("")}</tr>`
        )
        .join("");
}

document.addEventListener("DOMContentLoaded", () => {
    handleAuth("loginForm", "/api/auth/login");
    handleAuth("registerForm", "/api/auth/register");
    handleAuth("customerRegisterForm", "/api/auth/register-customer");
    document.querySelectorAll("[data-logout]").forEach((btn) => btn.addEventListener("click", logout));
    initThemeToggle();
    initSidebar();
    injectLiveIndicators();
});
