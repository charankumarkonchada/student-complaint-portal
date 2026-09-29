/**
 * Notifications JavaScript Module - Owned by K. Deepthi
 */
document.addEventListener("DOMContentLoaded", function () {
    // Auto-mark notifications as read or animate dismissal
    const unreadItems = document.querySelectorAll(".notification-unread");
    unreadItems.forEach(function (item) {
        item.addEventListener("mouseenter", function () {
            this.style.transition = "background-color 0.3s ease";
        });
    });
});
