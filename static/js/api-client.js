/**
 * 优化的API客户端
 * 包含缓存、重试机制、错误处理和性能优化
 */

class OptimizedAPIClient {
    constructor(options = {}) {
        this.baseURL = options.baseURL || '';
        this.timeout = options.timeout || 10000;
        this.retryAttempts = options.retryAttempts || 3;
        this.retryDelay = options.retryDelay || 1000;
        
        // 缓存配置
        this.cache = new Map();
        this.cacheTimeout = options.cacheTimeout || 5 * 60 * 1000; // 5分钟
        
        // 请求队列和并发控制
        this.pendingRequests = new Map();
        this.maxConcurrentRequests = options.maxConcurrentRequests || 6;
        this.activeRequests = 0;
        this.requestQueue = [];
        
        // 错误处理
        this.errorHandlers = new Map();
        
        // 性能监控
        this.performanceMetrics = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            averageResponseTime: 0,
            cacheHits: 0
        };
    }

    // 主要的请求方法
    async request(url, options = {}) {
        const startTime = performance.now();
        this.performanceMetrics.totalRequests++;

        try {
            // 检查缓存
            if (options.method === 'GET' || !options.method) {
                const cachedResponse = this.getFromCache(url, options);
                if (cachedResponse && !options.noCache) {
                    this.performanceMetrics.cacheHits++;
                    return cachedResponse;
                }
            }

            // 检查是否有相同的请求正在进行
            const requestKey = this.getRequestKey(url, options);
            if (this.pendingRequests.has(requestKey)) {
                return await this.pendingRequests.get(requestKey);
            }

            // 并发控制
            if (this.activeRequests >= this.maxConcurrentRequests) {
                await this.queueRequest();
            }

            // 创建请求Promise
            const requestPromise = this.executeRequest(url, options);
            this.pendingRequests.set(requestKey, requestPromise);
            this.activeRequests++;

            const response = await requestPromise;
            
            // 缓存GET请求的响应
            if ((options.method === 'GET' || !options.method) && !options.noCache) {
                this.setCache(url, options, response);
            }

            this.performanceMetrics.successfulRequests++;
            this.updateAverageResponseTime(startTime);
            
            return response;

        } catch (error) {
            this.performanceMetrics.failedRequests++;
            this.handleError(error, url, options);
            throw error;
        } finally {
            this.pendingRequests.delete(this.getRequestKey(url, options));
            this.activeRequests--;
            this.processQueue();
        }
    }

    // 执行实际的HTTP请求
    async executeRequest(url, options) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const requestOptions = {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: options.body ? JSON.stringify(options.body) : undefined,
            signal: controller.signal,
            ...options
        };

        try {
            let lastError;
            
            // 重试机制
            for (let attempt = 0; attempt <= this.retryAttempts; attempt++) {
                try {
                    const response = await fetch(this.baseURL + url, requestOptions);
                    clearTimeout(timeoutId);
                    
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return await response.json();
                    } else {
                        return await response.text();
                    }
                    
                } catch (error) {
                    lastError = error;
                    
                    // 如果是最后一次尝试，抛出错误
                    if (attempt === this.retryAttempts) {
                        throw error;
                    }
                    
                    // 如果是网络错误或超时，进行重试
                    if (this.shouldRetry(error)) {
                        await this.delay(this.retryDelay * Math.pow(2, attempt));
                    } else {
                        throw error;
                    }
                }
            }
            
            throw lastError;
            
        } finally {
            clearTimeout(timeoutId);
        }
    }

    // 缓存管理
    getFromCache(url, options) {
        const key = this.getCacheKey(url, options);
        const cached = this.cache.get(key);
        
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }
        
        if (cached) {
            this.cache.delete(key);
        }
        
        return null;
    }

    setCache(url, options, data) {
        const key = this.getCacheKey(url, options);
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });
        
        // 限制缓存大小
        if (this.cache.size > 100) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
    }

    getCacheKey(url, options) {
        return `${url}_${JSON.stringify(options.params || {})}_${options.method || 'GET'}`;
    }

    getRequestKey(url, options) {
        return `${options.method || 'GET'}_${url}_${JSON.stringify(options.body || {})}`;
    }

    // 并发控制
    async queueRequest() {
        return new Promise(resolve => {
            this.requestQueue.push(resolve);
        });
    }

    processQueue() {
        if (this.requestQueue.length > 0 && this.activeRequests < this.maxConcurrentRequests) {
            const resolve = this.requestQueue.shift();
            resolve();
        }
    }

    // 错误处理
    shouldRetry(error) {
        // 网络错误、超时或5xx服务器错误可以重试
        return error.name === 'AbortError' || 
               error.message.includes('fetch') ||
               (error.message.includes('HTTP 5'));
    }

    handleError(error, url, options) {
        const errorType = this.getErrorType(error);
        const handler = this.errorHandlers.get(errorType);
        
        if (handler) {
            handler(error, url, options);
        } else {
            console.error(`API请求失败 [${url}]:`, error);
        }
    }

    getErrorType(error) {
        if (error.name === 'AbortError') return 'timeout';
        if (error.message.includes('HTTP 4')) return 'client_error';
        if (error.message.includes('HTTP 5')) return 'server_error';
        if (error.message.includes('fetch')) return 'network_error';
        return 'unknown_error';
    }

    // 注册错误处理器
    onError(errorType, handler) {
        this.errorHandlers.set(errorType, handler);
    }

    // 工具方法
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    updateAverageResponseTime(startTime) {
        const responseTime = performance.now() - startTime;
        const total = this.performanceMetrics.totalRequests;
        const current = this.performanceMetrics.averageResponseTime;
        this.performanceMetrics.averageResponseTime = (current * (total - 1) + responseTime) / total;
    }

    // 便捷方法
    get(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    }

    post(url, data, options = {}) {
        return this.request(url, { ...options, method: 'POST', body: data });
    }

    put(url, data, options = {}) {
        return this.request(url, { ...options, method: 'PUT', body: data });
    }

    delete(url, options = {}) {
        return this.request(url, { ...options, method: 'DELETE' });
    }

    // 批量请求
    async batch(requests) {
        const promises = requests.map(req => 
            this.request(req.url, req.options).catch(error => ({ error, request: req }))
        );
        
        return await Promise.all(promises);
    }

    // 清理缓存
    clearCache() {
        this.cache.clear();
        this.performanceMetrics.cacheHits = 0;
    }

    // 获取性能指标
    getPerformanceMetrics() {
        return { ...this.performanceMetrics };
    }

    // 健康检查
    async healthCheck() {
        try {
            await this.get('/api/health', { timeout: 5000, noCache: true });
            return true;
        } catch (error) {
            return false;
        }
    }
}

// 创建全局API客户端实例
const apiClient = new OptimizedAPIClient({
    timeout: 15000,
    retryAttempts: 2,
    retryDelay: 1000,
    cacheTimeout: 5 * 60 * 1000,
    maxConcurrentRequests: 6
});

// 配置错误处理
apiClient.onError('network_error', (error, url) => {
    console.warn(`网络错误，请检查连接: ${url}`);
    // 可以显示用户友好的错误消息
});

apiClient.onError('server_error', (error, url) => {
    console.error(`服务器错误: ${url}`, error);
    // 可以显示服务器错误消息
});

apiClient.onError('timeout', (error, url) => {
    console.warn(`请求超时: ${url}`);
    // 可以显示超时提示
});

// 导出API客户端
window.apiClient = apiClient;
