document.addEventListener('DOMContentLoaded', function() {
    loadChapters();
});

function loadChapters() {
    fetch('/api/chapters')
        .then(response => response.json())
        .then(data => {
            const chapterList = document.getElementById('chapterList');
            data.chapters.forEach(chapter => {
                const div = document.createElement('div');
                div.className = 'chapter-item';
                div.innerHTML = `
                    <div class="chapter-title" onclick="loadConcepts('${chapter.title}')">
                        ${chapter.title}
                    </div>
                `;
                chapterList.appendChild(div);
            });
        })
        .catch(error => {
            console.error('加载章节失败:', error);
            showError('加载章节列表失败，请刷新页面重试');
        });
}

function loadConcepts(chapter) {
    fetch(`/api/concepts?chapter=${encodeURIComponent(chapter)}`)
        .then(response => response.json())
        .then(data => {
            const conceptList = document.getElementById('conceptList');
            conceptList.innerHTML = '';
            data.concepts.forEach(concept => {
                const div = document.createElement('div');
                div.className = 'concept-item';
                div.innerHTML = `
                    <div class="concept-title" onclick="getExplanation('${chapter}', '${concept}')">
                        ${concept}
                    </div>
                `;
                conceptList.appendChild(div);
            });
        })
        .catch(error => {
            console.error('加载知识点失败:', error);
            showError('加载知识点列表失败，请重试');
        });
}

function getExplanation(chapter, concept) {
    fetch('/api/explain', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            chapter: chapter,
            concept: concept
        })
    })
    .then(response => response.json())
    .then(data => {
        const aiExplanation = document.getElementById('aiExplanation');
        aiExplanation.innerHTML = data.explanation;
    })
    .catch(error => {
        console.error('获取讲解失败:', error);
        showError('获取AI讲解失败，请重试');
    });
}

function showError(message) {
    // 可以根据需要实现错误提示UI
    alert(message);
} 