/**
 * Material Design Ripple Effect
 * Pure JavaScript implementation for offline use
 */

class RippleEffect {
  constructor() {
    this.init();
  }

  init() {
    // Add ripple effect to all buttons with .md-btn class
    document.addEventListener('click', (event) => {
      const button = event.target.closest('.md-btn, .btn-primary, .btn-secondary, .btn-success, .btn-danger');
      if (button && !button.disabled) {
        this.createRipple(event, button);
      }
    });
  }

  createRipple(event, button) {
    // Remove existing ripple
    const existingRipple = button.querySelector('.ripple');
    if (existingRipple) {
      existingRipple.remove();
    }

    // Create ripple element
    const ripple = document.createElement('span');
    ripple.classList.add('ripple');

    // Calculate position and size
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;

    // Set ripple styles
    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;

    // Add ripple to button
    button.appendChild(ripple);

    // Remove ripple after animation
    setTimeout(() => {
      ripple.remove();
    }, 600);
  }
}

// Initialize ripple effect when DOM is ready
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    new RippleEffect();
  });
}

export default RippleEffect;
