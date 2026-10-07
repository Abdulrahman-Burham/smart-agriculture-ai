# المساعد الزراعي الخبير — RAG + LLM

نظام مساعد زراعي يجاوب المزارع بالعربي (بما فيه اللهجة المصرية) بالاعتماد **فقط** على الأدلة الزراعية المعتمدة، ويخصّص النصيحة حسب بيانات المزرعة (تحليل التربة من الـ OCR، تشخيص الصور من الـ Vision، الطقس). هذا هو مخرج **مهندس LLM & RAG** في وثيقة المشروع.

| المخرج المطلوب في الوثيقة | مكانه في المشروع |
|---|---|
| محرك المساعد الذكي (RAG System) | `agri_rag/pipeline.py`, `retrieval/hybrid.py`, `generation/` |
| قاعدة البيانات المتجهة (Vector DB) | `retrieval/vectorstore.py` (ChromaDB) + `ingestion/` |
| واجهة API للمساعد (LLM API) | `agri_rag/api/app.py` (FastAPI + SSE streaming) |
| بروتوكول تقييم دقة الإجابات | `docs/evaluation_protocol.md` + `agri_rag/evaluation/` |
| وكلاء التنبيهات (Agents) | `agri_rag/alerts/` |

## المعمارية

```
سؤال المزارع (نص / STT) + FarmContext (OCR + Vision + طقس)
        │
        ▼
 قاموس اللهجات  ──►  "القوطة" = "طماطم" ، "دبانة بيضا" = "الذبابة البيضاء"
        │
        ▼
 استرجاع هجين:  Dense (e5 + Chroma)  +  BM25   ──► دمج RRF ──► فلتر المحصول
        │
        ▼
 بوابة الثقة (min_similarity)  ──► أقل منها: رفض مهذب بدون استدعاء LLM (توفير تكلفة + منع هلوسة)
        │
        ▼
 Prompt مؤسَّس (مصادر مرقمة + سياق المزرعة)  ──► LLM Streaming ──► إجابة مع [1][2]
```

قرارات تصميم مهمة:
- **Hybrid retrieval**: الـ dense يفهم المعنى، والـ BM25 يلتقط المصطلحات والأرقام بدقة. الدمج بـ RRF دون معايرة الدرجات.
- **Chunking واعي بالعناوين** مع overlap وعنوان سياقي لكل chunk.
- **التنبيهات بقواعد شفافة**: القواعد (قابلة للتدقيق) تقرر *متى* ننبّه، والـ RAG يشرح *ماذا نفعل*. لا يوجد قرار ري صادر من نموذج لغوي مباشرة.
- **زمن الاستجابة**: Streaming، نموذج صغير افتراضيًا، cache لتضمين الأسئلة، والـ KPI (≤ 3 ثوانٍ لأول توكن) يُقاس في كل رد (`timings.within_budget`).
- **الأمان**: حارس "لا تخترع جرعات"، تجاهل أي تعليمات داخل المصادر (حماية من prompt injection)، مفتاح API، حدود طول المدخلات.

## التشغيل السريع

```bash
python -m venv .venv && source .venv/bin/activate
make install
cp .env.example .env          # ضع مفتاح الـ LLM
make ingest                   # فهرسة data/knowledge
make serve                    # http://localhost:8000/docs
```

تجربة من الطرفية:
```bash
python -m agri_rag.cli ask "الورق بتاع القوطة عليه بقع مايه غامقة" --farm-json data/eval/example_farm.json
```

بدون مفتاح API (للتجربة فقط): `AGRI_LLM_PROVIDER=fake AGRI_EMBEDDING_BACKEND=hash`.
لتشغيل نموذج مفتوح محليًا (Ollama/vLLM): `AGRI_LLM_PROVIDER=openai_compat` + `AGRI_LLM_BASE_URL`.

## الـ API

| Endpoint | الوظيفة |
|---|---|
| `POST /v1/chat` | رد كامل JSON (answer, sources, cited_ids, timings) |
| `POST /v1/chat/stream` | Server-Sent Events: `sources` ← `token`* ← `done` |
| `POST /v1/alerts/evaluate` | تنبيهات الري/التسميد/التربة/الأمراض لمزرعة (`enrich=true` لإضافة شرح RAG) |
| `POST /v1/admin/reindex` | إعادة فهرسة `data/knowledge` بعد إضافة أدلة |
| `GET /healthz` | فحص الصحة |

```bash
curl -N localhost:8000/v1/chat/stream -H 'X-API-Key: change-me' -H 'Content-Type: application/json' \
  -d '{"question":"الأرض مالحة أعمل إيه؟","farm":{"crop":"طماطم","soil":{"ph":8.1,"ec_ds_m":3.2}}}'
```

### عقد التكامل مع باقي الفريق
- **مهندس الـ OCR** يُخرج `SoilReport` (`domain/farm.py`): `ph, ec_ds_m, nitrogen_ppm, ...`
- **مهندس الـ Vision** يُخرج `VisionDiagnosis`: `label, confidence, crop, severity` (الثقة < 0.6 تُعرض للمزارع كـ"غير مؤكد").
- **الـ Backend** يجمعهم في `FarmContext` ويرسله مع السؤال.
- **الصوت**: الـ API نصي. التحويل الصوتي (STT مثل Whisper) يتم في الـ gateway/الموبايل ويُرسل النص الناتج إلى `/v1/chat`.


## الطقس التلقائي
الأبلكيشن يقدر يبعت `farm.weather` بنفسه (من حساس مثلًا) وده له الأولوية. لو ما بعتهوش وبعت موقع المزرعة
(`farm.latitude` و`farm.longitude`، أو على الأقل `farm.governorate`)، المساعد يجيب الحرارة والرطوبة والمطر
(آخر 24 ساعة + المتوقع خلال 48 ساعة) من Open-Meteo (مجاني، من غير مفتاح) ويستخدمها في الرد والتنبيهات.
- مهلة قصيرة (2 ثانية) وكاش 30 دقيقة، ولو الخدمة وقعت المساعد يكمّل بدون طقس.
- للتعطيل: `AGRI_WEATHER_ENABLED=false`. التجربة: `--farm-json data/eval/example_farm_location_only.json`.

## قاعدة المعرفة
ضع الأدلة في `data/knowledge/` (`.md` / `.txt` / `.pdf`) مع front matter اختياري:
```yaml
---
title: اللفحة المتأخرة في الطماطم
crop: طماطم        # أو "عام"
org: وزارة الزراعة / مركز البحوث الزراعية
year: 2024
---
```
ثم `make ingest` أو `POST /v1/admin/reindex`. إعادة الفهرسة آمنة (idempotent).

## التقييم
```bash
make eval-retrieval   # بدون API key: Hit@k, MRR, وقيمة min_similarity المقترحة
make eval             # شامل + LLM-judge + زمن الاستجابة → reports/eval_report.md
make test             # 29 اختبار وحدة/تكامل
```

## ⚠️ لازم تعملها قبل التسليم (حدود معروفة)
1. **الملفات الحالية في `data/knowledge/` محتوى تجريبي** كتبته لاختبار النظام، وليست مرجعًا زراعيًا معتمدًا. استبدلها بالأدلة الرسمية (وزارة الزراعة، مركز البحوث الزراعية) قبل أي عرض أو استخدام فعلي.
2. **قيم `config/crop_profiles.yaml`** (فترات الري والتسميد وحدود pH/EC) استرشادية، ويجب اعتمادها من مهندس زراعي لكل محصول وموسم.
3. **معايرة `min_similarity`** على مجموعة الأسئلة الحقيقية (الأمر الأول في قسم التقييم). القيمة الافتراضية 0.78 نقطة بداية لنموذج e5.
4. **PDF العربي**: استخراج النص من PDF عربي كثيرًا ما يكسّر الحروف. فضّل مصادر نصية أو مرّر الملف عبر محرك الـ OCR وراجع الـ chunks.
5. **ما اتجرّبش في بيئة التطوير**: تحميل نموذج e5 الحقيقي واستدعاء LLM حقيقي (لا يوجد وصول للإنترنت هناك). الاختبارات تستخدم embedder تجريبي و`FakeLLM`. شغّل `make eval` مرة بالإعدادات الحقيقية وراجع الأرقام.
6. **للإنتاج**: استبدل `InMemorySessionStore` بـ Redis، أضف rate limiting خلف الـ gateway، ومرّر السجلات لنظام مراقبة.
