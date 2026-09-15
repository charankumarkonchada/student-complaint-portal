/**
 * IntelliHostel Global Script
 * RGUKT Ongole Hostel Complaint Portal
 * Handles Navbar elevation, toasts, password toggles, scroll-to-top, and micro-interactions
 */

document.addEventListener("DOMContentLoaded", function () {
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
