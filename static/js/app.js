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
    initAnchorScrolling();
});

/**
 * Change the nav background on scroll so the fixed header stays readable.
 */
function initScrollEffects() {
    const nav = document.querySelector('.nav-container, nav.glass-nav');
    if (nav) {
        const updateNavBackground = () => {
            nav.dataset.scrolled = window.scrollY > 50 ? 'true' : 'false';
        };

        updateNavBackground();

        window.addEventListener('scroll', updateNavBackground, { passive: true });
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

function initAnchorScrolling() {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    document.addEventListener('click', (event) => {
        const anchor = event.target.closest('a[href^="#"]');
        if (!anchor) {
            return;
        }

        const href = anchor.getAttribute('href');
        if (!href || href === '#') {
            return;
        }

        const target = document.querySelector(href);
        if (!target) {
            return;
        }

        event.preventDefault();
        target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });

        if (typeof target.focus === 'function') {
            target.setAttribute('tabindex', '-1');
            target.focus({ preventScroll: true });
            window.setTimeout(() => target.removeAttribute('tabindex'), 0);
        }
    }, { passive: false });
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
