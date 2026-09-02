/**
 * IntelliHostel Global Script
 * RGUKT Ongole Hostel Complaint Portal
 */

document.addEventListener("DOMContentLoaded", function () {
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
        // Auto dismiss after 5.5 seconds
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

    // 4. Scroll To Top Button
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

    // 5. Button Ripple Effect
    document.querySelectorAll(".btn, .action-card-btn").forEach(function (btn) {
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
});

// Dynamic Ripple CSS Keyframe injection
const style = document.createElement("style");
style.textContent = `
@keyframes rippleAnim {
    to {
        transform: scale(3.5);
        opacity: 0;
    }
}`;
document.head.appendChild(style);
