/**
 * Recent Activity JavaScript Module - Owned by K. Vennela
 */
document.addEventListener("DOMContentLoaded", function () {
    // Smooth fade-in for activity log list items
    const items = document.querySelectorAll(".activity-item, .list-group-item");
    items.forEach(function (item, index) {
        item.style.opacity = "0";
        item.style.transform = "translateY(10px)";
        item.style.transition = "all 0.3s ease";

        setTimeout(function () {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, index * 50);
    });
});
