/**
 * Reset Password JavaScript Module - Owned by K. Deepthi
 */
document.addEventListener("DOMContentLoaded", function () {
    const resetForm = document.querySelector("form");
    const password = document.getElementById("password") || document.querySelector("input[name='password']");
    const confirm = document.getElementById("confirm_password") || document.querySelector("input[name='confirm_password']");
    const submitBtn = resetForm ? resetForm.querySelector("button[type='submit']") : null;

    if (resetForm && submitBtn) {
        resetForm.addEventListener("submit", function (e) {
            if (password && confirm && password.value !== confirm.value) {
                e.preventDefault();
                alert("Passwords do not match.");
                return;
            }
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Resetting Password...';
            submitBtn.style.pointerEvents = "none";
            submitBtn.style.opacity = "0.8";
        });
    }
});
