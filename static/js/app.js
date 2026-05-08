/**
 * SmartVest main app logic.
 *
 * Big picture:
 * - shared page interactions
 * - global logout behavior
 * - small visual polish used across the app shell
 */

document.addEventListener('DOMContentLoaded', () => {
    initScrollEffects();
    initFormInteractions();
});

/**
 * Change the nav background on scroll so the fixed header stays readable.
 */
function initScrollEffects() {
    const nav = document.querySelector('.nav-container, nav.glass-nav');
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
 * Add a focused class to wrapped inputs so CSS can style the active field.
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
 * Log the user out locally and on the server.
 *
 * Why this exists:
 * The browser cache, local storage, and Flask session all need to be cleared
 * so the next user does not inherit stale private state.
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
        // Fallback redirect
        window.location.href = "/";
    }
}
