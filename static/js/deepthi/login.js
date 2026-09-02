/**
 * Student Login JavaScript Module - Owned by K. Deepthi
 */
document.addEventListener("DOMContentLoaded", function () {
    // 1. Password Visibility Toggle
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

    // 2. Student ID Auto-uppercase & Pattern Checking
    const idInput = document.getElementById("id_no");
    const idError = document.getElementById("idError");

    if (idInput) {
        idInput.addEventListener("input", function () {
            this.value = this.value.toUpperCase();
            if (idError) {
                if (/^[ONRS][0-9]{6}$/.test(this.value)) {
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
                if (!/^[ONRS][0-9]{6}$/.test(idValue)) {
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
});
