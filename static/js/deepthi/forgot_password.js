/**
 * Forgot Password JavaScript Module - Owned by K. Deepthi
 */
document.addEventListener("DOMContentLoaded", function () {
    const forgotForm = document.querySelector("form[action*='forgot']") || document.querySelector("form");
    const submitBtn = forgotForm ? forgotForm.querySelector("button[type='submit']") : null;

    if (forgotForm && submitBtn) {
        forgotForm.addEventListener("submit", function () {
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending OTP...';
            submitBtn.style.pointerEvents = "none";
            submitBtn.style.opacity = "0.8";
        });
    }
});
