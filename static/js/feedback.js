/* global API */

(function () {
    // This script keeps feedback/review rendering readable by using classes
    // instead of inline-styled HTML strings.
    const MAX_RATING = 5;
    const stars = Array.from(document.querySelectorAll('.star'));
    const ratingInput = document.getElementById('reviewRating');

    function clampRating(value) {
        const numeric = Number(value || MAX_RATING);
        return Math.max(0, Math.min(MAX_RATING, numeric));
    }

    function renderStars(rating) {
        const clamped = clampRating(rating);
        return '★'.repeat(clamped) + '☆'.repeat(MAX_RATING - clamped);
    }

    function createReviewCard(author, comment, rating, isLocal = false) {
        const card = document.createElement('article');
        card.className = isLocal ? 'feedback-review-card feedback-review-card--local' : 'feedback-review-card';

        const header = document.createElement('div');
        header.className = 'feedback-review-header';

        const title = document.createElement('h4');
        title.className = 'feedback-review-author';
        title.textContent = author;

        const starsRow = document.createElement('div');
        starsRow.className = 'feedback-review-rating';
        starsRow.textContent = renderStars(rating);

        const body = document.createElement('p');
        body.className = 'feedback-review-text';
        body.textContent = comment;

        header.append(title, starsRow);
        card.append(header, body);
        return card;
    }

    function setStatus(statusNode, message, tone) {
        if (!statusNode) return;
        statusNode.className = `feedback-status feedback-status--${tone}`;
        statusNode.textContent = message;
    }

    function updateRatingStars(selectedRating) {
        // Keep the rating widget in sync with the hidden form field.
        const rating = clampRating(selectedRating);
        stars.forEach((star) => {
            const starValue = clampRating(star.dataset.value);
            const active = starValue <= rating;
            star.textContent = active ? '★' : '☆';
            star.classList.toggle('is-active', active);
            star.setAttribute('aria-checked', String(active));
        });
    }

    function renderReviews(reviews) {
        const container = document.getElementById('userReviewsList');
        if (!container) return;

        container.replaceChildren();

        if (!Array.isArray(reviews) || reviews.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'feedback-review-empty';
            empty.textContent = 'No reviews have been posted yet.';
            container.append(empty);
            return;
        }

        reviews.slice(0, 4).forEach((entry) => {
            container.append(createReviewCard(
                entry.username || 'SmartVest User',
                entry.comment || 'No review text available.',
                entry.rating
            ));
        });
    }

    function appendLocalReview(comment, rating) {
        const container = document.getElementById('userReviewsList');
        if (!container || !comment) return;

        const localCard = createReviewCard('You', comment, rating, true);
        container.prepend(localCard);

        while (container.children.length > 4) {
            container.removeChild(container.lastElementChild);
        }
    }

    async function loadReviews() {
        try {
            const reviews = await API.getReviews();
            renderReviews(reviews);
        } catch (error) {
            // Review loading is best-effort; the page stays usable if the API is temporarily unavailable.
        }
    }

    stars.forEach((star) => {
        star.addEventListener('click', () => {
            const value = clampRating(star.dataset.value);
            if (ratingInput) {
                ratingInput.value = String(value);
            }
            updateRatingStars(value);
        });
    });

    document.getElementById('systemFeedbackForm')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const status = document.getElementById('feedbackStatus');

        try {
            const data = await API.submitFeedback({
                subject: event.target.subject.value,
                message: event.target.message.value,
            });
            if (!data) return;
            setStatus(status, 'Feedback received! Thank you.', 'success');
            event.target.reset();
        } catch (error) {
            setStatus(status, 'Error submitting feedback', 'error');
        }
    });

    document.getElementById('publicReviewForm')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const status = document.getElementById('reviewStatus');
        const reviewText = (event.target.review.value || '').trim();
        const rating = clampRating(ratingInput?.value || MAX_RATING);

        try {
            const data = await API.submitReview({
                rating: ratingInput ? ratingInput.value : String(rating),
                review: event.target.review.value,
            });
            if (!data) return;

            setStatus(status, 'Review posted successfully!', 'success');
            event.target.reset();
            if (ratingInput) {
                ratingInput.value = String(MAX_RATING);
            }
            updateRatingStars(MAX_RATING);

            // Show the review immediately, then refresh from the API so the page catches moderation/state updates.
            appendLocalReview(reviewText, rating);
            loadReviews();
        } catch (error) {
            setStatus(status, 'Error posting review', 'error');
        }
    });

    document.addEventListener('DOMContentLoaded', () => {
        updateRatingStars(ratingInput ? ratingInput.value : MAX_RATING);
        loadReviews();
    });
})();
