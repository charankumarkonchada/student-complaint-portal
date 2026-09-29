/**
 * Admin Login JavaScript Module - Owned by R. Charan Kumar
 */
document.addEventListener("DOMContentLoaded", function () {
    // Password Visibility Toggle is handled globally by script.js with data-target & accessibility support

    const adminLoginForm = document.getElementById("adminLoginForm");
    const loginButton = document.getElementById("loginButton");

    if (adminLoginForm && loginButton) {
        adminLoginForm.addEventListener("submit", function () {
            loginButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Signing In...';
            loginButton.style.pointerEvents = "none";
            loginButton.style.opacity = "0.8";
        });
    }
});
