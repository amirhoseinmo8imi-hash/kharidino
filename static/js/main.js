/* =========================================================
   KHARIDINO
   Main JavaScript
   Mobile Menu / Animations / Alerts / Scroll / Interactions
   ========================================================= */

"use strict";

document.addEventListener("DOMContentLoaded", () => {

    /* =====================================================
       ELEMENTS
       ===================================================== */

    const body = document.body;
    const html = document.documentElement;

    /* =====================================================
       MOBILE MENU
       ===================================================== */

    const mobileMenuButton =
        document.querySelector(".mobile-menu-btn") ||
        document.getElementById("mobileMenuBtn");

    const navLinks =
        document.querySelector(".nav-links");

    let mobileMenuOpen = false;

    function openMobileMenu() {

        if (!navLinks) return;

        mobileMenuOpen = true;

        navLinks.classList.add("mobile-open");
        body.classList.add("menu-open");

        if (mobileMenuButton) {
            mobileMenuButton.classList.add("active");

            mobileMenuButton.setAttribute(
                "aria-expanded",
                "true"
            );

            const icon =
                mobileMenuButton.querySelector("i");

            if (icon) {
                icon.classList.remove("fa-bars");
                icon.classList.add("fa-xmark");
            }
        }
    }

    function closeMobileMenu() {

        if (!navLinks) return;

        mobileMenuOpen = false;

        navLinks.classList.remove("mobile-open");
        body.classList.remove("menu-open");

        if (mobileMenuButton) {

            mobileMenuButton.classList.remove("active");

            mobileMenuButton.setAttribute(
                "aria-expanded",
                "false"
            );

            const icon =
                mobileMenuButton.querySelector("i");

            if (icon) {
                icon.classList.remove("fa-xmark");
                icon.classList.add("fa-bars");
            }
        }
    }

    function toggleMobileMenu() {

        if (mobileMenuOpen) {
            closeMobileMenu();
        } else {
            openMobileMenu();
        }
    }

    if (mobileMenuButton && navLinks) {

        mobileMenuButton.setAttribute(
            "aria-expanded",
            "false"
        );

        mobileMenuButton.setAttribute(
            "aria-label",
            "باز کردن منو"
        );

        mobileMenuButton.addEventListener(
            "click",
            toggleMobileMenu
        );

        /* بستن منو بعد از کلیک روی لینک */

        navLinks
            .querySelectorAll("a")
            .forEach(link => {

                link.addEventListener(
                    "click",
                    () => {
                        closeMobileMenu();
                    }
                );

            });
    }

    /* بستن منو با کلیک بیرون */

    document.addEventListener(
        "click",
        event => {

            if (!mobileMenuOpen) return;

            const clickedInsideMenu =
                navLinks &&
                navLinks.contains(event.target);

            const clickedButton =
                mobileMenuButton &&
                mobileMenuButton.contains(event.target);

            if (
                !clickedInsideMenu &&
                !clickedButton
            ) {
                closeMobileMenu();
            }
        }
    );

    /* بستن با ESC */

    document.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Escape" &&
                mobileMenuOpen
            ) {
                closeMobileMenu();
            }
        }
    );

    /* =====================================================
       MOBILE MENU RESPONSIVE
       ===================================================== */

    window.addEventListener(
        "resize",
        () => {

            if (
                window.innerWidth > 900 &&
                mobileMenuOpen
            ) {
                closeMobileMenu();
            }

        },
        { passive: true }
    );


    /* =====================================================
       SCROLL EFFECT
       ===================================================== */

    const navbar =
        document.querySelector(".navbar");

    let lastScrollY = window.scrollY;

    function handleScroll() {

        const currentScroll =
            window.scrollY;

        /* Navbar glass effect */

        if (navbar) {

            if (currentScroll > 20) {
                navbar.classList.add(
                    "navbar-scrolled"
                );
            } else {
                navbar.classList.remove(
                    "navbar-scrolled"
                );
            }

        }

        /* جهت حرکت صفحه */

        if (navbar) {

            if (
                currentScroll > lastScrollY &&
                currentScroll > 150
            ) {
                navbar.classList.add(
                    "navbar-hidden"
                );
            } else {
                navbar.classList.remove(
                    "navbar-hidden"
                );
            }

        }

        lastScrollY = currentScroll;
    }

    let scrollTicking = false;

    window.addEventListener(
        "scroll",
        () => {

            if (!scrollTicking) {

                window.requestAnimationFrame(
                    () => {

                        handleScroll();

                        scrollTicking = false;

                    }
                );

                scrollTicking = true;
            }

        },
        { passive: true }
    );


    /* =====================================================
       SCROLL REVEAL
       ===================================================== */

    const revealElements =
        document.querySelectorAll(
            ".card, .product-card, .category-card, .store-card, .section-header, .hero-copy, .hero-grid"
        );

    if (
        "IntersectionObserver" in window &&
        revealElements.length
    ) {

        const revealObserver =
            new IntersectionObserver(
                (entries, observer) => {

                    entries.forEach(
                        entry => {

                            if (
                                entry.isIntersecting
                            ) {

                                entry.target.classList.add(
                                    "reveal-visible"
                                );

                                observer.unobserve(
                                    entry.target
                                );
                            }

                        }
                    );

                },
                {
                    threshold: 0.08,
                    rootMargin: "0px 0px -50px 0px"
                }
            );

        revealElements.forEach(
            element => {

                element.classList.add(
                    "reveal-element"
                );

                revealObserver.observe(
                    element
                );

            }
        );
    }


    /* =====================================================
       SMOOTH ANCHOR SCROLL
       ===================================================== */

    document
        .querySelectorAll('a[href^="#"]')
        .forEach(anchor => {

            anchor.addEventListener(
                "click",
                event => {

                    const href =
                        anchor.getAttribute("href");

                    if (
                        !href ||
                        href === "#"
                    ) {
                        return;
                    }

                    const target =
                        document.querySelector(href);

                    if (!target) return;

                    event.preventDefault();

                    const navbarHeight =
                        navbar
                            ? navbar.offsetHeight
                            : 0;

                    const targetPosition =
                        target.getBoundingClientRect().top +
                        window.scrollY -
                        navbarHeight -
                        15;

                    window.scrollTo({
                        top: targetPosition,
                        behavior: "smooth"
                    });

                    closeMobileMenu();

                }
            );

        });


    /* =====================================================
       ACTIVE NAVIGATION
       ===================================================== */

    const currentPath =
        window.location.pathname;

    document
        .querySelectorAll(".nav-links a")
        .forEach(link => {

            const href =
                link.getAttribute("href");

            if (
                href &&
                href !== "#" &&
                href !== "/" &&
                currentPath === href
            ) {
                link.classList.add("active");
            }

            if (
                href === "/" &&
                currentPath === "/"
            ) {
                link.classList.add("active");
            }

        });


    /* =====================================================
       FLASH / ALERT AUTO CLOSE
       ===================================================== */

    const flashMessages =
        document.querySelectorAll(
            ".flash, .alert"
        );

    flashMessages.forEach(
        (message, index) => {

            /* دکمه بستن */

            if (
                !message.querySelector(
                    ".flash-close"
                )
            ) {

                const closeButton =
                    document.createElement("button");

                closeButton.type = "button";

                closeButton.className =
                    "flash-close";

                closeButton.innerHTML =
                    '<i class="fa-solid fa-xmark"></i>';

                closeButton.setAttribute(
                    "aria-label",
                    "بستن"
                );

                message.appendChild(
                    closeButton
                );

                closeButton.addEventListener(
                    "click",
                    () => {

                        closeAlert(
                            message
                        );

                    }
                );
            }

            /* تأخیر بسته شدن */

            const delay =
                message.classList.contains(
                    "flash-danger"
                )
                    ? 9000
                    : 5500 + index * 500;

            setTimeout(
                () => {

                    if (
                        document.body.contains(
                            message
                        )
                    ) {
                        closeAlert(
                            message
                        );
                    }

                },
                delay
            );

        }
    );

    function closeAlert(element) {

        if (!element) return;

        element.classList.add(
            "flash-closing"
        );

        setTimeout(
            () => {

                element.remove();

            },
            350
        );
    }


    /* =====================================================
       DELETE CONFIRMATION
       ===================================================== */

    document
        .querySelectorAll(
            'form[action*="/delete/"]'
        )
        .forEach(form => {

            form.addEventListener(
                "submit",
                event => {

                    const confirmed =
                        window.confirm(
                            "آیا از حذف این مورد مطمئن هستید؟ این عملیات قابل بازگشت نیست."
                        );

                    if (!confirmed) {
                        event.preventDefault();
                    }

                }
            );

        });


    /* =====================================================
       FILE INPUT PREVIEW
       ===================================================== */

    const fileInputs =
        document.querySelectorAll(
            'input[type="file"]'
        );

    fileInputs.forEach(
        input => {

            input.addEventListener(
                "change",
                () => {

                    const file =
                        input.files &&
                        input.files[0];

                    if (!file) return;

                    const wrapper =
                        input.closest(
                            ".form-group"
                        );

                    if (!wrapper) return;

                    let fileInfo =
                        wrapper.querySelector(
                            ".file-info"
                        );

                    if (!fileInfo) {

                        fileInfo =
                            document.createElement(
                                "div"
                            );

                        fileInfo.className =
                            "file-info";

                        wrapper.appendChild(
                            fileInfo
                        );
                    }

                    const sizeMB =
                        file.size /
                        (1024 * 1024);

                    fileInfo.innerHTML =
                        `
                        <i class="fa-solid fa-file"></i>
                        <span>${escapeHtml(file.name)}</span>
                        <small>${sizeMB.toFixed(2)} MB</small>
                        `;

                }
            );

        }
    );


    /* =====================================================
       BACKGROUND FILE TYPE DETECTION
       ===================================================== */

    const backgroundInput =
        document.querySelector(
            'input[name="background_file"]'
        );

    const backgroundMode =
        document.querySelector(
            'select[name="mode"]'
        );

    if (
        backgroundInput &&
        backgroundMode
    ) {

        backgroundInput.addEventListener(
            "change",
            () => {

                const file =
                    backgroundInput.files &&
                    backgroundInput.files[0];

                if (!file) return;

                const extension =
                    file.name
                        .split(".")
                        .pop()
                        .toLowerCase();

                if (
                    extension === "mp4" ||
                    extension === "webm" ||
                    extension === "ogg"
                ) {
                    backgroundMode.value =
                        "video";
                }
                else if (
                    extension === "gif"
                ) {
                    backgroundMode.value =
                        "gif";
                }
                else if (
                    [
                        "jpg",
                        "jpeg",
                        "png",
                        "webp"
                    ].includes(extension)
                ) {
                    backgroundMode.value =
                        "image";
                }

            }
        );

    }


    /* =====================================================
       PASSWORD SHOW / HIDE
       ===================================================== */

    document
        .querySelectorAll(
            ".password-wrapper"
        )
        .forEach(wrapper => {

            const input =
                wrapper.querySelector(
                    'input[type="password"], input[data-password]'
                );

            const button =
                wrapper.querySelector(
                    ".password-toggle"
                );

            if (
                !input ||
                !button
            ) return;

            button.addEventListener(
                "click",
                () => {

                    const isPassword =
                        input.type === "password";

                    input.type =
                        isPassword
                            ? "text"
                            : "password";

                    const icon =
                        button.querySelector(
                            "i"
                        );

                    if (icon) {

                        icon.classList.toggle(
                            "fa-eye"
                        );

                        icon.classList.toggle(
                            "fa-eye-slash"
                        );

                    }

                }
            );

        });


    /* =====================================================
       QUANTITY CONTROLS
       ===================================================== */

    document
        .querySelectorAll(
            ".quantity-control"
        )
        .forEach(control => {

            const input =
                control.querySelector(
                    "input"
                );

            if (!input) return;

            const minus =
                control.querySelector(
                    ".quantity-minus"
                );

            const plus =
                control.querySelector(
                    ".quantity-plus"
                );

            if (minus) {

                minus.addEventListener(
                    "click",
                    () => {

                        let value =
                            parseInt(
                                input.value,
                                10
                            ) || 1;

                        value =
                            Math.max(
                                1,
                                value - 1
                            );

                        input.value =
                            value;

                        input.dispatchEvent(
                            new Event(
                                "change",
                                {
                                    bubbles: true
                                }
                            )
                        );

                    }
                );

            }

            if (plus) {

                plus.addEventListener(
                    "click",
                    () => {

                        let value =
                            parseInt(
                                input.value,
                                10
                            ) || 1;

                        value =
                            Math.min(
                                99,
                                value + 1
                            );

                        input.value =
                            value;

                        input.dispatchEvent(
                            new Event(
                                "change",
                                {
                                    bubbles: true
                                }
                            )
                        );

                    }
                );

            }

        });


    /* =====================================================
       NUMBER INPUT PROTECTION
       ===================================================== */

    document
        .querySelectorAll(
            'input[type="number"]'
        )
        .forEach(input => {

            input.addEventListener(
                "input",
                () => {

                    const min =
                        input.min !== ""
                            ? Number(input.min)
                            : null;

                    const max =
                        input.max !== ""
                            ? Number(input.max)
                            : null;

                    let value =
                        input.value;

                    if (
                        value !== "" &&
                        isNaN(Number(value))
                    ) {
                        input.value = "";
                        return;
                    }

                    if (
                        min !== null &&
                        Number(value) < min
                    ) {
                        input.value = min;
                    }

                    if (
                        max !== null &&
                        Number(value) > max
                    ) {
                        input.value = max;
                    }

                }
            );

        });


    /* =====================================================
       BUTTON LOADING STATE
       ===================================================== */

    document
        .querySelectorAll(
            "form"
        )
        .forEach(form => {

            form.addEventListener(
                "submit",
                event => {

                    if (
                        event.defaultPrevented
                    ) {
                        return;
                    }

                    const submitButton =
                        form.querySelector(
                            'button[type="submit"]'
                        );

                    if (!submitButton) {
                        return;
                    }

                    /* جلوگیری از چند کلیک */

                    if (
                        submitButton.dataset.loading ===
                        "true"
                    ) {
                        event.preventDefault();
                        return;
                    }

                    submitButton.dataset.loading =
                        "true";

                    submitButton.classList.add(
                        "is-loading"
                    );

                    submitButton.dataset.originalText =
                        submitButton.innerHTML;

                    submitButton.innerHTML =
                        `
                        <i class="fa-solid fa-spinner fa-spin"></i>
                        <span>در حال پردازش...</span>
                        `;

                }
            );

        });


    /* =====================================================
       SEARCH FORM
       ===================================================== */

    const searchForms =
        document.querySelectorAll(
            "form.search-form"
        );

    searchForms.forEach(
        form => {

            const input =
                form.querySelector(
                    'input[name="q"]'
                );

            if (!input) return;

            form.addEventListener(
                "submit",
                event => {

                    const value =
                        input.value.trim();

                    if (!value) {

                        event.preventDefault();

                        input.focus();

                        input.classList.add(
                            "input-error"
                        );

                        setTimeout(
                            () => {
                                input.classList.remove(
                                    "input-error"
                                );
                            },
                            1000
                        );

                    }

                }
            );

        }
    );


    /* =====================================================
       COPY TO CLIPBOARD
       ===================================================== */

    document
        .querySelectorAll(
            "[data-copy]"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                async () => {

                    const value =
                        button.dataset.copy;

                    if (!value) return;

                    try {

                        await navigator.clipboard.writeText(
                            value
                        );

                        const oldText =
                            button.innerHTML;

                        button.innerHTML =
                            `
                            <i class="fa-solid fa-check"></i>
                            کپی شد
                            `;

                        setTimeout(
                            () => {
                                button.innerHTML =
                                    oldText;
                            },
                            1500
                        );

                    } catch (error) {

                        console.warn(
                            "Clipboard failed",
                            error
                        );

                    }

                }
            );

        });


    /* =====================================================
       IMAGE LAZY LOADING
       ===================================================== */

    document
        .querySelectorAll("img")
        .forEach(image => {

            if (
                !image.hasAttribute(
                    "loading"
                )
            ) {
                image.setAttribute(
                    "loading",
                    "lazy"
                );
            }

        });


    /* =====================================================
       PRODUCT CARD TILT EFFECT
       ===================================================== */

    const productCards =
        document.querySelectorAll(
            ".product-card"
        );

    if (
        window.innerWidth > 900 &&
        !window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        ).matches
    ) {

        productCards.forEach(card => {

            card.addEventListener(
                "mousemove",
                event => {

                    const rect =
                        card.getBoundingClientRect();

                    const x =
                        event.clientX -
                        rect.left;

                    const y =
                        event.clientY -
                        rect.top;

                    const centerX =
                        rect.width / 2;

                    const centerY =
                        rect.height / 2;

                    const rotateX =
                        ((y - centerY) /
                            centerY) *
                        -2.5;

                    const rotateY =
                        ((x - centerX) /
                            centerX) *
                        2.5;

                    card.style.transform =
                        `
                        perspective(900px)
                        rotateX(${rotateX}deg)
                        rotateY(${rotateY}deg)
                        translateY(-7px)
                        `;

                }
            );

            card.addEventListener(
                "mouseleave",
                () => {

                    card.style.transform =
                        "";

                }
            );

        });

    }


    /* =====================================================
       RIPPLE EFFECT
       ===================================================== */

    document
        .querySelectorAll(
            ".btn"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                event => {

                    if (
                        button.disabled
                    ) {
                        return;
                    }

                    const rect =
                        button.getBoundingClientRect();

                    const ripple =
                        document.createElement(
                            "span"
                        );

                    ripple.className =
                        "btn-ripple";

                    const size =
                        Math.max(
                            rect.width,
                            rect.height
                        );

                    ripple.style.width =
                        `${size}px`;

                    ripple.style.height =
                        `${size}px`;

                    ripple.style.left =
                        `${event.clientX - rect.left - size / 2}px`;

                    ripple.style.top =
                        `${event.clientY - rect.top - size / 2}px`;

                    button.appendChild(
                        ripple
                    );

                    setTimeout(
                        () => {
                            ripple.remove();
                        },
                        600
                    );

                }
            );

        });


    /* =====================================================
       TOOLTIP
       ===================================================== */

    document
        .querySelectorAll(
            "[data-tooltip]"
        )
        .forEach(element => {

            element.addEventListener(
                "mouseenter",
                () => {

                    const text =
                        element.dataset.tooltip;

                    if (!text) return;

                    let tooltip =
                        document.querySelector(
                            ".kharidino-tooltip"
                        );

                    if (tooltip) {
                        tooltip.remove();
                    }

                    tooltip =
                        document.createElement(
                            "div"
                        );

                    tooltip.className =
                        "kharidino-tooltip";

                    tooltip.textContent =
                        text;

                    document.body.appendChild(
                        tooltip
                    );

                    const rect =
                        element.getBoundingClientRect();

                    tooltip.style.top =
                        `${rect.bottom + 8}px`;

                    tooltip.style.left =
                        `${rect.left + rect.width / 2}px`;

                    requestAnimationFrame(
                        () => {
                            tooltip.classList.add(
                                "show"
                            );
                        }
                    );

                }
            );

            element.addEventListener(
                "mouseleave",
                () => {

                    const tooltip =
                        document.querySelector(
                            ".kharidino-tooltip"
                        );

                    if (tooltip) {
                        tooltip.remove();
                    }

                }
            );

        });


    /* =====================================================
       BACK TO TOP
       ===================================================== */

    let backToTop =
        document.querySelector(
            "#backToTop"
        );

    if (!backToTop) {

        backToTop =
            document.createElement(
                "button"
            );

        backToTop.id =
            "backToTop";

        backToTop.className =
            "back-to-top";

        backToTop.innerHTML =
            '<i class="fa-solid fa-arrow-up"></i>';

        backToTop.setAttribute(
            "aria-label",
            "بازگشت به بالا"
        );

        document.body.appendChild(
            backToTop
        );

    }

    function updateBackToTop() {

        if (
            window.scrollY > 500
        ) {

            backToTop.classList.add(
                "show"
            );

        } else {

            backToTop.classList.remove(
                "show"
            );

        }

    }

    window.addEventListener(
        "scroll",
        updateBackToTop,
        { passive: true }
    );

    backToTop.addEventListener(
        "click",
        () => {

            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });

        }
    );


    /* =====================================================
       CURRENT YEAR
       ===================================================== */

    document
        .querySelectorAll(
            "[data-current-year]"
        )
        .forEach(element => {

            element.textContent =
                new Date().getFullYear();

        });


    /* =====================================================
       ESCAPE HTML
       ===================================================== */

    function escapeHtml(value) {

        const div =
            document.createElement(
                "div"
            );

        div.textContent =
            value;

        return div.innerHTML;
    }


    /* =====================================================
       INITIALIZE
       ===================================================== */

    handleScroll();
    updateBackToTop();

    html.classList.add(
        "js-loaded"
    );

    body.classList.add(
        "kharidino-ready"
    );

    console.log(
        "Kharidino main.js loaded successfully 🚀"
    );

});