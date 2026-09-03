/**
 * Add Complaint JavaScript Module - Owned by B. Jagan
 */
document.addEventListener("DOMContentLoaded", function () {
    // 1. Description Character Counter
    const description = document.getElementById("description");
    const counter = document.getElementById("characterCounter");

    if (description && counter) {
        function updateCounter() {
            const length = description.value.length;
            counter.textContent = length + " / 1000";

            if (length >= 900) {
                counter.style.color = "#dc2626";
            } else if (length >= 750) {
                counter.style.color = "#d97706";
            } else {
                counter.style.color = "#94a3b8";
            }
        }

        description.addEventListener("input", updateCounter);
        updateCounter();
    }

    // 2. Image Attachment Preview & Drag-Drop Handlers
    const imageInput = document.getElementById("image");
    const previewContainer = document.getElementById("newImagePreview") || document.getElementById("imagePreview");
    const previewImage = document.getElementById("previewImage");
    const uploadBox = document.getElementById("uploadBox");

    function displayImagePreview(file) {
        if (!file || !file.type.startsWith("image/")) {
            alert("Please select a valid image file.");
            if (imageInput) imageInput.value = "";
            if (previewContainer) previewContainer.style.display = "none";
            return;
        }

        const reader = new FileReader();
        reader.onload = function (event) {
            if (previewImage) previewImage.src = event.target.result;
            if (previewContainer) previewContainer.style.display = "block";
        };
        reader.readAsDataURL(file);

        if (uploadBox) {
            uploadBox.style.borderColor = "#f59e0b";
            uploadBox.style.background = "#fffbeb";
        }
    }

    if (imageInput) {
        imageInput.addEventListener("change", function () {
            const file = this.files[0];
            if (file) {
                displayImagePreview(file);
            } else if (previewContainer) {
                previewContainer.style.display = "none";
            }
        });
    }

    if (uploadBox && imageInput) {
        uploadBox.addEventListener("dragover", function (event) {
            event.preventDefault();
            uploadBox.style.borderColor = "#f59e0b";
            uploadBox.style.background = "#fffbeb";
        });

        uploadBox.addEventListener("dragleave", function () {
            uploadBox.style.borderColor = "#cbd5e1";
            uploadBox.style.background = "#f8fafc";
        });

        uploadBox.addEventListener("drop", function (event) {
            event.preventDefault();
            const files = event.dataTransfer.files;
            if (files.length === 0) return;

            const file = files[0];
            if (!file.type.startsWith("image/")) {
                alert("Please drop a valid image file.");
                return;
            }

            imageInput.files = files;
            displayImagePreview(file);

            uploadBox.style.borderColor = "#10b981";
            uploadBox.style.background = "#ecfdf5";
        });
    }

    // 3. Form Submit Loading Spinner
    const addForm = document.getElementById("complaintForm");
    const submitBtn = document.getElementById("submitBtn");
    if (addForm && submitBtn) {
        addForm.addEventListener("submit", function () {
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting Complaint...';
            submitBtn.style.pointerEvents = "none";
            submitBtn.style.opacity = "0.8";
        });
    }

    // 4. Live AI Analysis Preview
    const descriptionField = document.querySelector('[name="description"]');
    if (descriptionField && addForm) {
        const aiBox = document.createElement("div");
        aiBox.className = "alert alert-light border mt-3";
        aiBox.innerHTML = '<strong><i class="fa-solid fa-wand-magic-sparkles"></i> AI preview</strong><div id="aiPreview" class="small text-muted mt-2">Enter a title and description to analyze the complaint.</div>';
        descriptionField.parentElement.appendChild(aiBox);

        let aiTimer;
        async function runAI() {
            const title = document.querySelector('[name="title"]')?.value || "";
            const desc = document.querySelector('[name="description"]')?.value || "";
            const category = document.querySelector('[name="category"]:checked')?.value || "";
            const priority = document.querySelector('[name="priority"]:checked')?.value || "";

            if (title.length < 5 || desc.length < 10) return;

            try {
                const response = await fetch("/api/ai_analyze", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, description: desc, category, priority })
                });

                if (response.ok) {
                    const data = await response.json();
                    const aiPreviewEl = document.getElementById("aiPreview");
                    if (aiPreviewEl) {
                        aiPreviewEl.innerHTML = `Category: <b>${data.predicted_category}</b> (${data.category_confidence}%) · Priority: <b>${data.predicted_priority}</b> (${data.priority_confidence}%) · Estimated resolution: <b>${data.resolution_days} days</b>`;
                    }
                }
            } catch (e) {
                // Silently handle offline/mock AI preview
            }
        }

        const titleInput = document.querySelector('[name="title"]');
        [titleInput, descriptionField].forEach(function (el) {
            if (el) {
                el.addEventListener("input", function () {
                    clearTimeout(aiTimer);
                    aiTimer = setTimeout(runAI, 500);
                });
            }
        });
    }
});
