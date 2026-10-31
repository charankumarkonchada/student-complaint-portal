/**
 * Update Complaint Status JavaScript Module - Owned by R. Charan Kumar
 */
document.addEventListener("DOMContentLoaded", function () {
    // 1. Remarks Character Counter
    const remarks = document.getElementById("remarks");
    const counter = document.getElementById("characterCount");

    if (remarks && counter) {
        function updateCharacterCount() {
            const length = remarks.value.length;
            counter.textContent = length + " / 500";

            if (length >= 450) {
                counter.style.color = "#dc2626";
            } else {
                counter.style.color = "#94a3b8";
            }
        }

        updateCharacterCount();
        remarks.addEventListener("input", updateCharacterCount);
    }

    // 2. Status Select Dynamic Border Color and Resolution Proof Section Toggle
    const status = document.getElementById("status");
    const resolutionProofSection = document.getElementById("resolutionProofSection");
    const resolutionDropZone = document.getElementById("resolutionDropZone");
    const resolutionImageInput = document.getElementById("resolutionImageInput");
    const dropZonePlaceholder = document.getElementById("dropZonePlaceholder");
    const dropZonePreview = document.getElementById("dropZonePreview");
    const resolutionImagePreview = document.getElementById("resolutionImagePreview");
    const previewFilename = document.getElementById("previewFilename");
    const btnUploadImage = document.getElementById("btnUploadImage");
    const btnReplaceImage = document.getElementById("btnReplaceImage");
    const btnRemoveImage = document.getElementById("btnRemoveImage");
    const hasExistingProof = document.getElementById("hasExistingProof");
    const removeResolutionImage = document.getElementById("removeResolutionImage");
    const resolutionImageError = document.getElementById("resolutionImageError");

    function showError(msg) {
        if (resolutionImageError) {
            resolutionImageError.textContent = msg;
            resolutionImageError.style.display = "block";
        }
    }

    function clearError() {
        if (resolutionImageError) {
            resolutionImageError.textContent = "";
            resolutionImageError.style.display = "none";
        }
    }

    if (status) {
        function updateStatusUI() {
            if (status.value === "Pending") {
                status.style.borderColor = "#fecaca";
            } else if (status.value === "In Progress") {
                status.style.borderColor = "#fde68a";
            } else {
                status.style.borderColor = "#a7f3d0";
            }

            if (resolutionProofSection) {
                if (status.value === "Resolved") {
                    resolutionProofSection.style.display = "block";
                } else {
                    resolutionProofSection.style.display = "none";
                    clearError();
                }
            }
        }

        updateStatusUI();
        status.addEventListener("change", updateStatusUI);
    }

    const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
    const ALLOWED_EXTS = ["jpg", "jpeg", "png", "webp"];

    function handleFileSelection(file) {
        if (!file) return;

        clearError();
        const ext = file.name.split(".").pop().toLowerCase();
        if (!ALLOWED_EXTS.includes(ext)) {
            showError("Invalid image format. Supported formats: JPG, JPEG, PNG, WEBP.");
            if (resolutionImageInput) resolutionImageInput.value = "";
            return;
        }

        if (file.size > MAX_SIZE_BYTES) {
            showError("Image size exceeds the 5 MB limit. Please select a smaller photo.");
            if (resolutionImageInput) resolutionImageInput.value = "";
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            if (resolutionImagePreview) {
                resolutionImagePreview.src = e.target.result;
            }
            if (previewFilename) {
                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                previewFilename.textContent = file.name + " (" + sizeMB + " MB)";
            }
            if (dropZonePlaceholder) dropZonePlaceholder.style.display = "none";
            if (dropZonePreview) dropZonePreview.style.display = "block";
            if (removeResolutionImage) removeResolutionImage.value = "0";
            if (resolutionDropZone) resolutionDropZone.classList.add("has-image");
        };
        reader.readAsDataURL(file);
    }

    if (resolutionImageInput) {
        resolutionImageInput.addEventListener("change", function (e) {
            if (e.target.files && e.target.files[0]) {
                handleFileSelection(e.target.files[0]);
            }
        });
    }

    if (btnUploadImage) {
        btnUploadImage.addEventListener("click", function (e) {
            e.preventDefault();
            if (resolutionImageInput) resolutionImageInput.click();
        });
    }

    if (btnReplaceImage) {
        btnReplaceImage.addEventListener("click", function (e) {
            e.preventDefault();
            if (resolutionImageInput) resolutionImageInput.click();
        });
    }

    if (btnRemoveImage) {
        btnRemoveImage.addEventListener("click", function (e) {
            e.preventDefault();
            if (resolutionImageInput) resolutionImageInput.value = "";
            if (resolutionImagePreview) resolutionImagePreview.src = "";
            if (previewFilename) previewFilename.textContent = "";
            if (hasExistingProof) hasExistingProof.value = "0";
            if (removeResolutionImage) removeResolutionImage.value = "1";
            if (dropZonePreview) dropZonePreview.style.display = "none";
            if (dropZonePlaceholder) dropZonePlaceholder.style.display = "block";
            if (resolutionDropZone) resolutionDropZone.classList.remove("has-image");
            clearError();
        });
    }

    // Drag and Drop Handling
    if (resolutionDropZone) {
        ["dragenter", "dragover"].forEach(function (eventName) {
            resolutionDropZone.addEventListener(eventName, function (e) {
                e.preventDefault();
                e.stopPropagation();
                resolutionDropZone.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(function (eventName) {
            resolutionDropZone.addEventListener(eventName, function (e) {
                e.preventDefault();
                e.stopPropagation();
                resolutionDropZone.classList.remove("dragover");
            });
        });

        resolutionDropZone.addEventListener("drop", function (e) {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                const file = dt.files[0];
                if (resolutionImageInput) {
                    try {
                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(file);
                        resolutionImageInput.files = dataTransfer.files;
                    } catch (err) {
                        // Fallback for older browsers
                    }
                }
                handleFileSelection(file);
            }
        });
    }

    // 3. Form Submit Validation & Spinner
    const form = document.getElementById("updateComplaintForm");
    const submitButton = document.getElementById("updateSubmit");

    if (form && submitButton) {
        form.addEventListener("submit", function (e) {
            if (status && status.value === "Resolved") {
                const hasNewFile = resolutionImageInput && resolutionImageInput.files && resolutionImageInput.files.length > 0;
                const hasExisting = hasExistingProof && hasExistingProof.value === "1";
                const isRemoved = removeResolutionImage && removeResolutionImage.value === "1";

                if (!hasNewFile && (!hasExisting || isRemoved)) {
                    e.preventDefault();
                    showError("Please upload a resolution proof image to mark this complaint as Resolved.");
                    if (resolutionProofSection) {
                        resolutionProofSection.scrollIntoView({ behavior: "smooth", block: "center" });
                    }
                    return false;
                }
            }

            submitButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating Complaint...';
            submitButton.style.pointerEvents = "none";
            submitButton.style.opacity = "0.8";
        });
    }
});
