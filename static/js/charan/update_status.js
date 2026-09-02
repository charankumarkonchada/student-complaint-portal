/**
 * Update Complaint Status JavaScript Module - Owned by R. Charan Kumar
 */
document.addEventListener("DOMContentLoaded", function () {
    // 1. Remarks Character Counter
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

    // 2. Status Select Dynamic Border Color
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

    // 3. Form Submit Spinner
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
