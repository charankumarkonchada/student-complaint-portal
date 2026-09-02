/**
 * Student Dashboard JavaScript Module - Owned by K. Vennela
 */
document.addEventListener("DOMContentLoaded", function () {
    // 1. Dynamic Greeting Based on Current Time
    const greeting = document.getElementById("dashboardGreeting");
    if (greeting) {
        const hour = new Date().getHours();
        let message = "Good Morning,";

        if (hour >= 12 && hour < 17) {
            message = "Good Afternoon,";
        } else if (hour >= 17 && hour < 21) {
            message = "Good Evening,";
        } else if (hour >= 21 || hour < 5) {
            message = "Welcome,";
        }

        greeting.textContent = message;
    }

    // 2. Animated Counter for Numeric Badges
    const counters = document.querySelectorAll(".counter-number");
    counters.forEach(function (counter) {
        const target = parseInt(counter.textContent, 10);
        if (isNaN(target) || target === 0) return;

        let count = 0;
        const speed = Math.max(15, Math.floor(1000 / target));

        const timer = setInterval(function () {
            count++;
            counter.textContent = count;
            if (count >= target) {
                clearInterval(timer);
            }
        }, speed);
    });
});
