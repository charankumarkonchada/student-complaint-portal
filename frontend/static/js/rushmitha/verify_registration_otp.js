/**
 * Registration Email OTP Verification Module - Owned by M. Rushmitha
 */
document.addEventListener("DOMContentLoaded", function () {
    const otpInput = document.getElementById("otp");
    const verifyForm = document.getElementById("verifyOtpForm");
    const verifyBtn = document.getElementById("verifyOtpBtn");
    const verifyBtnText = document.getElementById("verifyBtnText");
    const verifyIcon = document.getElementById("verifyIcon");

    const resendBtn = document.getElementById("resendBtn");
    const resendText = document.getElementById("resendText");
    const resendIcon = document.getElementById("resendIcon");
    const cooldownSpan = document.getElementById("cooldownSeconds");

    let remainingSeconds = cooldownSpan ? parseInt(cooldownSpan.textContent.trim(), 10) : 0;
    if (isNaN(remainingSeconds)) {
        remainingSeconds = 0;
    }

    let countdownTimer = null;

    function startCooldown(seconds) {
        remainingSeconds = seconds;
        if (remainingSeconds <= 0) {
            enableResend();
            return;
        }

        disableResend();
        if (countdownTimer) clearInterval(countdownTimer);

        countdownTimer = setInterval(function () {
            remainingSeconds--;
            if (remainingSeconds <= 0) {
                clearInterval(countdownTimer);
                countdownTimer = null;
                enableResend();
            } else {
                updateResendLabel(remainingSeconds);
            }
        }, 1000);
    }

    function disableResend() {
        if (!resendBtn) return;
        resendBtn.disabled = true;
        updateResendLabel(remainingSeconds);
    }

    function enableResend() {
        if (!resendBtn) return;
        resendBtn.disabled = false;
        if (resendText) {
            resendText.textContent = "Resend Verification Code";
        }
        if (resendIcon) {
            resendIcon.className = "fa-solid fa-rotate-right me-1";
        }
    }

    function updateResendLabel(seconds) {
        if (resendText) {
            resendText.innerHTML = 'Resend Code in <span id="cooldownSeconds">' + seconds + "</span>s";
        }
    }

    if (remainingSeconds > 0) {
        startCooldown(remainingSeconds);
    }

    // Input sanitizer: only allow numbers and auto-submit on 6 digits
    if (otpInput) {
        otpInput.focus();
        otpInput.addEventListener("input", function () {
            this.value = this.value.replace(/\D/g, "").slice(0, 6);
        });

        // Allow paste event
        otpInput.addEventListener("paste", function (e) {
            e.preventDefault();
            const text = (e.clipboardData || window.clipboardData).getData("text");
            const clean = text.replace(/\D/g, "").slice(0, 6);
            this.value = clean;
        });
    }

    // Handle form submit loading state
    if (verifyForm && verifyBtn) {
        verifyForm.addEventListener("submit", function () {
            verifyBtn.disabled = true;
            if (verifyIcon) {
                verifyIcon.className = "fa-solid fa-spinner fa-spin";
            }
            if (verifyBtnText) {
                verifyBtnText.textContent = "Verifying Code...";
            }
        });
    }

    // Resend AJAX handling
    const resendForm = document.getElementById("resendOtpForm");
    if (resendForm && resendBtn) {
        resendForm.addEventListener("submit", function (e) {
            if (resendBtn.disabled) {
                e.preventDefault();
                return;
            }

            // AJAX call for smoother UX
            e.preventDefault();
            resendBtn.disabled = true;
            if (resendIcon) {
                resendIcon.className = "fa-solid fa-spinner fa-spin me-1";
            }
            if (resendText) {
                resendText.textContent = "Sending Code...";
            }

            const csrfTokenInput = resendForm.querySelector('input[name="csrf_token"]');
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : "";

            fetch(resendForm.action, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json"
                },
                body: new URLSearchParams({
                    csrf_token: csrfToken
                })
            })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { status: res.status, data: data };
                });
            })
            .then(function (result) {
                if (result.status === 200 && result.data.success) {
                    startCooldown(result.data.cooldown || 60);
                    // Flash notification or alert
                    const msg = result.data.message || "A new verification code has been sent.";
                    showNotice(msg, "success");
                } else {
                    const err = (result.data && result.data.error) ? result.data.error : "Failed to send OTP.";
                    showNotice(err, "danger");
                    if (result.data && result.data.cooldown) {
                        startCooldown(result.data.cooldown);
                    } else {
                        enableResend();
                    }
                }
            })
            .catch(function () {
                // Fallback to regular submit if fetch fails
                resendForm.submit();
            });
        });
    }

    function showNotice(msg, type) {
        let alertBox = document.querySelector(".alert");
        if (!alertBox) {
            alertBox = document.createElement("div");
            alertBox.className = "alert alert-" + type + " alert-dismissible fade show mt-3";
            const card = document.querySelector(".otp-verify-card");
            if (card) {
                const form = document.getElementById("verifyOtpForm");
                card.insertBefore(alertBox, form);
            }
        } else {
            alertBox.className = "alert alert-" + type + " alert-dismissible fade show mt-3";
        }
        alertBox.innerHTML = '<i class="fa-solid fa-circle-info me-2"></i>' + msg;
    }
});
