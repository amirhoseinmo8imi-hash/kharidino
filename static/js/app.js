/* =========================================================
   KHARIDINO
   Background Controller
   Video / GIF / Image / Animated Background
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    const background = document.getElementById("siteBackground");
    const video = document.getElementById("backgroundVideo");

    if (!background) {
        return;
    }


    /* =====================================================
       SETTINGS
    ====================================================== */

    const mode = background.dataset.mode || "css";

    let speed = parseFloat(
        background.dataset.speed || "18"
    );

    if (isNaN(speed) || speed <= 0) {
        speed = 18;
    }


    /* =====================================================
       CSS VARIABLE
    ====================================================== */

    document.documentElement.style.setProperty(
        "--bg-speed",
        `${speed}s`
    );


    /* =====================================================
       VIDEO BACKGROUND
    ====================================================== */

    if (video && mode === "video") {

        /*
         * بدون صدا
         */

        video.muted = true;
        video.volume = 0;


        /*
         * Loop
         */

        video.loop = true;


        /*
         * اجرای خودکار
         */

        video.autoplay = true;


        /*
         * سرعت ویدیو
         */

        video.playbackRate = 1;


        /*
         * تلاش برای Play
         */

        const playVideo = () => {

            const promise = video.play();

            if (promise !== undefined) {

                promise
                    .then(() => {
                        console.log(
                            "Kharidino background video started."
                        );
                    })
                    .catch(() => {

                        /*
                         * بعضی مرورگرها Play خودکار
                         * را محدود می‌کنند.
                         */

                        console.log(
                            "Background video autoplay was blocked."
                        );

                    });

            }

        };


        /*
         * وقتی ویدیو آماده شد
         */

        video.addEventListener(
            "loadeddata",
            playVideo
        );


        video.addEventListener(
            "canplay",
            playVideo
        );


        /*
         * اگر ویدیو Pause شد دوباره اجرا شود
         */

        video.addEventListener(
            "pause",
            () => {

                if (
                    !document.hidden &&
                    video.readyState >= 2
                ) {

                    video.play().catch(() => {});

                }

            }
        );


        /*
         * وقتی تب دوباره فعال شد
         */

        document.addEventListener(
            "visibilitychange",
            () => {

                if (
                    !document.hidden &&
                    video.paused
                ) {

                    video.play().catch(() => {});

                }

            }
        );


        /*
         * اجرای اولیه
         */

        playVideo();

    }


    /* =====================================================
       IMAGE / GIF BACKGROUND
    ====================================================== */

    if (
        mode === "image" ||
        mode === "gif"
    ) {

        const image =
            background.querySelector(
                ".site-background-image"
            );

        if (image) {

            image.style.animationDuration =
                `${speed}s`;

        }

    }


    /* =====================================================
       MOUSE PARALLAX
    ====================================================== */

    const media =
        background.querySelector(
            ".site-background-media"
        );

    if (media && window.innerWidth > 768) {

        let mouseX = 0;
        let mouseY = 0;

        let currentX = 0;
        let currentY = 0;


        document.addEventListener(
            "mousemove",
            (event) => {

                mouseX =
                    (event.clientX /
                        window.innerWidth -
                        0.5) * 2;

                mouseY =
                    (event.clientY /
                        window.innerHeight -
                        0.5) * 2;

            },
            {
                passive: true
            }
        );


        const animateParallax = () => {

            currentX +=
                (mouseX * 8 - currentX) * 0.04;

            currentY +=
                (mouseY * 8 - currentY) * 0.04;


            /*
             * روی ویدیو فقط حرکت خیلی نرم
             * اعمال می‌کنیم.
             */

            if (mode === "video") {

                media.style.transform =
                    `scale(1.05)
                     translate3d(
                        ${currentX}px,
                        ${currentY}px,
                        0
                     )`;

            }


            requestAnimationFrame(
                animateParallax
            );

        };


        animateParallax();

    }


    /* =====================================================
       REDUCED MOTION
    ====================================================== */

    const reducedMotion =
        window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        );


    const handleReducedMotion = () => {

        if (reducedMotion.matches) {

            /*
             * انیمیشن‌ها را برای کاربرانی
             * که Reduced Motion فعال دارند
             * کاهش می‌دهیم.
             */

            document.documentElement.style
                .setProperty(
                    "--bg-speed",
                    "9999s"
                );


            if (video) {

                /*
                 * ویدیو همچنان تصویر پس‌زمینه است
                 * ولی حرکت‌های اضافی حذف می‌شوند.
                 */

                video.style.animation =
                    "none";

            }

        }

    };


    handleReducedMotion();


    reducedMotion.addEventListener(
        "change",
        handleReducedMotion
    );


    /* =====================================================
       MOBILE OPTIMIZATION
    ====================================================== */

    const optimizeForMobile = () => {

        if (window.innerWidth <= 768) {

            /*
             * پارالاکس روی موبایل خاموش
             * تا مصرف CPU کمتر شود.
             */

            if (media) {

                media.style.transform =
                    "scale(1.03)";

            }

        }

    };


    optimizeForMobile();


    window.addEventListener(
        "resize",
        optimizeForMobile,
        {
            passive: true
        }
    );


    /* =====================================================
       BACKGROUND READY
    ====================================================== */

    background.classList.add(
        "background-ready"
    );


    console.log(
        `Kharidino background mode: ${mode}`
    );

});