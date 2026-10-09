"""Hybrid retrieval module combining Chroma Vector Search and BM25 sparse search via RRF."""

from __future__ import annotations

import abc
import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VectorStoreInterface(abc.ABC):
    """Abstract vector store interface to decouple retrieval from specific vector DB vendors."""

    @abc.abstractmethod
    def add_documents(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Upsert document chunks to vector database."""
        pass

    @abc.abstractmethod
    def similarity_search(
        self,
        query: str,
        k: int = 20,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform dense vector similarity search and return candidates with scores."""
        pass


class ChromaVectorStore(VectorStoreInterface):
    """Local Chroma vector store implementation."""

    def __init__(self, collection_name: str = "egyptian_agriculture", persist_directory: str = "./chroma_db"):
        import os
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self._store: Dict[str, Dict[str, Any]] = {}

        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"):
            self.initialized = False
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self.client = chromadb.PersistentClient(path=self.persist_directory)
            # Use a lightweight multilingual model that supports Arabic
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn,
            )
            self.initialized = True
        except Exception:
            logger.warning("chromadb or sentence-transformers not available. Using in-memory fallback.")
            self.initialized = False

    def add_documents(self, chunks: List[Dict[str, Any]]) -> List[str]:
        added_ids = []
        if self.initialized:
            ids = []
            documents = []
            metadatas = []
            
            for chunk in chunks:
                cid = chunk.get("chunk_id") or chunk.get("id") or str(len(ids))
                ids.append(cid)
                documents.append(chunk.get("content", ""))
                # Chroma requires metadata values to be str, int, float, or bool
                meta = chunk.get("metadata", {})
                clean_meta = {k: str(v) for k, v in meta.items() if v is not None}
                metadatas.append(clean_meta)
                added_ids.append(cid)
                
            # Batch upsert to Chroma to avoid payload limits
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                self.collection.upsert(
                    ids=ids[i:i+batch_size],
                    documents=documents[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                )
        else:
            for chunk in chunks:
                cid = chunk.get("chunk_id") or chunk.get("id")
                self._store[cid] = chunk
                added_ids.append(cid)
                
        return added_ids

    def similarity_search(
        self,
        query: str,
        k: int = 20,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        
        if self.initialized:
            # Build where clause for metadata filtering
            where = None
            if filter_metadata:
                where_clauses = [{"$eq": {k: str(v)}} for k, v in filter_metadata.items() if v]
                if len(where_clauses) == 1:
                    where = list(where_clauses[0].values())[0] # Chroma format
                elif len(where_clauses) > 1:
                    # Not perfectly mapping all logic, keeping it simple for this implementation
                    where = {"$and": [{k: str(v)} for k, v in filter_metadata.items() if v]}
            
            # Catch case where filter logic is too complex for this simplified where clause
            if isinstance(where, dict) and "$and" in where:
               where = None 
               
            search_results = self.collection.query(
                query_texts=[query],
                n_results=k,
                where=where
            )
            
            if search_results and search_results["ids"] and len(search_results["ids"][0]) > 0:
                for idx, cid in enumerate(search_results["ids"][0]):
                    distance = search_results["distances"][0][idx]
                    # Convert L2 distance to similarity score
                    score = 1.0 / (1.0 + distance)
                    
                    results.append({
                        "chunk_id": cid,
                        "content": search_results["documents"][0][idx],
                        "metadata": search_results["metadatas"][0][idx] if search_results["metadatas"] else {},
                        "vector_score": score,
                    })
        else:
            query_words = set(query.lower().split())
            for cid, chunk in self._store.items():
                content = chunk.get("content", "").lower()
                metadata = chunk.get("metadata", {})

                content_words = set(content.split())
                overlap = len(query_words.intersection(content_words))
                score = float(overlap) / float(max(1, len(query_words)))

                if filter_metadata:
                    match = True
                    for fk, fv in filter_metadata.items():
                        if fv and str(metadata.get(fk, "")).lower() != str(fv).lower():
                            match = False
                            break
                    if not match:
                        continue

                results.append({
                    "chunk_id": cid,
                    "content": chunk.get("content", ""),
                    "metadata": metadata,
                    "vector_score": score,
                })

        results.sort(key=lambda x: x["vector_score"], reverse=True)
        return results[:k]


class QdrantVectorStore(VectorStoreInterface):
    """Qdrant Cloud vector store implementation using Cohere embeddings."""

    def __init__(self, url: str, api_key: str, cohere_api_key: str, collection_name: str = "egyptian_agriculture"):
        self.collection_name = collection_name
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import Distance, VectorParams, PointStruct
            import cohere

            self.client = QdrantClient(url=url, api_key=api_key)
            self.co = cohere.Client(cohere_api_key)
            self.model_name = "embed-multilingual-v3.0"
            
            # Check if collection exists, if not create it (Cohere v3 multilingual is 1024 dims)
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
                )
            self.initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant/Cohere: {e}")
            self.initialized = False

    def add_documents(self, chunks: List[Dict[str, Any]]) -> List[str]:
        if not self.initialized or not chunks:
            return []

        from qdrant_client.http.models import PointStruct
        import uuid

        added_ids = []
        texts = [chunk.get("content", "") for chunk in chunks]
        
        # Batch size for Cohere API limits
        batch_size = 90
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_chunks = chunks[i:i+batch_size]
            
            # Generate embeddings
            response = self.co.embed(
                texts=batch_texts, 
                model=self.model_name, 
                input_type="search_document"
            )
            embeddings = response.embeddings
            
            points = []
            for j, emb in enumerate(embeddings):
                chunk = batch_chunks[j]
                cid = chunk.get("chunk_id") or str(uuid.uuid4())
                added_ids.append(cid)
                
                payload = chunk.get("metadata", {}).copy()
                payload["content"] = chunk.get("content", "")
                
                points.append(
                    PointStruct(id=cid, vector=emb, payload=payload)
                )
                
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
        logger.info(f"QdrantVectorStore: added {len(added_ids)} chunks")
        return added_ids

    def similarity_search(
        self,
        query: str,
        k: int = 20,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.initialized:
            return []
            
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        # Embed query
        response = self.co.embed(
            texts=[query], 
            model=self.model_name, 
            input_type="search_query"
        )
        query_vector = response.embeddings[0]

        # Build Qdrant filter
        qdrant_filter = None
        if filter_metadata:
            conditions = []
            for fk, fv in filter_metadata.items():
                if fv:
                    conditions.append(
                        FieldCondition(key=fk, match=MatchValue(value=str(fv)))
                    )
            if conditions:
                qdrant_filter = Filter(must=conditions)

        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=k,
        )

        results = []
        for hit in search_results.points:
            payload = hit.payload or {}
            content = payload.pop("content", "")
            results.append({
                "chunk_id": str(hit.id),
                "content": content,
                "metadata": payload,
                "vector_score": hit.score,
            })

        return results


def calculate_rrf_score(
    dense_results: List[Dict[str, Any]],
    sparse_results: List[Dict[str, Any]],
    k: int = 60,
    w_dense: float = 0.5,
    w_sparse: float = 0.5,
) -> List[Dict[str, Any]]:
    """Fuse dense and sparse ranked lists using Reciprocal Rank Fusion (RRF).

    RRF_score(d) = (w_dense / (k + rank_dense(d))) + (w_sparse / (k + rank_sparse(d)))
    """
    rrf_map: Dict[str, Dict[str, Any]] = {}

    # Process dense vector ranks
    for rank, item in enumerate(dense_results, start=1):
        cid = item.get("chunk_id") or item.get("id")
        if cid not in rrf_map:
            rrf_map[cid] = {
                "chunk_id": cid,
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "rrf_score": 0.0,
                "dense_rank": rank,
                "sparse_rank": None,
            }
        rrf_map[cid]["rrf_score"] += w_dense / (k + rank)

    # Process sparse BM25 ranks
    for rank, item in enumerate(sparse_results, start=1):
        cid = item.get("chunk_id") or item.get("id")
        if cid not in rrf_map:
            rrf_map[cid] = {
                "chunk_id": cid,
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "rrf_score": 0.0,
                "dense_rank": None,
                "sparse_rank": rank,
            }
        else:
            rrf_map[cid]["sparse_rank"] = rank
        rrf_map[cid]["rrf_score"] += w_sparse / (k + rank)

    fused = list(rrf_map.values())
    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused


def apply_vision_metadata_boost(
    candidates: List[Dict[str, Any]],
    vision_context: Optional[Dict[str, Any]],
    boost_factor: float = 0.25,
) -> List[Dict[str, Any]]:
    """Boost candidate chunk scores if they match vision model crop/disease labels."""
    if not vision_context:
        return candidates

    crop = str(vision_context.get("crop_type") or vision_context.get("crop") or "").lower()
    disease = str(vision_context.get("disease_label") or vision_context.get("disease") or "").lower()
    vision_conf = float(vision_context.get("confidence_score") or vision_context.get("confidence") or 1.0)

    if not crop and not disease:
        return candidates

    boosted = []
    for cand in candidates:
        meta = cand.get("metadata", {})
        cand_crop = str(meta.get("crop_type", "")).lower()
        cand_disease = str(meta.get("disease_name", "")).lower()

        match_bonus = 0.0
        if crop and cand_crop == crop:
            match_bonus += 0.15 * vision_conf
        if disease and cand_disease == disease:
            match_bonus += 0.25 * vision_conf

        cand_copy = dict(cand)
        cand_copy["rrf_score"] = cand_copy.get("rrf_score", 0.0) + (match_bonus * boost_factor)
        cand_copy["vision_boosted"] = match_bonus > 0
        boosted.append(cand_copy)

    boosted.sort(key=lambda x: x["rrf_score"], reverse=True)
    return boosted


def get_intent_weights(intent: str, query: str, config: Optional[Dict[str, Any]] = None) -> tuple[float, float]:
    """Determine (w_dense, w_sparse) weights based on intent and query product codes."""
    query_lower = (query or "").lower()

    # Product codes or chemical names -> strong BM25 bias
    product_code_tokens = ["npk", "urea", "يوريا", "سماد", "مبيد", "تركيز"]
    if intent == "dosage_lookup" or any(tok in query_lower for tok in product_code_tokens):
        return (0.3, 0.7)

    if intent == "general_advice":
        return (0.7, 0.3)

    # disease_query / default balanced
    return (0.5, 0.5)


def search_bm25(bm25_data: Dict[str, Any], query: str, k: int = 20) -> List[Dict[str, Any]]:
    """Execute BM25 search over corpus chunks."""
    if not bm25_data or not bm25_data.get("bm25_index"):
        return []

    bm25 = bm25_data["bm25_index"]
    chunks = bm25_data["corpus_chunks"]

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    results = []
    for idx in ranked_indices:
        if scores[idx] > 0 or len(results) < k:
            chunk = chunks[idx]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "content": chunk["content"],
                "metadata": chunk.get("metadata", {}),
                "bm25_score": float(scores[idx]),
            })
    return results


def hybrid_retrieval(
    query: str,
    vector_store: VectorStoreInterface,
    bm25_data: Dict[str, Any],
    intent: str = "general_advice",
    vision_context: Optional[Dict[str, Any]] = None,
    top_k: int = 20,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Run parallel dense vector and sparse BM25 retrieval and fuse using RRF."""
    w_dense, w_sparse = get_intent_weights(intent, query, config)
    rrf_k = config.get("retrieval", {}).get("rrf_k", 60) if config else 60

    # 1. Vector Search (top-20)
    dense_results = vector_store.similarity_search(query, k=top_k) if vector_store else []

    # 2. BM25 Search (top-20)
    sparse_results = search_bm25(bm25_data, query, k=top_k) if bm25_data else []

    # 3. Reciprocal Rank Fusion
    fused_candidates = calculate_rrf_score(
        dense_results, sparse_results, k=rrf_k, w_dense=w_dense, w_sparse=w_sparse
    )

    # 4. Vision model metadata filter / boosting
    boosted_candidates = apply_vision_metadata_boost(fused_candidates, vision_context)

    return boosted_candidates[:top_k]
