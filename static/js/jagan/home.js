/**
 * Home Page JavaScript Module - Owned by B. Jagan
 */
document.addEventListener("DOMContentLoaded", function () {
    // Smooth scroll for portal entry cards
    const portalButtons = document.querySelectorAll(".portal-btn, .hero-btn");
    portalButtons.forEach(btn => {
        btn.addEventListener("mouseenter", () => {
            btn.style.transform = "translateY(-2px)";
        });
        btn.addEventListener("mouseleave", () => {
            btn.style.transform = "translateY(0)";
        });
    });
});
