/**
 * Change Password JavaScript Module - Owned by K. Deepthi
 */
document.addEventListener("DOMContentLoaded", function () {
    const changeForm = document.getElementById("changePasswordForm") || document.querySelector("form[action*='change_password']");
    const newPass = document.getElementById("new_password");
    const confirmPass = document.getElementById("confirm_password");
    const errorEl = document.getElementById("passwordMismatch");
    const submitBtn = document.getElementById("changeSubmit") || (changeForm ? changeForm.querySelector("button[type='submit']") : null);

    if (newPass && confirmPass && errorEl) {
        function checkMatch() {
            if (confirmPass.value && newPass.value !== confirmPass.value) {
                errorEl.style.display = "block";
            } else {
                errorEl.style.display = "none";
            }
        }
        newPass.addEventListener("input", checkMatch);
        confirmPass.addEventListener("input", checkMatch);
    }

    if (changeForm && submitBtn) {
        changeForm.addEventListener("submit", function (e) {
            if (newPass && confirmPass && newPass.value !== confirmPass.value) {
                e.preventDefault();
                if (errorEl) errorEl.style.display = "block";
                return;
            }
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating Password...';
            submitBtn.style.pointerEvents = "none";
            submitBtn.style.opacity = "0.8";
        });
    }
});
