(function () {
    "use strict";

    const THEME_KEY = "studentDashboardTheme";

    function applyTheme() {
        const savedTheme = localStorage.getItem(THEME_KEY);
        const isDark = savedTheme === "dark";

        // Support both class names used by the existing pages.
        document.body.classList.toggle("dark", isDark);
        document.body.classList.toggle("dark-mode", isDark);

        const themeLabel = document.getElementById("theme-label");
        const themeIcon = document.getElementById("theme-icon");

        if (themeLabel) {
            themeLabel.textContent = isDark
                ? "Switch to Light Mode"
                : "Switch to Dark Mode";
        }

        if (themeIcon) {
            themeIcon.textContent = isDark ? "☀️" : "🌙";
        }
    }

    function initializeTheme() {
        applyTheme();

        // Keep any existing theme button label and icon synchronized.
        const themeToggle = document.getElementById("theme-toggle");

        if (themeToggle && !themeToggle.dataset.sharedThemeReady) {
            themeToggle.dataset.sharedThemeReady = "true";

            themeToggle.addEventListener("click", function () {
                const currentlyDark =
                    document.body.classList.contains("dark") ||
                    document.body.classList.contains("dark-mode");

                const newTheme = currentlyDark ? "light" : "dark";
                localStorage.setItem(THEME_KEY, newTheme);

                document.body.classList.toggle("dark", newTheme === "dark");
                document.body.classList.toggle("dark-mode", newTheme === "dark");

                const themeLabel = document.getElementById("theme-label");
                const themeIcon = document.getElementById("theme-icon");

                if (themeLabel) {
                    themeLabel.textContent = newTheme === "dark"
                        ? "Switch to Light Mode"
                        : "Switch to Dark Mode";
                }

                if (themeIcon) {
                    themeIcon.textContent = newTheme === "dark" ? "☀️" : "🌙";
                }
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeTheme);
    } else {
        initializeTheme();
    }
})();