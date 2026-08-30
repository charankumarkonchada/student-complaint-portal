/**
 * Authentication & Form Validation Module
 */

document.addEventListener("DOMContentLoaded", function () {
    // 1. Password Visibility Toggle
    const passwordInputs = document.querySelectorAll("input[type='password']");
    const toggleButtons = document.querySelectorAll("#passwordToggle, .toggle-password-btn");

    toggleButtons.forEach(function (toggle) {
        toggle.addEventListener("click", function () {
            const targetId = toggle.getAttribute("data-target") || "password";
            const password = document.getElementById(targetId) || document.getElementById("password");
            const icon = toggle.querySelector("i") || document.getElementById("passwordIcon");

            if (password) {
                if (password.type === "password") {
                    password.type = "text";
                    if (icon) {
                        icon.classList.remove("fa-eye");
                        icon.classList.add("fa-eye-slash");
                    }
                    toggle.setAttribute("aria-label", "Hide password");
                } else {
                    password.type = "password";
                    if (icon) {
                        icon.classList.remove("fa-eye-slash");
                        icon.classList.add("fa-eye");
                    }
                    toggle.setAttribute("aria-label", "Show password");
                }
            }
        });
    });

    // 2. Student ID Auto-uppercase & Pattern Checking
    const idInput = document.getElementById("id_no");
    const idError = document.getElementById("idError");

    if (idInput) {
        idInput.addEventListener("input", function () {
            this.value = this.value.toUpperCase();
            if (idError) {
                if (/^O[0-9]{6}$/.test(this.value)) {
                    idError.style.display = "none";
                    this.style.borderColor = "#dbe2ea";
                    this.classList.remove("is-invalid");
                } else if (this.value.length >= 7) {
                    idError.style.display = "block";
                }
            }
        });
    }

    // 3. Student Login Form Validation & Spinner
    const studentLoginForm = document.getElementById("studentLoginForm");
    const loginButton = document.getElementById("loginButton");

    if (studentLoginForm && loginButton) {
        studentLoginForm.addEventListener("submit", function (event) {
            if (idInput) {
                const idValue = idInput.value.trim().toUpperCase();
                if (!/^O[0-9]{6}$/.test(idValue)) {
                    event.preventDefault();
                    if (idError) idError.style.display = "block";
                    idInput.focus();
                    return;
                }
                idInput.value = idValue;
            }

            loginButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Signing In...';
            loginButton.style.pointerEvents = "none";
            loginButton.style.opacity = "0.8";
        });
    }

    // 4. Admin Login Form Submit Spinner
    const adminLoginForm = document.getElementById("adminLoginForm");
    if (adminLoginForm && loginButton) {
        adminLoginForm.addEventListener("submit", function () {
            loginButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Signing In...';
            loginButton.style.pointerEvents = "none";
            loginButton.style.opacity = "0.8";
        });
    }

    // 5. Change Password Form Submit Spinner & Validation
    const changePasswordForm = document.getElementById("changePasswordForm");
    const changePasswordBtn = document.getElementById("changePasswordBtn");
    if (changePasswordForm && changePasswordBtn) {
        changePasswordForm.addEventListener("submit", function (e) {
            const newPass = document.getElementById("new_password");
            const confirmPass = document.getElementById("confirm_password");
            const passErr = document.getElementById("passwordMatchError");

            if (newPass && confirmPass && newPass.value !== confirmPass.value) {
                e.preventDefault();
                if (passErr) passErr.style.display = "block";
                confirmPass.focus();
                return;
            }

            changePasswordBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating Password...';
            changePasswordBtn.style.pointerEvents = "none";
            changePasswordBtn.style.opacity = "0.8";
        });
    }

    // 6. Profile Form Submit Spinner
    const profileForm = document.getElementById("profileForm");
    const updateProfileBtn = document.getElementById("updateProfileBtn");
    if (profileForm && updateProfileBtn) {
        profileForm.addEventListener("submit", function () {
            updateProfileBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating Profile...';
            updateProfileBtn.style.pointerEvents = "none";
            updateProfileBtn.style.opacity = "0.8";
        });
    }
});

/**
 * Global Registration Form Validator
 */
function validateRegistration() {
    const idInput = document.getElementById("id_no");
    const idError = document.getElementById("idError");
    const password = document.getElementById("password") ? document.getElementById("password").value : "";
    const confirmPassword = document.getElementById("confirm_password") ? document.getElementById("confirm_password").value : "";
    const passwordError = document.getElementById("passwordError");

    const idPattern = /^O[0-9]{6}$/;
    let valid = true;

    if (idInput) {
        if (!idPattern.test(idInput.value)) {
            if (idError) idError.style.display = "block";
            idInput.classList.add("is-invalid");
            valid = false;
        } else {
            if (idError) idError.style.display = "none";
            idInput.classList.remove("is-invalid");
        }
    }

    if (password !== confirmPassword) {
        if (passwordError) passwordError.style.display = "block";
        const cPassEl = document.getElementById("confirm_password");
        if (cPassEl) cPassEl.classList.add("is-invalid");
        valid = false;
    } else {
        if (passwordError) passwordError.style.display = "none";
        const cPassEl = document.getElementById("confirm_password");
        if (cPassEl) cPassEl.classList.remove("is-invalid");
    }

    return valid;
}
