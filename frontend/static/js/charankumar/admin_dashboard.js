/**
 * Admin Dashboard Helper - Owned by K. Charankumar
 */
document.addEventListener("DOMContentLoaded", function () {
    // Quick Action button ripple and table hover enhancements
    const actionButtons = document.querySelectorAll(".btn");
    actionButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            btn.style.opacity = "0.9";
        });
    });
});
