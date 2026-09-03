/**
 * Student Profile JavaScript Module - Owned by M. Raghunitha
 */
document.addEventListener("DOMContentLoaded", function () {
    const profileForm = document.querySelector(".profile-form") || document.querySelector("form[action*='profile']");
    const submitBtn = profileForm ? profileForm.querySelector("button[type='submit']") : null;

    if (profileForm && submitBtn) {
        profileForm.addEventListener("submit", function () {
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving Changes...';
            submitBtn.style.pointerEvents = "none";
            submitBtn.style.opacity = "0.8";
        });
    }
});
