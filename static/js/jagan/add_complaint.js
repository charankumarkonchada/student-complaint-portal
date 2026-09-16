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
            uploadBox.classList.add("upload-success");
            uploadBox.classList.remove("drag-over");
        }
    }

    if (imageInput) {
        imageInput.addEventListener("change", function () {
            const file = this.files[0];
            if (file) {
                displayImagePreview(file);
            } else if (previewContainer) {
                previewContainer.style.display = "none";
                if (uploadBox) {
                    uploadBox.classList.remove("upload-success", "drag-over");
                }
            }
        });
    }

    if (uploadBox && imageInput) {
        uploadBox.addEventListener("dragover", function (event) {
            event.preventDefault();
            uploadBox.classList.add("drag-over");
        });

        uploadBox.addEventListener("dragleave", function () {
            uploadBox.classList.remove("drag-over");
        });

        uploadBox.addEventListener("drop", function (event) {
            event.preventDefault();
            uploadBox.classList.remove("drag-over");
            const files = event.dataTransfer.files;
            if (files.length === 0) return;

            const file = files[0];
            if (!file.type.startsWith("image/")) {
                alert("Please drop a valid image file.");
                return;
            }

            imageInput.files = files;
            displayImagePreview(file);
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
        aiBox.className = "ai-preview-card mt-3";
        aiBox.innerHTML = `
            <div class="ai-preview-header">
                <div class="ai-preview-title">
                    <i class="fa-solid fa-wand-magic-sparkles"></i>
                    <span>AI Preview</span>
                </div>
                <span class="ai-live-badge"><span class="ai-live-dot"></span> Live Assistant</span>
            </div>
            <div id="aiPreview" class="ai-preview-body">
                <div class="ai-idle-message">
                    <i class="fa-solid fa-circle-info me-1"></i>
                    <span>Enter a title and description to analyze the complaint in real-time.</span>
                </div>
            </div>
        `;
        descriptionField.parentElement.appendChild(aiBox);

        let aiTimer;
        async function runAI() {
            const title = document.querySelector('[name="title"]')?.value || "";
            const desc = document.querySelector('[name="description"]')?.value || "";
            const category = document.querySelector('[name="category"]:checked')?.value || "";
            const priority = document.querySelector('[name="priority"]:checked')?.value || "";

            if (title.length < 5 || desc.length < 10) return;

            const aiPreviewEl = document.getElementById("aiPreview");
            if (aiPreviewEl) {
                aiPreviewEl.innerHTML = '<div class="ai-analyzing-msg"><i class="fa-solid fa-spinner fa-spin me-2"></i> Analyzing complaint with AI...</div>';
            }

            try {
                const response = await fetch("/api/ai_analyze", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, description: desc, category, priority })
                });

                if (response.ok) {
                    const data = await response.json();
                    if (aiPreviewEl) {
                        const priClass = (data.predicted_priority || '').toLowerCase();
                        aiPreviewEl.innerHTML = `
                            <div class="ai-results-grid">
                                <div class="ai-result-card">
                                    <span class="ai-result-label">Predicted Category</span>
                                    <div class="ai-result-val-row">
                                        <span class="ai-result-value">${data.predicted_category}</span>
                                        <span class="ai-conf-pill">${data.category_confidence}%</span>
                                    </div>
                                </div>
                                <div class="ai-result-card">
                                    <span class="ai-result-label">Predicted Priority</span>
                                    <div class="ai-result-val-row">
                                        <span class="ai-result-value priority-text-${priClass}">${data.predicted_priority}</span>
                                        <span class="ai-conf-pill">${data.priority_confidence}%</span>
                                    </div>
                                </div>
                                <div class="ai-result-card">
                                    <span class="ai-result-label">Estimated Resolution</span>
                                    <div class="ai-result-val-row">
                                        <span class="ai-result-value">${data.resolution_days} <small class="ai-unit">days</small></span>
                                    </div>
                                </div>
                            </div>
                            <div class="ai-footer-note">
                                <i class="fa-solid fa-circle-check text-success me-1"></i>
                                <span>AI predictions ready. You may keep or modify your selected category and priority.</span>
                            </div>
                        `;
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
