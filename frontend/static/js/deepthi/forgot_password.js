/**
 * Forgot Password JavaScript Module - Owned by K. Deepthi
 * Validates RGUKT college email domain and provides responsive user feedback
 */
document.addEventListener("DOMContentLoaded", function () {
    const forgotForm = document.getElementById("forgotPasswordForm") || document.querySelector("form");
    const emailInput = document.getElementById("email") || (forgotForm ? forgotForm.querySelector("input[name='email']") : null);
    const submitBtn = document.getElementById("submitBtn") || (forgotForm ? forgotForm.querySelector("button[type='submit']") : null);
    const clientError = document.getElementById("emailClientError");
    const emailHelp = document.getElementById("emailHelp");

    const COLLEGE_DOMAIN = "@rguktong.ac.in";
    const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

    function showError(message) {
        if (emailInput) {
            emailInput.classList.add("is-invalid");
            emailInput.setAttribute("aria-invalid", "true");
        }
        if (clientError) {
            clientError.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> ' + message;
            clientError.classList.remove("d-none");
        }
        if (emailHelp) {
            emailHelp.classList.add("d-none");
        }
    }

    function clearError() {
        if (emailInput) {
            emailInput.classList.remove("is-invalid");
            emailInput.removeAttribute("aria-invalid");
        }
        if (clientError) {
            clientError.textContent = "";
            clientError.classList.add("d-none");
        }
        if (emailHelp) {
            emailHelp.classList.remove("d-none");
        }
    }

    function validateEmailValue(val) {
        const raw = (val || "").trim();
        if (!raw) {
            return { valid: false, message: "Email address is required." };
        }
        if (!EMAIL_REGEX.test(raw)) {
            return { valid: false, message: "Please enter a valid email address." };
        }
        const lower = raw.toLowerCase();
        if (!lower.endsWith(COLLEGE_DOMAIN) || lower === COLLEGE_DOMAIN || (lower.match(/@/g) || []).length !== 1) {
            return { valid: false, message: "Please enter your registered RGUKT college email address." };
        }
        return { valid: true };
    }

    if (emailInput) {
        emailInput.addEventListener("input", function () {
            if (emailInput.classList.contains("is-invalid")) {
                const res = validateEmailValue(emailInput.value);
                if (res.valid) {
                    clearError();
                }
            }
        });
    }

    if (forgotForm) {
        forgotForm.addEventListener("submit", function (e) {
            if (!emailInput) return;

            const res = validateEmailValue(emailInput.value);
            if (!res.valid) {
                e.preventDefault();
                e.stopPropagation();
                showError(res.message);
                emailInput.focus();
                return false;
            }

            clearError();

            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending OTP...';
                submitBtn.style.pointerEvents = "none";
                submitBtn.style.opacity = "0.8";
            }
        });
    }
});
