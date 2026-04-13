/**
 * Sonora Landing Page — app.js
 * Smooth animations, particle effects, scroll interactions
 */
(function() {
  'use strict';

  // ==========================================
  // HERO PARTICLES
  // ==========================================
  function createParticles() {
    const container = document.getElementById('heroParticles');
    if (!container) return;
    
    const style = document.createElement('style');
    style.textContent = `
      .hero__particles {
        position: absolute;
        inset: 0;
        overflow: hidden;
        pointer-events: none;
        z-index: 1;
      }
      .particle {
        position: absolute;
        border-radius: 50%;
        opacity: 0;
        animation: particleFloat var(--dur) var(--delay) ease-in-out infinite;
      }
      @keyframes particleFloat {
        0% { opacity: 0; transform: translateY(0) scale(0.5); }
        20% { opacity: var(--op); }
        80% { opacity: var(--op); }
        100% { opacity: 0; transform: translateY(-200px) scale(1); }
      }
    `;
    document.head.appendChild(style);

    for (let i = 0; i < 30; i++) {
      const dot = document.createElement('div');
      dot.className = 'particle';
      const size = Math.random() * 4 + 2;
      const hue = Math.random() > 0.5 ? '180' : '270'; // teal or purple
      dot.style.cssText = `
        width: ${size}px;
        height: ${size}px;
        left: ${Math.random() * 100}%;
        top: ${Math.random() * 100}%;
        background: hsl(${hue}, 80%, 60%);
        box-shadow: 0 0 ${size * 3}px hsl(${hue}, 80%, 60%);
        --dur: ${8 + Math.random() * 12}s;
        --delay: ${Math.random() * -15}s;
        --op: ${0.2 + Math.random() * 0.4};
      `;
      container.appendChild(dot);
    }
  }

  // ==========================================
  // SMOOTH NAV SCROLL
  // ==========================================
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const id = link.getAttribute('href');
      if (id === '#') return;
      const target = document.querySelector(id);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Close mobile menu
        document.querySelector('.nav__links')?.classList.remove('active');
      }
    });
  });

  // ==========================================
  // NAV BACKGROUND ON SCROLL
  // ==========================================
  const nav = document.querySelector('.nav');
  if (nav) {
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          nav.style.borderBottomColor = window.scrollY > 50 
            ? 'rgba(0,131,143,0.15)' 
            : 'var(--color-border)';
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  // ==========================================
  // COUNTER ANIMATION (Intersection Observer)
  // ==========================================
  function animateCounters() {
    const counters = document.querySelectorAll('[data-count]');
    if (!counters.length) return;
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const target = parseInt(el.dataset.count);
          const suffix = el.textContent.replace(/[\d]/g, '');
          let current = 0;
          const increment = target / 40;
          const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
              current = target;
              clearInterval(timer);
            }
            el.textContent = Math.round(current) + suffix;
          }, 30);
          observer.unobserve(el);
        }
      });
    }, { threshold: 0.5 });
    
    counters.forEach(c => observer.observe(c));
  }

  // ==========================================
  // INIT
  // ==========================================
  document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    animateCounters();
  });
})();
