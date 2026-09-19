"""End-to-end RAG response orchestrator with confidence thresholding and request logging."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from rag.generate import OpenAILLMProvider, MockLLMProvider, generate_grounded_answer
from rag.ingest import ingest_text_documents
from rag.pdf_ingest import load_pdfs_to_documents
from rag.preprocess import fallback_llm_rewrite, load_lexicon, log_fallback_query, preprocess_query
from rag.rerank import apply_metadata_filters, rerank_candidates
from rag.retrieve import ChromaVectorStore, hybrid_retrieval

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Orchestrates the 6-stage Egyptian Agricultural RAG pipeline end-to-end."""

    def __init__(self, config_path: str = "rag/config.yaml", lexicon_path: str = "rag/lexicon.json"):
        self.config = self._load_config(config_path)
        self.lexicon = load_lexicon(lexicon_path)

        # Initialize vector store interface and LLM provider
        self.vector_store = ChromaVectorStore(
            collection_name=self.config.get("vector_store", {}).get("collection_name", "egyptian_agriculture"),
            persist_directory=self.config.get("vector_store", {}).get("persist_directory", "./chroma_db"),
        )

        provider = os.getenv("RAG_LLM_PROVIDER", "mock").lower()
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("RAG_LLM_PROVIDER=openai requires OPENAI_API_KEY.")
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.llm_provider = OpenAILLMProvider(api_key=api_key, model_name=model_name)
        elif provider in {"groq", "openrouter"}:
            env_prefix = provider.upper()
            api_key = os.getenv(f"{env_prefix}_API_KEY")
            if not api_key:
                raise RuntimeError(f"RAG_LLM_PROVIDER={provider} requires {env_prefix}_API_KEY.")
            default_model = (
                "llama-3.3-70b-versatile"
                if provider == "groq"
                else "openai/gpt-4o-mini"
            )
            model_name = os.getenv(f"{env_prefix}_MODEL", default_model)
            default_base_url = (
                "https://api.groq.com/openai/v1"
                if provider == "groq"
                else "https://openrouter.ai/api/v1"
            )
            base_url = os.getenv(f"{env_prefix}_BASE_URL", default_base_url)
            self.llm_provider = OpenAILLMProvider(
                api_key=api_key,
                model_name=model_name,
                base_url=base_url,
            )
        elif provider == "mock":
            self.llm_provider = MockLLMProvider()
        else:
            raise ValueError(f"Unsupported RAG_LLM_PROVIDER: {provider}")
        self.bm25_data: Dict[str, Any] = {}

    def _load_config(self, path: str) -> Dict[str, Any]:
        filepath = Path(path)
        if not filepath.exists():
            logger.warning(f"Config file not found at {filepath}. Using default settings.")
            return {
                "confidence": {"threshold": 0.40},
                "retrieval": {"top_k_fused": 20, "rrf_k": 60},
                "rerank": {"top_k": 5, "use_cross_encoder": False},
                "logging": {
                    "requests_log": "logs/requests.jsonl",
                    "fallback_log": "logs/fallback_queries.jsonl",
                },
            }
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def ingest_documents(self, documents: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest knowledge base text documents into vector store and BM25 index."""
        result = ingest_text_documents(documents, self.vector_store, self.config)
        self.bm25_data = result["bm25_data"]
        return result

    def ingest_pdfs(
        self,
        pdf_paths: list[str],
        base_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parse PDF files and ingest extracted documents into the pipeline.

        Args:
            pdf_paths: List of paths to PDF files to ingest.
            base_metadata: Optional metadata overrides (crop_type, region, etc.).

        Returns:
            Summary dict with num_pdfs, num_documents, num_chunks.
        """
        logger.info(f"Loading {len(pdf_paths)} PDF(s) for ingestion...")
        documents = load_pdfs_to_documents(pdf_paths, base_metadata=base_metadata)
        logger.info(f"Extracted {len(documents)} section-documents from PDFs")

        if not documents:
            logger.warning("No documents extracted from the provided PDFs.")
            return {"num_pdfs": len(pdf_paths), "num_documents": 0, "num_chunks": 0}

        result = self.ingest_documents(documents)
        return {
            "num_pdfs": len(pdf_paths),
            "num_documents": result["num_documents"],
            "num_chunks": result["num_chunks"],
        }

    def log_request(
        self,
        query: str,
        retrieved_chunk_ids: list[str],
        answer: str,
        confidence: float,
        needs_review: bool,
        vision_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log request details to logs/requests.jsonl."""
        log_file = self.config.get("logging", {}).get("requests_log", "logs/requests.jsonl")
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "timestamp": time.time(),
            "query": query,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "answer": answer,
            "confidence": confidence,
            "needs_agronomist_review": needs_review,
            "vision_context": vision_context,
        }

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def run(
        self,
        user_query: str,
        vision_context: Optional[Dict[str, Any]] = None,
        crop_filter: Optional[str] = None,
        disease_filter: Optional[str] = None,
        region_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the end-to-end pipeline for a user query."""
        start_time = time.time()

        # Stage 1: Preprocess (Orthography, Lexicon, Intent)
        prep_data = preprocess_query(user_query, self.lexicon, vision_context=vision_context)
        query_text = prep_data["canonical_query"]
        intent = prep_data["intent"]

        # Stage 2: Hybrid Retrieval (Vector + BM25 + RRF + Vision metadata boost)
        fused_candidates = hybrid_retrieval(
            query=query_text,
            vector_store=self.vector_store,
            bm25_data=self.bm25_data,
            intent=intent,
            vision_context=vision_context,
            top_k=self.config.get("retrieval", {}).get("top_k_fused", 20),
            config=self.config,
        )

        # Stage 3: Reranking & Metadata Filtering
        crop_target = crop_filter or (vision_context.get("crop_type") if vision_context else None)
        disease_target = disease_filter or (vision_context.get("disease_label") if vision_context else None)

        filtered_candidates = apply_metadata_filters(
            fused_candidates, crop=crop_target, disease=disease_target, region=region_filter
        )

        top_k = self.config.get("rerank", {}).get("top_k", 5)
        use_ce = self.config.get("rerank", {}).get("use_cross_encoder", False)
        final_chunks = rerank_candidates(
            filtered_candidates, query=query_text, top_k=top_k, use_cross_encoder=use_ce, config=self.config
        )

        # Stage 4: Grounded Generation
        gen_result = generate_grounded_answer(query_text, final_chunks, self.llm_provider, self.config)
        confidence = gen_result["retrieval_confidence"]
        threshold = self.config.get("confidence", {}).get("threshold", 0.40)

        # Fallback Check: If empty lexicon match & low confidence, attempt LLM query rewrite once
        if confidence < threshold and not prep_data["metadata"]["has_lexicon_matches"]:
            rewritten_query = fallback_llm_rewrite(user_query, self.llm_provider)
            log_fallback_query(user_query, rewritten_query)

            # Retry retrieval once with rewritten query
            fused_candidates_fallback = hybrid_retrieval(
                query=rewritten_query,
                vector_store=self.vector_store,
                bm25_data=self.bm25_data,
                intent=intent,
                vision_context=vision_context,
                top_k=self.config.get("retrieval", {}).get("top_k_fused", 20),
                config=self.config,
            )
            final_chunks_fallback = rerank_candidates(
                fused_candidates_fallback, query=rewritten_query, top_k=top_k, config=self.config
            )
            fallback_gen = generate_grounded_answer(rewritten_query, final_chunks_fallback, self.llm_provider, self.config)

            # Accept fallback if it improved confidence
            if fallback_gen["retrieval_confidence"] > confidence:
                gen_result = fallback_gen
                confidence = gen_result["retrieval_confidence"]
                final_chunks = final_chunks_fallback

        # Stage 5: Response Formatting & Threshold Branching
        needs_review = confidence < threshold
        answer_output = gen_result["answer"]
        if needs_review:
            answer_output += "\n\n⚠️ تذكير: نتيجة لمستوى الثقة المنخفض في مطابقة البيانات، يتطلب هذا الطلب مراجعة المهندس الزراعي قبل التنفيذ."

        retrieved_chunk_ids = [c.get("chunk_id", "") for c in final_chunks]

        # Stage 6: Request Logging
        self.log_request(
            query=user_query,
            retrieved_chunk_ids=retrieved_chunk_ids,
            answer=answer_output,
            confidence=confidence,
            needs_review=needs_review,
            vision_context=vision_context,
        )

        latency = time.time() - start_time

        return {
            "query": user_query,
            "processed_query": query_text,
            "intent": intent,
            "answer": answer_output,
            "citations": gen_result["citations"],
            "retrieval_confidence": confidence,
            "needs_agronomist_review": needs_review,
            "vision_context_used": vision_context,
            "latency_seconds": round(latency, 4),
        }
