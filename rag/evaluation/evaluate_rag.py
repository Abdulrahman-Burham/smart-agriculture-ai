import json
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from rag.respond import RAGPipeline
from rag.generate import GroqLLMProvider

load_dotenv()

# Test dataset: Questions and Expected Key Concepts (to help the judge)
TEST_DATASET = [
    {
        "question": "كيف أكافح حشرة المن في القمح؟",
        "expected_concepts": ["سومثيون", "ملاسون", "قمم نامية", "بؤر الإصابة"]
    },
    {
        "question": "ما هي المبيدات الموصى بها لعلاج البياض الزغبي في البصل؟",
        "expected_concepts": ["ريدوميل", "شامب", "مانكوزيب", "فوليو جولد"]
    },
    {
        "question": "ما هو علاج ذبابة الفاكهة في الخوخ؟",
        "expected_concepts": ["مبيد", "مكافحة", "ذبابة الفاكهة"]
    },
    {
        "question": "هل أستطيع ري الطماطم وقت الظهيرة في الصيف؟",
        "expected_concepts": ["لا ينصح", "تبخر", "أمراض فطرية"] # General advice check
    }
]

EVAL_PROMPT = """
You are an expert agricultural AI evaluator.
You will be provided with a Question, the Retrieved Context (Sources), and the RAG System's Answer.
Evaluate the answer on a scale of 0 to 10 for each of the following criteria:

1. Faithfulness (0-10): Did the answer rely strictly on the provided Context without hallucinating external information?
2. Answer Relevance (0-10): Did the answer directly and accurately address the user's question?
3. Completeness (0-10): Did it mention specific pesticides and dosages if they were in the context?

Output your evaluation in strict JSON format like this:
{{
  "faithfulness": 9,
  "relevance": 10,
  "completeness": 8,
  "reasoning": "Brief explanation in Arabic..."
}}

Question: {question}
Answer: {answer}
Context: {context}
"""

def evaluate():
    print("Starting RAG Evaluation...")
    pipeline = RAGPipeline(config_path="rag/config.yaml", lexicon_path="rag/lexicon.json")
    pipeline.llm_provider = GroqLLMProvider(api_key=os.environ.get("GROQ_API_KEY"))
    
    total_score = 0
    max_possible = len(TEST_DATASET) * 30
    
    results_log = []

    for i, test in enumerate(TEST_DATASET):
        q = test["question"]
        print(f"\n[{i+1}/{len(TEST_DATASET)}] Testing Query: {q}")
        
        # Run RAG
        result = pipeline.run(q)
        answer = result["answer"]
        
        # Extract context
        context_texts = "\n".join([c["content"] for c in result.get("sources", [])])
        
        # Ask LLM to judge
        eval_prompt_formatted = EVAL_PROMPT.format(
            question=q, answer=answer, context=context_texts
        )
        
        try:
            eval_response_raw = pipeline.llm_provider.generate(eval_prompt_formatted, context=[])
            
            # Simple JSON extraction
            json_str = eval_response_raw
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1]
                
            eval_result = json.loads(json_str.strip())
            
            score = eval_result["faithfulness"] + eval_result["relevance"] + eval_result["completeness"]
            total_score += score
            
            print(f"  -> Faithfulness: {eval_result['faithfulness']}/10")
            print(f"  -> Relevance: {eval_result['relevance']}/10")
            print(f"  -> Completeness: {eval_result['completeness']}/10")
            print(f"  -> Reasoning: {eval_result['reasoning']}")
            
        except Exception as e:
            print(f"  -> Error evaluating this question: {e}")
            max_possible -= 30

    if max_possible > 0:
        accuracy = (total_score / max_possible) * 100
        print(f"\n====================================")
        print(f"🎯 RAG System Accuracy: {accuracy:.2f}%")
        print(f"====================================")

if __name__ == "__main__":
    evaluate()
