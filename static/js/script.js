/**
 * IntelliHostel Global Script
 * RGUKT Ongole Hostel Complaint Portal
 * Handles Navbar elevation, toasts, password toggles, scroll-to-top, and micro-interactions
 */

document.addEventListener("DOMContentLoaded", function () {
    // CSRF protection for AJAX/fetch requests. Server validates every state-changing request.
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta && window.fetch) {
        const originalFetch = window.fetch.bind(window);
        window.fetch = function(input, init) {
            init = init || {};
            const method = (init.method || (input && input.method) || "GET").toUpperCase();
            if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
                const headers = new Headers(init.headers || {});
                if (!headers.has("X-CSRFToken")) headers.set("X-CSRFToken", csrfMeta.content);
                init.headers = headers;
            }
            return originalFetch(input, init);
        };
    }

    // 0. Theme Management System (Light / Dark Mode with Persistence & System Detection)
    function getPreferredTheme() {
        try {
            const stored = localStorage.getItem("theme");
            if (stored === "dark" || stored === "light") {
                return stored;
            }
        } catch (e) {}
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function syncThemeUI(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        const isDark = theme === "dark";
        const toggleButtons = document.querySelectorAll(".theme-toggle-btn");

        toggleButtons.forEach(function (btn) {
            btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
            btn.setAttribute("aria-pressed", isDark ? "true" : "false");
            btn.setAttribute("title", isDark ? "Switch to light mode" : "Switch to dark mode");

            const icon = btn.querySelector(".theme-toggle-icon");
            if (icon) {
                if (isDark) {
                    icon.classList.remove("fa-moon");
                    icon.classList.add("fa-sun");
                } else {
                    icon.classList.remove("fa-sun");
                    icon.classList.add("fa-moon");
                }
            }

            const label = btn.querySelector(".theme-toggle-label");
            if (label) {
                label.textContent = isDark ? "Light Mode" : "Dark Mode";
            }
        });

        window.dispatchEvent(new CustomEvent("themeChanged", { detail: { theme: theme } }));
    }

    function setTheme(newTheme) {
        try {
            localStorage.setItem("theme", newTheme);
        } catch (e) {}
        syncThemeUI(newTheme);
    }

    // Initialize UI on load
    const currentTheme = document.documentElement.getAttribute("data-theme") || getPreferredTheme();
    syncThemeUI(currentTheme);

    // Event delegation on theme toggles
    document.addEventListener("click", function (e) {
        const toggleBtn = e.target.closest(".theme-toggle-btn");
        if (!toggleBtn) return;
        e.preventDefault();

        const activeTheme = document.documentElement.getAttribute("data-theme") || "light";
        const targetTheme = activeTheme === "dark" ? "light" : "dark";
        setTheme(targetTheme);
    });

    // Listen to OS scheme changes if user hasn't explicitly set a preference
    if (window.matchMedia) {
        try {
            window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
                if (!localStorage.getItem("theme")) {
                    syncThemeUI(e.matches ? "dark" : "light");
                }
            });
        } catch (e) {}
    }

    // 1. Navbar Sticky & Scroll Elevation
    const navbar = document.querySelector(".portal-navbar");
    function handleNavbarScroll() {
        if (!navbar) return;
        if (window.scrollY > 15) {
            navbar.classList.add("navbar-scrolled");
        } else {
            navbar.classList.remove("navbar-scrolled");
        }
    }
    window.addEventListener("scroll", handleNavbarScroll, { passive: true });
    handleNavbarScroll();

    // 2. Mobile Navbar auto-collapse on link click
    const navCollapse = document.getElementById("mainNavbar");
    if (navCollapse) {
        const navLinks = navCollapse.querySelectorAll(".nav-link-item, .nav-btn-logout, .nav-btn-primary, .nav-btn-outline");
        navLinks.forEach(function (link) {
            link.addEventListener("click", function () {
                if (window.innerWidth < 992 && navCollapse.classList.contains("show")) {
                    const bsCollapse = bootstrap.Collapse.getInstance(navCollapse);
                    if (bsCollapse) {
                        bsCollapse.hide();
                    }
                }
            });
        });
    }

    // 3. Floating Toast Auto-Dismissal & Close Action
    const toasts = document.querySelectorAll(".portal-toast");
    toasts.forEach(function (toast) {
        const dismissTimer = setTimeout(function () {
            dismissToast(toast);
        }, 5500);

        const closeBtn = toast.querySelector(".toast-btn-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", function () {
                clearTimeout(dismissTimer);
                dismissToast(toast);
            });
        }
    });

    function dismissToast(toastElement) {
        if (!toastElement) return;
        toastElement.classList.add("fade-out");
        setTimeout(function () {
            toastElement.remove();
            const container = document.querySelector(".portal-toast-container");
            if (container && container.children.length === 0) {
                container.remove();
            }
        }, 300);
    }

    // 4. Global Password Visibility Toggle System (Accessible, Repeatable, Delegated)
    document.addEventListener("click", function (e) {
        const toggleBtn = e.target.closest(".password-toggle, [data-password-toggle], #passwordToggle");
        if (!toggleBtn) return;

        e.preventDefault();

        // 1. Locate the associated input
        let input = null;
        const targetId = toggleBtn.getAttribute("data-target") || toggleBtn.getAttribute("aria-controls");
        if (targetId) {
            input = document.getElementById(targetId);
        }

        if (!input) {
            const container = toggleBtn.closest(
                ".login-input-wrapper, .admin-input-wrapper, .input-wrapper-reg, .reset-input-wrapper, .field-input-wrap, .password-field-group, .input-group, .password-input-wrapper, .form-group-reg, .reset-form-group, .admin-form-group, .login-form-group"
            ) || toggleBtn.parentElement;

            if (container) {
                input = container.querySelector("input[type='password'], input[type='text']");
            }
        }

        if (!input) return;

        // 2. Toggle password visibility without losing value
        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";

        // 3. Synchronize Font Awesome eye icon
        const icon = toggleBtn.matches("i, svg") ? toggleBtn : toggleBtn.querySelector("i, svg");
        if (icon) {
            if (isPassword) {
                icon.classList.remove("fa-eye");
                icon.classList.add("fa-eye-slash");
            } else {
                icon.classList.remove("fa-eye-slash");
                icon.classList.add("fa-eye");
            }
        }

        // 4. Update accessibility states
        const label = isPassword ? "Hide password" : "Show password";
        toggleBtn.setAttribute("aria-label", label);
        toggleBtn.setAttribute("aria-pressed", isPassword ? "true" : "false");
        toggleBtn.setAttribute("title", label);
    });

    // 5. Scroll To Top Button
    const scrollTopBtn = document.getElementById("scrollTopBtn");
    if (scrollTopBtn) {
        window.addEventListener("scroll", function () {
            if (window.scrollY > 300) {
                scrollTopBtn.style.display = "flex";
            } else {
                scrollTopBtn.style.display = "none";
            }
        }, { passive: true });

        scrollTopBtn.addEventListener("click", function () {
            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });
        });
    }

    // 6. Tactile Button Ripple Effect
    document.querySelectorAll(".btn, .hero-btn, .portal-btn").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            const circle = document.createElement("span");
            const diameter = Math.max(btn.clientWidth, btn.clientHeight);
            const radius = diameter / 2;

            const rect = btn.getBoundingClientRect();
            circle.style.width = circle.style.height = `${diameter}px`;
            circle.style.left = `${e.clientX - rect.left - radius}px`;
            circle.style.top = `${e.clientY - rect.top - radius}px`;
            circle.style.position = "absolute";
            circle.style.borderRadius = "50%";
            circle.style.backgroundColor = "rgba(255, 255, 255, 0.35)";
            circle.style.transform = "scale(0)";
            circle.style.animation = "rippleAnim 0.6s linear";
            circle.style.pointerEvents = "none";

            btn.style.position = btn.style.position || "relative";
            btn.style.overflow = "hidden";

            const existingRipple = btn.querySelector(".ripple-span");
            if (existingRipple) existingRipple.remove();

            circle.classList.add("ripple-span");
            btn.appendChild(circle);

            setTimeout(() => {
                circle.remove();
            }, 600);
        });
    });

    // 7. Modern Scroll-Reveal Animation Observer (Repeating on Viewport Entry/Exit)
    const prefersReducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!prefersReducedMotion && "IntersectionObserver" in window) {
        const revealObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("reveal-visible");
                } else {
                    entry.target.classList.remove("reveal-visible");
                }
            });
        }, {
            root: null,
            rootMargin: "0px 0px -40px 0px",
            threshold: 0.12
        });

        const revealElements = document.querySelectorAll(
            ".reveal-fade, .reveal-up, .reveal-down, .reveal-left, .reveal-right, .reveal-scale"
        );
        revealElements.forEach(function (el) {
            revealObserver.observe(el);
        });
    } else {
        document.querySelectorAll(
            ".reveal-fade, .reveal-up, .reveal-down, .reveal-left, .reveal-right, .reveal-scale"
        ).forEach(function (el) {
            el.classList.add("reveal-visible");
        });
    }

    // 8. Global Logout Confirmation System (Accessible, Prevents Accidental Logouts, Preserves Backend Routes)
    (function initLogoutConfirmationModal() {
        let pendingLogoutUrl = null;
        let modalInstance = null;

        function getModalElements() {
            const modalEl = document.getElementById("logoutConfirmModal");
            if (!modalEl) return null;

            if (!modalInstance && window.bootstrap && window.bootstrap.Modal) {
                modalInstance = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl, {
                    backdrop: true,
                    keyboard: true
                });
            }
            return {
                modalEl: modalEl,
                instance: modalInstance,
                confirmBtn: modalEl.querySelector("#logoutConfirmBtn"),
                cancelBtn: modalEl.querySelector("#logoutCancelBtn")
            };
        }

        // Delegated click handler on any logout link/button
        document.addEventListener("click", function (e) {
            const trigger = e.target.closest(
                ".nav-btn-logout, a[href$='/logout'], a[href$='/admin_logout'], a[href*='/logout'], a[href*='/admin_logout'], [data-logout-trigger]"
            );
            if (!trigger) return;

            // Do not intercept if click is already inside the logout confirmation modal!
            if (trigger.closest("#logoutConfirmModal")) return;

            const modalContext = getModalElements();
            if (!modalContext || !modalContext.modalEl) {
                // If modal is not present in DOM, allow default link navigation
                return;
            }

            e.preventDefault();
            e.stopPropagation();

            // Extract intended destination URL (e.g. /logout or /admin_logout)
            pendingLogoutUrl = trigger.getAttribute("href") || (trigger.dataset && trigger.dataset.logoutUrl) || "/logout";

            // Update modal confirm form action and button state
            const logoutForm = document.getElementById("logoutConfirmForm");
            if (logoutForm && pendingLogoutUrl && pendingLogoutUrl !== "#") {
                logoutForm.setAttribute("action", pendingLogoutUrl);
            }

            if (modalContext.confirmBtn) {
                modalContext.confirmBtn.classList.remove("disabled");
                modalContext.confirmBtn.removeAttribute("aria-disabled");
                modalContext.confirmBtn.removeAttribute("data-logging-out");
                const span = modalContext.confirmBtn.querySelector("span");
                if (span) span.textContent = "Logout";
            }

            // Show modal safely
            if (modalContext.instance) {
                modalContext.instance.show();
            } else if (window.bootstrap && window.bootstrap.Modal) {
                modalInstance = new bootstrap.Modal(modalContext.modalEl, { backdrop: true, keyboard: true });
                modalInstance.show();
            }
        });

        // Handle confirmed logout button click inside modal
        document.addEventListener("click", function (e) {
            const confirmBtn = e.target.closest("#logoutConfirmBtn");
            if (!confirmBtn) return;

            // Prevent double submission
            if (confirmBtn.classList.contains("disabled") || confirmBtn.getAttribute("data-logging-out") === "true") {
                e.preventDefault();
                return;
            }

            const logoutForm = document.getElementById("logoutConfirmForm");
            const target = (logoutForm && logoutForm.getAttribute("action") && logoutForm.getAttribute("action") !== "#")
                ? logoutForm.getAttribute("action")
                : (pendingLogoutUrl || "/logout");

            if (logoutForm) {
                logoutForm.setAttribute("action", target);
            }

            confirmBtn.classList.add("disabled");
            confirmBtn.setAttribute("aria-disabled", "true");
            confirmBtn.setAttribute("data-logging-out", "true");
            const span = confirmBtn.querySelector("span");
            if (span) {
                span.textContent = "Logging out...";
            }

            if (logoutForm) {
                e.preventDefault();
                logoutForm.submit();
            }
        });

        // Modal lifecycle: Focus management and cleanup
        const modalEl = document.getElementById("logoutConfirmModal");
        if (modalEl) {
            modalEl.addEventListener("shown.bs.modal", function () {
                const cancelBtn = modalEl.querySelector("#logoutCancelBtn");
                if (cancelBtn) {
                    cancelBtn.focus();
                }
            });

            modalEl.addEventListener("hidden.bs.modal", function () {
                pendingLogoutUrl = null;
                const confirmBtn = modalEl.querySelector("#logoutConfirmBtn");
                if (confirmBtn) {
                    confirmBtn.classList.remove("disabled");
                    confirmBtn.removeAttribute("aria-disabled");
                    confirmBtn.removeAttribute("data-logging-out");
                    const span = confirmBtn.querySelector("span");
                    if (span) span.textContent = "Logout";
                }
            });
        }
    })();
});

// Keyframe for ripple
if (!document.getElementById("ripple-keyframes")) {
    const style = document.createElement("style");
    style.id = "ripple-keyframes";
    style.textContent = `
    @keyframes rippleAnim {
        to {
            transform: scale(3.5);
            opacity: 0;
        }
    }`;
    document.head.appendChild(style);
}
