/**
 * Service Worker 注册和管理
 * 提供缓存管理和离线支持
 */

class ServiceWorkerManager {
    constructor() {
        this.registration = null;
        this.isSupported = 'serviceWorker' in navigator;
        this.isOnline = navigator.onLine;
        
        this.init();
    }

    async init() {
        if (!this.isSupported) {
            console.log('Service Worker not supported');
            return;
        }

        try {
            await this.register();
            this.setupEventListeners();
            this.checkForUpdates();
        } catch (error) {
            console.error('Service Worker initialization failed:', error);
        }
    }

    async register() {
        try {
            this.registration = await navigator.serviceWorker.register('/static/js/sw.js', {
                scope: '/'
            });

            console.log('Service Worker registered successfully:', this.registration);

            // 监听安装事件
            this.registration.addEventListener('updatefound', () => {
                const newWorker = this.registration.installing;
                console.log('New Service Worker installing...');

                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed') {
                        if (navigator.serviceWorker.controller) {
                            // 有新版本可用
                            this.showUpdateNotification();
                        } else {
                            // 首次安装完成
                            this.showInstallNotification();
                        }
                    }
                });
            });

        } catch (error) {
            console.error('Service Worker registration failed:', error);
            throw error;
        }
    }

    setupEventListeners() {
        // 监听网络状态变化
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.showNetworkStatus('online');
            console.log('Network: Online');
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.showNetworkStatus('offline');
            console.log('Network: Offline');
        });

        // 监听Service Worker消息
        navigator.serviceWorker.addEventListener('message', event => {
            this.handleMessage(event.data);
        });

        // 监听控制器变化
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            console.log('Service Worker controller changed');
            // 可以选择重新加载页面
            // window.location.reload();
        });
    }

    handleMessage(data) {
        const { type, payload } = data;

        switch (type) {
            case 'CACHE_UPDATED':
                console.log('Cache updated:', payload);
                break;
            case 'OFFLINE_READY':
                this.showOfflineReadyNotification();
                break;
            default:
                console.log('Unknown SW message:', data);
        }
    }

    async checkForUpdates() {
        if (!this.registration) return;

        try {
            await this.registration.update();
            console.log('Checked for Service Worker updates');
        } catch (error) {
            console.error('Failed to check for updates:', error);
        }
    }

    async skipWaiting() {
        if (!this.registration || !this.registration.waiting) return;

        // 发送消息给等待中的Service Worker
        this.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    }

    async clearCache() {
        if (!this.registration || !this.registration.active) {
            console.warn('No active Service Worker to clear cache');
            return false;
        }

        try {
            const messageChannel = new MessageChannel();
            
            return new Promise((resolve, reject) => {
                messageChannel.port1.onmessage = event => {
                    if (event.data.success) {
                        console.log('Cache cleared successfully');
                        resolve(true);
                    } else {
                        console.error('Failed to clear cache:', event.data.error);
                        reject(new Error(event.data.error));
                    }
                };

                this.registration.active.postMessage(
                    { type: 'CLEAR_CACHE' },
                    [messageChannel.port2]
                );
            });
        } catch (error) {
            console.error('Failed to clear cache:', error);
            return false;
        }
    }

    async getCacheSize() {
        if (!this.registration || !this.registration.active) {
            return 0;
        }

        try {
            const messageChannel = new MessageChannel();
            
            return new Promise((resolve) => {
                messageChannel.port1.onmessage = event => {
                    resolve(event.data.size || 0);
                };

                this.registration.active.postMessage(
                    { type: 'GET_CACHE_SIZE' },
                    [messageChannel.port2]
                );
            });
        } catch (error) {
            console.error('Failed to get cache size:', error);
            return 0;
        }
    }

    showUpdateNotification() {
        if (window.UIUtils && typeof window.UIUtils.createNotification === 'function') {
            window.UIUtils.createNotification(
                '有新版本可用，点击刷新页面以获取最新功能',
                'info',
                10000
            );
        } else {
            console.log('New version available');
        }

        // 创建更新按钮
        this.createUpdateButton();
    }

    showInstallNotification() {
        if (window.UIUtils && typeof window.UIUtils.createNotification === 'function') {
            window.UIUtils.createNotification(
                '应用已安装，现在可以离线使用',
                'success',
                5000
            );
        } else {
            console.log('App installed for offline use');
        }
    }

    showOfflineReadyNotification() {
        if (window.UIUtils && typeof window.UIUtils.createNotification === 'function') {
            window.UIUtils.createNotification(
                '离线模式已准备就绪',
                'info',
                3000
            );
        }
    }

    showNetworkStatus(status) {
        const message = status === 'online' ? '网络连接已恢复' : '网络连接已断开，正在使用离线模式';
        const type = status === 'online' ? 'success' : 'warning';

        if (window.UIUtils && typeof window.UIUtils.createNotification === 'function') {
            window.UIUtils.createNotification(message, type, 3000);
        }
    }

    createUpdateButton() {
        // 检查是否已经存在更新按钮
        if (document.getElementById('sw-update-btn')) return;

        const updateBtn = document.createElement('button');
        updateBtn.id = 'sw-update-btn';
        updateBtn.className = 'btn btn-primary position-fixed';
        updateBtn.style.cssText = `
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;
        updateBtn.innerHTML = '<i class="fas fa-sync-alt me-2"></i>更新应用';
        
        updateBtn.addEventListener('click', async () => {
            updateBtn.disabled = true;
            updateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>更新中...';
            
            try {
                await this.skipWaiting();
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } catch (error) {
                console.error('Update failed:', error);
                updateBtn.disabled = false;
                updateBtn.innerHTML = '<i class="fas fa-sync-alt me-2"></i>更新应用';
            }
        });

        document.body.appendChild(updateBtn);

        // 5秒后自动隐藏按钮
        setTimeout(() => {
            if (updateBtn.parentNode) {
                updateBtn.style.opacity = '0.7';
            }
        }, 5000);
    }

    // 获取Service Worker状态
    getStatus() {
        if (!this.isSupported) {
            return 'not-supported';
        }

        if (!this.registration) {
            return 'not-registered';
        }

        if (this.registration.installing) {
            return 'installing';
        }

        if (this.registration.waiting) {
            return 'waiting';
        }

        if (this.registration.active) {
            return 'active';
        }

        return 'unknown';
    }

    // 获取缓存统计信息
    async getCacheStats() {
        const size = await this.getCacheSize();
        const sizeInMB = (size / (1024 * 1024)).toFixed(2);
        
        return {
            size: size,
            sizeFormatted: `${sizeInMB} MB`,
            isOnline: this.isOnline,
            status: this.getStatus()
        };
    }
}

// 创建全局Service Worker管理器实例
const swManager = new ServiceWorkerManager();

// 导出到全局作用域
window.swManager = swManager;

// 页面加载完成后显示缓存状态（开发模式）
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.addEventListener('load', async () => {
        setTimeout(async () => {
            const stats = await swManager.getCacheStats();
            console.log('Cache Stats:', stats);
        }, 2000);
    });
}
