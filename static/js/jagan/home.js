/**
 * IntelliHostel — Home Page JavaScript Module
 * Interactive 4-Step Process Showcase & Landing Interactions
 * Owned by B. Jagan
 */
document.addEventListener("DOMContentLoaded", function () {
    // 1. Interactive 4-Step Showcase
    initHowItWorksShowcase();

    // 2. Hero & Action Button Micro-interactions
    initButtonEffects();

    // 3. Section-Based Landing Navbar Active Highlighter & Smooth Scroll
    initLandingNavObserver();

    // 4. Sticky Navbar Scroll Effect
    initNavbarScrollEffect();
});

/**
 * Micro-interactions for portal and landing buttons
 */
function initButtonEffects() {
    const interactiveBtns = document.querySelectorAll(".portal-btn, .hero-btn");
    interactiveBtns.forEach(btn => {
        btn.addEventListener("mouseenter", () => {
            btn.style.transform = "translateY(-2px)";
        });
        btn.addEventListener("mouseleave", () => {
            btn.style.transform = "translateY(0)";
        });
    });
}

/**
 * Initializes the interactive Step-by-Step workflow showcase
 */
function initHowItWorksShowcase() {
    const container = document.getElementById("howItWorksContainer");
    if (!container) return;

    const showcaseCard = document.getElementById("howItWorksShowcase");
    const stepButtons = Array.from(container.querySelectorAll(".how-it-works-step"));
    const visualPanels = Array.from(container.querySelectorAll(".visual-panel"));
    const detailBox = document.getElementById("howItWorksDetailBox");
    const showcaseBadgeText = document.getElementById("showcaseBadgeText");
    const showcaseTitle = document.getElementById("showcaseTitle");
    const showcaseDescription = document.getElementById("showcaseDescription");
    const showcaseTags = document.getElementById("showcaseTags");
    const showcaseBtn = document.getElementById("showcaseBtn");
    const showcaseBtnText = document.getElementById("showcaseBtnText");

    let currentStep = 1;
    let isTransitioning = false;

    // Step configuration data aligning with project requirements
    const stepsData = {
        1: {
            stage: "STEP 01 OF 04",
            title: "Submit Complaint",
            description: "Students submit hostel issues with category, description, and optional photo evidence.",
            tags: ["Complaint Details", "Photo Evidence", "Instant Triage"],
            btnText: "Raise a Complaint",
            theme: "teal"
        },
        2: {
            stage: "STEP 02 OF 04",
            title: "AI Analysis",
            description: "Machine learning analyzes the complaint to predict category, priority, resolution time, and similar issues.",
            tags: ["Category Prediction", "Priority Prediction", "Similarity Detection"],
            btnText: "Explore AI Engine",
            theme: "ai"
        },
        3: {
            stage: "STEP 03 OF 04",
            title: "Admin Review",
            description: "Administrators review complaints, assign staff, update status, and manage common issues.",
            tags: ["Review & Assign", "Status Tracking", "Common Issues"],
            btnText: "Open Admin Portal",
            theme: "admin"
        },
        4: {
            stage: "STEP 04 OF 04",
            title: "Resolution",
            description: "Students track progress, receive notifications, and see the complaint move to resolution.",
            tags: ["Status Updates", "Complaint History", "Notifications"],
            btnText: "Track Resolution",
            theme: "resolution"
        }
    };

    /**
     * Activates a specific step and displays its unique visual composition
     * @param {number} stepNum - The step number (1-4)
     * @param {boolean} focusTab - Whether to move keyboard focus to the activated tab
     */
    function switchStep(stepNum, focusTab = false) {
        if (stepNum === currentStep || isTransitioning) return;
        if (!stepsData[stepNum]) return;

        isTransitioning = true;
        currentStep = stepNum;

        const data = stepsData[stepNum];

        // 1. Update Navigation Buttons
        stepButtons.forEach(btn => {
            const num = parseInt(btn.getAttribute("data-step"), 10);
            const isActive = num === stepNum;
            btn.classList.toggle("active", isActive);
            btn.setAttribute("aria-selected", isActive ? "true" : "false");
            btn.setAttribute("tabindex", isActive ? "0" : "-1");

            if (isActive && focusTab) {
                btn.focus();
            }
        });

        // 2. Animate out active content & visual
        if (detailBox) detailBox.classList.add("is-transitioning");
        visualPanels.forEach(panel => {
            if (panel.classList.contains("active")) {
                panel.classList.add("is-transitioning");
            }
        });

        // 3. Swap content after brief transition delay (140ms)
        setTimeout(() => {
            // Update Theme Classes on container and showcase
            if (showcaseCard) {
                showcaseCard.className = `how-it-works-visual-stage theme-${data.theme}`;
            }

            // Update Text & Meta
            if (showcaseBadgeText) showcaseBadgeText.textContent = data.stage;
            if (showcaseTitle) showcaseTitle.textContent = data.title;
            if (showcaseDescription) showcaseDescription.textContent = data.description;

            // Feature Chips
            if (showcaseTags) {
                showcaseTags.innerHTML = "";
                data.tags.forEach(tag => {
                    const tagEl = document.createElement("span");
                    tagEl.className = `showcase-tag tag-${data.theme}`;
                    tagEl.textContent = tag;
                    showcaseTags.appendChild(tagEl);
                });
            }

            // CTA Button Link & Text
            const targetUrl = container.dataset[`urlStep${stepNum}`] || "#";
            if (showcaseBtn) {
                showcaseBtn.setAttribute("href", targetUrl);
                if (showcaseBtnText) showcaseBtnText.textContent = data.btnText;
                showcaseBtn.className = `showcase-btn btn-${data.theme}`;
            }

            // Swap Visual Panel
            visualPanels.forEach(panel => {
                const pNum = parseInt(panel.getAttribute("data-step"), 10);
                const isActive = pNum === stepNum;
                panel.classList.toggle("active", isActive);
                panel.classList.remove("is-transitioning");
            });

            // Animate in
            requestAnimationFrame(() => {
                if (detailBox) detailBox.classList.remove("is-transitioning");
                isTransitioning = false;
            });
        }, 140);
    }

    // Attach click events
    stepButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            const stepNum = parseInt(this.getAttribute("data-step"), 10);
            switchStep(stepNum, false);
        });

        // Keyboard navigation (Arrow keys, Home, End)
        btn.addEventListener("keydown", function (e) {
            let targetStep = null;
            if (e.key === "ArrowDown" || e.key === "ArrowRight") {
                e.preventDefault();
                targetStep = currentStep < 4 ? currentStep + 1 : 1;
            } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
                e.preventDefault();
                targetStep = currentStep > 1 ? currentStep - 1 : 4;
            } else if (e.key === "Home") {
                e.preventDefault();
                targetStep = 1;
            } else if (e.key === "End") {
                e.preventDefault();
                targetStep = 4;
            }

            if (targetStep !== null) {
                switchStep(targetStep, true);
            }
        });
    });
}

/**
 * Initializes IntersectionObserver for section-based navbar highlighting, linear navigation, and reliable hash sync
 */
function initLandingNavObserver() {
    const landingNavLinks = Array.from(document.querySelectorAll(".landing-nav-link"));
    if (!landingNavLinks.length) return;

    // Linear Landing Sections on IntelliHostel:
    // 1. Home -> 2. Features -> 3. How It Works -> 4. Get Started -> 5. About
    const sectionIds = ["home", "features", "how-it-works", "get-started", "about"];
    const sections = sectionIds
        .map(id => document.getElementById(id))
        .filter(Boolean);

    if (!sections.length) return;

    let isProgrammaticScroll = false;
    let scrollLockTimer = null;

    /**
     * Resolves target element for navigation, supporting aliases like #portals -> #get-started
     * @param {string} id
     * @returns {HTMLElement|null}
     */
    function resolveTargetElement(id) {
        if (!id) return null;
        const cleanId = id.replace("#", "").trim().toLowerCase();
        if (cleanId === "portals" || cleanId === "portal") {
            return document.getElementById("get-started") || document.getElementById("portals");
        }
        return document.getElementById(cleanId);
    }

    /**
     * Sets the active state on the appropriate navbar item
     * @param {string} sectionId - The ID of the currently visible section
     */
    function setActiveSection(sectionId) {
        const canonicalId = (sectionId === "portals") ? "get-started" : sectionId;
        landingNavLinks.forEach(link => {
            const target = link.getAttribute("data-section");
            const isActive = target === canonicalId;
            link.classList.toggle("active", isActive);
            if (isActive) {
                link.setAttribute("aria-current", "page");
            } else {
                link.removeAttribute("aria-current");
            }
        });
    }

    /**
     * Dynamic navbar height
     */
    function getNavbarHeight() {
        const navbar = document.querySelector(".portal-navbar");
        return navbar ? navbar.getBoundingClientRect().height : 76;
    }

    /**
     * Calculates the exact sticky navbar offset and smoothly scrolls to the target section
     * @param {HTMLElement} targetEl
     * @param {boolean} updateUrl
     * @param {boolean} smooth
     */
    function scrollToSection(targetEl, updateUrl = true, smooth = true) {
        if (!targetEl) return;

        isProgrammaticScroll = true;
        clearTimeout(scrollLockTimer);

        // Force reveal visibility so element geometry and heights are accurately computed
        targetEl.classList.add("reveal-visible");
        targetEl.querySelectorAll(".reveal-fade, .reveal-up, .reveal-down, .reveal-left, .reveal-right, .reveal-scale")
            .forEach(el => el.classList.add("reveal-visible"));

        const navHeight = getNavbarHeight();
        const rect = targetEl.getBoundingClientRect();
        const targetTop = rect.top + window.pageYOffset - navHeight;

        const effectiveId = targetEl.id === "portals" ? "get-started" : targetEl.id;

        if (updateUrl && window.history && window.history.pushState) {
            window.history.pushState(null, "", `#${effectiveId}`);
        }

        window.scrollTo({
            top: Math.max(0, Math.round(targetTop)),
            behavior: smooth ? "smooth" : "auto"
        });

        setActiveSection(effectiveId);

        scrollLockTimer = setTimeout(() => {
            isProgrammaticScroll = false;
        }, smooth ? 800 : 100);
    }

    // Precision IntersectionObserver to track which section occupies the viewport
    const sectionObserver = new IntersectionObserver((entries) => {
        if (isProgrammaticScroll) return;

        const visibleEntries = entries.filter(e => e.isIntersecting);
        if (visibleEntries.length > 0) {
            visibleEntries.sort((a, b) => b.intersectionRatio - a.intersectionRatio);
            const activeId = visibleEntries[0].target.id;
            const effectiveId = activeId === "portals" ? "get-started" : activeId;
            setActiveSection(effectiveId);

            if (window.history && window.history.replaceState) {
                window.history.replaceState(null, "", `#${effectiveId}`);
            }
        }
    }, {
        root: null,
        threshold: [0.2, 0.5]
    });

    sections.forEach(section => sectionObserver.observe(section));

    // Boundary guards for smooth highlighting
    window.addEventListener("scroll", function () {
        if (isProgrammaticScroll) return;

        if (window.pageYOffset < 60) {
            setActiveSection("home");
            if (window.history && window.history.replaceState && window.location.hash !== "#home") {
                window.history.replaceState(null, "", "#home");
            }
        } else if ((window.innerHeight + window.pageYOffset) >= (document.documentElement.scrollHeight - 50)) {
            setActiveSection("about");
            if (window.history && window.history.replaceState && window.location.hash !== "#about") {
                window.history.replaceState(null, "", "#about");
            }
        }
    }, { passive: true });

    // Handle navbar link click interactions
    landingNavLinks.forEach(link => {
        link.addEventListener("click", function (e) {
            const sectionId = this.getAttribute("data-section");
            const targetEl = resolveTargetElement(sectionId);

            if (targetEl) {
                if (window.location.pathname === "/" || window.location.pathname.endsWith("/index.html")) {
                    e.preventDefault();
                    scrollToSection(targetEl, true, true);
                }
            }

            // Automatically close Bootstrap mobile drawer if open
            const navbarCollapse = document.getElementById("mainNavbar");
            if (navbarCollapse && navbarCollapse.classList.contains("show")) {
                if (window.bootstrap && window.bootstrap.Collapse) {
                    const bsCollapse = window.bootstrap.Collapse.getInstance(navbarCollapse) || new window.bootstrap.Collapse(navbarCollapse, { toggle: false });
                    bsCollapse.hide();
                } else {
                    navbarCollapse.classList.remove("show");
                }
            }
        });
    });

    // Handle initial page load with hash (e.g. /#features, /#how-it-works, /#get-started, /#about)
    function handleHashNavigation(smooth = false) {
        if (window.location.hash) {
            const targetEl = resolveTargetElement(window.location.hash);
            if (targetEl) {
                scrollToSection(targetEl, false, smooth);
                return true;
            }
        }
        return false;
    }

    // Initial check on DOMContentLoaded
    if (!handleHashNavigation(false)) {
        setActiveSection("home");
    }

    // Secondary pass on window load when images, fonts, and stylesheets are completely parsed
    window.addEventListener("load", function () {
        if (window.location.hash) {
            handleHashNavigation(false);
        }
    });

    // Handle browser back/forward or hash changes in URL bar
    window.addEventListener("hashchange", function () {
        handleHashNavigation(true);
    });
}

/**
 * Adds subtle shadow and compact padding to sticky navbar on scroll
 */
function initNavbarScrollEffect() {
    const navbar = document.querySelector(".portal-navbar");
    if (!navbar) return;

    function handleScroll() {
        if (window.scrollY > 20) {
            navbar.classList.add("navbar-scrolled");
        } else {
            navbar.classList.remove("navbar-scrolled");
        }
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
}
