# AI-Powered Document Intelligence & Study Assistant (RAG + Gemini + Django)

A full-stack Django web application that allows users to upload PDF and TXT documents, ask natural-language questions, and receive grounded answers backed strictly by document content. Includes a full **AI Study Suite**: **Interactive 3D Flashcards**, **Executive Short Notes**, **Important Topics Extraction**, and **Self-Grading Quiz Tests**.

---

## Features

1. **Document-Grounded Chat (RAG)**: Dense 3072-dimensional vector search with FAISS and strict anti-hallucination grounding with Gemini.
2. **🎴 3D Flip Flashcards**: Interactive active-recall study deck with card flip animation, category tags, counter, and keyboard shortcuts (`Space` to flip, `←`/`→` arrows to navigate).
3. **📝 Short Notes & Cheat Sheet**: Structured executive summary, high-yield bullet takeaways, and thematic section breakdowns with 1-click Markdown clipboard copy.
4. **📌 Important Topics**: Automated extraction of core themes and concepts labeled with `Crucial`, `High`, and `Core Concept` priority badges.
5. **🎯 Interactive Quiz Test**: Multiple-choice assessment with instant answer validation (green/red), live percentage score calculation, and verified document explanations.

```
[User Browser / AJAX]
       │
       ▼
[Django View / Form Validation] ──(File Size & Extension Check)
       │
       ├─► [Text Extraction & Cleaning] (pypdf for PDFs / plain read for TXT)
       ├─► [Overlapping Chunker] (800 chars, 150 overlap)
       ├─► [Gemini Embeddings] (gemini-embedding-001 via Google GenAI)
       ├─► [FAISS Vector Store] (Scoped per document, IndexFlatIP)
       │
[Query Flow]
       │
       ▼
[Embed Query] ──► [FAISS Dense Similarity Search] ──► [Top-K Chunks]
       │
       ▼ (Pass ONLY retrieved chunks as context)
[Gemini Generation] ──(System Instruction for Strict Grounding)──► [Answer + Source Passages]
```

---

## Tech Stack & Vector Store Justification

- **Backend**: Python 3.13, Django 6.1
- **Vector Store**: **FAISS (Facebook AI Similarity Search)**
  - *Justification*:
    1. **Lightweight & High Performance**: FAISS runs in-process with minimal overhead, avoiding the 40+ transitive server dependencies of ChromaDB.
    2. **Document-Scoped Isolation**: Each document has its own dedicated `.faiss` index file, ensuring complete data boundary isolation between documents.
    3. **Normalized Cosine Similarity**: Uses `IndexFlatIP` on L2-normalized Gemini embeddings, producing mathematically exact cosine similarity in the range `[0, 1]`.
    4. **Django ORM Synergy**: Chunk metadata and text are stored in Django's relational database while FAISS accelerates dense similarity search.
- **Generative AI & Embeddings**: Google Gemini API (`gemini-3.5-flash` / `gemini-embedding-001`)
- **Document Processing**: `pypdf` for PDF page extraction, multi-encoding handler for TXT
- **Frontend**: Bootstrap 5, Bootstrap Icons, Vanilla JavaScript (`fetch` / AJAX)

---

## Project Structure

```
doc_intel_rag/
│
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── doc_intel_rag/                  # Django project configuration
│   ├── __init__.py
│   ├── settings.py                 # Settings with django-environ
│   ├── urls.py                     # Root routing
│   ├── wsgi.py
│   └── asgi.py
│
├── rag_assistant/                  # Core RAG Application
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # Document, DocumentChunk, ChatMessage
│   ├── forms.py                    # DocumentUploadForm with validation
│   ├── views.py                    # AJAX upload, query, history, delete
│   ├── urls.py
│   ├── admin.py                    # Django Admin configuration
│   ├── tests.py                    # Unit & integration test suite
│   │
│   ├── rag/                        # Modular RAG subsystem
│   │   ├── __init__.py
│   │   ├── extractor.py            # PDF/TXT extraction & text cleaning
│   │   ├── chunker.py              # Overlapping sliding chunker
│   │   ├── embeddings.py           # Gemini embedding generator
│   │   ├── vector_store.py         # FAISS vector store manager
│   │   ├── retriever.py            # Top-k semantic search & thresholding
│   │   └── generator.py            # Gemini prompt augmentation & generation
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── app.css             # Polished UI styles
│   │   └── js/
│   │       └── app.js              # Fetch/AJAX reactive single-page logic
│   │
│   └── templates/
│       └── rag_assistant/
│           ├── base.html           # Base layout with navbar & status badges
│           └── index.html          # Single-page 3-panel RAG workspace
│
└── media/                          # Upload storage
    ├── documents/                  # Uploaded files
    └── indices/                    # Scoped FAISS .faiss binary files
```

---

## Setup & Running Instructions

### 1. Clone & Set Up Virtual Environment

```bash
cd doc_intel_rag
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and set your Gemini API Key:

```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 4. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Run the Test Suite

```bash
python manage.py test
```

### 6. Start the Development Server

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser.

---

## Key RAG Flow

1. **Upload & Validation**: Validates file extension (`.pdf`, `.txt`) and size limit (10MB).
2. **Text Cleaning & Extraction**: Page-by-page PDF extraction with control-character stripping and paragraph preservation.
3. **Overlapping Chunking**: Splits text into 800-character segments with a 150-character sliding overlap at sentence/paragraph boundaries.
4. **Vector Indexing**: Generates 768-dimensional normalized embeddings via Gemini API and builds a document-scoped `faiss.IndexFlatIP`.
5. **Real Retrieval**: Queries are embedded and evaluated against the FAISS index. If the top similarity score is below `SIMILARITY_THRESHOLD` (0.35), the pipeline rejects the query without calling the LLM.
6. **Strict Grounding**: The LLM prompt is injected *only* with the retrieved top-k passages under a strict system instruction prohibiting hallucinations.
7. **Source Passages**: Every answer displays the exact retrieved passages with chunk index, page number, and similarity score.
