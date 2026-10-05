document.addEventListener("DOMContentLoaded", () => {
    // Dismissible messages.
    document.querySelectorAll(".alert").forEach((alert) => {
        window.setTimeout(() => alert.remove(), 6000);
    });

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Glass navbar state + active navigation item.
    const nav = document.querySelector(".site-nav");
    const updateNav = () => {
        if (!nav) return;
        nav.classList.toggle("scrolled", window.scrollY > 18);
    };
    updateNav();
    window.addEventListener("scroll", updateNav, { passive: true });

    const currentPath = window.location.pathname.replace(/\/$/, "") || "/";
    document.querySelectorAll(".site-nav .nav-link").forEach((link) => {
        const linkUrl = new URL(link.href, window.location.origin);
        const linkPath = linkUrl.pathname.replace(/\/$/, "") || "/";
        if (linkPath === currentPath) {
            link.classList.add("active");
            link.setAttribute("aria-current", "page");
        }
    });

    // Subtle scroll reveal across the site.
    const revealElements = document.querySelectorAll("[data-reveal]");
    if (reduceMotion) {
        revealElements.forEach((element) => element.classList.add("is-visible"));
    } else if ("IntersectionObserver" in window) {
        const revealObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

        revealElements.forEach((element) => revealObserver.observe(element));
    } else {
        revealElements.forEach((element) => element.classList.add("is-visible"));
    }

    // Automatically reveal common content on pages that do not need template changes.
    if (!reduceMotion && "IntersectionObserver" in window) {
        const automaticSelectors = [
            ".cardx",
            ".feature",
            ".university",
            ".testimonial",
            ".quote",
            ".faq-item",
            ".formcard",
            ".stickycard",
            ".section-head",
            ".hero.compact .container"
        ];

        const candidates = document.querySelectorAll(automaticSelectors.map((selector) => `${selector}:not([data-reveal])`).join(","));
        candidates.forEach((element) => {
            if (!element.hasAttribute("data-reveal")) {
                element.setAttribute("data-reveal", "");
            }
        });

        const automaticObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.08, rootMargin: "0px 0px -30px 0px" });

        candidates.forEach((element) => automaticObserver.observe(element));
    }

    // Statistics count up once when they enter the viewport.
    const counters = document.querySelectorAll("[data-count]");
    const runCounter = (element) => {
        const raw = element.dataset.count || "";
        const target = parseInt(raw.replace(/[^0-9]/g, ""), 10);
        if (!Number.isFinite(target)) return;

        const suffix = raw.includes("+") ? "+" : "";
        const prefix = raw.match(/^[^0-9]*/)?.[0] || "";

        if (reduceMotion) {
            element.textContent = `${prefix}${target.toLocaleString()}${suffix}`;
            return;
        }

        const duration = 1100;
        const start = performance.now();

        const tick = (now) => {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const value = Math.floor(target * eased);
            element.textContent = `${prefix}${value.toLocaleString()}${suffix}`;

            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        };

        requestAnimationFrame(tick);
    };

    if (counters.length && "IntersectionObserver" in window) {
        const counterObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    runCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.45 });

        counters.forEach((counter) => counterObserver.observe(counter));
    } else {
        counters.forEach(runCounter);
    }
});
