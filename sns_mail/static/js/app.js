// ============================================
// SNS MAIL - Futuristic UI JavaScript
// Parallax Scrolling & Advanced Effects
// ============================================

// Document Ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme first
    initTheme();
    
    // Initialize splash screen
    initSplashScreen();
    
    // Initialize all components
    initParallax();
    initNavbar();
    initTooltips();
    initPopovers();
    initAutoHideAlerts();
    initConfirmDelete();
    initFileUpload();
    initEmailSearch();
    initEmailMarkRead();
    initBulkActions();
    initPasswordStrength();
    initAnimations();
    initScrollEffects();
    initCounterAnimations();
    
    console.log('🚀 SNS Mail UI Initialized');
});

// ============================================
// THEME SWITCHING (LIGHT/DARK MODE)
// ============================================

function initTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    
    // Check for saved theme preference or default to dark
    const savedTheme = localStorage.getItem('sns_mail_theme') || 'dark';
    applyTheme(savedTheme);
    
    // Theme toggle button click handler
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            // Add animation class
            document.body.style.transition = 'all 0.5s ease';
            
            applyTheme(newTheme);
            localStorage.setItem('sns_mail_theme', newTheme);
            
            // Animate the icon
            if (themeIcon) {
                themeIcon.style.transform = 'rotate(360deg) scale(1.2)';
                setTimeout(() => {
                    themeIcon.style.transform = '';
                }, 300);
            }
        });
    }
}

function applyTheme(theme) {
    const themeIcon = document.getElementById('themeIcon');
    
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        if (themeIcon) {
            themeIcon.className = 'fas fa-sun';
        }
    } else {
        document.documentElement.removeAttribute('data-theme');
        if (themeIcon) {
            themeIcon.className = 'fas fa-moon';
        }
    }
    
    // Update meta theme-color for mobile browsers
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
        metaThemeColor.content = theme === 'light' ? '#f8fafc' : '#050508';
    }
}

// Function to get current theme
function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
}

// Function to toggle theme programmatically
function toggleTheme() {
    const currentTheme = getCurrentTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
    localStorage.setItem('sns_mail_theme', newTheme);
}

// ============================================
// SPLASH SCREEN
// ============================================

function initSplashScreen() {
    const splashScreen = document.getElementById('splashScreen');
    if (!splashScreen) return;
    
    // Check if this is the first visit (using sessionStorage)
    const hasSeenSplash = sessionStorage.getItem('sns_mail_splash_seen');
    
    if (hasSeenSplash) {
        // Skip splash screen for subsequent page loads in the same session
        splashScreen.style.display = 'none';
        return;
    }
    
    // Mark splash as seen
    sessionStorage.setItem('sns_mail_splash_seen', 'true');
    
    // The splash screen will auto-hide via CSS animation after 2.5s
    // But we can also handle it with JavaScript for more control
    setTimeout(function() {
        splashScreen.style.opacity = '0';
        splashScreen.style.visibility = 'hidden';
        splashScreen.style.pointerEvents = 'none';
        
        // Remove from DOM after animation
        setTimeout(function() {
            splashScreen.remove();
        }, 500);
    }, 2500);
}

// ============================================
// PARALLAX SCROLLING EFFECTS
// ============================================

function initParallax() {
    const parallaxElements = document.querySelectorAll('.parallax-layer');
    const heroSections = document.querySelectorAll('.hero-section');
    
    if (parallaxElements.length === 0 && heroSections.length === 0) return;
    
    let ticking = false;
    
    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(function() {
                const scrollY = window.pageYOffset;
                
                // Parallax for layers
                parallaxElements.forEach(function(element) {
                    const speed = element.dataset.speed || 0.5;
                    const yPos = -(scrollY * speed);
                    element.style.transform = 'translate3d(0, ' + yPos + 'px, 0)';
                });
                
                // Hero section parallax
                heroSections.forEach(function(section) {
                    const rect = section.getBoundingClientRect();
                    if (rect.bottom > 0 && rect.top < window.innerHeight) {
                        const yPos = scrollY * 0.3;
                        section.style.backgroundPositionY = yPos + 'px';
                    }
                });
                
                ticking = false;
            });
            ticking = true;
        }
    });
}

// ============================================
// NAVBAR EFFECTS
// ============================================

function initNavbar() {
    const navbar = document.getElementById('mainNavbar');
    if (!navbar) return;
    
    let lastScroll = 0;
    
    window.addEventListener('scroll', function() {
        const currentScroll = window.pageYOffset;
        
        // Add scrolled class for background change
        if (currentScroll > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        
        // Hide/show navbar on scroll (optional - commented out for now)
        // if (currentScroll > lastScroll && currentScroll > 100) {
        //     navbar.style.transform = 'translateY(-100%)';
        // } else {
        //     navbar.style.transform = 'translateY(0)';
        // }
        
        lastScroll = currentScroll;
    });
}

// ============================================
// TOOLTIPS & POPOVERS
// ============================================

function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            animation: true,
            delay: { show: 100, hide: 100 }
        });
    });
    
    // Custom tooltip for verified badges
    document.querySelectorAll('.verified-badge[data-tooltip]').forEach(function(badge) {
        badge.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'custom-tooltip';
            tooltip.textContent = this.dataset.tooltip;
            tooltip.style.cssText = `
                position: absolute;
                background: var(--bg-secondary);
                color: var(--text-primary);
                padding: 0.5rem 1rem;
                border-radius: 8px;
                font-size: 0.85rem;
                z-index: 10000;
                white-space: nowrap;
                border: 1px solid rgba(0, 240, 255, 0.3);
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
            `;
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.top = (rect.bottom + 10) + 'px';
            tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
            
            this._tooltip = tooltip;
        });
        
        badge.addEventListener('mouseleave', function() {
            if (this._tooltip) {
                this._tooltip.remove();
                delete this._tooltip;
            }
        });
    });
}

function initPopovers() {
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl, {
            animation: true
        });
    });
}

// ============================================
// AUTO-HIDE ALERTS
// ============================================

function initAutoHideAlerts() {
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            if (alert.classList.contains('show')) {
                var bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        });
    }, 5000);
}

// ============================================
// CONFIRM DELETE
// ============================================

function initConfirmDelete() {
    document.querySelectorAll('[data-confirm-delete]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            showConfirmModal(
                'Confirm Delete',
                'Are you sure you want to delete this item? This action cannot be undone.',
                'danger',
                function() {
                    if (btn.tagName === 'A') {
                        window.location.href = btn.href;
                    } else if (btn.form) {
                        btn.form.submit();
                    } else {
                        btn.click();
                    }
                }
            );
        });
    });
}

// Custom Confirm Modal
function showConfirmModal(title, message, type, onConfirm) {
    // Create modal
    const modalHtml = `
        <div class="modal fade" id="confirmModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-exclamation-triangle text-${type} me-2"></i>
                            ${title}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-${type}" id="confirmModalBtn">
                            <i class="fas fa-check me-2"></i>Confirm
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('confirmModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Initialize and show modal
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    modal.show();
    
    // Handle confirm button
    document.getElementById('confirmModalBtn').addEventListener('click', function() {
        modal.hide();
        if (onConfirm) onConfirm();
    });
    
    // Clean up on hide
    document.getElementById('confirmModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// ============================================
// FILE UPLOAD
// ============================================

function initFileUpload() {
    // File upload preview
    document.querySelectorAll('.file-upload-input').forEach(function(input) {
        input.addEventListener('change', function(e) {
            var file = e.target.files[0];
            if (file) {
                var preview = this.closest('.file-upload-wrapper').querySelector('.file-preview');
                if (preview) {
                    preview.innerHTML = '<strong>Selected:</strong> ' + file.name;
                }
            }
        });
    });

    // Drag and drop file upload
    document.querySelectorAll('.file-upload-wrapper').forEach(function(wrapper) {
        var input = wrapper.querySelector('input[type="file"]');
        
        wrapper.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('dragover');
            this.style.borderColor = 'var(--accent-primary)';
            this.style.background = 'rgba(0, 240, 255, 0.1)';
        });

        wrapper.addEventListener('dragleave', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
            this.style.borderColor = '';
            this.style.background = '';
        });

        wrapper.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
            this.style.borderColor = '';
            this.style.background = '';
            var files = e.dataTransfer.files;
            if (files.length > 0) {
                input.files = files;
                var preview = this.querySelector('.file-preview');
                if (preview) {
                    preview.innerHTML = '<strong>Selected:</strong> ' + files[0].name;
                }
                // Trigger change event
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    });
}

// ============================================
// EMAIL SEARCH
// ============================================

function initEmailSearch() {
    var searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    let debounceTimer;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function() {
            var searchTerm = searchInput.value.toLowerCase().trim();
            var emailItems = document.querySelectorAll('.email-item');
            let visibleCount = 0;
            
            emailItems.forEach(function(item) {
                var text = item.textContent.toLowerCase();
                var subject = item.querySelector('.email-subject')?.textContent.toLowerCase() || '';
                var sender = item.querySelector('.email-sender')?.textContent.toLowerCase() || '';
                
                if (text.includes(searchTerm) || subject.includes(searchTerm) || sender.includes(searchTerm)) {
                    item.style.display = '';
                    item.classList.add('fade-in');
                    visibleCount++;
                } else {
                    item.style.display = 'none';
                    item.classList.remove('fade-in');
                }
            });
            
            // Update count if exists
            var countEl = document.getElementById('emailCount');
            if (countEl) {
                countEl.textContent = visibleCount;
            }
        }, 300);
    });
}

// ============================================
// EMAIL MARK AS READ
// ============================================

function initEmailMarkRead() {
    document.querySelectorAll('.email-item').forEach(function(item) {
        item.addEventListener('click', function() {
            if (!this.classList.contains('unread')) return;
            
            var emailId = this.dataset.emailId;
            if (emailId) {
                fetch('/api/email/' + emailId + '/mark-read', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                }).then(function(response) {
                    if (response.ok) {
                        item.classList.remove('unread');
                        item.classList.add('fade-in');
                        updateUnreadCount();
                    }
                }).catch(function(error) {
                    console.error('Error marking email as read:', error);
                });
            }
        });
    });
}

// ============================================
// BULK ACTIONS
// ============================================

function initBulkActions() {
    document.querySelectorAll('.bulk-select').forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            var checkboxes = document.querySelectorAll('.email-checkbox');
            checkboxes.forEach(function(cb) {
                cb.checked = this.checked;
                cb.closest('.email-item')?.classList.toggle('selected', this.checked);
            }, this);
            
            updateBulkActionButtons();
        });
    });
    
    // Individual checkbox change
    document.querySelectorAll('.email-checkbox').forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            this.closest('.email-item')?.classList.toggle('selected', this.checked);
            updateBulkActionButtons();
        });
    });
}

function updateBulkActionButtons() {
    var checkedCount = document.querySelectorAll('.email-checkbox:checked').length;
    var bulkButtons = document.querySelectorAll('.bulk-action-btn');
    
    bulkButtons.forEach(function(btn) {
        btn.disabled = checkedCount === 0;
        if (checkedCount > 0) {
            btn.querySelector('.count')?.textContent = '(' + checkedCount + ')';
        }
    });
}

// ============================================
// PASSWORD STRENGTH
// ============================================

function initPasswordStrength() {
    var passwordInput = document.getElementById('password');
    var confirmPasswordInput = document.getElementById('confirm_password');
    var passwordStrength = document.getElementById('password-strength');
    
    if (passwordInput && passwordStrength) {
        passwordInput.addEventListener('input', function() {
            var strength = checkPasswordStrength(this.value);
            updatePasswordStrength(strength);
        });
    }

    if (confirmPasswordInput && passwordInput) {
        confirmPasswordInput.addEventListener('input', function() {
            var match = this.value === passwordInput.value;
            updatePasswordMatch(match);
        });
    }
}

function checkPasswordStrength(password) {
    var strength = 0;
    var feedback = [];
    
    if (password.length >= 8) strength++;
    else feedback.push('At least 8 characters');
    
    if (password.length >= 12) strength++;
    
    if (/[a-z]/.test(password)) strength++;
    else feedback.push('Lowercase letter');
    
    if (/[A-Z]/.test(password)) strength++;
    else feedback.push('Uppercase letter');
    
    if (/\d/.test(password)) strength++;
    else feedback.push('Number');
    
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) strength++;
    else feedback.push('Special character');
    
    return {
        score: strength,
        feedback: feedback,
        level: strength >= 5 ? 'strong' : strength >= 3 ? 'medium' : 'weak'
    };
}

function updatePasswordStrength(strength) {
    var strengthBar = document.getElementById('password-strength-bar');
    var strengthText = document.getElementById('password-strength-text');
    var strengthFeedback = document.getElementById('password-strength-feedback');
    
    if (!strengthBar || !strengthText) return;
    
    // Update bar
    strengthBar.style.width = (strength.score * 16.67) + '%';
    
    // Update colors and text
    if (strength.level === 'strong') {
        strengthBar.className = 'progress-bar bg-success';
        strengthText.textContent = 'Strong Password';
        strengthText.className = 'text-success';
    } else if (strength.level === 'medium') {
        strengthBar.className = 'progress-bar bg-warning';
        strengthText.textContent = 'Medium Strength';
        strengthText.className = 'text-warning';
    } else {
        strengthBar.className = 'progress-bar bg-danger';
        strengthText.textContent = 'Weak Password';
        strengthText.className = 'text-danger';
    }
    
    // Update feedback
    if (strengthFeedback) {
        strengthFeedback.innerHTML = strength.feedback.map(function(item) {
            return '<span class="badge bg-secondary me-1">' + item + '</span>';
        }).join(' ');
    }
}

function updatePasswordMatch(match) {
    var matchIndicator = document.getElementById('password-match');
    if (!matchIndicator) return;
    
    var confirmInput = document.getElementById('confirm_password');
    if (match && confirmInput.value.length > 0) {
        matchIndicator.innerHTML = '<i class="fas fa-check-circle text-success"></i> Passwords match';
    } else if (confirmInput.value.length > 0) {
        matchIndicator.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Passwords do not match';
    } else {
        matchIndicator.innerHTML = '';
    }
}

// ============================================
// ANIMATIONS
// ============================================

function initAnimations() {
    // Intersection Observer for fade-in animations
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe cards and other elements
    document.querySelectorAll('.card, .email-item, .list-group-item').forEach(function(el) {
        observer.observe(el);
    });
}

// ============================================
// SCROLL EFFECTS
// ============================================

function initScrollEffects() {
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Scroll to top button
    const scrollTopBtn = document.getElementById('scrollTopBtn');
    if (scrollTopBtn) {
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                scrollTopBtn.classList.add('visible');
            } else {
                scrollTopBtn.classList.remove('visible');
            }
        });
        
        scrollTopBtn.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

// ============================================
// COUNTER ANIMATIONS
// ============================================

function initCounterAnimations() {
    const counters = document.querySelectorAll('[data-counter]');
    
    const observerOptions = {
        threshold: 0.5
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    counters.forEach(function(counter) {
        observer.observe(counter);
    });
}

function animateCounter(element) {
    const target = parseInt(element.dataset.counter);
    const duration = parseInt(element.dataset.duration) || 2000;
    const start = 0;
    const startTime = performance.now();
    
    function updateCounter(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = Math.floor(start + (target - start) * easeOutQuart);
        
        element.textContent = current.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(updateCounter);
        } else {
            element.textContent = target.toLocaleString();
        }
    }
    
    requestAnimationFrame(updateCounter);
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

// Update unread count
function updateUnreadCount() {
    var unreadCount = document.querySelectorAll('.email-item.unread').length;
    var unreadBadge = document.querySelector('.navbar .badge.bg-primary');
    if (unreadBadge) {
        unreadBadge.textContent = unreadCount;
        unreadBadge.style.display = unreadCount > 0 ? 'inline' : 'none';
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    var k = 1024;
    var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Show loading spinner
function showLoading(button) {
    var originalText = button.innerHTML;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...';
    button.disabled = true;
    button.dataset.originalText = originalText;
}

// Hide loading spinner
function hideLoading(button) {
    if (button.dataset.originalText) {
        button.innerHTML = button.dataset.originalText;
        button.disabled = false;
        delete button.dataset.originalText;
    }
}

// AJAX request wrapper
function apiRequest(url, options = {}) {
    return fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
        },
        ...options
    });
}

// Show toast notification
function showToast(message, type = 'info') {
    var toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
    
    var toastId = 'toast-' + Date.now();
    var iconMap = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    
    var toastHtml = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <i class="fas fa-${iconMap[type] || 'info-circle'} text-${type === 'error' ? 'danger' : type} me-2"></i>
                <strong class="me-auto">SNS Mail</strong>
                <small>Just now</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    var toastElement = document.getElementById(toastId);
    var toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 4000
    });
    
    toast.show();
    
    // Remove toast from DOM after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// QR Code scanner
function startQRScanner() {
    var video = document.getElementById('qr-video');
    var canvas = document.getElementById('qr-canvas');
    
    if (!video || !canvas) return;
    
    var context = canvas.getContext('2d');
    
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(function(stream) {
                video.srcObject = stream;
                video.play();
                
                // Create scanning overlay
                const overlay = document.createElement('div');
                overlay.className = 'qr-scanning-overlay';
                overlay.innerHTML = `
                    <div class="qr-scanning-line"></div>
                `;
                video.parentElement.appendChild(overlay);
                
                setInterval(function() {
                    if (video.readyState === video.HAVE_ENOUGH_DATA) {
                        canvas.height = video.videoHeight;
                        canvas.width = video.videoWidth;
                        context.drawImage(video, 0, 0, canvas.width, canvas.height);
                        var imageData = context.getImageData(0, 0, canvas.width, canvas.height);
                        // QR code scanning logic would go here
                    }
                }, 100);
            })
            .catch(function(err) {
                console.error("Error accessing camera:", err);
                showToast("Unable to access camera", "error");
            });
    } else {
        showToast("Camera access not supported", "error");
    }
}

// Copy to clipboard
function copyToClipboard(text, successMessage = 'Copied to clipboard!') {
    navigator.clipboard.writeText(text).then(function() {
        showToast(successMessage, 'success');
    }).catch(function(err) {
        console.error('Failed to copy:', err);
        showToast('Failed to copy to clipboard', 'error');
    });
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle function
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ============================================
// EXPORT FUNCTIONS FOR GLOBAL USE
// ============================================

window.SNSMail = {
    // Password functions
    checkPasswordStrength: checkPasswordStrength,
    updatePasswordStrength: updatePasswordStrength,
    updatePasswordMatch: updatePasswordMatch,
    
    // Email functions
    updateUnreadCount: updateUnreadCount,
    
    // Utility functions
    formatFileSize: formatFileSize,
    showLoading: showLoading,
    hideLoading: hideLoading,
    apiRequest: apiRequest,
    showToast: showToast,
    copyToClipboard: copyToClipboard,
    
    // QR Scanner
    startQRScanner: startQRScanner,
    
    // Modal
    showConfirmModal: showConfirmModal,
    
    // Debounce/Throttle
    debounce: debounce,
    throttle: throttle
};

// ============================================
// KEYBOARD SHORTCUTS
// ============================================

document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(function(modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
        });
    }
});

// ============================================
// END OF FILE
// ============================================