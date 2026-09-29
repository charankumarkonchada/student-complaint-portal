/**
 * Complaint History JavaScript Module - Owned by B. Jagan
 */
document.addEventListener("DOMContentLoaded", function () {
    // Auto submit filter on status change
    const statusSelect = document.querySelector("select[name='status']");
    if (statusSelect) {
        statusSelect.addEventListener("change", function () {
            this.form.submit();
        });
    }
});
