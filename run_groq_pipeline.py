import json
import sys
from rag.respond import RAGPipeline
from rag.generate import GroqLLMProvider

def main():
    api_key = "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"
    pdf_path = "التوصيات_المعتمدة_لمكافحة_الآفات_الزراعية.pdf"
    
    print("Initializing RAG Pipeline...")
    pipeline = RAGPipeline()
    
    # Inject Groq LLM Provider
    print("Connecting to Groq LLM (openai/gpt-oss-120b)...")
    pipeline.llm_provider = GroqLLMProvider(api_key=api_key)
    
    # Adjust config to fit Groq API limits (max 8000 tokens)
    pipeline.config["rerank"] = {"top_k": 2}
    
    print(f"Ingesting PDF: {pdf_path}...")
    ingest_result = pipeline.ingest_pdfs([pdf_path])
    print(f"Ingestion complete: {ingest_result['num_chunks']} chunks created.")
    
    query = "كيف أكافح حشرة المن في القمح؟"
    print(f"\nUser Query: {query}")
    print("-" * 50)
    
    # Need to pass an empty vision_context or None
    result = pipeline.run(
        user_query=query,
        crop_filter="قمح"
    )
    
    print("\n[Generated Answer]")
    print(result["answer"])
    
    print("\n[Citations]")
    for citation in result["citations"]:
        print(f" - {citation['citation_tag']}: {citation['source_doc']} (Chunk: {citation['chunk_id'][:8]}...)")
        
    print(f"\nRetrieval Confidence: {result['retrieval_confidence']}")
    print(f"Needs Agronomist Review: {result['needs_agronomist_review']}")

if __name__ == "__main__":
    main()
