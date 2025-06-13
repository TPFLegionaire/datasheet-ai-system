# Datasheet AI Comparison System

Transforming the way engineers **collect**, **extract**, **store**, **compare**, and **query** technical specifications from supplier datasheets.

---

## 1. Project Overview

The Datasheet AI Comparison System is a full-stack application that lets you:

| Feature | Description |
|---------|-------------|
| 📤 Upload | Drag-and-drop PDF datasheets. |
| 🤖 Extraction | Extract supplier, part numbers, and key parameters (temperature range, data rate, wavelength, etc.) using real PDF parsing and AI-powered pattern recognition. |
| 🗄 Storage | Persist raw datasheet metadata, variants, and parameters in SQLite. |
| 🔍 Compare | Visually compare a chosen parameter across suppliers/parts with tables and bar charts. |
| 💬 Query | Ask natural-language questions and receive AI answers grounded in your stored data (Mistral API). |

The codebase currently includes **Phase 1** (real PDF extraction + database storage). Subsequent phases will add full AI querying, advanced UI polish, and cloud deployment.

---

## 2. Installation

### Prerequisites
* Python 3.9 +
* `pip` (or `pipx`, `poetry`, etc.)

### Clone & set up
```bash
git clone https://github.com/TPFLegionaire/datasheet-ai-system.git
cd datasheet-ai-system
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

> **Note**  
> `PyMuPDF` depends on system libraries (`libmupdf`). On most Linux/macOS machines it installs automatically via wheels. If build fails, visit PyMuPDF docs for OS-specific steps.

---

## 3. Usage Guide

### 3.1 Command-line test (Phase 1)
```bash
python test_extraction.py path/to/datasheet.pdf --debug
```
This script:
1. extracts structured data,  
2. saves it to `datasheet_system.db`,  
3. shows a verification summary.

### 3.2 Run the Streamlit web app
```bash
streamlit run streamlit_app.py
```
Open `http://localhost:8501` in your browser.

1. **Upload** tab → select one or more PDFs.  
2. Wait for the “✅ Extracted & stored” messages.  
3. Switch to **Compare** tab → choose a parameter to see tables/charts.  
4. (Optional) enter your Mistral API key in the sidebar and try the **Query** tab.

---

## 4. Architecture & Components

```
┌────────────┐       PDF bytes        ┌───────────────┐
│ Streamlit  │ ─────────────────────▶ │  PDFExtractor │
│  Front-end │   drag-&-drop upload   └───────────────┘
│   (UI)     │                       extracted JSON
│            │ ◀─────────────────────┐
└────┬───────┘                        │
     │ DB queries/comparison          ▼
┌────▼────────┐             ┌───────────────────┐
│ Database    │◀────────────│ DatabaseManager   │
│ (SQLite)    │  CRUD ops   └───────────────────┘
└─────────────┘
```

### Key modules

| Module | Purpose |
|--------|---------|
| `pdf_extractor.py` | Uses **PyMuPDF** + regex heuristics to pull text/tables and derive parameters. |
| `database.py`      | All persistence logic—schema creation, inserts, queries, backups. |
| `streamlit_app.py` | User interface, file upload handling, charts, and (future) AI queries. |
| `test_extraction.py` | CLI harness to validate extraction & DB flow. |

### Data model

* **datasheets** – one record per PDF  
* **parameters** – flattened list of every parameter/variant row  
* **parts** – unique part numbers for quick lookup  
* **queries** – log of user NL questions & responses

---

## 5. Development Roadmap

| Phase | Goal | Status |
|-------|------|--------|
| **1** | Real PDF extraction + robust SQLite schema | ✅ Complete |
| **2** | Plug actual Mistral API for extraction fallback & NL Q&A | ⏳ In progress |
| **3** | Batch uploads, better error handling, auth, richer UI filters | ⏳ |
| **4** | Cloud deployment (Streamlit Community Cloud / Docker + FastAPI) | ⏳ |
| **5** | Automated tests, CI/CD, performance tuning on large corpora | ⏳ |

Contributions & issue reports are welcome—see `CONTRIBUTING.md` (to be added).

---

### License
MIT License © 2025 San Francisco AI Factory
