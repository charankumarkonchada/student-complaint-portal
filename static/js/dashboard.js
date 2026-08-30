/**
 * IntelliHostel Dashboard Helper
 */

document.addEventListener("DOMContentLoaded", function () {
    // 1. Dynamic Time-based Greeting
    const greetingEl = document.getElementById("dynamicGreeting");
    if (greetingEl) {
        const hour = new Date().getHours();
        let greeting = "Welcome";
        if (hour >= 4 && hour < 12) {
            greeting = "Good morning";
        } else if (hour >= 12 && hour < 17) {
            greeting = "Good afternoon";
        } else {
            greeting = "Good evening";
        }
        greetingEl.textContent = greeting;
    }

    // 2. Animate KPI Stat Numbers
    const kpiValues = document.querySelectorAll(".kpi-value[data-target]");
    kpiValues.forEach(function (el) {
        const target = parseInt(el.getAttribute("data-target"), 10) || 0;
        if (target === 0) {
            el.textContent = "0";
            return;
        }

        let start = 0;
        const duration = 800; // ms
        const stepTime = 20;
        const totalSteps = duration / stepTime;
        const increment = target / totalSteps;

        const timer = setInterval(function () {
            start += increment;
            if (start >= target) {
                el.textContent = target.toString();
                clearInterval(timer);
            } else {
                el.textContent = Math.floor(start).toString();
            }
        }, stepTime);
    });
});
