/**
 * Student Registration JavaScript Module - Owned by M. Rushmitha
 */
function validateRegistration() {
    const idInput = document.getElementById("id_no");
    const idError = document.getElementById("idError");
    const password = document.getElementById("password") ? document.getElementById("password").value : "";
    const confirmPassword = document.getElementById("confirm_password") ? document.getElementById("confirm_password").value : "";
    const passwordError = document.getElementById("passwordError");

    const idPattern = /^[ONRS][0-9]{6}$/i;
    let valid = true;

    if (idInput) {
        if (!idPattern.test(idInput.value.trim())) {
            if (idError) idError.style.display = "block";
            idInput.classList.add("is-invalid");
            valid = false;
        } else {
            if (idError) idError.style.display = "none";
            idInput.classList.remove("is-invalid");
        }
    }

    const emailInput = document.getElementById("email");
    const emailMismatchError = document.getElementById("emailMismatchError");

    if (idInput && emailInput && idInput.value && emailInput.value) {
        const idVal = idInput.value.trim().toLowerCase();
        const emailVal = emailInput.value.trim().toLowerCase();
        if (idPattern.test(idVal) && emailVal.includes("@")) {
            const emailLocal = emailVal.split("@")[0];
            if (emailLocal !== idVal) {
                if (emailMismatchError) emailMismatchError.style.display = "block";
                emailInput.classList.add("is-invalid");
                valid = false;
            } else {
                if (emailMismatchError) emailMismatchError.style.display = "none";
                emailInput.classList.remove("is-invalid");
            }
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

document.addEventListener("DOMContentLoaded", function () {
    const idInput = document.getElementById("id_no");
    const idError = document.getElementById("idError");
    const emailInput = document.getElementById("email");
    const emailMismatchError = document.getElementById("emailMismatchError");

    function checkEmailIdMatch() {
        if (idInput && emailInput && emailMismatchError) {
            const idVal = idInput.value.trim().toLowerCase();
            const emailVal = emailInput.value.trim().toLowerCase();
            if (/^[onrs][0-9]{6}$/.test(idVal) && emailVal.includes("@")) {
                const emailLocal = emailVal.split("@")[0];
                if (emailLocal !== idVal) {
                    emailMismatchError.style.display = "block";
                } else {
                    emailMismatchError.style.display = "none";
                    emailInput.classList.remove("is-invalid");
                }
            } else {
                emailMismatchError.style.display = "none";
            }
        }
    }

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
            checkEmailIdMatch();
        });
    }

    if (emailInput) {
        emailInput.addEventListener("input", checkEmailIdMatch);
    }
});
