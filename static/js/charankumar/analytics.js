/**
 * AI Analytics Dashboard Helper - Owned by K. Charankumar
 */
document.addEventListener("DOMContentLoaded", function () {
    // Ensure Chart.js responsive redraw on window resize
    window.addEventListener("resize", function () {
        if (typeof Chart !== "undefined") {
            Chart.instances.forEach(function (chart) {
                chart.resize();
            });
        }
    });
});
