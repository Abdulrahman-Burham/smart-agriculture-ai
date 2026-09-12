"""Sample end-to-end query demonstration for the Egyptian Agricultural RAG pipeline."""

from __future__ import annotations

import json
from rag.respond import RAGPipeline


def main():
    print("=" * 70)
    print("🌱 Initializing Egyptian Agricultural RAG Pipeline...")
    print("=" * 70)

    pipeline = RAGPipeline(config_path="rag/config.yaml", lexicon_path="rag/lexicon.json")

    # 1. Sample Knowledge Base Ingestion (Guides & Treatment Protocols)
    sample_documents = [
        {
            "source_doc": "potato_disease_guide.txt",
            "doc_type": "guide",
            "crop_type": "potato",
            "disease_name": "late_blight",
            "region": "delta",
            "content": (
                "تعتبر الندوة المتاخرة (اللفحة المتأخرة) من أخطر الأمراض الفطرية التي تصيب محصول البطاطس والطماطم في مصر، "
                "وتزداد شدتها في فترات الرطوبة العالية وانخفاض درجات الحرارة في فصل الشتاء. "
                "تظهر الأغراض على شكل بقع مائية داكنة على الأوراق والسيقان مع وجود نمو زغبي أبيض على السطح السفلي."
            ),
        },
        {
            "source_doc": "late_blight_protocol.txt",
            "doc_type": "protocol",
            "crop_type": "potato",
            "disease_name": "late_blight",
            "region": "delta",
            "content": (
                "البروتوكول العلاجي المعتمد لمرض اللفحة المتأخرة في البطاطس:\n"
                "1. الوقاية: الرش الدوري باستخدام المبيدات النحاسية أو مركب المانكوزيب بمعدل 250 جرام لكل 100 لتر ماء.\n"
                "2. عند ظهور الإصابة العلاجية: رش مركب ميتالاكسيل + مانكوزيب بمعدل 200 جرام لكل 100 لتر ماء مع تجنب زيادة مياه الري.\n"
                "3. تجنب الري بالرش فوق الأشجار لتقليل الرطوبة حول الأوراق."
            ),
        },
        {
            "source_doc": "fertilizer_guide.txt",
            "doc_type": "guide",
            "crop_type": "general",
            "disease_name": "general",
            "region": "egypt_general",
            "content": (
                "التسميد المتوازن بمركبات NPK واليوريا يعتبر العمود الفقري لزيادة إنتاجية الفدان. "
                "يتم إضافة سماد اليوريا بنسبة 46% نتروجين على دفعات متتالية خلال فترة النمو الخضري."
            ),
        },
    ]

    print("\n📦 Ingesting sample text knowledge base...")
    ingest_summary = pipeline.ingest_documents(sample_documents)
    print(f"✅ Ingested {ingest_summary['num_documents']} documents into {ingest_summary['num_chunks']} chunks.")

    # 2. Sample User Query with Vision Model Input
    user_query = "عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟"
    vision_context = {
        "crop_type": "potato",
        "disease_label": "late_blight",
        "confidence_score": 0.94,
    }

    print("\n----------------------------------------------------------------------")
    print(f"🗣️  User Dialect Query: '{user_query}'")
    print(f"📷 Vision Context: {vision_context}")
    print("----------------------------------------------------------------------\n")

    # 3. Pipeline Execution
    response = pipeline.run(user_query, vision_context=vision_context)

    # 4. Display Formatted Output
    print("✨ Full Pipeline Output:")
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
