<<<<<<< HEAD
# Egyptian Agricultural Retrieval-Augmented Generation (RAG) System

A modular, production-grade RAG pipeline tailored for Egyptian farmers and agricultural management platforms. The assistant answers farmer inquiries (disease treatment, fertilization, irrigation) in Egyptian farming Arabic (اللهجة الزراعية المصرية), grounded in curated agricultural guides and treatment protocols, while incorporating computer-vision model metadata (crop type, disease label, confidence score).

---

## Architecture Overview

The pipeline consists of six modular, strictly typed stages:

```
[ User Query + Vision Input ]
             │
             ▼
   1. rag/preprocess.py  ──► Normalize Arabic orthography, dialect canonicalization, intent detection
             │
             ▼
   2. rag/ingest.py      ──► Section chunking (guides) & single-unit chunking (treatment protocols)
             │
             ▼
   3. rag/retrieve.py    ──► Parallel Vector (Chroma) + Sparse (BM25) search with RRF (k=60) & Vision boost
             │
             ▼
   4. rag/rerank.py      ──► Metadata filtering (crop/disease/region) & reranking to top-k
             │
             ▼
   5. rag/generate.py    ──► Grounded prompt assembly, provider-agnostic LLM interface, citation extraction
             │
             ▼
   6. rag/respond.py     ──► Confidence threshold branching (needs_agronomist_review) & JSONL logging
```

---

## Stage Specifications

### 1. `preprocess.py`
- **Orthography Normalization**: Unifies Alef variants (`أ`, `إ`, `آ` $\rightarrow$ `ا`), `ى` $\rightarrow$ `ي`, `ة` $\rightarrow$ `ه` at word endings, strips diacritics, and deduplicates repeated characters.
- **Dialect Canonicalization**: Standardizes Egyptian agricultural terms and English code-switched terms via `rag/lexicon.json` (e.g. `"ندوة"` $\rightarrow$ `"لفحة متاخرة"`, `"عفار"` $\rightarrow$ `"كبريت زراعي"`, `"NPK"` $\rightarrow$ `"سماد مركبي NPK"`).
- **Intent Detection**: Classifies queries into `disease_query`, `dosage_lookup`, or `general_advice`.
- **Query Rewrite Fallback**: On low retrieval confidence / unmapped dialect terms, invokes a fast LLM rewrite and logs fallback traces to `logs/fallback_queries.jsonl`.

### 2. `ingest.py`
- **Agricultural Guides**: Split by section/paragraph semantic boundaries (300–500 tokens, ~15% overlap).
- **Treatment Protocols**: Kept intact as single inviolable units per treatment instruction block to prevent partial or hazardous advice.
- **Metadata Tagging**: Tags every chunk with `crop_type`, `disease_name`, `region`, `source_doc`, and `doc_type`.
- **Indexing**: Upserts embeddings to Chroma (via `VectorStoreInterface`) and builds a `rank_bm25` sparse index over the corpus.

### 3. `retrieve.py`
- **VectorStore Abstraction**: Uses `VectorStoreInterface` wrapping `ChromaVectorStore` locally with seamless pluggability for `PineconeVectorStore`.
- **Hybrid Search**: Runs parallel dense vector retrieval (top-20) and sparse BM25 retrieval (top-20).
- **Reciprocal Rank Fusion (RRF)**: Merges ranks with $k=60$:
  $$RRF\_score(d) = \frac{w_{dense}}{60 + r_{dense}(d)} + \frac{w_{sparse}}{60 + r_{sparse}(d)}$$
- **Dynamic Weighting**: Biases BM25 higher ($w=0.7$) for `dosage_lookup` or chemical product codes; biases vector higher ($w=0.7$) for `general_advice`.
- **Vision Model Boosting**: Boosts candidates matching vision model predictions (`crop_type`, `disease_label`, `confidence_score`).

### 4. `rerank.py`
- **Metadata Filtering**: Applies strict or soft filters for crop, disease, and region.
- **Reranking**: Reranks fused candidates down to final top-k (default $k=5$), with optional `sentence-transformers` CrossEncoder support.

### 5. `generate.py`
- **Grounded Prompting**: Instructs LLM to answer strictly from context in Egyptian farming Arabic and cite chunk tags (`[مصدر 1]`, `[مصدر 2]`).
- **Provider-Agnostic LLM Interface**: Implements `LLMProviderInterface` with implementations for `MockLLMProvider`, `OpenAILLMProvider`, and custom models.
- **Confidence Scoring**: Computes normalized retrieval confidence score ($0.0$ to $1.0$).

### 6. `respond.py`
- **Threshold Branching**: Compares retrieval confidence against `confidence.threshold` in `config.yaml` ($0.40$). If below threshold, sets `needs_agronomist_review: true` and appends a warning tag.
- **JSONL Logging**: Records every query request, retrieved chunk IDs, generated response, confidence, and flag status in `logs/requests.jsonl`.

---

## Directory Structure

```
.
├── rag/
│   ├── preprocess.py
│   ├── ingest.py
│   ├── retrieve.py
│   ├── rerank.py
│   ├── generate.py
│   ├── respond.py
│   ├── config.yaml
│   ├── lexicon.json
│   └── tests/
│       ├── test_preprocess.py
│       ├── test_retrieve.py
│       └── test_generate.py
├── example_run.py
├── requirements.txt
└── README.md
```

---

## Installation & Setup

1. **Create and Activate Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Unit Tests**:
   ```bash
   pytest rag/tests/ -v
   ```

4. **Execute End-to-End Sample Run**:
   ```bash
   python example_run.py
   ```
