/**
 * 性能优化和浏览器兼容性工具库
 * 包含polyfills、性能优化工具和兼容性检测
 */

// 浏览器兼容性检测
const BrowserCompat = {
    // 检测CSS变量支持
    supportsCSSVariables: function() {
        return window.CSS && CSS.supports && CSS.supports('color', 'var(--fake-var)');
    },

    // 检测Intersection Observer支持
    supportsIntersectionObserver: function() {
        return 'IntersectionObserver' in window;
    },

    // 检测requestAnimationFrame支持
    supportsRequestAnimationFrame: function() {
        return 'requestAnimationFrame' in window;
    },

    // 检测Fetch API支持
    supportsFetch: function() {
        return 'fetch' in window;
    },

    // 检测Promise支持
    supportsPromise: function() {
        return 'Promise' in window;
    },

    // 获取浏览器信息
    getBrowserInfo: function() {
        const ua = navigator.userAgent;
        const browsers = {
            chrome: /chrome/i.test(ua),
            firefox: /firefox/i.test(ua),
            safari: /safari/i.test(ua) && !/chrome/i.test(ua),
            edge: /edge/i.test(ua),
            ie: /msie|trident/i.test(ua)
        };
        return browsers;
    }
};

// Polyfills
const Polyfills = {
    // requestAnimationFrame polyfill
    initRequestAnimationFrame: function() {
        if (!BrowserCompat.supportsRequestAnimationFrame()) {
            let lastTime = 0;
            window.requestAnimationFrame = function(callback) {
                const currTime = new Date().getTime();
                const timeToCall = Math.max(0, 16 - (currTime - lastTime));
                const id = window.setTimeout(function() {
                    callback(currTime + timeToCall);
                }, timeToCall);
                lastTime = currTime + timeToCall;
                return id;
            };
            window.cancelAnimationFrame = function(id) {
                clearTimeout(id);
            };
        }
    },

    // Promise polyfill (简化版)
    initPromise: function() {
        if (!BrowserCompat.supportsPromise()) {
            // 加载Promise polyfill
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/es6-promise@4/dist/es6-promise.auto.min.js';
            document.head.appendChild(script);
        }
    },

    // Fetch polyfill
    initFetch: function() {
        if (!BrowserCompat.supportsFetch()) {
            // 加载fetch polyfill
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/whatwg-fetch@3.6.2/dist/fetch.umd.js';
            document.head.appendChild(script);
        }
    },

    // Intersection Observer polyfill
    initIntersectionObserver: function() {
        if (!BrowserCompat.supportsIntersectionObserver()) {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/intersection-observer@0.12.0/intersection-observer.js';
            document.head.appendChild(script);
        }
    },

    // 初始化所有polyfills
    initAll: function() {
        this.initRequestAnimationFrame();
        this.initPromise();
        this.initFetch();
        this.initIntersectionObserver();
    }
};

// 性能优化工具
const PerformanceUtils = {
    // 防抖函数
    debounce: function(func, wait, immediate) {
        let timeout;
        return function executedFunction() {
            const context = this;
            const args = arguments;
            const later = function() {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(context, args);
        };
    },

    // 节流函数
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    // 懒加载图片
    lazyLoadImages: function() {
        const images = document.querySelectorAll('img[data-src]');
        
        if (BrowserCompat.supportsIntersectionObserver()) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        imageObserver.unobserve(img);
                    }
                });
            });

            images.forEach(img => imageObserver.observe(img));
        } else {
            // 回退方案：立即加载所有图片
            images.forEach(img => {
                img.src = img.dataset.src;
                img.classList.remove('lazy');
            });
        }
    },

    // 预加载关键资源
    preloadResources: function(resources) {
        resources.forEach(resource => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.href = resource.href;
            link.as = resource.as || 'script';
            if (resource.crossorigin) link.crossOrigin = resource.crossorigin;
            document.head.appendChild(link);
        });
    },

    // 优化DOM操作
    batchDOMUpdates: function(callback) {
        if (BrowserCompat.supportsRequestAnimationFrame()) {
            requestAnimationFrame(callback);
        } else {
            setTimeout(callback, 16);
        }
    },

    // 内存清理
    cleanup: function() {
        // 清理事件监听器
        if (window.performanceCleanupTasks) {
            window.performanceCleanupTasks.forEach(task => {
                if (typeof task === 'function') {
                    task();
                }
            });
            window.performanceCleanupTasks = [];
        }
    }
};

// CSS变量回退处理
const CSSVariableFallback = {
    init: function() {
        if (!BrowserCompat.supportsCSSVariables()) {
            this.applyCSSFallbacks();
        }
    },

    applyCSSFallbacks: function() {
        const fallbacks = {
            '--primary-color': '#667eea',
            '--secondary-color': '#764ba2',
            '--accent-color': '#f093fb',
            '--success-color': '#4CAF50',
            '--warning-color': '#ff9800',
            '--error-color': '#f44336',
            '--text-primary': '#2c3e50',
            '--text-secondary': '#7f8c8d',
            '--bg-primary': '#ffffff',
            '--bg-secondary': '#f8f9fa',
            '--border-radius': '12px',
            '--shadow-light': '0 2px 10px rgba(0,0,0,0.1)',
            '--shadow-medium': '0 4px 20px rgba(0,0,0,0.15)'
        };

        // 创建样式表
        const style = document.createElement('style');
        let css = '';

        // 为每个CSS变量创建回退样式
        Object.keys(fallbacks).forEach(variable => {
            const value = fallbacks[variable];
            const className = variable.replace('--', 'fallback-').replace('-', '-');
            
            if (variable.includes('color')) {
                css += `.${className} { color: ${value} !important; }\n`;
                css += `.${className}-bg { background-color: ${value} !important; }\n`;
            } else if (variable.includes('shadow')) {
                css += `.${className} { box-shadow: ${value} !important; }\n`;
            } else if (variable.includes('radius')) {
                css += `.${className} { border-radius: ${value} !important; }\n`;
            }
        });

        style.textContent = css;
        document.head.appendChild(style);
    }
};

// 性能监控
const PerformanceMonitor = {
    init: function() {
        this.measurePageLoad();
        this.measureResourceTiming();
    },

    measurePageLoad: function() {
        window.addEventListener('load', () => {
            if ('performance' in window) {
                const perfData = performance.timing;
                const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
                console.log(`页面加载时间: ${pageLoadTime}ms`);
                
                // 发送性能数据到服务器（可选）
                this.sendPerformanceData({
                    pageLoadTime: pageLoadTime,
                    domContentLoaded: perfData.domContentLoadedEventEnd - perfData.navigationStart,
                    firstPaint: this.getFirstPaint()
                });
            }
        });
    },

    measureResourceTiming: function() {
        if ('performance' in window && 'getEntriesByType' in performance) {
            window.addEventListener('load', () => {
                const resources = performance.getEntriesByType('resource');
                const slowResources = resources.filter(resource => resource.duration > 1000);
                
                if (slowResources.length > 0) {
                    console.warn('慢加载资源:', slowResources);
                }
            });
        }
    },

    getFirstPaint: function() {
        if ('performance' in window && 'getEntriesByType' in performance) {
            const paintEntries = performance.getEntriesByType('paint');
            const firstPaint = paintEntries.find(entry => entry.name === 'first-paint');
            return firstPaint ? firstPaint.startTime : null;
        }
        return null;
    },

    sendPerformanceData: function(data) {
        // 这里可以发送性能数据到服务器进行分析
        // fetch('/api/performance', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(data)
        // });
    }
};

// 初始化所有优化功能
document.addEventListener('DOMContentLoaded', function() {
    // 初始化polyfills
    Polyfills.initAll();
    
    // 初始化CSS变量回退
    CSSVariableFallback.init();
    
    // 初始化性能监控
    PerformanceMonitor.init();
    
    // 初始化懒加载
    PerformanceUtils.lazyLoadImages();
    
    // 预加载关键资源
    PerformanceUtils.preloadResources([
        { href: '/static/css/style.css', as: 'style' },
        { href: '/static/js/main.js', as: 'script' }
    ]);
});

// 页面卸载时清理
window.addEventListener('beforeunload', function() {
    PerformanceUtils.cleanup();
});

// 导出工具函数供其他脚本使用
window.BrowserCompat = BrowserCompat;
window.PerformanceUtils = PerformanceUtils;
window.Polyfills = Polyfills;
