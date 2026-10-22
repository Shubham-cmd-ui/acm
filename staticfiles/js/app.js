/**
 * AI-Powered Document Intelligence Assistant
 * Frontend AJAX & Reactive Interaction Controller
 * Includes: Hybrid Grounded/General Q&A, 3D Flashcards, Rich Short Notes, Topics & Custom Quizzes
 */

document.addEventListener('DOMContentLoaded', function () {
    // =========================================================================
    // Core DOM Elements
    // =========================================================================
    const uploadForm = document.getElementById('uploadForm');
    const documentFileInput = document.getElementById('documentFile');
    const uploadSubmitBtn = document.getElementById('uploadSubmitBtn');
    const uploadProgressContainer = document.getElementById('uploadProgressContainer');
    const uploadStatusText = document.getElementById('uploadStatusText');
    const uploadAlert = document.getElementById('uploadAlert');

    const documentListContainer = document.getElementById('documentListContainer');
    const documentCountBadge = document.getElementById('documentCountBadge');
    const docSearchInput = document.getElementById('docSearchInput');
    const activeDocTitle = document.getElementById('activeDocTitle');
    const activeDocMeta = document.getElementById('activeDocMeta');
    const activeDocumentIdInput = document.getElementById('activeDocumentId');

    const chatMessagesContainer = document.getElementById('chatMessagesContainer');
    const chatWelcomeCard = document.getElementById('chatWelcomeCard');
    const queryForm = document.getElementById('queryForm');
    const queryInput = document.getElementById('queryInput');
    const sendQueryBtn = document.getElementById('sendQueryBtn');
    const typingIndicator = document.getElementById('typingIndicator');
    const clearChatBtn = document.getElementById('clearChatBtn');

    // Badges
    const flashcardsBadge = document.getElementById('flashcardsBadge');
    const topicsBadge = document.getElementById('topicsBadge');
    const quizBadge = document.getElementById('quizBadge');

    // Flashcards Elements
    const flashcardsPlaceholder = document.getElementById('flashcardsPlaceholder');
    const flashcardsWorkspace = document.getElementById('flashcardsWorkspace');
    const flashcardCountSelect = document.getElementById('flashcardCountSelect');
    const generateFlashcardsCustomBtn = document.getElementById('generateFlashcardsCustomBtn');
    const flashcardInner = document.getElementById('flashcardInner');
    const flashcardQuestion = document.getElementById('flashcardQuestion');
    const flashcardAnswer = document.getElementById('flashcardAnswer');
    const flashcardCategoryBadge = document.getElementById('flashcardCategoryBadge');
    const flashcardCounter = document.getElementById('flashcardCounter');
    const flashcardProgressBar = document.getElementById('flashcardProgressBar');
    const prevFlashcardBtn = document.getElementById('prevFlashcardBtn');
    const nextFlashcardBtn = document.getElementById('nextFlashcardBtn');
    const flipFlashcardBtn = document.getElementById('flipFlashcardBtn');
    const shuffleFlashcardsBtn = document.getElementById('shuffleFlashcardsBtn');

    // Notes Elements
    const notesPlaceholder = document.getElementById('notesPlaceholder');
    const notesWorkspace = document.getElementById('notesWorkspace');
    const notesTitleDisplay = document.getElementById('notesTitleDisplay');
    const notesReadTimeBadge = document.getElementById('notesReadTimeBadge');
    const notesSummaryText = document.getElementById('notesSummaryText');
    const notesTakeawaysList = document.getElementById('notesTakeawaysList');
    const notesGlossaryCard = document.getElementById('notesGlossaryCard');
    const notesGlossaryContainer = document.getElementById('notesGlossaryContainer');
    const notesSectionsContainer = document.getElementById('notesSectionsContainer');
    const notesConclusionsCard = document.getElementById('notesConclusionsCard');
    const notesConclusionsList = document.getElementById('notesConclusionsList');
    const generateNotesBtn = document.getElementById('generateNotesBtn');
    const regenerateNotesBtn = document.getElementById('regenerateNotesBtn');
    const copyNotesBtn = document.getElementById('copyNotesBtn');

    // Topics Elements
    const topicsPlaceholder = document.getElementById('topicsPlaceholder');
    const topicsWorkspace = document.getElementById('topicsWorkspace');
    const topicsGridContainer = document.getElementById('topicsGridContainer');
    const generateTopicsBtn = document.getElementById('generateTopicsBtn');

    // Quiz Elements
    const quizPlaceholder = document.getElementById('quizPlaceholder');
    const quizWorkspace = document.getElementById('quizWorkspace');
    const quizCountSelect = document.getElementById('quizCountSelect');
    const quizDifficultySelect = document.getElementById('quizDifficultySelect');
    const quizTopicSelect = document.getElementById('quizTopicSelect');
    const generateQuizCustomBtn = document.getElementById('generateQuizCustomBtn');
    const refreshQuizBtn = document.getElementById('refreshQuizBtn');
    const quizLoadingContainer = document.getElementById('quizLoadingContainer');
    const quizLoadingStatus = document.getElementById('quizLoadingStatus');
    const quizAttemptTitle = document.getElementById('quizAttemptTitle');
    const quizQuestionsContainer = document.getElementById('quizQuestionsContainer');
    const submitQuizBtn = document.getElementById('submitQuizBtn');
    const resetQuizBtn = document.getElementById('resetQuizBtn');
    const quizScoreBadge = document.getElementById('quizScoreBadge');

    // Quiz Results Dashboard Elements
    const quizResultsDashboard = document.getElementById('quizResultsDashboard');
    const resultsScoreTitle = document.getElementById('resultsScoreTitle');
    const resultsScoreSubtitle = document.getElementById('resultsScoreSubtitle');
    const resultsDeltaContainer = document.getElementById('resultsDeltaContainer');
    const resultsProgressBar = document.getElementById('resultsProgressBar');
    const quizWeakTopicsCard = document.getElementById('quizWeakTopicsCard');
    const quizWeakTopicsList = document.getElementById('quizWeakTopicsList');
    const weakTopicsCountBadge = document.getElementById('weakTopicsCountBadge');
    const quizTopicScoresContainer = document.getElementById('quizTopicScoresContainer');
    const quizRecommendationsList = document.getElementById('quizRecommendationsList');
    const quizHistoryContainer = document.getElementById('quizHistoryContainer');

    // =========================================================================
    // Reactive State
    // =========================================================================
    let studyState = {
        loadedDocId: null,
        flashcards: [],
        short_notes: {},
        important_topics: [],
        quiz: [],
    };

    let flashcardIndex = 0;
    let quizUserAnswers = {}; // { questionId: selectedOptionIndex }
    let isQuizSubmitted = false;

    // Helper: Retrieve CSRF Token from Cookie
    function getCsrfToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue || document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    }

    function scrollToBottom() {
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }

    function showAlert(message, type = 'danger') {
        uploadAlert.className = `alert alert-${type} mt-3 py-2 small mb-0 rounded-2`;
        uploadAlert.textContent = message;
        uploadAlert.classList.remove('d-none');
        setTimeout(() => { uploadAlert.classList.add('d-none'); }, 8000);
    }

    function escapeHtml(text) {
        if (!text) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    // =========================================================================
    // 1. AJAX Document Upload
    // =========================================================================
    uploadForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const file = documentFileInput.files[0];
        if (!file) {
            showAlert('Please select a file to upload.', 'warning');
            return;
        }

        // Client-side validation: extension, empty check, and 50 MB limit
        const filename = file.name.toLowerCase();
        if (!filename.endsWith('.pdf') && !filename.endsWith('.txt')) {
            showAlert(`Unsupported file format for '${file.name}'. Only .pdf and .txt files are allowed.`, 'warning');
            return;
        }

        if (file.size === 0) {
            showAlert(`The file '${file.name}' is empty (0 bytes).`, 'danger');
            return;
        }

        const maxBytes = 50 * 1024 * 1024; // 50 MB
        if (file.size > maxBytes) {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
            showAlert(`File '${file.name}' is ${sizeMB} MB, which exceeds the maximum limit of 50 MB.`, 'danger');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        uploadSubmitBtn.disabled = true;
        uploadProgressContainer.classList.remove('d-none');
        uploadStatusText.textContent = `Extracting, chunking & generating embeddings for '${file.name}'...`;
        uploadAlert.classList.add('d-none');

        try {
            const response = await fetch('/upload/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to process and index document.');
            }

            showAlert(data.message, 'success');
            uploadForm.reset();
            await refreshDocumentList(data.document.id);
            setActiveDocument(data.document.id, data.document.filename, data.document.total_chunks, data.document.file_type);

        } catch (error) {
            showAlert(error.message, 'danger');
        } finally {
            uploadSubmitBtn.disabled = false;
            uploadProgressContainer.classList.add('d-none');
        }
    });

    // =========================================================================
    // 2. Document List & Search Filter
    // =========================================================================
    if (docSearchInput) {
        docSearchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            document.querySelectorAll('.document-item').forEach(item => {
                const name = (item.getAttribute('data-doc-name') || '').toLowerCase();
                item.style.display = name.includes(query) ? '' : 'none';
            });
        });
    }

    async function refreshDocumentList(activeIdToSelect = null) {
        try {
            const response = await fetch('/api/documents/');
            const data = await response.json();
            if (!data.success) return;

            const docs = data.documents;
            documentCountBadge.textContent = docs.length;

            if (docs.length === 0) {
                documentListContainer.innerHTML = `
                    <div id="noDocumentsPlaceholder" class="p-4 text-center text-muted small">
                        <i class="bi bi-file-earmark-arrow-up fs-2 d-block text-secondary mb-2"></i>
                        No documents uploaded yet.<br>Upload a PDF or TXT file above to start.
                    </div>
                `;
                resetToEmptyState();
                return;
            }

            let html = '';
            docs.forEach(doc => {
                const isActive = activeIdToSelect ? (doc.id === activeIdToSelect) : (activeDocumentIdInput.value === doc.id);
                const badgeClass = doc.file_type.toLowerCase() === 'pdf' ? 'bg-danger-subtle text-danger border-danger-subtle' : 'bg-info-subtle text-info border-info-subtle';

                html += `
                    <div class="list-group-item list-group-item-action document-item p-3 ${isActive ? 'active-doc bg-light' : ''}"
                         data-doc-id="${doc.id}"
                         data-doc-name="${escapeHtml(doc.filename)}"
                         data-doc-chunks="${doc.total_chunks}"
                         data-doc-type="${doc.file_type}">
                        <div class="d-flex w-100 justify-content-between align-items-start mb-1">
                            <div class="text-truncate me-2">
                                <span class="badge ${badgeClass} border me-1 small">${doc.file_type}</span>
                                <span class="fw-semibold small doc-name-label" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</span>
                            </div>
                            <button type="button" class="btn btn-outline-danger btn-xs delete-doc-btn p-0 px-1 border-0" data-doc-id="${doc.id}" title="Delete document">
                                <i class="bi bi-trash3"></i>
                            </button>
                        </div>
                        <div class="d-flex justify-content-between text-muted small mt-2">
                            <span><i class="bi bi-grid-3x3-gap"></i> ${doc.total_chunks} chunks</span>
                            <span><i class="bi bi-file-earmark"></i> ${doc.size}</span>
                        </div>
                    </div>
                `;
            });

            documentListContainer.innerHTML = html;
            bindDocumentListEvents();

        } catch (err) {
            console.error('Failed to refresh document list', err);
        }
    }

    function bindDocumentListEvents() {
        document.querySelectorAll('.document-item').forEach(item => {
            item.addEventListener('click', function (e) {
                if (e.target.closest('.delete-doc-btn')) return;
                const docId = this.getAttribute('data-doc-id');
                const docName = this.getAttribute('data-doc-name');
                const docChunks = this.getAttribute('data-doc-chunks');
                const docType = this.getAttribute('data-doc-type') || 'PDF';
                setActiveDocument(docId, docName, docChunks, docType);
            });
        });

        document.querySelectorAll('.delete-doc-btn').forEach(btn => {
            btn.addEventListener('click', async function (e) {
                e.stopPropagation();
                const docId = this.getAttribute('data-doc-id');
                if (!confirm('Are you sure you want to delete this document and its FAISS index?')) return;

                try {
                    const resp = await fetch(`/api/documents/${docId}/delete/`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': getCsrfToken() }
                    });
                    const resData = await resp.json();
                    if (resData.success) {
                        await refreshDocumentList();
                        if (activeDocumentIdInput.value === docId) {
                            const firstDoc = document.querySelector('.document-item');
                            if (firstDoc) { firstDoc.click(); } else { resetToEmptyState(); }
                        }
                    }
                } catch (err) {
                    alert('Error deleting document: ' + err.message);
                }
            });
        });
    }

    function setActiveDocument(id, name, chunks, type) {
        activeDocumentIdInput.value = id;
        activeDocTitle.textContent = name;
        activeDocMeta.textContent = `${type.toUpperCase()} • ${chunks} indexed chunks • Grounded Q&A + AI Study Suite`;

        queryInput.disabled = false;
        queryInput.placeholder = `Ask a question about '${name}'...`;
        sendQueryBtn.disabled = false;

        document.querySelectorAll('.document-item').forEach(el => {
            el.classList.toggle('active-doc', el.getAttribute('data-doc-id') === id);
            el.classList.toggle('bg-light', el.getAttribute('data-doc-id') === id);
        });

        loadDocumentHistory(id);
        loadStudyMaterials(id);
    }

    function resetToEmptyState() {
        activeDocumentIdInput.value = '';
        activeDocTitle.textContent = 'No Active Document Selected';
        activeDocMeta.textContent = 'Upload or select a document from the left sidebar';
        queryInput.disabled = true;
        queryInput.placeholder = 'Upload or select a document first to ask questions...';
        sendQueryBtn.disabled = true;
        chatMessagesContainer.innerHTML = '';
        if (chatWelcomeCard) chatMessagesContainer.appendChild(chatWelcomeCard);
        hideStudyWorkspaces();
    }

    // =========================================================================
    // 3. Load Chat History
    // =========================================================================
    async function loadDocumentHistory(docId) {
        chatMessagesContainer.innerHTML = '';
        try {
            const resp = await fetch(`/api/documents/${docId}/history/`);
            const data = await resp.json();

            if (data.success && data.history.length > 0) {
                data.history.forEach(msg => {
                    appendUserMessage(msg.question);
                    appendAiMessage(msg.answer, msg.sources, msg.is_grounded, false, 1.0);
                });
                scrollToBottom();
            } else {
                if (chatWelcomeCard) chatMessagesContainer.appendChild(chatWelcomeCard);
            }
        } catch (err) {
            console.error('Error fetching chat history', err);
        }
    }

    // =========================================================================
    // 4. Grounded / Hybrid Q&A Query Submission
    // =========================================================================
    queryForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const query = queryInput.value.trim();
        const docId = activeDocumentIdInput.value;

        if (!query || !docId) return;

        if (chatWelcomeCard && chatWelcomeCard.parentNode === chatMessagesContainer) {
            chatMessagesContainer.removeChild(chatWelcomeCard);
        }

        appendUserMessage(query);
        queryInput.value = '';
        queryInput.disabled = true;
        sendQueryBtn.disabled = true;

        typingIndicator.classList.remove('d-none');
        scrollToBottom();

        try {
            const response = await fetch('/api/query/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ document_id: docId, query: query })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to generate answer.');
            }

            appendAiMessage(
                data.answer,
                data.sources,
                data.is_grounded,
                data.is_general_knowledge,
                data.top_score
            );

        } catch (error) {
            appendAiErrorMessage(error.message);
        } finally {
            typingIndicator.classList.add('d-none');
            queryInput.disabled = false;
            sendQueryBtn.disabled = false;
            queryInput.focus();
            scrollToBottom();
        }
    });

    function appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'chat-msg d-flex justify-content-end';
        div.innerHTML = `
            <div class="user-bubble">
                <div class="fw-medium">${escapeHtml(text)}</div>
            </div>
        `;
        chatMessagesContainer.appendChild(div);
        scrollToBottom();
    }

    // =========================================================================
    // Markdown Rendering & Syntax Enhancement Engine
    // =========================================================================

    // Clean markdown syntax for calm, natural Text-to-Speech playback
    function stripMarkdownForSpeech(md) {
        if (!md) return '';
        return md
            .replace(/```[\s\S]*?```/g, ' [code block omitted] ')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/#+\s+/g, '')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/__([^_]+)__/g, '$1')
            .replace(/_([^_]+)_/g, '$1')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .replace(/^>\s+/gm, '')
            .replace(/\|[^\n]+\|/g, ' ')
            .replace(/^[-*+]\s+/gm, '')
            .replace(/^\d+\.\s+/gm, '')
            .replace(/\s+/g, ' ')
            .trim();
    }

    // Renders full GitHub-flavored Markdown with tables, code blocks, lists, and bold text
    function renderMarkdownToHtml(markdownText) {
        if (!markdownText) return '';

        // 1. Try marked.js if loaded from CDN
        if (typeof window.marked !== 'undefined' && typeof window.marked.parse === 'function') {
            try {
                window.marked.setOptions({
                    gfm: true,
                    breaks: true,
                });
                let parsedHtml = window.marked.parse(markdownText);
                if (typeof window.DOMPurify !== 'undefined') {
                    parsedHtml = window.DOMPurify.sanitize(parsedHtml);
                }
                return postProcessMarkdownHtml(parsedHtml);
            } catch (err) {
                console.warn('marked.js parse failed, using fallback regex parser', err);
            }
        }

        // 2. Built-in resilient regex parser fallback
        return renderFallbackMarkdown(markdownText);
    }

    // Enhance rendered HTML with copy-able code headers and responsive tables
    function postProcessMarkdownHtml(html) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        // Wrap <pre><code> code blocks with a header bar, language pill, and copy button
        tempDiv.querySelectorAll('pre').forEach(pre => {
            const codeEl = pre.querySelector('code');
            const classList = codeEl ? codeEl.className : '';
            const langMatch = classList.match(/language-([a-zA-Z0-9_-]+)/);
            const lang = langMatch ? langMatch[1] : 'code';

            const wrapper = document.createElement('div');
            wrapper.className = 'code-block-wrapper';
            wrapper.innerHTML = `
                <div class="code-block-header">
                    <span class="code-lang-tag">${escapeHtml(lang)}</span>
                    <button type="button" class="btn-copy-code" title="Copy code snippet">
                        <i class="bi bi-clipboard"></i> <span>Copy</span>
                    </button>
                </div>
            `;
            pre.parentNode.insertBefore(wrapper, pre);
            wrapper.appendChild(pre);
        });

        // Wrap <table> with responsive container and SkyLearn styling
        tempDiv.querySelectorAll('table').forEach(table => {
            table.className = 'table table-sm skylearn-md-table';
            const wrapper = document.createElement('div');
            wrapper.className = 'skylearn-md-table-wrapper';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        });

        return tempDiv.innerHTML;
    }

    // Resilient standalone Markdown parser (works offline or if CDN is blocked)
    function renderFallbackMarkdown(md) {
        let text = escapeHtml(md);

        // Fenced code blocks ```lang ... ```
        text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function (match, lang, code) {
            const language = lang || 'code';
            return `<div class="code-block-wrapper">
                <div class="code-block-header">
                    <span class="code-lang-tag">${language}</span>
                    <button type="button" class="btn-copy-code" title="Copy code"><i class="bi bi-clipboard"></i> <span>Copy</span></button>
                </div>
                <pre><code>${code.trim()}</code></pre>
            </div>`;
        });

        // Inline code `code`
        text = text.replace(/`([^`]+)`/g, '<code class="skylearn-inline-code">$1</code>');

        // Headers ###, ##, #
        text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

        // Bold and Italic
        text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Blockquotes
        text = text.replace(/^>\s+(.*$)/gim, '<blockquote><p>$1</p></blockquote>');

        // Lists
        text = text.replace(/^\s*[-*]\s+(.*$)/gim, '<li>$1</li>');
        text = text.replace(/(<li>.*<\/li>)/gims, '<ul>$1</ul>');

        // Paragraphs
        text = text.split('\n\n').map(p => {
            if (p.startsWith('<h') || p.startsWith('<div') || p.startsWith('<ul>') || p.startsWith('<blockquote>')) {
                return p;
            }
            return `<p>${p.replace(/\n/g, '<br>')}</p>`;
        }).join('');

        return text;
    }

    function appendAiMessage(answer, sources, isGrounded, isGeneralKnowledge, topScore) {
        const div = document.createElement('div');
        div.className = 'chat-msg d-flex justify-content-start';

        let bubbleClass = 'grounded-success';
        let statusBadge = '';
        let scoreBadge = '';

        if (isGrounded) {
            bubbleClass = 'grounded-success';
            statusBadge = `<span class="badge bg-leaf-soft text-leaf-deep border-0 fw-bold"><i class="bi bi-shield-check me-1 text-leaf"></i> Grounded in Lesson</span>`;
            const scorePercent = topScore ? Math.round(topScore * 100) : 0;
            if (sources && sources.length > 0) {
                scoreBadge = `<span class="badge bg-surface text-ink-muted border small"><i class="bi bi-bullseye text-sky me-1"></i> Match: ${scorePercent}%</span>`;
            }
        } else if (isGeneralKnowledge) {
            bubbleClass = 'general-knowledge-mode';
            statusBadge = `<span class="badge bg-berry-soft text-berry-deep border-0 fw-bold"><i class="bi bi-stars me-1 text-berry"></i> AI Tutor Knowledge</span>`;
        } else {
            bubbleClass = 'fallback-warning';
            statusBadge = `<span class="badge bg-sun-soft text-sun-deep border-0 fw-bold"><i class="bi bi-exclamation-triangle me-1 text-sun"></i> Not in Lesson</span>`;
        }

        const encodedAnswer = encodeURIComponent(answer);
        const renderedHtml = renderMarkdownToHtml(answer);

        // Generate Source Reference Accordion if grounded sources exist
        let sourcesHtml = '';
        if (isGrounded && sources && sources.length > 0) {
            const accordionId = `sources_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            let passageItemsHtml = '';

            sources.forEach((src, idx) => {
                const pageLabel = src.page_number ? `Page ${src.page_number}` : 'Lesson Passage';
                const srcScore = src.score ? `${Math.round(src.score * 100)}%` : 'N/A';

                passageItemsHtml += `
                    <div class="passage-item">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="badge bg-sky-soft text-sky-deep border-0 small fw-bold">Source #${idx + 1} &bull; ${pageLabel} &bull; Chunk #${src.chunk_index}</span>
                            <span class="badge bg-surface text-ink-muted border small">Relevance: ${srcScore}</span>
                        </div>
                        <div class="passage-text">${escapeHtml(src.content)}</div>
                    </div>
                `;
            });

            sourcesHtml = `
                <div class="source-references-card mt-3">
                    <button class="source-header-btn" type="button" data-bs-toggle="collapse" data-bs-target="#${accordionId}">
                        <span><i class="bi bi-layers-fill text-sky me-1"></i> Verified Lesson Sources (${sources.length} matching passages)</span>
                        <i class="bi bi-chevron-down"></i>
                    </button>
                    <div id="${accordionId}" class="collapse show p-2 border-top">
                        ${passageItemsHtml}
                    </div>
                </div>
            `;
        }

        div.innerHTML = `
            <div class="ai-bubble-container">
                <div class="ai-bubble ${bubbleClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                        <div class="d-flex align-items-center gap-2">
                            <div class="skylearn-logo-badge" style="width: 32px; height: 32px; font-size: 1rem;">
                                <i class="bi bi-robot text-sky"></i>
                            </div>
                            <span class="fw-bold small text-dark">LearningHub AI Tutor</span>
                        </div>
                        <div class="d-flex gap-2 align-items-center flex-wrap">
                            <button type="button" class="btn btn-copy-response btn-sm" data-raw="${encodedAnswer}" title="Copy response to clipboard">
                                <i class="bi bi-clipboard"></i>
                                <span>Copy</span>
                            </button>
                            <button type="button" class="btn btn-read-to-me btn-sm chat-tts-btn" data-text="${encodedAnswer}" title="Read answer aloud">
                                <i class="bi bi-volume-up-fill"></i>
                                <span>Read to me</span>
                            </button>
                            ${statusBadge}
                            ${scoreBadge}
                        </div>
                    </div>
                    <div class="answer-content text-dark">${renderedHtml}</div>
                    ${sourcesHtml}
                </div>
            </div>
        `;

        chatMessagesContainer.appendChild(div);
        scrollToBottom();
    }

    function appendAiErrorMessage(errorMessage) {
        const div = document.createElement('div');
        div.className = 'chat-msg d-flex justify-content-start';
        div.innerHTML = `
            <div class="ai-bubble-container">
                <div class="ai-bubble border-danger bg-danger-subtle">
                    <div class="d-flex align-items-center gap-2 text-danger mb-1">
                        <i class="bi bi-exclamation-octagon-fill"></i>
                        <span class="fw-bold small">Query Failed</span>
                    </div>
                    <div class="small text-danger">${escapeHtml(errorMessage)}</div>
                </div>
            </div>
        `;
        chatMessagesContainer.appendChild(div);
        scrollToBottom();
    }

    clearChatBtn.addEventListener('click', function () {
        chatMessagesContainer.innerHTML = '';
        if (chatWelcomeCard) chatMessagesContainer.appendChild(chatWelcomeCard);
    });

    // =========================================================================
    // 5. AI Study Suite: Load & Generate Management
    // =========================================================================
    async function loadStudyMaterials(docId) {
        if (!docId) {
            hideStudyWorkspaces();
            return;
        }

        try {
            const resp = await fetch(`/api/documents/${docId}/study-materials/`);
            const data = await resp.json();

            if (data.success && data.exists) {
                studyState = {
                    loadedDocId: docId,
                    flashcards: data.flashcards || [],
                    short_notes: data.short_notes || {},
                    important_topics: data.important_topics || [],
                    quiz: data.quiz || []
                };

                renderAllStudyFeatures();
            } else {
                hideStudyWorkspaces();
            }
        } catch (err) {
            console.error('Error fetching study materials', err);
            hideStudyWorkspaces();
        }
    }

    function hideStudyWorkspaces() {
        flashcardsPlaceholder.classList.remove('d-none');
        flashcardsWorkspace.classList.add('d-none');
        flashcardsBadge.classList.add('d-none');

        notesPlaceholder.classList.remove('d-none');
        notesWorkspace.classList.add('d-none');

        topicsPlaceholder.classList.remove('d-none');
        topicsWorkspace.classList.add('d-none');
        topicsBadge.classList.add('d-none');

        quizPlaceholder.classList.remove('d-none');
        quizWorkspace.classList.add('d-none');
        quizBadge.classList.add('d-none');
    }

    function renderAllStudyFeatures() {
        // Flashcards
        if (studyState.flashcards && studyState.flashcards.length > 0) {
            flashcardsPlaceholder.classList.add('d-none');
            flashcardsWorkspace.classList.remove('d-none');
            flashcardsBadge.textContent = studyState.flashcards.length;
            flashcardsBadge.classList.remove('d-none');
            flashcardIndex = 0;
            renderActiveFlashcard();
        }

        // Notes
        if (studyState.short_notes && studyState.short_notes.summary) {
            notesPlaceholder.classList.add('d-none');
            notesWorkspace.classList.remove('d-none');
            renderShortNotes();
        }

        // Topics
        if (studyState.important_topics && studyState.important_topics.length > 0) {
            topicsPlaceholder.classList.add('d-none');
            topicsWorkspace.classList.remove('d-none');
            topicsBadge.textContent = studyState.important_topics.length;
            topicsBadge.classList.remove('d-none');
            renderImportantTopics();
            populateQuizTopicOptions(studyState.important_topics);
        }

        // Quiz
        if (studyState.quiz && studyState.quiz.length > 0) {
            quizPlaceholder.classList.add('d-none');
            quizWorkspace.classList.remove('d-none');
            quizBadge.textContent = `${studyState.quiz.length} Qs`;
            quizBadge.classList.remove('d-none');
            quizUserAnswers = {};
            isQuizSubmitted = false;
            renderQuiz();
        }
    }

    function populateQuizTopicOptions(topics) {
        if (!quizTopicSelect) return;
        const currentVal = quizTopicSelect.value;
        let html = '<option value="all">All Topics</option>';
        if (topics && topics.length > 0) {
            topics.forEach(t => {
                const title = t.title || t;
                const isSelected = (title === currentVal) ? 'selected' : '';
                html += `<option value="${escapeHtml(title)}" ${isSelected}>${escapeHtml(title)}</option>`;
            });
        }
        quizTopicSelect.innerHTML = html;
        if (currentVal && quizTopicSelect.querySelector(`option[value="${currentVal}"]`)) {
            quizTopicSelect.value = currentVal;
        } else {
            quizTopicSelect.value = 'all';
        }
    }

    async function triggerGenerateStudyMaterials(force = false, options = {}) {
        const docId = activeDocumentIdInput.value;
        if (!docId) {
            alert('Please select or upload a document first.');
            return;
        }

        const flashcardCount = options.flashcard_count || parseInt(flashcardCountSelect.value || 10);
        const quizCount = options.quiz_count || parseInt(quizCountSelect.value || 5);

        // UI Loading state
        const actionButtons = [
            generateFlashcardsCustomBtn,
            generateQuizCustomBtn,
            generateNotesBtn,
            generateTopicsBtn,
            regenerateNotesBtn
        ].filter(Boolean);

        actionButtons.forEach(btn => {
            btn.disabled = true;
            btn.dataset.origHtml = btn.innerHTML;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Generating...`;
        });

        try {
            const resp = await fetch(`/api/documents/${docId}/study-materials/generate/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    force: force,
                    flashcard_count: flashcardCount,
                    quiz_count: quizCount
                })
            });

            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.error || 'Failed to generate study materials.');
            }

            studyState = {
                loadedDocId: docId,
                flashcards: data.flashcards || [],
                short_notes: data.short_notes || {},
                important_topics: data.important_topics || [],
                quiz: data.quiz || []
            };

            renderAllStudyFeatures();

        } catch (err) {
            alert('Study material generation error: ' + err.message);
        } finally {
            actionButtons.forEach(btn => {
                btn.disabled = false;
                if (btn.dataset.origHtml) btn.innerHTML = btn.dataset.origHtml;
            });
        }
    }

    // Bind custom count generate buttons
    if (generateFlashcardsCustomBtn) {
        generateFlashcardsCustomBtn.addEventListener('click', () => {
            triggerGenerateStudyMaterials(true, { flashcard_count: parseInt(flashcardCountSelect.value) });
        });
    }

    if (generateQuizCustomBtn) {
        generateQuizCustomBtn.addEventListener('click', () => {
            generateFreshQuiz(true);
        });
    }

    if (refreshQuizBtn) {
        refreshQuizBtn.addEventListener('click', () => {
            generateFreshQuiz(true);
        });
    }

    if (generateNotesBtn) generateNotesBtn.addEventListener('click', () => triggerGenerateStudyMaterials(true));
    if (regenerateNotesBtn) regenerateNotesBtn.addEventListener('click', () => triggerGenerateStudyMaterials(true));
    if (generateTopicsBtn) generateTopicsBtn.addEventListener('click', () => triggerGenerateStudyMaterials(true));

    // =========================================================================
    // 6. Interactive Flashcard Deck Controller
    // =========================================================================
    function renderActiveFlashcard() {
        const cards = studyState.flashcards;
        if (!cards || cards.length === 0) return;

        if (flashcardIndex >= cards.length) flashcardIndex = 0;
        if (flashcardIndex < 0) flashcardIndex = cards.length - 1;

        const card = cards[flashcardIndex];
        flashcardQuestion.textContent = card.front;
        flashcardAnswer.textContent = card.back;
        flashcardCategoryBadge.textContent = card.category || 'Core Concept';
        flashcardCounter.textContent = `Card ${flashcardIndex + 1} of ${cards.length}`;

        flashcardInner.classList.remove('flipped');

        const pct = Math.round(((flashcardIndex + 1) / cards.length) * 100);
        flashcardProgressBar.style.width = `${pct}%`;
    }

    function toggleFlashcardFlip() {
        flashcardInner.classList.toggle('flipped');
    }

    flashcardInner.addEventListener('click', toggleFlashcardFlip);
    flipFlashcardBtn.addEventListener('click', toggleFlashcardFlip);

    nextFlashcardBtn.addEventListener('click', function () {
        flashcardIndex++;
        renderActiveFlashcard();
    });

    prevFlashcardBtn.addEventListener('click', function () {
        flashcardIndex--;
        renderActiveFlashcard();
    });

    shuffleFlashcardsBtn.addEventListener('click', function () {
        const arr = studyState.flashcards;
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        flashcardIndex = 0;
        renderActiveFlashcard();
    });

    // Keyboard navigation
    document.addEventListener('keydown', function (e) {
        const flashcardsPane = document.getElementById('view-flashcards');
        if (!flashcardsPane || !flashcardsPane.classList.contains('active')) return;
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;

        if (e.code === 'Space') {
            e.preventDefault();
            toggleFlashcardFlip();
        } else if (e.code === 'ArrowRight') {
            e.preventDefault();
            flashcardIndex++;
            renderActiveFlashcard();
        } else if (e.code === 'ArrowLeft') {
            e.preventDefault();
            flashcardIndex--;
            renderActiveFlashcard();
        }
    });

    // =========================================================================
    // 7. Short Notes & Cheat Sheet Controller (Enhanced)
    // =========================================================================
    function renderShortNotes() {
        const notes = studyState.short_notes;
        if (!notes) return;

        if (notesTitleDisplay) notesTitleDisplay.textContent = notes.title || activeDocTitle.textContent;
        if (notesReadTimeBadge) notesReadTimeBadge.textContent = notes.read_time || '4 min read';
        notesSummaryText.textContent = notes.summary || 'Summary not available.';

        // Key Takeaways
        let takeawaysHtml = '';
        (notes.key_takeaways || []).forEach(item => {
            takeawaysHtml += `
                <li class="note-takeaway-item">
                    <i class="bi bi-check-circle-fill text-success fs-6 mt-1 flex-shrink-0"></i>
                    <span>${escapeHtml(item)}</span>
                </li>
            `;
        });
        notesTakeawaysList.innerHTML = takeawaysHtml;

        // Glossary / Key Definitions
        if (notes.glossary && notes.glossary.length > 0) {
            notesGlossaryCard.classList.remove('d-none');
            let glossaryHtml = '';
            notes.glossary.forEach(g => {
                glossaryHtml += `
                    <div class="col-md-6">
                        <div class="glossary-item-card">
                            <strong class="text-primary small d-block mb-1">${escapeHtml(g.term)}</strong>
                            <span class="text-secondary small">${escapeHtml(g.definition)}</span>
                        </div>
                    </div>
                `;
            });
            notesGlossaryContainer.innerHTML = glossaryHtml;
        } else {
            notesGlossaryCard.classList.add('d-none');
        }

        // Structured Sections
        let sectionsHtml = '';
        (notes.sections || []).forEach(sec => {
            let pointsHtml = '';
            (sec.points || []).forEach(p => {
                pointsHtml += `<li class="mb-2"><i class="bi bi-caret-right-fill text-primary small me-1"></i> ${escapeHtml(p)}</li>`;
            });

            sectionsHtml += `
                <div class="card border-0 shadow-sm mb-3 bg-white rounded-3">
                    <div class="card-body p-3">
                        <h6 class="fw-bold text-dark mb-1">${escapeHtml(sec.heading)}</h6>
                        ${sec.summary ? `<p class="text-muted small mb-2">${escapeHtml(sec.summary)}</p>` : ''}
                        <ul class="list-unstyled mb-0 small text-secondary">
                            ${pointsHtml}
                        </ul>
                    </div>
                </div>
            `;
        });
        notesSectionsContainer.innerHTML = sectionsHtml;

        // Conclusions
        if (notes.conclusions && notes.conclusions.length > 0) {
            notesConclusionsCard.classList.remove('d-none');
            let conclusionsHtml = '';
            notes.conclusions.forEach(c => {
                conclusionsHtml += `
                    <li class="note-takeaway-item">
                        <i class="bi bi-arrow-right-circle-fill text-warning fs-6 mt-1 flex-shrink-0"></i>
                        <span>${escapeHtml(c)}</span>
                    </li>
                `;
            });
            notesConclusionsList.innerHTML = conclusionsHtml;
        } else {
            notesConclusionsCard.classList.add('d-none');
        }
    }

    copyNotesBtn.addEventListener('click', function () {
        const notes = studyState.short_notes;
        if (!notes) return;

        let markdown = `# ${notes.title || activeDocTitle.textContent}\n\n`;
        markdown += `> **Read Time:** ${notes.read_time || '4 min read'}\n\n`;
        markdown += `## Executive Summary\n${notes.summary}\n\n`;

        markdown += `## Key Takeaways\n`;
        (notes.key_takeaways || []).forEach(k => { markdown += `- ${k}\n`; });
        markdown += `\n`;

        if (notes.glossary && notes.glossary.length > 0) {
            markdown += `## Key Terminology\n`;
            notes.glossary.forEach(g => { markdown += `- **${g.term}**: ${g.definition}\n`; });
            markdown += `\n`;
        }

        (notes.sections || []).forEach(sec => {
            markdown += `### ${sec.heading}\n`;
            if (sec.summary) markdown += `${sec.summary}\n\n`;
            (sec.points || []).forEach(p => { markdown += `- ${p}\n`; });
            markdown += `\n`;
        });

        if (notes.conclusions && notes.conclusions.length > 0) {
            markdown += `## Practical Conclusions\n`;
            notes.conclusions.forEach(c => { markdown += `- ${c}\n`; });
            markdown += `\n`;
        }

        navigator.clipboard.writeText(markdown).then(() => {
            const originalText = copyNotesBtn.innerHTML;
            copyNotesBtn.className = 'btn btn-success btn-sm fw-semibold';
            copyNotesBtn.innerHTML = `<i class="bi bi-check-lg me-1"></i> Copied to Clipboard!`;
            setTimeout(() => {
                copyNotesBtn.className = 'btn btn-outline-success btn-sm fw-semibold';
                copyNotesBtn.innerHTML = originalText;
            }, 2500);
        });
    });

    // =========================================================================
    // 8. Important Topics Controller
    // =========================================================================
    function renderImportantTopics() {
        const topics = studyState.important_topics;
        if (!topics || topics.length === 0) return;

        let html = '';
        topics.forEach((topic) => {
            let badgeClass = 'bg-primary-subtle text-primary border-primary-subtle';
            const imp = (topic.importance || '').toLowerCase();
            if (imp.includes('crucial')) {
                badgeClass = 'bg-danger-subtle text-danger border-danger-subtle';
            } else if (imp.includes('high')) {
                badgeClass = 'bg-warning-subtle text-warning border-warning-subtle';
            }

            let pointsHtml = '';
            (topic.key_points || []).forEach(pt => {
                pointsHtml += `<li class="mb-1 text-secondary small"><i class="bi bi-check2 text-primary me-1"></i> ${escapeHtml(pt)}</li>`;
            });

            html += `
                <div class="col-md-6">
                    <div class="topic-card shadow-sm rounded-3">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <h6 class="fw-bold mb-0 text-dark">${escapeHtml(topic.title)}</h6>
                            <span class="badge ${badgeClass} border small">${escapeHtml(topic.importance || 'High')}</span>
                        </div>
                        <p class="text-muted small mb-2" style="line-height: 1.55;">${escapeHtml(topic.overview)}</p>
                        <ul class="list-unstyled mb-0 border-top pt-2 mt-2">
                            ${pointsHtml}
                        </ul>
                    </div>
                </div>
            `;
        });

        topicsGridContainer.innerHTML = html;
    }

    // =========================================================================
    // 9. Interactive Quiz Test Controller (Fresh Generation & Weak Topic Analysis)
    // =========================================================================
    function renderQuiz(gradedQuestions = null) {
        const questions = gradedQuestions || studyState.quiz;
        if (!questions || questions.length === 0) return;

        let html = '';
        questions.forEach((q, qIdx) => {
            const userChoice = quizUserAnswers[q.id];
            const difficultyBadge = q.difficulty ? `<span class="badge bg-secondary-subtle text-secondary border small text-capitalize">${escapeHtml(q.difficulty)}</span>` : '';
            const topicBadge = q.topic ? `<span class="badge bg-primary-subtle text-primary border border-primary-subtle small"><i class="bi bi-tag-fill me-1"></i>${escapeHtml(q.topic)}</span>` : '';

            let optionsHtml = '';
            q.options.forEach((opt, optIdx) => {
                let optionClass = '';
                let feedbackIcon = '';

                if (isQuizSubmitted) {
                    if (optIdx === q.correct_index) {
                        optionClass = 'is-correct';
                        feedbackIcon = `<i class="bi bi-check-circle-fill text-success ms-auto fs-5"></i>`;
                    } else if (userChoice === optIdx) {
                        optionClass = 'is-incorrect';
                        feedbackIcon = `<i class="bi bi-x-circle-fill text-danger ms-auto fs-5"></i>`;
                    }
                } else if (userChoice === optIdx) {
                    optionClass = 'selected';
                }

                optionsHtml += `
                    <label class="quiz-option-label ${optionClass}" data-q-id="${q.id}" data-opt-idx="${optIdx}">
                        <input type="radio" name="question_${q.id}" value="${optIdx}" ${userChoice === optIdx ? 'checked' : ''} ${isQuizSubmitted ? 'disabled' : ''} class="form-check-input mt-0 me-2">
                        <span class="flex-grow-1">${escapeHtml(opt)}</span>
                        ${feedbackIcon}
                    </label>
                `;
            });

            let explanationHtml = '';
            if (isQuizSubmitted && q.explanation) {
                explanationHtml = `
                    <div class="quiz-explanation-box mt-3">
                        <div class="d-flex align-items-center gap-1 mb-1 text-primary fw-semibold small">
                            <i class="bi bi-info-circle-fill"></i>
                            <span>Document Evidence & Explanation:</span>
                        </div>
                        <div class="text-secondary small" style="line-height: 1.6;">${escapeHtml(q.explanation)}</div>
                    </div>
                `;
            }

            html += `
                <div class="quiz-question-card bg-white shadow-sm rounded-3 p-3 mb-3 border" id="quizCard_${q.id}">
                    <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-light text-dark border small fw-bold">Question ${qIdx + 1} of ${questions.length}</span>
                            ${topicBadge}
                        </div>
                        <div>
                            ${difficultyBadge}
                        </div>
                    </div>
                    <h6 class="fw-bold text-dark mb-3" style="line-height: 1.5;">${escapeHtml(q.question)}</h6>
                    <div class="quiz-options-group d-flex flex-column gap-2">
                        ${optionsHtml}
                    </div>
                    ${explanationHtml}
                </div>
            `;
        });

        quizQuestionsContainer.innerHTML = html;

        if (!isQuizSubmitted) {
            document.querySelectorAll('.quiz-option-label').forEach(label => {
                label.addEventListener('click', function () {
                    const qId = parseInt(this.getAttribute('data-q-id'));
                    const optIdx = parseInt(this.getAttribute('data-opt-idx'));

                    quizUserAnswers[qId] = optIdx;

                    const parentCard = document.getElementById(`quizCard_${qId}`);
                    parentCard.querySelectorAll('.quiz-option-label').forEach(l => l.classList.remove('selected'));
                    this.classList.add('selected');
                });
            });
        }
    }

    async function generateFreshQuiz(force = true, customOptions = {}) {
        const docId = activeDocumentIdInput.value;
        if (!docId) {
            alert('Please select or upload a document first.');
            return;
        }

        const count = customOptions.count || parseInt(quizCountSelect.value || 5);
        const difficulty = customOptions.difficulty || quizDifficultySelect.value || 'mixed';
        const topic = customOptions.topic !== undefined ? customOptions.topic : (quizTopicSelect.value || 'all');

        // UI Loading state
        quizLoadingContainer.classList.remove('d-none');
        quizWorkspace.classList.add('d-none');
        quizPlaceholder.classList.add('d-none');
        generateQuizCustomBtn.disabled = true;
        refreshQuizBtn.disabled = true;

        if (quizLoadingStatus) {
            quizLoadingStatus.textContent = `Synthesizing ${count} fresh questions (${difficulty.toUpperCase()}) on ${topic === 'all' ? 'document topics' : topic}...`;
        }

        try {
            const resp = await fetch(`/api/documents/${docId}/quiz/generate/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    count: count,
                    difficulty: difficulty,
                    topic: topic
                })
            });

            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.error || 'Failed to generate fresh quiz.');
            }

            studyState.quiz = data.quiz;
            quizUserAnswers = {};
            isQuizSubmitted = false;

            if (quizBadge) {
                quizBadge.textContent = `${data.quiz.length} Qs`;
                quizBadge.classList.remove('d-none');
            }

            if (quizAttemptTitle) {
                const topicLabel = topic !== 'all' ? ` - ${topic}` : '';
                quizAttemptTitle.textContent = `Quiz (${difficulty.toUpperCase()}${topicLabel})`;
            }

            quizResultsDashboard.classList.add('d-none');
            quizScoreBadge.classList.add('d-none');
            submitQuizBtn.disabled = false;
            submitQuizBtn.innerHTML = `<i class="bi bi-check-all me-1"></i> Submit Quiz & Analyze Performance`;

            renderQuiz();

            quizLoadingContainer.classList.add('d-none');
            quizWorkspace.classList.remove('d-none');
            quizWorkspace.scrollIntoView({ behavior: 'smooth' });

        } catch (err) {
            alert('Quiz Generation Error: ' + err.message);
            quizLoadingContainer.classList.add('d-none');
            if (studyState.quiz && studyState.quiz.length > 0) {
                quizWorkspace.classList.remove('d-none');
            } else {
                quizPlaceholder.classList.remove('d-none');
            }
        } finally {
            generateQuizCustomBtn.disabled = false;
            refreshQuizBtn.disabled = false;
        }
    }

    async function submitQuizAndAnalyze() {
        const questions = studyState.quiz;
        if (!questions || questions.length === 0) return;

        const answeredCount = Object.keys(quizUserAnswers).length;
        if (answeredCount < questions.length) {
            if (!confirm(`You have answered ${answeredCount} of ${questions.length} questions. Submit anyway?`)) {
                return;
            }
        }

        const docId = activeDocumentIdInput.value;
        if (!docId) return;

        submitQuizBtn.disabled = true;
        submitQuizBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Analyzing Answers...`;

        try {
            const resp = await fetch(`/api/documents/${docId}/quiz/submit/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    questions: questions,
                    user_answers: quizUserAnswers,
                    difficulty: quizDifficultySelect.value,
                    target_topic: quizTopicSelect.value !== 'all' ? quizTopicSelect.value : ''
                })
            });

            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.error || 'Failed to submit quiz.');
            }

            isQuizSubmitted = true;

            // Re-render questions with answer indicators and explanations
            renderQuiz(data.graded_questions);

            // Render Overall Score Banner & SkyLearn Star Achievement
            resultsScoreTitle.textContent = `${data.percentage.toFixed(0)}%`;
            const resultsScoreHeadline = document.getElementById('resultsScoreHeadline');
            if (resultsScoreHeadline) {
                if (data.percentage === 100) {
                    resultsScoreHeadline.textContent = "Outstanding mastery! You earned 3 Gold Stars! 🌟";
                    resultsScoreHeadline.className = "fw-bold text-leaf-deep mb-1";
                } else if (data.percentage >= 70) {
                    resultsScoreHeadline.textContent = "Great job! You passed with flying colors! 🚀";
                    resultsScoreHeadline.className = "fw-bold text-sky-deep mb-1";
                } else {
                    resultsScoreHeadline.textContent = "Good effort! Let's review the topics below and try again! 💪";
                    resultsScoreHeadline.className = "fw-bold text-coral-deep mb-1";
                }
            }

            // Update Star Row
            const star1 = document.getElementById('star1');
            const star2 = document.getElementById('star2');
            const star3 = document.getElementById('star3');
            if (star1 && star2 && star3) {
                star1.className = 'bi bi-star-fill star-icon';
                if (data.percentage === 100) {
                    star2.className = 'bi bi-star-fill star-icon';
                    star3.className = 'bi bi-star-fill star-icon';
                } else if (data.percentage >= 70) {
                    star2.className = 'bi bi-star-fill star-icon';
                    star3.className = 'bi bi-star-fill star-icon dimmed';
                } else {
                    star2.className = 'bi bi-star-fill star-icon dimmed';
                    star3.className = 'bi bi-star-fill star-icon dimmed';
                }
            }

            resultsScoreSubtitle.textContent = `${data.score} of ${data.total_questions} questions correct (${quizDifficultySelect.value.toUpperCase()} difficulty)`;
            resultsProgressBar.style.width = `${data.percentage}%`;
            resultsProgressBar.className = `progress-bar ${data.percentage >= 70 ? 'bg-success' : (data.percentage >= 50 ? 'bg-warning' : 'bg-danger')}`;

            // Historical progress delta badge
            let deltaHtml = '';
            if (data.delta !== null && data.delta !== undefined) {
                if (data.delta > 0) {
                    deltaHtml = `<span class="badge bg-leaf-soft text-leaf-deep border-0 p-2"><i class="bi bi-graph-up-arrow me-1"></i> +${data.delta}% improvement from last attempt</span>`;
                } else if (data.delta < 0) {
                    deltaHtml = `<span class="badge bg-coral-soft text-coral-deep border-0 p-2"><i class="bi bi-graph-down-arrow me-1"></i> ${data.delta}% vs last attempt</span>`;
                } else {
                    deltaHtml = `<span class="badge bg-surface text-ink-muted border p-2"><i class="bi bi-dash me-1"></i> Same score as last attempt</span>`;
                }
            } else {
                deltaHtml = `<span class="badge bg-sun-soft text-sun-deep border-0 p-2"><i class="bi bi-flag-fill me-1"></i> First Attempt Recorded</span>`;
            }
            resultsDeltaContainer.innerHTML = deltaHtml;

            // Trigger SkyLearn Celebratory Confetti Burst for quiz completion
            launchConfettiCelebration();

            // Increment streak
            incrementStreak();

            // Render Weak Topics Diagnostics
            const weakTopics = data.weak_topics || [];
            weakTopicsCountBadge.textContent = `${weakTopics.length} Weak Topics`;

            if (weakTopics.length > 0) {
                let weakHtml = '';
                weakTopics.forEach(wt => {
                    weakHtml += `
                        <div class="weak-topic-item d-flex flex-wrap justify-content-between align-items-center gap-2">
                            <div>
                                <div class="d-flex align-items-center gap-2">
                                    <strong class="text-danger">${escapeHtml(wt.topic)}</strong>
                                    <span class="badge bg-danger-subtle text-danger border border-danger-subtle small">${wt.accuracy.toFixed(0)}% Accuracy (${wt.correct}/${wt.total})</span>
                                </div>
                                <div class="text-muted small mt-1">${escapeHtml(wt.reason)}</div>
                                <div class="text-secondary small mt-1"><i class="bi bi-lightbulb-fill text-warning me-1"></i> ${escapeHtml(wt.recommendation)}</div>
                            </div>
                            <div>
                                <button type="button" class="btn btn-outline-danger btn-sm practice-weak-topic-btn fw-semibold shadow-sm" data-topic="${escapeHtml(wt.topic)}">
                                    <i class="bi bi-play-circle-fill me-1"></i> Practice This Topic
                                </button>
                            </div>
                        </div>
                    `;
                });
                quizWeakTopicsList.innerHTML = weakHtml;
            } else {
                quizWeakTopicsList.innerHTML = `
                    <div class="alert alert-success py-2 px-3 small mb-0 d-flex align-items-center gap-2">
                        <i class="bi bi-check-circle-fill text-success fs-6"></i>
                        <span>Outstanding! No topics fell below the 60% accuracy threshold in this attempt.</span>
                    </div>
                `;
            }

            // Render Topic-Wise Performance Breakdown
            const topicScores = data.topic_scores || {};
            let topicBreakdownHtml = '';
            for (const [tName, tData] of Object.entries(topicScores)) {
                const acc = tData.percentage || 0;
                let barColor = 'bg-success';
                let badgeColor = 'text-success border-success-subtle bg-success-subtle';
                if (acc < 60) {
                    barColor = 'bg-danger';
                    badgeColor = 'text-danger border-danger-subtle bg-danger-subtle';
                } else if (acc < 75) {
                    barColor = 'bg-warning';
                    badgeColor = 'text-warning border-warning-subtle bg-warning-subtle';
                }

                topicBreakdownHtml += `
                    <div class="topic-score-row">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="fw-semibold small text-dark">${escapeHtml(tName)}</span>
                            <span class="badge ${badgeColor} border small">${acc.toFixed(0)}% (${tData.correct}/${tData.total})</span>
                        </div>
                        <div class="progress rounded-pill" style="height: 6px;">
                            <div class="progress-bar ${barColor}" style="width: ${acc}%;"></div>
                        </div>
                    </div>
                `;
            }
            quizTopicScoresContainer.innerHTML = topicBreakdownHtml || '<div class="text-muted small">No topic breakdown available.</div>';

            // Render Actionable Recommendations
            let recsHtml = '';
            (data.recommendations || []).forEach(rec => {
                recsHtml += `
                    <li class="d-flex align-items-start gap-2 mb-2">
                        <i class="bi bi-arrow-right-circle-fill text-primary mt-1"></i>
                        <span>${escapeHtml(rec)}</span>
                    </li>
                `;
            });
            quizRecommendationsList.innerHTML = recsHtml;

            // Render Attempt History Trajectory
            const history = data.history || [];
            if (history.length > 0) {
                let histHtml = `
                    <div class="table-responsive">
                        <table class="table table-sm table-borderless align-middle mb-0 small">
                            <thead>
                                <tr class="text-muted border-bottom">
                                    <th>Date</th>
                                    <th>Difficulty</th>
                                    <th>Topic</th>
                                    <th>Score</th>
                                    <th>Accuracy</th>
                                    <th>Weak Topics</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                history.forEach(h => {
                    const accBadge = h.percentage >= 70 ? 'bg-success-subtle text-success' : (h.percentage >= 50 ? 'bg-warning-subtle text-warning' : 'bg-danger-subtle text-danger');
                    histHtml += `
                        <tr class="border-bottom">
                            <td>${escapeHtml(h.created_at)}</td>
                            <td><span class="badge bg-light text-secondary border text-capitalize">${escapeHtml(h.difficulty)}</span></td>
                            <td class="text-truncate" style="max-width: 140px;" title="${escapeHtml(h.target_topic)}">${escapeHtml(h.target_topic)}</td>
                            <td><strong>${h.score}</strong> / ${h.total_questions}</td>
                            <td><span class="badge ${accBadge} border">${h.percentage.toFixed(0)}%</span></td>
                            <td>${h.weak_count > 0 ? `<span class="badge bg-danger-subtle text-danger border">${h.weak_count} weak</span>` : '<span class="text-success"><i class="bi bi-check-lg"></i> None</span>'}</td>
                        </tr>
                    `;
                });
                histHtml += `</tbody></table></div>`;
                quizHistoryContainer.innerHTML = histHtml;
            } else {
                quizHistoryContainer.innerHTML = '<div class="text-muted small">No prior attempt history.</div>';
            }

            // Show results dashboard
            quizResultsDashboard.classList.remove('d-none');
            quizScoreBadge.textContent = `Score: ${data.score} / ${data.total_questions} (${data.percentage.toFixed(0)}%)`;
            quizScoreBadge.className = data.percentage >= 70
                ? 'badge bg-success-subtle text-success border border-success-subtle px-3 py-2 fs-6'
                : 'badge bg-warning-subtle text-warning border border-warning-subtle px-3 py-2 fs-6';
            quizScoreBadge.classList.remove('d-none');

            submitQuizBtn.disabled = true;
            submitQuizBtn.innerHTML = `<i class="bi bi-check2-all me-1"></i> Attempt Submitted & Evaluated`;

            // Bind Practice Weak Topic buttons
            document.querySelectorAll('.practice-weak-topic-btn').forEach(btn => {
                btn.addEventListener('click', function () {
                    const topicToPractice = this.getAttribute('data-topic');
                    if (topicToPractice) {
                        let foundOption = false;
                        for (let opt of quizTopicSelect.options) {
                            if (opt.value === topicToPractice) {
                                opt.selected = true;
                                foundOption = true;
                                break;
                            }
                        }
                        if (!foundOption) {
                            const newOpt = document.createElement('option');
                            newOpt.value = topicToPractice;
                            newOpt.textContent = topicToPractice;
                            newOpt.selected = true;
                            quizTopicSelect.appendChild(newOpt);
                        }
                        generateFreshQuiz(true, { topic: topicToPractice });
                    }
                });
            });

            quizResultsDashboard.scrollIntoView({ behavior: 'smooth' });

        } catch (err) {
            alert('Quiz Evaluation Error: ' + err.message);
            submitQuizBtn.disabled = false;
            submitQuizBtn.innerHTML = `<i class="bi bi-check-all me-1"></i> Submit Quiz & Analyze Performance`;
        }
    }

    submitQuizBtn.addEventListener('click', submitQuizAndAnalyze);

    resetQuizBtn.addEventListener('click', function () {
        quizUserAnswers = {};
        isQuizSubmitted = false;
        quizResultsDashboard.classList.add('d-none');
        quizScoreBadge.classList.add('d-none');
        submitQuizBtn.disabled = false;
        submitQuizBtn.innerHTML = `<i class="bi bi-check-all me-1"></i> Submit Quiz & Analyze Performance`;
        renderQuiz();
    });

    // =========================================================================
    // 10. SkyLearn Interactive Tools & Accessibility System
    // =========================================================================

    // Text-to-Speech Accessibility ("Read to Me")
    function speakText(text) {
        if (!('speechSynthesis' in window)) {
            alert('Text-to-speech audio is not supported in this browser.');
            return;
        }
        window.speechSynthesis.cancel();
        if (!text || !text.trim()) return;

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.95; // Calm, clear pace for students
        utterance.pitch = 1.05; // Warm, friendly tone
        window.speechSynthesis.speak(utterance);
    }

    // Audio reader event delegation in chat (with markdown stripped for speech)
    if (chatMessagesContainer) {
        chatMessagesContainer.addEventListener('click', function (e) {
            const btn = e.target.closest('.chat-tts-btn');
            if (btn) {
                const textToSpeak = btn.getAttribute('data-text');
                const cleanText = stripMarkdownForSpeech(textToSpeak ? decodeURIComponent(textToSpeak) : '');
                btn.classList.toggle('speaking');
                speakText(cleanText);
                setTimeout(() => { btn.classList.remove('speaking'); }, 5000);
                return;
            }

            // Copy code snippet button
            const copyCodeBtn = e.target.closest('.btn-copy-code');
            if (copyCodeBtn) {
                const wrapper = copyCodeBtn.closest('.code-block-wrapper');
                const codeEl = wrapper ? wrapper.querySelector('pre code') : null;
                if (codeEl) {
                    navigator.clipboard.writeText(codeEl.innerText).then(() => {
                        copyCodeBtn.innerHTML = '<i class="bi bi-check2 text-success"></i> <span>Copied!</span>';
                        setTimeout(() => {
                            copyCodeBtn.innerHTML = '<i class="bi bi-clipboard"></i> <span>Copy</span>';
                        }, 2000);
                    });
                }
                return;
            }

            // Copy full AI response button
            const copyRespBtn = e.target.closest('.btn-copy-response');
            if (copyRespBtn) {
                const raw = copyRespBtn.getAttribute('data-raw');
                const textToCopy = raw ? decodeURIComponent(raw) : '';
                if (textToCopy) {
                    navigator.clipboard.writeText(textToCopy).then(() => {
                        copyRespBtn.innerHTML = '<i class="bi bi-check2 text-leaf"></i> <span>Copied!</span>';
                        setTimeout(() => {
                            copyRespBtn.innerHTML = '<i class="bi bi-clipboard"></i> <span>Copy</span>';
                        }, 2000);
                    });
                }
                return;
            }
        });
    }

    // Flashcard speech button
    const readFlashcardBtn = document.getElementById('readFlashcardBtn');
    if (readFlashcardBtn) {
        readFlashcardBtn.addEventListener('click', function () {
            const cards = studyState.flashcards;
            if (cards && cards.length > flashcardIndex) {
                const activeCard = cards[flashcardIndex];
                speakText(`Question: ${activeCard.front}. Answer: ${activeCard.back}`);
            }
        });
    }

    // Notes speech button
    const readNotesBtn = document.getElementById('readNotesBtn');
    if (readNotesBtn) {
        readNotesBtn.addEventListener('click', function () {
            const notes = studyState.short_notes;
            if (notes && notes.summary) {
                const takeaways = (notes.key_takeaways || []).join('. ');
                speakText(`Executive Summary: ${notes.summary}. Key Takeaways: ${takeaways}`);
            }
        });
    }

    // Dyslexia-Friendly Reading Ruler
    let isReadingRulerActive = false;
    const readingRuler = document.getElementById('skylearnReadingRuler');
    const readingRulerToggleBtn = document.getElementById('readingRulerToggleBtn');

    if (readingRulerToggleBtn && readingRuler) {
        readingRulerToggleBtn.addEventListener('click', function () {
            isReadingRulerActive = !isReadingRulerActive;
            this.classList.toggle('active', isReadingRulerActive);
            readingRuler.classList.toggle('d-none', !isReadingRulerActive);
        });

        document.addEventListener('mousemove', function (e) {
            if (isReadingRulerActive) {
                readingRuler.style.top = `${e.clientY - 18}px`;
            }
        });
    }

    // High Contrast Accessibility Mode Toggle
    const highContrastToggleBtn = document.getElementById('highContrastToggleBtn');
    if (highContrastToggleBtn) {
        const isHighContrast = localStorage.getItem('skylearn_high_contrast') === 'true';
        if (isHighContrast) {
            document.body.classList.add('high-contrast');
            highContrastToggleBtn.classList.add('active');
        }

        highContrastToggleBtn.addEventListener('click', function () {
            const active = document.body.classList.toggle('high-contrast');
            this.classList.toggle('active', active);
            localStorage.setItem('skylearn_high_contrast', active);
        });
    }

    // Audience Mode Switcher (Student vs Teacher/Parent View)
    const studentModeBtn = document.getElementById('studentModeBtn');
    const teacherModeBtn = document.getElementById('teacherModeBtn');
    const parentInsightsCard = document.getElementById('parentInsightsCard');

    function setAudienceMode(mode) {
        if (mode === 'teacher') {
            teacherModeBtn?.classList.add('active');
            studentModeBtn?.classList.remove('active');
            parentInsightsCard?.classList.remove('d-none');
            localStorage.setItem('skylearn_view_mode', 'teacher');
        } else {
            studentModeBtn?.classList.add('active');
            teacherModeBtn?.classList.remove('active');
            parentInsightsCard?.classList.add('d-none');
            localStorage.setItem('skylearn_view_mode', 'student');
        }
    }

    studentModeBtn?.addEventListener('click', () => setAudienceMode('student'));
    teacherModeBtn?.addEventListener('click', () => setAudienceMode('teacher'));
    const savedMode = localStorage.getItem('skylearn_view_mode') || 'student';
    setAudienceMode(savedMode);

    // Interactive Quick Prompt Chips
    document.querySelectorAll('.quick-prompt-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const promptText = this.getAttribute('data-prompt');
            if (promptText && queryInput) {
                queryInput.value = promptText;
                queryForm.dispatchEvent(new Event('submit', { cancelable: true }));
            }
        });
    });

    // Confetti Celebration (1.6s Burst on Quiz Completion)
    function launchConfettiCelebration() {
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }
        const canvas = document.getElementById('skylearnConfettiCanvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const colors = ['#3B82F6', '#FBBF24', '#22C55E', '#A855F7', '#60A5FA', '#FCD34D'];
        const particleCount = 75;
        const particles = [];

        for (let i = 0; i < particleCount; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * -canvas.height * 0.5,
                size: Math.random() * 8 + 6,
                color: colors[Math.floor(Math.random() * colors.length)],
                vx: (Math.random() - 0.5) * 5,
                vy: Math.random() * 3.5 + 3,
                rotation: Math.random() * 360,
                rotationSpeed: (Math.random() - 0.5) * 8
            });
        }

        const startTime = performance.now();
        const duration = 1600; // 1.6s as specified in skylearn-DESIGN.md

        function draw(time) {
            const elapsed = time - startTime;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            particles.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;
                p.rotation += p.rotationSpeed;

                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rotation * Math.PI) / 180);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.65);
                ctx.restore();
            });

            if (elapsed < duration) {
                requestAnimationFrame(draw);
            } else {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
        }

        requestAnimationFrame(draw);
    }

    // Daily Learning Streak Management
    function initStreak() {
        const streak = parseInt(localStorage.getItem('skylearn_streak') || '3');
        const streakElem = document.getElementById('streakCountNumber');
        if (streakElem) streakElem.textContent = streak;
    }

    function incrementStreak() {
        const current = parseInt(localStorage.getItem('skylearn_streak') || '3');
        const next = current + 1;
        localStorage.setItem('skylearn_streak', next.toString());
        const streakElem = document.getElementById('streakCountNumber');
        if (streakElem) {
            streakElem.textContent = next;
            const pill = document.getElementById('streakPill');
            if (pill) {
                pill.style.boxShadow = '0 0 24px rgba(251, 191, 36, 0.7)';
                setTimeout(() => { pill.style.boxShadow = ''; }, 2200);
            }
        }
    }

    // Drag-and-Drop file upload visual feedback
    const uploadDropZone = document.getElementById('uploadDropZone');
    if (uploadDropZone && documentFileInput) {
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadDropZone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
                uploadDropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadDropZone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
                uploadDropZone.classList.remove('dragover');
            }, false);
        });

        uploadDropZone.addEventListener('drop', e => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                documentFileInput.files = files;
            }
        }, false);
    }

    // =========================================================================
    // 11. Initialization
    // =========================================================================
    bindDocumentListEvents();
    initStreak();

    const initialDocId = activeDocumentIdInput.value;
    if (initialDocId) {
        loadDocumentHistory(initialDocId);
        loadStudyMaterials(initialDocId);
    }
});
