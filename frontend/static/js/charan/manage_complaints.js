/**
 * Manage Complaints JavaScript Module - Owned by R. Charan Kumar
 */
function openAdminImage(src) {
    const modal = document.getElementById("adminImageModal");
    const image = document.getElementById("adminModalImage");

    if (modal && image) {
        image.src = src;
        modal.classList.add("active");
        document.body.style.overflow = "hidden";
    }
}

function closeAdminImage(event) {
    if (event && event.target && event.target.id !== "adminImageModal") {
        return;
    }

    const modal = document.getElementById("adminImageModal");
    if (modal) {
        modal.classList.remove("active");
        document.body.style.overflow = "";
    }
}

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        const modal = document.getElementById("adminImageModal");
        if (modal) {
            modal.classList.remove("active");
            document.body.style.overflow = "";
        }
    }
});

document.addEventListener("DOMContentLoaded", function () {
    const inputs = document.querySelectorAll(".filter-input");
    inputs.forEach(function (input) {
        input.addEventListener("change", function () {
            this.style.borderColor = "#2563eb";
        });
    });
});
