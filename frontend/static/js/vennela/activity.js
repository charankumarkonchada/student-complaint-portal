/**
 * Recent Activity JavaScript Module - Owned by K. Vennela
 */
document.addEventListener("DOMContentLoaded", function () {
    // Ensure all activity log list items are visible
    const items = document.querySelectorAll(".activity-item, .list-group-item");
    items.forEach(function (item) {
        item.style.opacity = "1";
        item.style.transform = "none";
    });
});
