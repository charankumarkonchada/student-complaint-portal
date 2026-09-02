/**
 * Admin Login JavaScript Module - Owned by R. Charan Kumar
 */
document.addEventListener("DOMContentLoaded", function () {
    const passwordInput = document.getElementById("password");
    const toggleButton = document.getElementById("passwordToggle");

    if (toggleButton && passwordInput) {
        toggleButton.addEventListener("click", function () {
            const icon = toggleButton.querySelector("i");
            if (passwordInput.type === "password") {
                passwordInput.type = "text";
                if (icon) {
                    icon.classList.remove("fa-eye");
                    icon.classList.add("fa-eye-slash");
                }
                toggleButton.setAttribute("aria-label", "Hide password");
            } else {
                passwordInput.type = "password";
                if (icon) {
                    icon.classList.remove("fa-eye-slash");
                    icon.classList.add("fa-eye");
                }
                toggleButton.setAttribute("aria-label", "Show password");
            }
        });
    }

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
