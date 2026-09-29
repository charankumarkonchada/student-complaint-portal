/**
 * Verify Reset OTP JavaScript Module - Owned by K. Deepthi
 */
document.addEventListener("DOMContentLoaded", function () {
    const otpInput = document.getElementById("otp") || document.querySelector("input[name='otp']");
    const verifyForm = document.querySelector("form");
    const submitBtn = verifyForm ? verifyForm.querySelector("button[type='submit']") : null;

    if (otpInput) {
        otpInput.addEventListener("input", function () {
            this.value = this.value.replace(/[^0-9]/g, "").slice(0, 6);
        });
    }

    if (verifyForm && submitBtn) {
        verifyForm.addEventListener("submit", function () {
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verifying...';
            submitBtn.style.pointerEvents = "none";
            submitBtn.style.opacity = "0.8";
        });
    }
});
