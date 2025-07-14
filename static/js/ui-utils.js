/**
 * UI工具类 - 提供通用的UI组件和工具函数
 */

class UIUtils {
    constructor() {
        this.notifications = [];
        this.init();
    }

    /**
     * 初始化UI工具
     */
    init() {
        this.createNotificationContainer();
        this.setupGlobalStyles();
    }

    /**
     * 创建通知容器
     */
    createNotificationContainer() {
        if (document.getElementById('notification-container')) return;

        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            pointer-events: none;
        `;
        document.body.appendChild(container);
    }

    /**
     * 设置全局样式
     */
    setupGlobalStyles() {
        if (document.getElementById('ui-utils-styles')) return;

        const style = document.createElement('style');
        style.id = 'ui-utils-styles';
        style.textContent = `
            .notification {
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                padding: 16px 20px;
                margin-bottom: 12px;
                min-width: 300px;
                max-width: 400px;
                pointer-events: auto;
                transform: translateX(100%);
                opacity: 0;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                border-left: 4px solid #667eea;
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .notification.show {
                transform: translateX(0);
                opacity: 1;
            }

            .notification.success {
                border-left-color: #22c55e;
            }

            .notification.warning {
                border-left-color: #f59e0b;
            }

            .notification.error {
                border-left-color: #ef4444;
            }

            .notification-icon {
                font-size: 18px;
                flex-shrink: 0;
            }

            .notification.success .notification-icon {
                color: #22c55e;
            }

            .notification.warning .notification-icon {
                color: #f59e0b;
            }

            .notification.error .notification-icon {
                color: #ef4444;
            }

            .notification.info .notification-icon {
                color: #3b82f6;
            }

            .notification-content {
                flex: 1;
            }

            .notification-title {
                font-weight: 600;
                color: #1f2937;
                margin-bottom: 2px;
            }

            .notification-message {
                color: #6b7280;
                font-size: 14px;
            }

            .notification-close {
                background: none;
                border: none;
                color: #9ca3af;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: color 0.2s;
            }

            .notification-close:hover {
                color: #6b7280;
            }

            @media (max-width: 480px) {
                .notification {
                    min-width: auto;
                    max-width: calc(100vw - 40px);
                    margin: 0 20px 12px 20px;
                }

                #notification-container {
                    right: 0;
                    left: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 创建通知
     * @param {string} message - 通知消息
     * @param {string} type - 通知类型 (success, warning, error, info)
     * @param {number} duration - 显示时长（毫秒）
     * @param {string} title - 通知标题（可选）
     */
    createNotification(message, type = 'info', duration = 3000, title = null) {
        const container = document.getElementById('notification-container');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;

        const iconMap = {
            success: 'fas fa-check-circle',
            warning: 'fas fa-exclamation-triangle',
            error: 'fas fa-times-circle',
            info: 'fas fa-info-circle'
        };

        const titleMap = {
            success: '成功',
            warning: '警告',
            error: '错误',
            info: '提示'
        };

        const notificationTitle = title || titleMap[type] || '通知';

        notification.innerHTML = `
            <div class="notification-icon">
                <i class="${iconMap[type] || iconMap.info}"></i>
            </div>
            <div class="notification-content">
                <div class="notification-title">${notificationTitle}</div>
                <div class="notification-message">${message}</div>
            </div>
            <button class="notification-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;

        container.appendChild(notification);

        // 触发显示动画
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });

        // 自动移除
        if (duration > 0) {
            setTimeout(() => {
                this.removeNotification(notification);
            }, duration);
        }

        return notification;
    }

    /**
     * 移除通知
     * @param {HTMLElement} notification - 通知元素
     */
    removeNotification(notification) {
        if (!notification || !notification.parentElement) return;

        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentElement) {
                notification.parentElement.removeChild(notification);
            }
        }, 300);
    }

    /**
     * 清除所有通知
     */
    clearAllNotifications() {
        const container = document.getElementById('notification-container');
        if (container) {
            container.innerHTML = '';
        }
    }

    /**
     * 创建确认对话框
     * @param {string} message - 确认消息
     * @param {string} title - 对话框标题
     * @returns {Promise<boolean>} - 用户选择结果
     */
    confirm(message, title = '确认') {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                opacity: 0;
                transition: opacity 0.3s;
            `;

            modal.innerHTML = `
                <div style="
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    max-width: 400px;
                    width: 90%;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                    transform: scale(0.9);
                    transition: transform 0.3s;
                ">
                    <h3 style="margin: 0 0 16px 0; color: #1f2937; font-size: 18px; font-weight: 600;">${title}</h3>
                    <p style="margin: 0 0 24px 0; color: #6b7280; line-height: 1.5;">${message}</p>
                    <div style="display: flex; gap: 12px; justify-content: flex-end;">
                        <button id="cancel-btn" style="
                            padding: 8px 16px;
                            border: 1px solid #d1d5db;
                            background: white;
                            color: #374151;
                            border-radius: 8px;
                            cursor: pointer;
                            font-size: 14px;
                            transition: all 0.2s;
                        ">取消</button>
                        <button id="confirm-btn" style="
                            padding: 8px 16px;
                            border: none;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border-radius: 8px;
                            cursor: pointer;
                            font-size: 14px;
                            transition: all 0.2s;
                        ">确认</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            // 显示动画
            requestAnimationFrame(() => {
                modal.style.opacity = '1';
                modal.querySelector('div').style.transform = 'scale(1)';
            });

            // 事件处理
            const cleanup = () => {
                modal.style.opacity = '0';
                modal.querySelector('div').style.transform = 'scale(0.9)';
                setTimeout(() => {
                    if (modal.parentElement) {
                        modal.parentElement.removeChild(modal);
                    }
                }, 300);
            };

            modal.querySelector('#confirm-btn').onclick = () => {
                cleanup();
                resolve(true);
            };

            modal.querySelector('#cancel-btn').onclick = () => {
                cleanup();
                resolve(false);
            };

            modal.onclick = (e) => {
                if (e.target === modal) {
                    cleanup();
                    resolve(false);
                }
            };
        });
    }

    /**
     * 创建加载指示器
     * @param {string} message - 加载消息
     * @returns {HTMLElement} - 加载元素
     */
    createLoader(message = '加载中...') {
        const loader = document.createElement('div');
        loader.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 9998;
            opacity: 0;
            transition: opacity 0.3s;
        `;

        loader.innerHTML = `
            <div style="
                width: 40px;
                height: 40px;
                border: 3px solid #e5e7eb;
                border-top-color: #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-bottom: 16px;
            "></div>
            <div style="color: #6b7280; font-size: 16px;">${message}</div>
        `;

        // 添加旋转动画
        if (!document.getElementById('loader-styles')) {
            const style = document.createElement('style');
            style.id = 'loader-styles';
            style.textContent = `
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(loader);

        requestAnimationFrame(() => {
            loader.style.opacity = '1';
        });

        return loader;
    }

    /**
     * 移除加载指示器
     * @param {HTMLElement} loader - 加载元素
     */
    removeLoader(loader) {
        if (!loader || !loader.parentElement) return;

        loader.style.opacity = '0';
        setTimeout(() => {
            if (loader.parentElement) {
                loader.parentElement.removeChild(loader);
            }
        }, 300);
    }
}

// 创建全局实例
window.UIUtils = new UIUtils();

// 兼容性支持
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIUtils;
}
