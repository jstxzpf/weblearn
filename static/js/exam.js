document.addEventListener('DOMContentLoaded', function() {
    let selectedChapters = [];
    let currentDifficulty = 'easy';
    let currentExam = null;

    // 从URL获取主题
    const urlParams = new URLSearchParams(window.location.search);
    const subject = urlParams.get('subject');

    // 加载章节列表
    loadChapters();

    async function loadChapters() {
        try {
            const response = await fetch(`/api/chapters?subject=${subject}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            const chapterList = document.getElementById('chapterList');
            chapterList.innerHTML = '';

            if (data.error) {
                chapterList.innerHTML = `<div class="alert alert-error">${data.error}</div>`;
                return;
            }

            if (data.chapters && data.chapters.length > 0) {
                data.chapters.forEach((chapter, index) => {
                    const div = document.createElement('div');
                    div.className = 'form-check mb-2';
                    div.innerHTML = `
                        <label class="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                            <input class="form-check-input" type="checkbox" value="${chapter.title}" id="chapter_${index}">
                            <div class="flex items-center gap-2">
                                <i class="fas fa-book text-primary"></i>
                                <span class="font-medium">${chapter.title}</span>
                            </div>
                        </label>
                    `;
                    chapterList.appendChild(div);
                });

                chapterList.addEventListener('change', function(e) {
                    if (e.target.type === 'checkbox') {
                        updateSelectedChapters();
                    }
                });

            } else {
                chapterList.innerHTML = `
                    <div class="text-center text-gray-500 p-6">
                        <i class="fas fa-info-circle text-2xl mb-2"></i>
                        <p>暂无可用章节</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('加载章节失败:', error);
            document.getElementById('chapterList').innerHTML =
                '<div class="alert alert-error">加载章节列表失败</div>';
        }
    }

    function updateSelectedChapters() {
        const checkboxes = document.querySelectorAll('#chapterList input[type="checkbox"]:checked');
        selectedChapters = Array.from(checkboxes).map(cb => cb.value);
    }

    document.querySelectorAll('.difficulty-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.difficulty-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentDifficulty = this.dataset.difficulty;
        });
    });

    window.generateExam = async function() {
        if (selectedChapters.length === 0) {
            showNotification('请至少选择一个章节', 'warning');
            return;
        }

        const choiceCount = parseInt(document.getElementById('choiceCount').value) || 0;
        const judgeCount = parseInt(document.getElementById('judgeCount').value) || 0;

        if (choiceCount + judgeCount === 0) {
            showNotification('请设置题目数量', 'warning');
            return;
        }

        const selectedTypes = [];
        if (choiceCount > 0) {
            selectedTypes.push('单项选择题');
        }
        if (judgeCount > 0) {
            selectedTypes.push('判断题');
        }

        if (selectedTypes.length === 0) {
            showNotification('请至少选择一种题型', 'warning');
            return;
        }

        try {
            showProgressModal();

            const response = await fetch('/api/generate_exam', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    subject: subject,
                    chapters: selectedChapters,
                    types: selectedTypes,
                    choice_count: choiceCount,
                    judge_count: judgeCount,
                    difficulty: currentDifficulty
                })
            });

            const data = await response.json();

            if (data.title || data.questions) {
                currentExam = data;
                displayExam(data);
                hideProgressModal();
                showNotification('试卷生成成功！', 'success');
            } else {
                throw new Error(data.error || '生成试卷失败');
            }
        } catch (error) {
            console.error('生成试卷失败:', error);
            hideProgressModal();
            showNotification('生成试卷失败: ' + error.message, 'error');
        }
    };

    function displayExam(exam) {
        const examPreview = document.getElementById('examPreview');
        let html = `
            <div class="exam-header mb-6">
                <h2 class="text-2xl font-bold text-center mb-2">${exam.title || '智能生成试卷'}</h2>
                <div class="text-center text-gray-600 mb-4">
                    <span class="mr-4">学科：${subject}</span>
                    <span class="mr-4">难度：${getDifficultyText(exam.difficulty || currentDifficulty)}</span>
                    <span class="mr-4">题目数量：${(exam.questions || []).length}</span>
                    <span>总分：${exam.totalScore || 0}分</span>
                </div>
                <hr class="my-4">
            </div>
        `;

        if (exam.questions && exam.questions.length > 0) {
            exam.questions.forEach((question, index) => {
                html += `
                    <div class="question-item mb-6 p-4 border rounded-lg">
                        <div class="question-header mb-3 flex justify-between items-center">
                            <div>
                                <span class="question-number font-bold text-lg">${index + 1}.</span>
                                <span class="question-type badge ${question.type === 'choice' ? 'bg-primary' : 'bg-success'} ml-2">
                                    ${question.type === 'choice' ? '选择题' : '判断题'}
                                </span>
                            </div>
                            <span class="question-score text-sm text-gray-500">(${question.score || 1}分)</span>
                        </div>
                        <div class="question-content mb-3">
                            <p class="font-medium text-gray-800">${question.question}</p>
                        </div>
                `;

                if (question.type === 'choice' && question.options && question.options.length > 0) {
                    html += '<div class="options-list space-y-2">';
                    question.options.forEach((option, optIndex) => {
                        const letter = String.fromCharCode(65 + optIndex);
                        html += `
                            <div class="option-item flex items-start gap-2 p-2 bg-gray-50 rounded">
                                <span class="option-letter font-semibold text-primary">${letter}.</span>
                                <span class="flex-1">${option}</span>
                            </div>
                        `;
                    });
                    html += '</div>';
                } else if (question.type === 'judge') {
                    html += `
                        <div class="judge-options flex gap-4 mt-3">
                            <div class="option-item flex items-center gap-2 p-2 bg-gray-50 rounded">
                                <span class="option-letter font-semibold text-primary">A.</span>
                                <span>正确</span>
                            </div>
                            <div class="option-item flex items-center gap-2 p-2 bg-gray-50 rounded">
                                <span class="option-letter font-semibold text-primary">B.</span>
                                <span>错误</span>
                            </div>
                        </div>
                    `;
                }

                html += '</div>';
            });

            document.getElementById('startExamBtn').style.display = 'inline-flex';
            document.getElementById('saveBtn').style.display = 'inline-flex';
            document.getElementById('exportBtn').style.display = 'inline-flex';
        } else {
            html += '<div class="alert alert-warning">未生成任何题目</div>';
        }

        examPreview.innerHTML = html;
    }

    function getDifficultyText(difficulty) {
        const difficultyMap = {
            'easy': '简单',
            'medium': '中等',
            'hard': '困难'
        };
        return difficultyMap[difficulty] || '中等';
    }

    window.saveExam = async function() {
        if (!currentExam) {
            showNotification('没有可保存的试卷', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/save_exam', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    exam: currentExam,
                    subject: subject,
                    chapters: selectedChapters,
                    difficulty: currentDifficulty
                })
            });

            const data = await response.json();

            if (data.success) {
                showNotification('试卷保存成功！', 'success');
            } else {
                throw new Error(data.error || '保存失败');
            }
        } catch (error) {
            console.error('保存试卷失败:', error);
            showNotification('保存试卷失败: ' + error.message, 'error');
        }
    };

    window.exportExam = function() {
        if (!currentExam) {
            showNotification('没有可导出的试卷', 'warning');
            return;
        }

        let content = `${currentExam.title || '智能生成试卷'}\n`;
        content += `学科：${subject}\n`;
        content += `难度：${getDifficultyText(currentDifficulty)}\n`;
        content += `题目数量：${(currentExam.questions || []).length}\n\n`;

        if (currentExam.questions) {
            currentExam.questions.forEach((question, index) => {
                content += `${index + 1}. ${question.question}\n`;

                if (question.type === 'choice' && question.options) {
                    question.options.forEach((option, optIndex) => {
                        const letter = String.fromCharCode(65 + optIndex);
                        content += `${letter}. ${option}\n`;
                    });
                }

                content += '\n';
            });
        }

        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `试卷_${new Date().toISOString().slice(0, 10)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showNotification('试卷导出成功！', 'success');
    };

    window.startExam = async function() {
        if (!currentExam) {
            showNotification('请先生成试卷', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/create_exam_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ exam: currentExam })
            });

            const data = await response.json();

            if (data.session_id) {
                window.open(`/exam_taking/${data.session_id}`, '_blank');
            } else {
                throw new Error(data.error || '无法创建考试会话');
            }
        } catch (error) {
            console.error('开始考试失败:', error);
            showNotification('开始考试失败: ' + error.message, 'error');
        }
    };

    function showProgressModal() {
        const modal = new bootstrap.Modal(document.getElementById('progressModal'));
        const progressBar = document.querySelector('#progressModal .progress-bar');
        const progressText = document.getElementById('progressText');

        let progress = 0;
        const messages = [
            '分析知识点结构...',
            '智能选择题目类型...',
            '生成题目内容...',
            '优化题目质量...',
            '完成试卷生成...'
        ];

        const interval = setInterval(() => {
            progress += 20;
            progressBar.style.width = progress + '%';

            if (progress <= 100) {
                const messageIndex = Math.floor((progress - 1) / 20);
                if (messages[messageIndex]) {
                    progressText.textContent = messages[messageIndex];
                }
            }

            if (progress >= 100) {
                clearInterval(interval);
            }
        }, 800);

        modal.show();
    }

    function hideProgressModal() {
        const modalElement = document.getElementById('progressModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) {
            modal.hide();
        }
    }

    function showNotification(message, type) {
        if (window.UIUtils && typeof window.UIUtils.createNotification === 'function') {
            window.UIUtils.createNotification(message, type, 3000);
        } else {
            alert(message);
        }
    }
});