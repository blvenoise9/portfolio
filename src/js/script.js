// DATAPRO ANALYTICS PORTFOLIO - MAIN SCRIPT
// Professional Navigation & Smooth Interactions

// DOM Elements
const hamburger = document.querySelector('.hamburger');
const navMenu = document.querySelector('.nav-menu');
const navLinks = document.querySelectorAll('.nav-link');
const contactForm = document.getElementById('contact-form');
const navbar = document.getElementById('navbar');

// Initialize Systems
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    initializeScrollEffects();
    initializeAnimations();
    initializeContactForm();
    initializeStarField();
    initializeModals();
    console.log('DataPro Analytics Portfolio - System Online');
});

// === NAVIGATION SYSTEM ===
function initializeNavigation() {
    // Mobile Navigation Toggle
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
            
            // Mobile hamburger animation
            const bars = hamburger.querySelectorAll('.bar');
            bars.forEach((bar, index) => {
                if (hamburger.classList.contains('active')) {
                    if (index === 0) {
                        bar.style.transform = 'rotate(45deg) translate(5px, 5px)';
                    } else if (index === 1) {
                        bar.style.opacity = '0';
                    } else {
                        bar.style.transform = 'rotate(-45deg) translate(7px, -6px)';
                    }
                } else {
                    bar.style.transform = 'none';
                    bar.style.opacity = '1';
                }
            });
        });
    }

    // Smooth scrolling for navigation links
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            
            if (targetSection) {
                // Close mobile menu if open
                navMenu.classList.remove('active');
                hamburger.classList.remove('active');
                
                // Reset hamburger animation
                const bars = hamburger.querySelectorAll('.bar');
                bars.forEach(bar => {
                    bar.style.transform = 'none';
                    bar.style.opacity = '1';
                });
                
                // Smooth scroll
                targetSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                // Update active navigation state
                navLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');
            }
        });
    });

    // Navbar scroll effect
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        
        // Update active navigation based on scroll position
        updateActiveNavigation();
    });

    // Close mobile menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!hamburger.contains(e.target) && !navMenu.contains(e.target)) {
            hamburger.classList.remove('active');
            navMenu.classList.remove('active');
            
            const bars = hamburger.querySelectorAll('.bar');
            bars.forEach(bar => {
                bar.style.transform = 'none';
                bar.style.opacity = '1';
            });
        }
    });

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hamburger.classList.remove('active');
            navMenu.classList.remove('active');
        }
    });
}

// Update active navigation highlight
function updateActiveNavigation() {
    const sections = document.querySelectorAll('section');
    const scrollPos = window.scrollY + 150;

    sections.forEach(section => {
        const top = section.offsetTop;
        const bottom = top + section.offsetHeight;
        const id = section.getAttribute('id');
        const correspondingLink = document.querySelector(`.nav-link[href="#${id}"]`);

        if (scrollPos >= top && scrollPos <= bottom) {
            navLinks.forEach(link => link.classList.remove('active'));
            if (correspondingLink) {
                correspondingLink.classList.add('active');
            }
        }
    });
}

// === SCROLL EFFECTS ===
function initializeScrollEffects() {
    // Scroll-in animations removed per design update
}

// === ANIMATIONS ===
function initializeAnimations() {
    // Add visibility class for scroll animations
    const style = document.createElement('style');
    style.textContent = `
        .visible {
            opacity: 1 !important;
            transform: translateY(0) !important;
        }
    `;
    document.head.appendChild(style);

    // Typewriter effect for hero title
    const heroTitle = document.querySelector('.hero-title');
    if (heroTitle) {
        const text = heroTitle.textContent;
        heroTitle.textContent = '';
        heroTitle.style.opacity = '1';
        
        let i = 0;
        const typeWriter = () => {
            if (i < text.length) {
                heroTitle.textContent += text.charAt(i);
                i++;
                setTimeout(typeWriter, 50);
            }
        };
        
        setTimeout(typeWriter, 1000);
    }

    // Hover effects for project cards
    const projectCards = document.querySelectorAll('.project-card');
    projectCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            const placeholder = card.querySelector('.project-placeholder');
            if (placeholder) {
                placeholder.style.transform = 'scale(1.1)';
                placeholder.style.transition = 'transform 0.3s ease';
            }
        });
        
        card.addEventListener('mouseleave', () => {
            const placeholder = card.querySelector('.project-placeholder');
            if (placeholder) {
                placeholder.style.transform = 'scale(1)';
            }
        });
    });
}

// Animate stats counter
function animateStats(statElement) {
    const number = statElement.querySelector('h3');
    if (number) {
        const finalNumber = parseInt(number.textContent);
        const increment = finalNumber / 50;
        let current = 0;
        
        const counter = setInterval(() => {
            current += increment;
            if (current >= finalNumber) {
                number.textContent = finalNumber + (finalNumber === 100 ? '%' : '+');
                clearInterval(counter);
            } else {
                number.textContent = Math.floor(current) + (finalNumber === 100 ? '%' : '+');
            }
        }, 30);
    }
}

// Animate skill items with delay
function animateSkillItems(skillCategory) {
    const skillItems = skillCategory.querySelectorAll('.skill-item');
    skillItems.forEach((item, index) => {
        setTimeout(() => {
            item.style.opacity = '1';
            item.style.transform = 'scale(1)';
        }, index * 100);
    });
}

// === CONTACT FORM ===
function initializeContactForm() {
    if (!contactForm) return;

    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(contactForm);
        const submitBtn = contactForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        // Loading state
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
        submitBtn.disabled = true;
        
        try {
            // Simulate form submission
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Success feedback
            showNotification('Message sent successfully! I\'ll get back to you soon.', 'success');
            contactForm.reset();
            
        } catch (error) {
            showNotification('Failed to send message. Please try again.', 'error');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
}

// === NOTIFICATION SYSTEM ===
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => notification.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
        <i class="fas fa-times close-notification" style="margin-left: 1rem; cursor: pointer;"></i>
    `;
    
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Auto hide
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
    
    // Manual close
    notification.querySelector('.close-notification').addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    });
}

// === STAR FIELD ===
function initializeStarField() {
    // Create additional twinkling stars
    const starCount = 50;
    
    for (let i = 0; i < starCount; i++) {
        const star = document.createElement('div');
        star.style.cssText = `
            position: fixed;
            background: white;
            border-radius: 50%;
            pointer-events: none;
            z-index: -3;
            animation: twinkle ${2 + Math.random() * 3}s ease-in-out infinite alternate;
        `;
        
        const size = Math.random() * 1.5 + 0.5;
        star.style.width = size + 'px';
        star.style.height = size + 'px';
        star.style.left = Math.random() * 100 + '%';
        star.style.top = Math.random() * 100 + '%';
        star.style.animationDelay = Math.random() * 2 + 's';
        
        document.body.appendChild(star);
    }
    
    // Add twinkle animation
    const starStyle = document.createElement('style');
    starStyle.textContent = `
        @keyframes twinkle {
            from { opacity: 0.3; }
            to { opacity: 0.8; }
        }
    `;
    document.head.appendChild(starStyle);
}

// === SMOOTH LOADING ===
window.addEventListener('load', () => {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.5s ease';

    setTimeout(() => {
        document.body.style.opacity = '1';

        // Open desktop modal after fade-in when returning from a project page
        if (new URLSearchParams(window.location.search).get('openDesktop') === 'true') {
            const projectsModal = document.getElementById('projects-modal');
            if (projectsModal) {
                projectsModal.classList.add('open');
                document.body.style.overflow = 'hidden';
            }
            history.replaceState(null, '', window.location.pathname);
        }
    }, 100);
});

// === MODALS ===
function initializeModals() {
    const aboutModal    = document.getElementById('about-modal');
    const projectsModal = document.getElementById('projects-modal');
    const iphoneModal   = document.getElementById('iphone-modal');
    const notebookBtn   = document.getElementById('notebook-btn');
    const laptopBtn     = document.getElementById('laptop-btn');
    const iphoneBtn     = document.getElementById('iphone-btn');
    const aboutClose    = document.getElementById('about-close');
    const projectsClose = document.getElementById('projects-close');
    const iphoneClose   = document.getElementById('iphone-close');

    function openModal(modal) {
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeModal(modal) {
        modal.classList.remove('open');
        document.body.style.overflow = '';
    }

    if (notebookBtn && aboutModal) {
        notebookBtn.addEventListener('click', () => openModal(aboutModal));
    }
    if (laptopBtn && projectsModal) {
        laptopBtn.addEventListener('click', () => openModal(projectsModal));
    }
    if (iphoneBtn && iphoneModal) {
        iphoneBtn.addEventListener('click', () => openModal(iphoneModal));
    }
    if (aboutClose) {
        aboutClose.addEventListener('click', () => closeModal(aboutModal));
    }
    if (projectsClose) {
        projectsClose.addEventListener('click', () => closeModal(projectsModal));
    }
    if (iphoneClose) {
        iphoneClose.addEventListener('click', () => closeModal(iphoneModal));
    }

    // Close about modal on backdrop click
    if (aboutModal) {
        aboutModal.addEventListener('click', (e) => {
            if (e.target === aboutModal) closeModal(aboutModal);
        });
    }

    // Close projects modal on backdrop click
    if (projectsModal) {
        projectsModal.addEventListener('click', (e) => {
            if (e.target === projectsModal) closeModal(projectsModal);
        });
    }

    // Close iPhone modal on backdrop click
    if (iphoneModal) {
        iphoneModal.addEventListener('click', (e) => {
            if (e.target === iphoneModal) closeModal(iphoneModal);
        });
    }

    // Close on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal(aboutModal);
            closeModal(projectsModal);
            closeModal(iphoneModal);
        }
    });

}

console.log('DataPro Analytics Portfolio - All Systems Operational'); 