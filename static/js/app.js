/**
 * SmartVest Main App Logic
 * Handles global UI interactions, animations, and common components.
 */

document.addEventListener('DOMContentLoaded', () => {
    initScrollEffects();
    initMobileMenu();
    initFormInteractions();
});

/**
 * Header scroll background effect
 */
function initScrollEffects() {
    const nav = document.querySelector('nav.glass-nav');
    if (nav) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                nav.style.background = 'rgba(0, 0, 0, 0.8)';
            } else {
                nav.style.background = 'rgba(0, 0, 0, 0.5)';
            }
        });
    }
}

/**
 * Mobile nav controls are handled in the base templates.
 * Keeping this as a no-op avoids double-binding the sidebar toggle.
 */
function initMobileMenu() {
    return;
}

/**
 * Glossy form field animations
 */
function initFormInteractions() {
    const inputs = document.querySelectorAll('.glass-input input');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            input.parentElement.classList.add('focused');
        });
        input.addEventListener('blur', () => {
            if (!input.value) {
                input.parentElement.classList.remove('focused');
            }
        });
    });
}

/**
 * Utility: Format numeric amounts without currency symbols.
 */
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(amount) || 0);
}

/**
 * Logout functionality
 * Clears local state and synchronized session.
 */
async function logout() {
    try {
        // Clear all local identifiers
        localStorage.clear();
        sessionStorage.clear();
        
        // Terminate server-side session
        await API.logout();
        
        // Redirect to system gateway
        window.location.href = "/login";
    } catch (err) {
        console.error("Logout Protocol Failure:", err);
        // Fallback redirect
        window.location.href = "/";
    }
}
