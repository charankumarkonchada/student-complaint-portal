/**
 * Admin Portal Management JavaScript Module
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
    // 1. Filter Input Focus Highlights
    const inputs = document.querySelectorAll(".filter-input");
    inputs.forEach(function (input) {
        input.addEventListener("change", function () {
            this.style.borderColor = "#2563eb";
        });
    });

    // 2. Remarks Character Counter (Update Status Page)
    const remarks = document.getElementById("remarks");
    const counter = document.getElementById("characterCount");

    if (remarks && counter) {
        function updateCharacterCount() {
            const length = remarks.value.length;
            counter.textContent = length + " / 500";

            if (length >= 450) {
                counter.style.color = "#dc2626";
            } else {
                counter.style.color = "#94a3b8";
            }
        }

        updateCharacterCount();
        remarks.addEventListener("input", updateCharacterCount);
    }

    // 3. Status Select Dynamic Border Color
    const status = document.getElementById("status");
    if (status) {
        function updateStatusColor() {
            if (status.value === "Pending") {
                status.style.borderColor = "#fecaca";
            } else if (status.value === "In Progress") {
                status.style.borderColor = "#fde68a";
            } else {
                status.style.borderColor = "#a7f3d0";
            }
        }

        updateStatusColor();
        status.addEventListener("change", updateStatusColor);
    }

    // 4. Update Status Form Submit Spinner
    const form = document.getElementById("updateComplaintForm");
    const submitButton = document.getElementById("updateSubmit");

    if (form && submitButton) {
        form.addEventListener("submit", function () {
            submitButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating Complaint...';
            submitButton.style.pointerEvents = "none";
            submitButton.style.opacity = "0.8";
        });
    }
});
