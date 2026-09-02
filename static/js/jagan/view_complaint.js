/**
 * View Complaint Details JavaScript Module - Owned by B. Jagan
 */
document.addEventListener("DOMContentLoaded", function () {
    // Image viewer tooltip
    const imageLink = document.querySelector(".complaint-detail-card a[target='_blank']");
    if (imageLink) {
        imageLink.setAttribute("title", "Click to view full size image");
    }
});
