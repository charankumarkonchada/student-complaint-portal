/**
 * Edit Complaint JavaScript Module - Owned by M. Raghunitha
 */
function openEditImage(src) {
    const modal = document.getElementById("editImageModal");
    const image = document.getElementById("modalImage");

    if (modal && image) {
        image.src = src;
        modal.classList.add("active");
        document.body.style.overflow = "hidden";
    }
}

function closeEditImage(event) {
    if (event && event.target && event.target.id !== "editImageModal") {
        return;
    }

    const modal = document.getElementById("editImageModal");
    if (modal) {
        modal.classList.remove("active");
        document.body.style.overflow = "";
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // 1. Description Character Counter
    const desc = document.getElementById("description");
    const counter = document.getElementById("charCount");

    if (desc && counter) {
        function updateCharCount() {
            const length = desc.value.length;
            counter.textContent = length + " / 1000";

            if (length >= 900) {
                counter.style.color = "#dc2626";
            } else {
                counter.style.color = "#94a3b8";
            }
        }

        desc.addEventListener("input", updateCharCount);
        updateCharCount();
    }

    // 2. Replacement Image Preview
    const imageInput = document.getElementById("image");
    const previewContainer = document.getElementById("newImagePreview");
    const previewImage = document.getElementById("previewImage");

    if (imageInput && previewContainer && previewImage) {
        imageInput.addEventListener("change", function () {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (event) {
                    previewImage.src = event.target.result;
                    previewContainer.style.display = "block";
                };
                reader.readAsDataURL(file);
            } else {
                previewContainer.style.display = "none";
            }
        });
    }

    // 3. Form Submit Spinner
    const editForm = document.getElementById("editComplaintForm");
    const updateBtn = document.getElementById("updateBtn");

    if (editForm && updateBtn) {
        editForm.addEventListener("submit", function () {
            updateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating Complaint...';
            updateBtn.style.pointerEvents = "none";
            updateBtn.style.opacity = "0.8";
        });
    }
});
