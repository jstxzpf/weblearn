// 性能优化的工具函数
class UIUtils {
    // 显示现代化加载提示
    static showLoading(element, message = '加载中...') {
        element.innerHTML = `
            <div class="loading d-flex align-items-center justify-content-center">
                <div class="spinner-border text-primary me-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span class="fw-medium">${message}</span>
            </div>
        `;
    }

    // 显示现代化错误信息
    static showError(element, message) {
        element.innerHTML = `
            <div class="alert alert-danger d-flex align-items-center" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div>${message}</div>
            </div>
        `;
    }

    // 显示成功信息
    static showSuccess(element, message) {
        element.innerHTML = `
            <div class="alert alert-success d-flex align-items-center" role="alert">
                <i class="fas fa-check-circle me-2"></i>
                <div>${message}</div>
            </div>
        `;
    }

    // 处理 AJAX 错误
    static handleAjaxError(error, element) {
        console.error('请求失败:', error);
        this.showError(element, '请求失败，请稍后重试');
    }

    // 防抖函数 - 优化版本
    static debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    }

    // 节流函数
    static throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // 平滑滚动到元素 - 兼容性增强
    static scrollToElement(element, offset = 0) {
        const elementPosition = element.offsetTop - offset;

        // 检查是否支持smooth scrolling
        if ('scrollBehavior' in document.documentElement.style) {
            window.scrollTo({
                top: elementPosition,
                behavior: 'smooth'
            });
        } else {
            // 回退到动画滚动
            this.animateScrollTo(elementPosition, 500);
        }
    }

    // 动画滚动回退方案
    static animateScrollTo(to, duration) {
        const start = window.pageYOffset || document.documentElement.scrollTop;
        const change = to - start;
        const startTime = Date.now();

        const animateScroll = function() {
            const timeElapsed = Date.now() - startTime;
            const progress = Math.min(timeElapsed / duration, 1);
            const ease = progress * (2 - progress); // easeOutQuad

            window.scrollTo(0, start + change * ease);

            if (timeElapsed < duration) {
                if (window.requestAnimationFrame) {
                    requestAnimationFrame(animateScroll);
                } else {
                    setTimeout(animateScroll, 16);
                }
            }
        };

        if (window.requestAnimationFrame) {
            requestAnimationFrame(animateScroll);
        } else {
            setTimeout(animateScroll, 16);
        }
    }

    // 检测元素是否在视口中
    static isInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }

    // 创建通知 - 兼容性增强
    static createNotification(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} notification-toast`;

        // 使用兼容的样式设置
        const styles = [
            'position: fixed',
            'top: 20px',
            'right: 20px',
            'z-index: 9999',
            'min-width: 300px',
            'opacity: 0',
            'transition: all 0.3s ease'
        ];

        if (notification.style.transform !== undefined) {
            styles.push('transform: translateX(100%)');
        } else {
            styles.push('margin-right: -320px');
        }

        notification.style.cssText = styles.join('; ');
        notification.textContent = message;

        document.body.appendChild(notification);

        // 显示动画
        setTimeout(() => {
            notification.style.opacity = '1';
            if (notification.style.transform !== undefined) {
                notification.style.transform = 'translateX(0)';
            } else {
                notification.style.marginRight = '0';
            }
        }, 10);

        // 自动隐藏
        setTimeout(() => {
            notification.style.opacity = '0';
            if (notification.style.transform !== undefined) {
                notification.style.transform = 'translateX(100%)';
            } else {
                notification.style.marginRight = '-320px';
            }
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }, duration);
    }

    // 添加加载状态到按钮
    static setButtonLoading(button, loading = true) {
        if (loading) {
            button.disabled = true;
            button.dataset.originalText = button.innerHTML;
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                加载中...
            `;
        } else {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText || button.innerHTML;
        }
    }
}

// 性能优化的API请求类
class APIClient {
    constructor() {
        this.cache = new Map();
        this.pendingRequests = new Map();
    }

    // 带缓存的GET请求
    async get(url, options = {}) {
        const cacheKey = url + JSON.stringify(options);

        // 检查缓存
        if (this.cache.has(cacheKey) && !options.noCache) {
            return this.cache.get(cacheKey);
        }

        // 检查是否有相同的请求正在进行
        if (this.pendingRequests.has(cacheKey)) {
            return this.pendingRequests.get(cacheKey);
        }

        // 发起新请求
        const request = fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        }).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        }).then(data => {
            // 缓存结果
            if (!options.noCache) {
                this.cache.set(cacheKey, data);
                // 5分钟后清除缓存
                setTimeout(() => this.cache.delete(cacheKey), 5 * 60 * 1000);
            }
            return data;
        }).finally(() => {
            this.pendingRequests.delete(cacheKey);
        });

        this.pendingRequests.set(cacheKey, request);
        return request;
    }

    // POST请求
    async post(url, data, options = {}) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        }).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        });
    }

    // 清除缓存
    clearCache() {
        this.cache.clear();
    }
}

// 全局API客户端实例
const apiClient = new APIClient();

// 页面初始化优化
document.addEventListener('DOMContentLoaded', function() {
    // 使用 requestAnimationFrame 优化动画
    const initializeAnimations = () => {
        // 为卡片添加现代化悬停效果
        document.querySelectorAll('.card').forEach(card => {
            card.addEventListener('mouseenter', UIUtils.throttle(() => {
                card.style.transform = 'translateY(-4px)';
                card.style.boxShadow = '0 8px 25px rgba(0,0,0,0.15)';
            }, 16));

            card.addEventListener('mouseleave', UIUtils.throttle(() => {
                card.style.transform = 'translateY(0)';
                card.style.boxShadow = '';
            }, 16));
        });

        // 为按钮添加波纹效果
        document.querySelectorAll('.btn').forEach(button => {
            button.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;

                ripple.style.cssText = `
                    position: absolute;
                    width: ${size}px;
                    height: ${size}px;
                    left: ${x}px;
                    top: ${y}px;
                    background: rgba(255,255,255,0.3);
                    border-radius: 50%;
                    transform: scale(0);
                    animation: ripple 0.6s linear;
                    pointer-events: none;
                `;

                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);

                setTimeout(() => ripple.remove(), 600);
            });
        });
    };

    // 使用 requestAnimationFrame 确保在下一帧执行
    requestAnimationFrame(initializeAnimations);

    // 添加CSS动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }

        .fade-in {
            animation: fadeIn 0.5s ease-in;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);
});