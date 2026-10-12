/**
 * Smart Agriculture AI — Multi-Language Engine (Arabic 🇪🇬 / English 🇬🇧 / Français 🇫🇷)
 * Supports instant RTL/LTR switching, non-destructive TextNode + rich HTML translation, and localStorage persistence.
 */
(function () {
    const STORAGE_KEY = 'agri_lang';
    const SUPPORTED = ['ar', 'en', 'fr'];

    const DICT = {
        en: {
            // Top Bar & Navbar (Landing + Dashboard + Mobile + Login)
            "🏆 وضع عرض Demo Day التفاعلي": "🏆 Interactive Demo Day Showcase",
            "منصة الذكاء الاصطناعي الزراعي المصرية (Vision + Hybrid Agri-RAG + Gemini 3.8 Neural Voice)": "Egyptian AgriTech AI Platform (Vision + Hybrid Agri-RAG + Gemini 3.8 Neural Voice)",
            "💻 لوحة الكمبيوتر": "💻 Desktop Dashboard",
            "📱 تطبيق الموبايل": "📱 Mobile App",
            "⚡ الفحص السريع": "⚡ Quick Scan",
            "🧠 معمارية النظام": "🧠 AI Architecture",
            "منصة الزراعة الذكية": "Smart Agriculture AI",
            "Smart Agriculture AI • مرشدك الزراعي المصري": "Smart Agriculture AI • Egyptian Agricultural Advisor",
            "واجهات المنصة": "Interfaces",
            "معمارية الذكاء الاصطناعي": "AI Architecture",
            "المميزات": "Features",
            "المحاصيل المدعومة": "Supported Crops",
            "🌙 الوضع الليلي": "🌙 Dark Mode",
            "☀️ الوضع الفاتح": "☀️ Light Mode",
            "🔐 تسجيل الدخول": "🔐 Sign In",
            "🚀 افتح المنصة الآن": "🚀 Launch Platform",

            // Hero Section
            "أول مساعد زراعي ذكي يتحدث باللهجة المصرية ومعتمد علمياً": "First Scientifically Grounded Egyptian Arabic Agricultural AI Assistant",
            "مهندس زراعي خبير في جيبك..": "An Expert Agronomist in Your Pocket..",
            "يفحص زرعك بالصورة ويكلمك بالمصري!": "Diagnoses Your Crops by Photo & Speaks Egyptian Arabic!",
            "صوّر ورقة النبات المصابة أو اسأل بصوتك بالعامية المصرية، وهتاخد تشخيص فوري بالرؤية الحاسوبية (": "Snap a photo of an infected leaf or ask by voice in Egyptian Arabic for instant Computer Vision diagnosis (",
            ") مع روشتة علاجية وجرعات دقيقة بالفدان من نشرات": ") and exact per-feddan treatment dosages from",
            "مركز البحوث الزراعية": "Agricultural Research Center",
            "مربوطة بطقس محافظتك لحظياً.": "bulletins synced with your governorate's live weather.",
            "🚀 ابدأ الفحص والاستشارة مجاناً": "🚀 Start Free Diagnosis & Consultation",
            "💻 لوحة العرض الكاملة (Desktop)": "💻 Full Desktop Dashboard",
            "🔊 اسمع ترحيب المهندس بالمصري": "🔊 Hear Egyptian Agronomist Welcome",
            "⏹️ إيقاف الصوت المصري": "⏹️ Stop Audio",
            "⏳ جاري تجهيز الصوت المصري...": "⏳ Preparing Egyptian Neural Audio...",
            "✅ فحص 38 مرض وآفة بالصورة": "✅ 38 Plant Diseases Diagnosed by Vision",
            "✅ نطق بشري مصري طبيعي (Gemini 3.8 TTS)": "✅ Natural Egyptian Neural Voice (Gemini 3.8 TTS)",
            "✅ طقس لحظي لـ 27 محافظة مصرية": "✅ Live Weather for 27 Egyptian Governorates",

            // Hero Interactive Showcase Card
            "محاكاة حية للتشخيص والروشتة (جرّب الضغط)": "Live Diagnosis & Prescription Simulator (Try Clicking)",
            "اختر محصولاً لمعاينة تشخيص الرؤية الحاسوبية والرد الصوتي المصري": "Select a crop to preview Computer Vision diagnosis & Egyptian voice prescription",
            "متصل الآن": "Live Now",
            "🍅 طماطم (ندوة متأخرة)": "🍅 Tomato (Late Blight)",
            "🥔 بطاطس (ندوة مبكرة)": "🥔 Potato (Early Blight)",
            "🥭 مانجو (بياض دقيقي)": "🥭 Mango (Powdery Mildew)",
            "🔬 التشخيص: طماطم — الندوة المتأخرة (Late Blight)": "🔬 Diagnosis: Tomato — Late Blight",
            "🔬 التشخيص: بطاطس — الندوة المبكرة (Early Blight)": "🔬 Diagnosis: Potato — Early Blight",
            "🔬 التشخيص: مانجو — البياض الدقيقي ولفحة الأزهار": "🔬 Diagnosis: Mango — Powdery Mildew & Blossom Blight",
            "ثقة 97.8%": "97.8% Confidence",
            "ثقة 96.4%": "96.4% Confidence",
            "ثقة 95.9%": "95.9% Confidence",
            "النموذج:": "Model:",
            "فلتر النباتات:": "Plant Gatekeeper:",
            "✅ ورقة نبات حقيقية": "✅ Verified Plant Leaf",
            "📚 نشرة وزارة الزراعة #142": "📚 Ministry of Agriculture Bulletin #142",
            "📚 نشرة معهد أمراض النبات #89": "📚 Plant Pathology Institute Bulletin #89",
            "📚 نشرة بحوث البساتين — المانجو": "📚 Horticulture Research Bulletin — Mango",
            "🤖 روشتة المهندس الزراعي الذكي (باللهجة المصرية):": "🤖 Smart Agronomist Prescription (Egyptian Dialect):",
            "Agri-RAG الهجين": "Hybrid Agri-RAG",
            "«يا باشمهندس، الورقة دي فيها": "“Engineer, this leaf shows",
            "ندوة متأخرة في الطماطم": "Tomato Late Blight",
            "والجو الرطب بيزودها. أول خطوة توقف الري بالغمر وتقلل الرطوبة، وترش فوراً": "accelerated by high humidity. First, stop flood irrigation, reduce moisture, and immediately spray",
            "أوكسي كلور النحاس أو ريدوميل جولد": "Copper Oxychloride or Ridomil Gold",
            "بمعدل 250 جرام لكل 100 لتر ميه آخر النهار.»": "at 250g per 100L of water in the late afternoon.”",
            "«بص يا حاج، الحلقات البنية دي": "“Look farmer, these concentric brown rings indicate",
            "ندوة مبكرة في البطاطس": "Potato Early Blight",
            ". لم الورق السفلي المصاب بره الغيط، ورش": ". Remove infected lower leaves from the field and spray",
            "أزوكسي ستروبين أو مانكوزيب": "Azoxystrobin or Mancozeb",
            "بمعدل 250 جرام لكل 100 لتر ميه، مع اهتمامك بتسميد البوتاسيوم عشان يقوي العرش.»": "at 250g per 100L of water, alongside potassium fertilization to strengthen the canopy.”",
            "«خلي بالك يا باشمهندس، الشماريخ الزهرية عليها": "“Watch out engineer, the flower panicles have",
            "بياض دقيقي في المانجو": "Mango Powdery Mildew",
            ". رش فوراً": ". Immediately spray",
            "كبريت ميكروني": "Micronized Sulfur",
            "بمعدل 250 جرام لكل 100 لتر ميه في الصباح الباكر أو قبل الغروب، وابعد عن الرش وقت الحر الشديد.»": "at 250g per 100L of water early morning or before sunset, avoiding peak midday heat.”",
            "🔊 استمع لهذه الروشتة بالصوت المصري": "🔊 Listen in Egyptian Neural Voice",
            "💬 افتح في المنصة ←": "💬 Open in Dashboard →",
            "🌤️ طقس المحافظات الزراعي المباشر:": "🌤️ Live Agricultural Governorate Weather:",
            "جاري جلب حالة الجو...": "Fetching live weather...",

            // Stats Strip
            "مرض وآفة نباتية بالصورة": "Plant Diseases & Pests via Vision",
            "نموذج EfficientNetV2B2 + فلتر النباتات": "EfficientNetV2B2 + Smart Plant Gatekeeper",
            "محافظة مصرية مربوطة بالطقس": "Egyptian Governorates with Live Weather",
            "حرارة • رطوبة • سرعة رياح • إنذار مبكر": "Temp • Humidity • Wind Speed • Early Warning",
            "عملية فحص واستشارة زراعية": "Live Diagnoses & Consultations",
            "تحديث لحظي من قاعدة بيانات المنصة": "Real-time telemetry from production DB",
            "تحدث واستماع بالعامية المصرية": "Egyptian Arabic Speech & Listening",

            // Architecture Section
            "معمارية الذكاء الاصطناعي (System Architecture)": "AI System Architecture",
            "كيف تعمل المنصة خلف الكواليس في أقل من ثانية؟": "How Does the Platform Work Behind the Scenes in Under a Second?",
            "خط أنابيب ذكي من 4 مراحل يدمج الرؤية الحاسوبية، الاسترجاع المعرفي الهجين الموثق، والنماذج الصوتية العصبية باللهجة المصرية.": "A 4-stage intelligent pipeline integrating Computer Vision, grounded Hybrid RAG retrieval, and Egyptian Neural TTS.",
            "المرحلة 01 • الفلترة الذكية": "Stage 01 • Smart Gatekeeper",
            "بوابة التحقق من النبات": "Plant Verification Gatekeeper",
            "فحص جودة الإضاءة وحدة الصورة واستبعاد الصور غير النباتية أو العشوائية تلقائياً قبل التشغيل لضمان دقة التشخيص 100%.": "Inspects lighting & sharpness and automatically rejects non-plant images before classification to ensure 100% reliability.",
            "المرحلة 02 • الرؤية الحاسوبية": "Stage 02 • Computer Vision",
            "تشخيص أمراض الأوراق": "Leaf Disease Classification",
            "تحليل البقع والندوات والبياض الدقيقي ونقص العناصر مع حساب نسبة الثقة وهامش التأكد (Confidence Margin) للتعلم النشط.": "Detects blights, mildew, spots, and nutrient deficiencies while computing confidence margins for Active Learning.",
            "المرحلة 03 • الاسترجاع الهجين": "Stage 03 • Hybrid Retrieval",
            "المستشار الزراعي المعتمد": "Grounded Agricultural RAG",
            "دمج البحث الدلالي واللفظي في نشرات مركز البحوث الزراعية مع طقس المحافظة ومساحة المزرعة بالفدان ونوع الري.": "Combines dense (e5) + lexical (BM25) search over Agricultural Research Center bulletins with live governorate weather and farm size.",
            "المرحلة 04 • النطق العصبي المصري": "Stage 04 • Neural Speech",
            "توليد الصوت المصري الطبيعي": "Natural Egyptian Neural Voice",
            "تحويل الأرقام والرموز العلمية إلى عامية مصرية زراعية سليمة وتوليد صوت بشري مصري (رجالي/نسائي) فائق الوضوح.": "Normalizes scientific units into natural spoken Egyptian Arabic and synthesizes ultra-clear male/female voices via Gemini 3.8 TTS.",

            // Interfaces Section
            "واجهات مصممة لكل مزارع ومهندس": "Interfaces Designed for Every Farmer & Engineer",
            "اختر الواجهة المناسبة لجهازك أو لعرضك": "Choose the Right Interface for Your Device or Demo",
            "صممنا المنصة بثلاث واجهات متكاملة لتناسب العمل الميداني بالموبايل في الحقل أو العرض التفصيلي على شاشة الكمبيوتر.": "Three tailored interfaces built for field work on mobile phones or detailed presentations on desktop screens.",
            "الأكثر استخداماً في الحقل": "Most Used in the Field",
            "📱 تطبيق الموبايل الذكي": "📱 Smart Mobile App",
            "واجهة تطبيق أصلية سريعة للموبايل: صوّر الورقة بالكاميرا مباشرة، سجل سؤالك بالصوت، واسمع الروشتة باللهجة المصرية مع تحديد موقع مزرعتك بالـ GPS.": "Fast native-like mobile UI: snap leaf photos directly with the camera, ask by voice, hear Egyptian prescriptions, and pin GPS farm coordinates.",
            "افتح واجهة الموبايل ←": "Open Mobile App →",
            "مثالية لعرض Demo Day": "Ideal for Demo Day",
            "💻 منصة الكمبيوتر المتكاملة": "💻 Full Desktop Control Center",
            "شاشة مزدوجة تجمع بين فحص الصور، المحادثة الذكية مع المهندس الزراعي، أمثلة العرض الجاهزة، سجل فحوصات المزرعة، ومؤشرات الطقس والإنذار المبكر.": "Dual-pane workstation combining leaf image scanning, AI agronomist chat, 1-click Demo Day presets, farm history, and live weather alerts.",
            "افتح لوحة الكمبيوتر ←": "Open Desktop Dashboard →",
            "بضغطتين فقط": "Just 2 Clicks",
            "⚡ الفحص السريع المبسط": "⚡ Simplified 2-Click Scanner",
            "واجهة مبسطة جداً للفحص الفوري: ارفع صورة الورقة واضغط زر التشخيص لتحصل على اسم المرض والروشتة العلاجية المسموعة فوراً.": "Ultra-simple interface for instant diagnosis: upload a leaf photo and click diagnose to get the disease name and spoken treatment immediately.",
            "افتح الفحص المبسط ←": "Open Quick Scanner →",

            // Features Section
            "تقنيات الذكاء الاصطناعي الزراعي": "AgriTech AI Capabilities",
            "كل ما تحتاجه لحماية محصولك وزيادة الإنتاجية": "Everything You Need to Protect Crops & Boost Yield",
            "منظومة متكاملة تربط الرؤية الحاسوبية باسترجاع المعرفة الموثقة والطقس الحي لخدمة الفلاح والمهندس الزراعي المصري.": "An integrated ecosystem connecting Computer Vision, grounded agricultural knowledge retrieval, and live weather for Egyptian farmers.",
            "تشخيص أمراض النبات بالصورة": "Visual Plant Disease Diagnosis",
            "نموذج": "Model",
            "مدعوم بفلتر ذكي يرفض الصور غير النباتية تلقائياً ويشخص الأمراض الفطرية والبكتيرية ونقص العناصر بدقة عالية.": "backed by a smart gatekeeper that rejects non-plant images and diagnoses fungal, bacterial, and nutrient disorders.",
            "روشتات معتمدة (Agri-RAG)": "Verified Prescriptions (Agri-RAG)",
            "محرك بحث هجين (": "Hybrid search engine (",
            ") يستخرج الجرعات والمبيدات الموصى بها من نشرات مركز البحوث الزراعية ووزارة الزراعة المصرية بدون تأليف.": ") extracting verified dosages and fungicides from Egyptian Ministry of Agriculture bulletins with zero hallucination.",
            "يتحدث ويسمع باللهجة المصرية": "Speaks & Listens in Egyptian Dialect",
            "سجل سؤالك بصوتك بالعامية المصرية، واسمع الإجابة بصوت بشري مصري طبيعي وواضح (رجالي أو نسائي) يشرح لك خطوات العلاج والجرعات بسهولة.": "Record your question in Egyptian Arabic and listen to clear natural Egyptian male/female voice explaining treatment steps.",
            "ربط تلقائي بطقس محافظتك": "Automatic Governorate Weather Sync",
            "يتابع درجة الحرارة والرطوبة وسرعة الرياح في محافظتك (أو عبر الـ GPS) لينبهك لأوقات انتشار الفطريات وأفضل ميعاد للرش أو الري.": "Tracks temperature, humidity, and wind speed in your governorate (or via GPS) to warn against fungal outbreaks and optimal spray times.",
            "ذاكرة ذكية لبيانات مزرعتك": "Persistent Farm Context Memory",
            "يتذكر اسمك، محصولك الأساسي، مساحة أرضك بالفدان، ونوع الري (تنقيط، غمر، رش) ليحسب لك التوصيات على مقاس أرضك بالضبط.": "Remembers your name, primary crop, farm area in feddans, and irrigation type (drip, flood, sprinkler) for tailored dosages.",
            "مشاركة فورية على واتساب": "Instant WhatsApp Sharing",
            "انسخ الروشتة العلاجية أو شاركها بضغطة زر واحدة عبر واتساب مع العمال أو المهندسين في المزرعة لتنفيذ خطة العلاج فوراً.": "Copy or share the treatment prescription in one click via WhatsApp with farm workers or engineers for immediate execution.",

            // Crops Section
            "تغطية واسعة للمحاصيل المصرية": "Broad Coverage of Egyptian Crops",
            "اضغط على أي محصول لبدء استشارة فورية عنه": "Click Any Crop to Launch an Instant Consultation",
            "تدعم المنصة تشخيص واستشارات المحاصيل الاستراتيجية والخضر والفاكهة في البيئة الزراعية المصرية.": "Supports visual diagnosis and agronomic advisory for strategic field crops, vegetables, and orchards in Egypt.",
            "🍅 الطماطم": "🍅 Tomato",
            "🥔 البطاطس": "🥔 Potato",
            "🥭 المانجو": "🥭 Mango",
            "🌾 القمح": "🌾 Wheat",
            "🌽 الذرة": "🌽 Corn / Maize",
            "🌾 الأرز": "🌾 Rice",
            "🍇 العنب": "🍇 Grapes",
            "🫑 الفلفل": "🫑 Bell Pepper",
            "🍊 الموالح والبرتقال": "🍊 Citrus & Orange",
            "🍓 الفراولة": "🍓 Strawberry",
            "🥒 الخيار والقرعيات": "🥒 Cucumber & Cucurbits",
            "🫒 الزيتون": "🫒 Olive",
            "🌴 النخيل": "🌴 Date Palm",

            // Bottom CTA & Footer
            "جاهز لتجربة المنصة الحية أو استعراضها أمام لجنة التحكيم؟": "Ready to Experience the Live Platform or Present to the Jury?",
            "افتح لوحة التحكم الكاملة بضغطة واحدة، أو سجّل حساب مزرعتك لحفظ تاريخ الفحوصات والاستشارات الخاصة بأرضك.": "Launch the full control dashboard in one click, or register your farm account to save your diagnosis and consultation history.",
            "💻 افتح لوحة العرض الكاملة": "💻 Open Full Dashboard",
            "📱 افتح تطبيق الموبايل": "📱 Open Mobile App",
            "👤 تسجيل دخول / حساب مزارع": "👤 Sign In / Farmer Account",
            "منصة الزراعة الذكية (Smart Agriculture AI) — جميع الحقوق محفوظة © 2026": "Smart Agriculture AI Platform — All Rights Reserved © 2026",
            "نسخة الكمبيوتر": "Desktop Version",
            "تطبيق الموبايل": "Mobile App",
            "الفحص السريع": "Quick Scan",
            "تسجيل الدخول": "Sign In",

            // Desktop Dashboard (index.html)
            "الخبير الزراعي الذكي": "Smart Agricultural Advisor",
            "رجوع": "Back",
            "🔐 دخول": "🔐 Sign In",
            "✨ حساب جديد": "✨ Register",
            "📜 سجلي": "📜 History",
            "🚪 خروج": "🚪 Logout",
            "🏠 صفحة العرض (Landing)": "🏠 Landing Page",
            "🤖 المساعد الذكي والتشخيص": "🤖 AI Assistant & Diagnosis",
            "📊 لوحة تحليلات AgriTech (Power BI)": "📊 AgriTech Analytics (Power BI)",
            "📱 نسخة الموبايل (App)": "📱 Mobile App UI",
            "🎯 التشخيص السريع بالصورة": "🎯 Quick Photo Scan",
            "🔬 API موديل الصور": "🔬 Vision API Docs",
            "🌾 API محرك Agri-RAG": "🌾 Agri-RAG API Docs",
            "👁️ التشخيص البصري بالصورة": "👁️ Computer Vision Leaf Diagnosis",
            "① اختيار/تصوير الورقة": "① Select / Snap Leaf",
            "② فحص بالذكاء الاصطناعي": "② AI Vision Scan",
            "③ التشخيص وخطة العلاج": "③ Diagnosis & Prescription",
            "🎛️ موديل الصور:": "🎛️ Vision Model:",
            "⚡ EfficientNetV2B2 (الأساسي)": "⚡ EfficientNetV2B2 (Primary)",
            "🧪 ResNet18 (إضافي)": "🧪 ResNet18 (Secondary)",
            "تغيير الصورة": "Change Image",
            "اضغط لرفع صورة ورقة النبات أو تصويرها بالكاميرا": "Click to upload a plant leaf photo or capture with camera",
            "🖼️ اختر من المعرض": "🖼️ Choose from Gallery",
            "📷 تصوير بالكاميرا": "📷 Capture with Camera",
            "🔍 2. فحص وإظهار العلاج": "🔍 2. Diagnose & Show Treatment",
            "🎬 عينات عرض Demo Day الفورية:": "🎬 Instant Demo Day Samples:",
            "تشخيص النبات": "Plant Diagnosis",
            "المحصول": "Crop Type",
            "💊 خطة العلاج والجرعات الموصى بها من الخبير الزراعي:": "💊 Recommended Treatment Plan & Dosages:",
            "🔊 اسمع الروشتة بالمصري": "🔊 Listen in Egyptian Arabic",
            "💬 متابعة النقاش والسؤال عن هذه الصورة في الشات ⬅️": "💬 Continue Discussion About This Leaf in Chat →",
            "💬 المستشار الزراعي الذكي": "💬 Smart Agricultural Advisor",
            "🌾 محرك Agri-RAG": "🌾 Agri-RAG Engine",
            "🧠 اختيار محرك الذكاء:": "🧠 RAG Engine:",
            "🌾 محرك Agri-RAG (الأساسي المعتمد)": "🌾 Agri-RAG Engine (Primary Grounded)",
            "🤖 محرك RAG الاحتياطي (اختياري)": "🤖 Fallback RAG Engine",
            "🎯 موقعي (GPS)": "🎯 My GPS",
            "⚙️ تعديل أرضي ▾": "⚙️ Edit Farm ▾",
            "🗣️ م. شاكر (مصري)": "🗣️ Eng. Shakir (Egyptian)",
            "🗣️ م. سلمى (مصرية)": "🗣️ Eng. Salma (Egyptian)",
            "🔊 نطق تلقائي": "🔊 Auto-Speak",
            "🧠 الذاكرة متصلة": "🧠 Memory Active",
            "🔄 جلسة جديدة": "🔄 New Session",
            "📍 المحافظة:": "📍 Governorate:",
            "🌱 المحصول:": "🌱 Crop:",
            "🚜 المساحة (فدان):": "🚜 Area (Feddan):",
            "💧 نظام الري:": "💧 Irrigation:",
            "🍅 الندوة المتأخرة بالطماطم": "🍅 Tomato Late Blight",
            "🥔 اللفحة المبكرة بالبطاطس": "🥔 Potato Early Blight",
            "🌾 صدأ القمح": "🌾 Wheat Yellow Rust",
            "🥭 أمراض المانجو": "🥭 Mango Diseases",
            "اكتب سؤالك الزراعي هنا...": "Type your agricultural question here...",
            "🎯 نسبة الثقة": "🎯 Confidence Score",
            "⚡ زمن الاستجابة": "⚡ Response Latency",
            "🌡️ درجة الحرارة": "🌡️ Temperature",
            "📊 عدد الاستشارات": "📊 Consultations",

            // Mobile App (mobile.html)
            "المستشار الزراعي": "Agri-AI Advisor",
            "ذاكرة متصلة • فحص وتشخيص": "Connected Memory • Scan & Diagnose",
            "حسابي": "Account",
            "فحص أوراق النبات بالكاميرا": "Camera Leaf Disease Scanner",
            "دقة 97.6%": "97.6% Accuracy",
            "تصوير الورقة": "Snap Leaf",
            "من المعرض": "From Gallery",
            "🎙️ الصوت المصري:": "🎙️ Egyptian Voice:",
            "نطق تلقائي": "Auto-Speak",
            "المستشار والفحص": "Advisor & Scan",
            "أرضي وموقعي": "My Farm & GPS",
            "سجلي الزراعي": "My History",
            "اسأل عن مرض، جرعة مبيد، أو جدول ري...": "Ask about a plant disease, pesticide dosage, or irrigation...",

            // Login Page (login.html)
            "🏠 رجوع لصفحة العرض الرئيسية": "🏠 Back to Landing Page",
            "سجّل دخولك لحفظ تشخيصات محصولك وتوصيات مزرعتك": "Sign in to save your crop diagnoses and farm prescriptions",
            "الدخول السريع بحساب Google": "Sign in with Google",
            "أو عبر رقم الموبايل / البريد الإلكتروني": "Or with Mobile Number / Email",
            "إنشاء حساب مزارع جديد": "Create New Farmer Account",
            "رقم الموبايل أو البريد الإلكتروني": "Egyptian Mobile Number or Email",
            "مثال: 01012345678 أو email@domain.com": "e.g., 01012345678 or email@domain.com",
            "كلمة المرور": "Password",
            "أدخل كلمة المرور": "Enter your password",
            "تسجيل الدخول بكلمة المرور": "Sign In with Password",
            "👤 الاسم بالكامل (حروف عربية أو إنجليزية فقط)": "👤 Full Name (Arabic or English letters)",
            "الاسم بالكامل": "Full Name",
            "📱 رقم الموبايل المصري (11 رقم) أو البريد الإلكتروني": "📱 Egyptian Mobile Number (11 digits) or Email",
            "📍 المحافظة": "📍 Governorate",
            "المحافظة": "Governorate",
            "🌾 المحصول الأساسي": "🌾 Primary Crop",
            "المحصول الأساسي": "Primary Crop",
            "🚜 مساحة الأرض (بالفدان)": "🚜 Farm Size (Feddan)",
            "مساحة الأرض (فدان)": "Farm Size (Feddan)",
            "💧 نظام الري الأساسي": "💧 Primary Irrigation System",
            "نظام الري": "Irrigation System",
            "🔑 كلمة المرور (6 أحرف أو أرقام غير مكررة على الأقل)": "🔑 Password (At least 6 non-repeating characters)",
            "6 أحرف أو أرقام على الأقل": "At least 6 characters",
            "🔒 تأكيد كلمة المرور": "🔒 Confirm Password",
            "تأكيد كلمة المرور": "Confirm Password",
            "🌱 إنشاء الحساب والدخول فوراً": "🌱 Create Account & Sign In",
            "إنشاء الحساب والدخول فوراً": "Create Account & Sign In",
            "العودة للرئيسية": "Back to Home",
            "الرئيسية": "Home",
            "التشخيص السريع بالصورة": "Quick Photo Diagnosis",
            "خدمة الإرشاد الزراعي الرقمي لمحافظات مصر": "Digital Agricultural Advisory for Egypt's Governorates",
            "فحص أمراض النباتات بالصورة، وتوصيات علاجية معتمدة من نشرات وزارة الزراعة المصرية": "Visual Plant Disease Diagnosis & Verified Egyptian Ministry of Agriculture Prescriptions",
            "لوحة الكمبيوتر": "Desktop Dashboard",
            "تطبيق الموبايل": "Mobile App",
            "الفحص السريع": "Quick Scan",
            "كيف نعمل": "How It Works",
            "مرشدك الزراعي المصري": "Your Egyptian Agricultural Advisor",
            "فحص النبات والمستشار": "Plant Scanner & Advisor",
            "إحصائيات المحاصيل": "Crop Analytics",
            "نسخة الموبايل": "Mobile View",
            "نماذج جاهزة للتجربة السريعة:": "Instant Sample Cases:",
            "فحص بصري دقيق": "Precision Visual Scan",
            "نتيجة الفحص": "Diagnosis Result",
            "إرشاد زراعي معتمد": "Verified Agronomic Guidance",
            "ابدأ الفحص والاستشارة مجاناً": "Start Free Diagnosis & Consultation",
            "لوحة العرض الكاملة": "Full Desktop Dashboard",
            "اسمع ترحيب المهندس بالمصري": "Hear Egyptian Agronomist Welcome",
            "فحص 38 مرض وآفة بالصورة": "38 Plant Diseases Diagnosed by Photo",
            "صوت مصري واضح ومسموع": "Clear Natural Egyptian Voice",
            "طقس لحظي لـ 27 محافظة مصرية": "Live Weather for 27 Governorates",
            "جاهز لفحص محصولك أو استشارة المهندس الزراعي؟": "Ready to Diagnose Your Crop or Consult the Agronomist?",
            "افتح لوحة التشخيص الكاملة": "Open Full Diagnosis Dashboard",
            "تسجيل دخول / حساب مزارع": "Sign In / Farmer Account",
            "المتابعة بحساب Google": "Continue with Google",
            "الدخول السريع بالبريد أو رقم الموبايل": "Quick Sign-In with Email or Mobile",
            "صفحة الدخول وإنشاء حساب مزارع كامل": "Full Login & Farmer Registration Page"
        },

        fr: {
            // Top Bar & Navbar
            "🏆 وضع عرض Demo Day التفاعلي": "🏆 Mode Démo Interactif (Demo Day)",
            "منصة الذكاء الاصطناعي الزراعي المصرية (Vision + Hybrid Agri-RAG + Gemini 3.8 Neural Voice)": "Plateforme IA Agricole Égyptienne (Vision + Agri-RAG Hybride + Voix Neurale Gemini 3.8)",
            "💻 لوحة الكمبيوتر": "💻 Tableau de Bord PC",
            "📱 تطبيق الموبايل": "📱 Application Mobile",
            "⚡ الفحص السريع": "⚡ Scan Rapide",
            "🧠 معمارية النظام": "🧠 Architecture IA",
            "منصة الزراعة الذكية": "Smart Agriculture AI",
            "Smart Agriculture AI • مرشدك الزراعي المصري": "Smart Agriculture AI • Conseiller Agricole Intelligent",
            "واجهات المنصة": "Interfaces",
            "معمارية الذكاء الاصطناعي": "Architecture IA",
            "المميزات": "Fonctionnalités",
            "المحاصيل المدعومة": "Cultures Supportées",
            "🌙 الوضع الليلي": "🌙 Mode Sombre",
            "☀️ الوضع الفاتح": "☀️ Mode Clair",
            "🔐 تسجيل الدخول": "🔐 Connexion",
            "🚀 افتح المنصة الآن": "🚀 Ouvrir la Plateforme",

            // Hero Section
            "أول مساعد زراعي ذكي يتحدث باللهجة المصرية ومعتمد علمياً": "Premier assistant IA agricole en dialecte égyptien validé scientifiquement",
            "مهندس زراعي خبير في جيبك..": "Un Ingénieur Agronome dans Votre Poche..",
            "يفحص زرعك بالصورة ويكلمك بالمصري!": "Diagnostique vos plantes par photo et vous parle en égyptien !",
            "صوّر ورقة النبات المصابة أو اسأل بصوتك بالعامية المصرية، وهتاخد تشخيص فوري بالرؤية الحاسوبية (": "Prenez en photo une feuille infectée ou posez votre question vocalement pour un diagnostic immédiat (",
            ") مع روشتة علاجية وجرعات دقيقة بالفدان من نشرات": ") et des dosages précis par feddan issus du",
            "مركز البحوث الزراعية": "Centre de Recherche Agricole",
            "مربوطة بطقس محافظتك لحظياً.": "reliés en direct à la météo de votre gouvernorat.",
            "🚀 ابدأ الفحص والاستشارة مجاناً": "🚀 Démarrer le Diagnostic Gratuit",
            "💻 لوحة العرض الكاملة (Desktop)": "💻 Tableau de Bord Complet (PC)",
            "🔊 اسمع ترحيب المهندس بالمصري": "🔊 Écouter l'Accueil Vocal Égyptien",
            "⏹️ إيقاف الصوت المصري": "⏹️ Arrêter l'Audio",
            "⏳ جاري تجهيز الصوت المصري...": "⏳ Préparation de la voix égyptienne...",
            "✅ فحص 38 مرض وآفة بالصورة": "✅ 38 Maladies Végétales Détectées par Vision",
            "✅ نطق بشري مصري طبيعي (Gemini 3.8 TTS)": "✅ Voix Humaine Égyptienne (Gemini 3.8 TTS)",
            "✅ طقس لحظي لـ 27 محافظة مصرية": "✅ Météo en Direct pour 27 Gouvernorats",

            // Hero Interactive Showcase Card
            "محاكاة حية للتشخيص والروشتة (جرّب الضغط)": "Simulation en Direct du Diagnostic (Cliquez pour essayer)",
            "اختر محصولاً لمعاينة تشخيص الرؤية الحاسوبية والرد الصوتي المصري": "Choisissez une culture pour prévisualiser le diagnostic par vision et la prescription vocale",
            "متصل الآن": "En Ligne",
            "🍅 طماطم (ندوة متأخرة)": "🍅 Tomate (Mildiou)",
            "🥔 بطاطس (ندوة مبكرة)": "🥔 Pomme de terre (Alternariose)",
            "🥭 مانجو (بياض دقيقي)": "🥭 Mangue (Oïdium)",
            "🔬 التشخيص: طماطم — الندوة المتأخرة (Late Blight)": "🔬 Diagnostic : Tomate — Mildiou (Late Blight)",
            "🔬 التشخيص: بطاطس — الندوة المبكرة (Early Blight)": "🔬 Diagnostic : Pomme de terre — Alternariose (Early Blight)",
            "🔬 التشخيص: مانجو — البياض الدقيقي ولفحة الأزهار": "🔬 Diagnostic : Mangue — Oïdium",
            "ثقة 97.8%": "Confiance 97.8%",
            "ثقة 96.4%": "Confiance 96.4%",
            "ثقة 95.9%": "Confiance 95.9%",
            "النموذج:": "Modèle :",
            "فلتر النباتات:": "Filtre Végétal :",
            "✅ ورقة نبات حقيقية": "✅ Feuille Végétale Vérifiée",
            "📚 نشرة وزارة الزراعة #142": "📚 Bulletin Ministère de l'Agriculture #142",
            "📚 نشرة معهد أمراض النبات #89": "📚 Bulletin Institut de Phytopathologie #89",
            "📚 نشرة بحوث البساتين — المانجو": "📚 Bulletin Recherche Horticole — Mangue",
            "🤖 روشتة المهندس الزراعي الذكي (باللهجة المصرية):": "🤖 Prescription de l'Agronome IA (Dialecte Égyptien) :",
            "Agri-RAG الهجين": "Agri-RAG Hybride",
            "«يا باشمهندس، الورقة دي فيها": "« Ingénieur, cette feuille présente le",
            "ندوة متأخرة في الطماطم": "Mildiou de la Tomate",
            "والجو الرطب بيزودها. أول خطوة توقف الري بالغمر وتقلل الرطوبة، وترش فوراً": "favorisé par l'humidité. Arrêtez l'irrigation par submersion et pulvérisez immédiatement",
            "أوكسي كلور النحاس أو ريدوميل جولد": "Oxychlorure de Cuivre ou Ridomil Gold",
            "بمعدل 250 جرام لكل 100 لتر ميه آخر النهار.»": "à raison de 250g pour 100L d'eau en fin d'après-midi. »",
            "«بص يا حاج، الحلقات البنية دي": "« Ces anneaux bruns concentriques indiquent",
            "ندوة مبكرة في البطاطس": "l'Alternariose de la Pomme de terre",
            ". لم الورق السفلي المصاب بره الغيط، ورش": ". Retirez les feuilles basses infectées et pulvérisez",
            "أزوكسي ستروبين أو مانكوزيب": "Azoxystrobine ou Mancozèbe",
            "بمعدل 250 جرام لكل 100 لتر ميه، مع اهتمامك بتسميد البوتاسيوم عشان يقوي العرش.»": "à 250g pour 100L d'eau avec un apport potassique. »",
            "«خلي بالك يا باشمهندس، الشماريخ الزهرية عليها": "« Attention, les panicules florales présentent",
            "بياض دقيقي في المانجو": "l'Oïdium du Manguier",
            ". رش فوراً": ". Pulvérisez immédiatement du",
            "كبريت ميكروني": "Soufre Micronisé",
            "بمعدل 250 جرام لكل 100 لتر ميه في الصباح الباكر أو قبل الغروب، وابعد عن الرش وقت الحر الشديد.»": "à 250g pour 100L d'eau tôt le matin ou avant le coucher du soleil. »",
            "🔊 استمع لهذه الروشتة بالصوت المصري": "🔊 Écouter la Prescription en Voix Égyptienne",
            "💬 افتح في المنصة ←": "💬 Ouvrir dans la Plateforme →",
            "🌤️ طقس المحافظات الزراعي المباشر:": "🌤️ Météo Agricole en Direct :",
            "جاري جلب حالة الجو...": "Chargement de la météo...",

            // Stats Strip
            "مرض وآفة نباتية بالصورة": "Maladies & Ravageurs Détectés par Image",
            "نموذج EfficientNetV2B2 + فلتر النباتات": "EfficientNetV2B2 + Filtre Intelligent",
            "محافظة مصرية مربوطة بالطقس": "Gouvernorats Égyptiens Reliés à la Météo",
            "حرارة • رطوبة • سرعة رياح • إنذار مبكر": "Température • Humidité • Vent • Alerte Précoce",
            "عملية فحص واستشارة زراعية": "Diagnostics & Consultations en Direct",
            "تحديث لحظي من قاعدة بيانات المنصة": "Télémétrie en temps réel depuis la base de données",
            "تحدث واستماع بالعامية المصرية": "Conversation Vocale en Arabe Égyptien",

            // Architecture Section
            "معمارية الذكاء الاصطناعي (System Architecture)": "Architecture du Système IA",
            "كيف تعمل المنصة خلف الكواليس في أقل من ثانية؟": "Comment Fonctionne la Plateforme en Moins d'une Seconde ?",
            "خط أنابيب ذكي من 4 مراحل يدمج الرؤية الحاسوبية، الاسترجاع المعرفي الهجين الموثق، والنماذج الصوتية العصبية باللهجة المصرية.": "Un pipeline intelligent en 4 étapes intégrant Vision par Ordinateur, RAG Hybride et Synthèse Vocale Neurale Égyptienne.",
            "المرحلة 01 • الفلترة الذكية": "Étape 01 • Filtrage Intelligent",
            "بوابة التحقق من النبات": "Validation de Feuille Végétale",
            "فحص جودة الإضاءة وحدة الصورة واستبعاد الصور غير النباتية أو العشوائية تلقائياً قبل التشغيل لضمان دقة التشخيص 100%.": "Vérifie l'éclairage et la netteté et rejette automatiquement les images non végétales avant l'analyse.",
            "المرحلة 02 • الرؤية الحاسوبية": "Étape 02 • Vision par Ordinateur",
            "تشخيص أمراض الأوراق": "Classification des Maladies Foliaires",
            "تحليل البقع والندوات والبياض الدقيقي ونقص العناصر مع حساب نسبة الثقة وهامش التأكد (Confidence Margin) للتعلم النشط.": "Analyse les taches, le mildiou et l'oïdium avec calcul de la marge de confiance pour l'apprentissage actif.",
            "المرحلة 03 • الاسترجاع الهجين": "Étape 03 • Recherche Hybride RAG",
            "المستشار الزراعي المعتمد": "Conseiller Agricole Certifié (Agri-RAG)",
            "دمج البحث الدلالي واللفظي في نشرات مركز البحوث الزراعية مع طقس المحافظة ومساحة المزرعة بالفدان ونوع الري.": "Combine recherche sémantique (e5) et lexicale (BM25) dans les bulletins officiels avec la météo et la surface en feddans.",
            "المرحلة 04 • النطق العصبي المصري": "Étape 04 • Voix Neurale Égyptienne",
            "توليد الصوت المصري الطبيعي": "Synthèse Vocale Égyptienne Naturelle",
            "تحويل الأرقام والرموز العلمية إلى عامية مصرية زراعية سليمة وتوليد صوت بشري مصري (رجالي/نسائي) فائق الوضوح.": "Convertit les unités scientifiques en arabe égyptien parlé et génère une voix humaine naturelle via Gemini 3.8 TTS.",

            // Interfaces & Features
            "واجهات مصممة لكل مزارع ومهندس": "Interfaces Conçues pour Chaque Agriculteur & Ingénieur",
            "اختر الواجهة المناسبة لجهازك أو لعرضك": "Choisissez l'Interface Adaptée à Votre Appareil",
            "صممنا المنصة بثلاث واجهات متكاملة لتناسب العمل الميداني بالموبايل في الحقل أو العرض التفصيلي على شاشة الكمبيوتر.": "Trois interfaces complémentaires pour le travail de terrain sur mobile ou les présentations détaillées sur PC.",
            "الأكثر استخداماً في الحقل": "Plus Utilisé au Champ",
            "📱 تطبيق الموبايل الذكي": "📱 Application Mobile Intelligente",
            "واجهة تطبيق أصلية سريعة للموبايل: صوّر الورقة بالكاميرا مباشرة، سجل سؤالك بالصوت، واسمع الروشتة باللهجة المصرية مع تحديد موقع مزرعتك بالـ GPS.": "Interface mobile rapide : photographiez la feuille, posez votre question vocalement et écoutez la prescription avec localisation GPS.",
            "افتح واجهة الموبايل ←": "Ouvrir l'App Mobile →",
            "مثالية لعرض Demo Day": "Idéal pour le Demo Day",
            "💻 منصة الكمبيوتر المتكاملة": "💻 Poste de Contrôle PC Complet",
            "شاشة مزدوجة تجمع بين فحص الصور، المحادثة الذكية مع المهندس الزراعي، أمثلة العرض الجاهزة، سجل فحوصات المزرعة، ومؤشرات الطقس والإنذار المبكر.": "Double panneau réunissant diagnostic photo, chat IA, exemples Demo Day en 1 clic, historique et météo en direct.",
            "افتح لوحة الكمبيوتر ←": "Ouvrir le Tableau de Bord →",
            "بضغطتين فقط": "En 2 Clics",
            "⚡ الفحص السريع المبسط": "⚡ Diagnostic Rapide Simplifié",
            "واجهة مبسطة جداً للفحص الفوري: ارفع صورة الورقة واضغط زر التشخيص لتحصل على اسم المرض والروشتة العلاجية المسموعة فوراً.": "Interface ultra-simple : téléversez la photo d'une feuille et cliquez pour obtenir le diagnostic et le traitement vocal.",
            "افتح الفحص المبسط ←": "Ouvrir le Scan Rapide →",
            "تقنيات الذكاء الاصطناعي الزراعي": "Technologies IA Agricoles",
            "كل ما تحتاجه لحماية محصولك وزيادة الإنتاجية": "Tout pour Protéger Vos Cultures et Augmenter le Rendement",
            "منظومة متكاملة تربط الرؤية الحاسوبية باسترجاع المعرفة الموثقة والطقس الحي لخدمة الفلاح والمهندس الزراعي المصري.": "Un écosystème complet reliant vision par ordinateur, recherche documentaire certifiée et météo en temps réel.",
            "تشخيص أمراض النبات بالصورة": "Diagnostic Visuel par Photo",
            "نموذج": "Modèle",
            "مدعوم بفلتر ذكي يرفض الصور غير النباتية تلقائياً ويشخص الأمراض الفطرية والبكتيرية ونقص العناصر بدقة عالية.": "doté d'un filtre intelligent rejetant les images non végétales et diagnostiquant les maladies fongiques et bactériennes.",
            "روشتات معتمدة (Agri-RAG)": "Prescriptions Certifiées (Agri-RAG)",
            "محرك بحث هجين (": "Moteur hybride (",
            ") يستخرج الجرعات والمبيدات الموصى بها من نشرات مركز البحوث الزراعية ووزارة الزراعة المصرية بدون تأليف.": ") extrayant les doses officielles des bulletins du Centre de Recherche Agricole sans hallucination.",
            "يتحدث ويسمع باللهجة المصرية": "Parle et Écoute en Dialecte Égyptien",
            "سجل سؤالك بصوتك بالعامية المصرية، واسمع الإجابة بصوت بشري مصري طبيعي وواضح (رجالي أو نسائي) يشرح لك خطوات العلاج والجرعات بسهولة.": "Posez votre question vocalement et écoutez la réponse avec une voix égyptienne naturelle (homme ou femme).",
            "ربط تلقائي بطقس محافظتك": "Synchronisation Météo Automatique",
            "يتابع درجة الحرارة والرطوبة وسرعة الرياح في محافظتك (أو عبر الـ GPS) لينبهك لأوقات انتشار الفطريات وأفضل ميعاد للرش أو الري.": "Suit la température, l'humidité et le vent dans votre gouvernorat (ou par GPS) pour optimiser le moment de pulvérisation.",
            "ذاكرة ذكية لبيانات مزرعتك": "Mémoire Intelligente de Votre Ferme",
            "يتذكر اسمك، محصولك الأساسي، مساحة أرضك بالفدان، ونوع الري (تنقيط، غمر، رش) ليحسب لك التوصيات على مقاس أرضك بالضبط.": "Mémorise votre culture, la superficie en feddans et le système d'irrigation pour calculer des doses sur mesure.",
            "مشاركة فورية على واتساب": "Partage Instantané sur WhatsApp",
            "انسخ الروشتة العلاجية أو شاركها بضغطة زر واحدة عبر واتساب مع العمال أو المهندسين في المزرعة لتنفيذ خطة العلاج فوراً.": "Copiez ou partagez la prescription en un clic sur WhatsApp avec votre équipe sur le terrain.",

            // Crops
            "تغطية واسعة للمحاصيل المصرية": "Large Couverture des Cultures Égyptiennes",
            "اضغط على أي محصول لبدء استشارة فورية عنه": "Cliquez sur une Culture pour Lancer une Consultation",
            "تدعم المنصة تشخيص واستشارات المحاصيل الاستراتيجية والخضر والفاكهة في البيئة الزراعية المصرية.": "Prend en charge le diagnostic et le conseil pour les grandes cultures, légumes et arbres fruitiers en Égypte.",
            "🍅 الطماطم": "🍅 Tomate",
            "🥔 البطاطس": "🥔 Pomme de terre",
            "🥭 المانجو": "🥭 Mangue",
            "🌾 القمح": "🌾 Blé",
            "🌽 الذرة": "🌽 Maïs",
            "🌾 الأرز": "🌾 Riz",
            "🍇 العنب": "🍇 Raisin",
            "🫑 الفلفل": "🫑 Poivron",
            "🍊 الموالح والبرتقال": "🍊 Agrumes & Orange",
            "🍓 الفراولة": "🍓 Fraise",
            "🥒 الخيار والقرعيات": "🥒 Concombre",
            "🫒 الزيتون": "🫒 Olive",
            "🌴 النخيل": "🌴 Palmier Dattier",

            // Bottom CTA & Dashboard & Login
            "جاهز لتجربة المنصة الحية أو استعراضها أمام لجنة التحكيم؟": "Prêt à Tester la Plateforme en Direct devant le Jury ?",
            "افتح لوحة التحكم الكاملة بضغطة واحدة، أو سجّل حساب مزرعتك لحفظ تاريخ الفحوصات والاستشارات الخاصة بأرضك.": "Ouvrez le tableau de bord complet en un clic ou créez un compte pour sauvegarder l'historique de votre ferme.",
            "💻 افتح لوحة العرض الكاملة": "💻 Ouvrir le Tableau de Bord",
            "📱 افتح تطبيق الموبايل": "📱 Ouvrir l'App Mobile",
            "👤 تسجيل دخول / حساب مزارع": "👤 Connexion / Compte Agriculteur",
            "منصة الزراعة الذكية (Smart Agriculture AI) — جميع الحقوق محفوظة © 2026": "Smart Agriculture AI — Tous droits réservés © 2026",
            "نسخة الكمبيوتر": "Version PC",
            "تطبيق الموبايل": "App Mobile",
            "الفحص السريع": "Scan Rapide",
            "تسجيل الدخول": "Connexion",
            "الخبير الزراعي الذكي": "Conseiller Agricole Intelligent",
            "رجوع": "Retour",
            "🔐 دخول": "🔐 Connexion",
            "✨ حساب جديد": "✨ Inscription",
            "📜 سجلي": "📜 Historique",
            "🚪 خروج": "🚪 Déconnexion",
            "🏠 صفحة العرض (Landing)": "🏠 Page d'Accueil (Landing)",
            "🤖 المساعد الذكي والتشخيص": "🤖 Assistant IA & Diagnostic",
            "📊 لوحة تحليلات AgriTech (Power BI)": "📊 Analytique AgriTech (Power BI)",
            "📱 نسخة الموبايل (App)": "📱 Version Mobile (App)",
            "🎯 التشخيص السريع بالصورة": "🎯 Diagnostic Photo Rapide",
            "🔬 API موديل الصور": "🔬 Docs API Vision",
            "🌾 API محرك Agri-RAG": "🌾 Docs API Agri-RAG",
            "👁️ التشخيص البصري بالصورة": "👁️ Diagnostic Visuel par Image",
            "① اختيار/تصوير الورقة": "① Choisir / Photographier",
            "② فحص بالذكاء الاصطناعي": "② Analyse Vision IA",
            "③ التشخيص وخطة العلاج": "③ Diagnostic & Traitement",
            "🎛️ موديل الصور:": "🎛️ Modèle Vision :",
            "⚡ EfficientNetV2B2 (الأساسي)": "⚡ EfficientNetV2B2 (Principal)",
            "🧪 ResNet18 (إضافي)": "🧪 ResNet18 (Secondaire)",
            "اضغط لرفع صورة ورقة النبات أو تصويرها بالكاميرا": "Cliquez pour téléverser une feuille ou prendre une photo",
            "🖼️ اختر من المعرض": "🖼️ Galerie",
            "📷 تصوير بالكاميرا": "📷 Caméra",
            "🔍 2. فحص وإظهار العلاج": "🔍 2. Diagnostiquer",
            "🎬 عينات عرض Demo Day الفورية:": "🎬 Échantillons Demo Day Instantanés :",
            "💬 المستشار الزراعي الذكي": "💬 Conseiller Agricole IA",
            "🌾 محرك Agri-RAG": "🌾 Moteur Agri-RAG",
            "🧠 اختيار محرك الذكاء:": "🧠 Moteur IA :",
            "🎯 موقعي (GPS)": "🎯 Mon GPS",
            "⚙️ تعديل أرضي ▾": "⚙️ Ma Ferme ▾",
            "🔊 نطق تلقائي": "🔊 Lecture Auto",
            "🧠 الذاكرة متصلة": "🧠 Mémoire Active",
            "🔄 جلسة جديدة": "🔄 Nouvelle Session",
            "📍 المحافظة:": "📍 Gouvernorat :",
            "🌱 المحصول:": "🌱 Culture :",
            "🚜 المساحة (فدان):": "🚜 Surface (Feddan) :",
            "💧 نظام الري:": "💧 Irrigation :",
            "🍅 الندوة المتأخرة بالطماطم": "🍅 Mildiou de la Tomate",
            "🥔 اللفحة المبكرة بالبطاطس": "🥔 Alternariose Pomme de terre",
            "🌾 صدأ القمح": "🌾 Rouille du Blé",
            "🥭 أمراض المانجو": "🥭 Maladies du Manguier",
            "اكتب سؤالك الزراعي هنا...": "Écrivez votre question agricole ici...",
            "🎯 نسبة الثقة": "🎯 Confiance",
            "⚡ زمن الاستجابة": "⚡ Latence",
            "🌡️ درجة الحرارة": "🌡️ Température",
            "📊 عدد الاستشارات": "📊 Consultations",
            "🏠 رجوع لصفحة العرض الرئيسية": "🏠 Retour à l'Accueil",
            "سجّل دخولك لحفظ تشخيصات محصولك وتوصيات مزرعتك": "Connectez-vous pour sauvegarder vos diagnostics et recommandations",
            "الدخول السريع بحساب Google": "Continuer avec Google",
            "أو عبر رقم الموبايل / البريد الإلكتروني": "Ou par Téléphone / Email",
            "إنشاء حساب مزارع جديد": "Créer un Compte Agriculteur",
            "رقم الموبايل أو البريد الإلكتروني": "Numéro de Mobile ou Email",
            "كلمة المرور": "Mot de Passe",
            "تسجيل الدخول بكلمة المرور": "Se Connecter",
            "🌱 إنشاء الحساب والدخول فوراً": "🌱 Créer le Compte",
            "إنشاء الحساب والدخول فوراً": "Créer le Compte",
            "الاسم بالكامل": "Nom Complet",
            "المحافظة": "Gouvernorat",
            "المحصول الأساسي": "Culture Principale",
            "مساحة الأرض (فدان)": "Surface (Feddan)",
            "نظام الري": "Système d'Irrigation",
            "تأكيد كلمة المرور": "Confirmer le Mot de Passe",
            "العودة للرئيسية": "Retour à l'Accueil",
            "الرئيسية": "Accueil",
            "التشخيص السريع بالصورة": "Diagnostic Photo Rapide",
            "خدمة الإرشاد الزراعي الرقمي لمحافظات مصر": "Service de Conseil Agricole Numérique pour l'Égypte",
            "فحص أمراض النباتات بالصورة، وتوصيات علاجية معتمدة من نشرات وزارة الزراعة المصرية": "Diagnostic Visuel des Plantes & Recommandations du Ministère de l'Agriculture",
            "لوحة الكمبيوتر": "Tableau de Bord PC",
            "تطبيق الموبايل": "Application Mobile",
            "الفحص السريع": "Scan Rapide",
            "كيف نعمل": "Comment ça marche",
            "مرشدك الزراعي المصري": "Votre Conseiller Agricole Égyptien",
            "فحص النبات والمستشار": "Diagnostic & Conseiller",
            "إحصائيات المحاصيل": "Statistiques Agricoles",
            "نسخة الموبايل": "Version Mobile",
            "نماذج جاهزة للتجربة السريعة:": "Exemples Rapides à Tester :",
            "فحص بصري دقيق": "Analyse Visuelle Précise",
            "نتيجة الفحص": "Résultat du Diagnostic",
            "إرشاد زراعي معتمد": "Conseil Agricole Certifié",
            "ابدأ الفحص والاستشارة مجاناً": "Démarrer le Diagnostic Gratuit",
            "لوحة العرض الكاملة": "Tableau de Bord Complet",
            "اسمع ترحيب المهندس بالمصري": "Écouter l'Accueil Vocal Égyptien",
            "فحص 38 مرض وآفة بالصورة": "38 Maladies Végétales Détectées par Photo",
            "صوت مصري واضح ومسموع": "Voix Égyptienne Claire et Naturelle",
            "طقس لحظي لـ 27 محافظة مصرية": "Météo en Direct pour 27 Gouvernorats",
            "جاهز لفحص محصولك أو استشارة المهندس الزراعي؟": "Prêt à Diagnostiquer Votre Culture ou Consulter l'Agronome ?",
            "افتح لوحة التشخيص الكاملة": "Ouvrir le Tableau de Bord Complet",
            "تسجيل دخول / حساب مزارع": "Connexion / Compte Agriculteur",
            "المتابعة بحساب Google": "Continuer avec Google",
            "الدخول السريع بالبريد أو رقم الموبايل": "Connexion Rapide par Email ou Téléphone",
            "صفحة الدخول وإنشاء حساب مزارع كامل": "Page Complète de Connexion et d'Inscription"
        }
    };

    function getCurrentLang() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY) || 'ar';
            return SUPPORTED.includes(saved) ? saved : 'ar';
        } catch (e) {
            return 'ar';
        }
    }

    function translateTextNode(node, lang) {
        if (!node || node.nodeType !== 3) return;
        const parent = node.parentElement;
        if (!parent) return;
        const tag = parent.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'CODE') return;

        const raw = node.nodeValue || '';
        const trimmed = raw.trim();
        if (!trimmed) return;

        if (node._origAr === undefined) {
            node._origAr = raw;
            node._origTrimmedAr = trimmed;
        } else if (lang !== 'ar' && trimmed !== node._origTrimmedAr) {
            // If dynamic JS updated the text in Arabic (e.g., scenario switcher or theme toggle), update _origAr if it matches a known Arabic key
            if ((DICT.en && DICT.en[trimmed]) || (DICT.fr && DICT.fr[trimmed])) {
                node._origAr = raw;
                node._origTrimmedAr = trimmed;
            }
        }

        if (lang === 'ar') {
            if (node.nodeValue !== node._origAr) {
                node.nodeValue = node._origAr;
            }
            return;
        }

        const langDict = DICT[lang] || {};
        const key = node._origTrimmedAr;
        if (langDict[key]) {
            node.nodeValue = node._origAr.replace(key, langDict[key]);
        }
    }

    function translateAttributes(root, lang) {
        if (!root || !root.querySelectorAll) return;
        const inputs = root.querySelectorAll('input[placeholder], textarea[placeholder]');
        inputs.forEach(el => {
            if (el._origPhAr === undefined) {
                el._origPhAr = el.getAttribute('placeholder') || '';
            }
            if (lang === 'ar') {
                el.setAttribute('placeholder', el._origPhAr);
            } else {
                const t = (DICT[lang] || {})[el._origPhAr.trim()];
                if (t) el.setAttribute('placeholder', t);
            }
        });
    }

    function walkAndTranslate(root, lang) {
        if (!root) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
        let n;
        while ((n = walker.nextNode())) {
            translateTextNode(n, lang);
        }
        translateAttributes(root, lang);
    }

    function applyLanguage(lang) {
        const cleanLang = SUPPORTED.includes(lang) ? lang : 'ar';
        try {
            localStorage.setItem(STORAGE_KEY, cleanLang);
        } catch (e) {}

        document.documentElement.setAttribute('lang', cleanLang);
        document.documentElement.setAttribute('dir', cleanLang === 'ar' ? 'rtl' : 'ltr');

        if (document.body) {
            walkAndTranslate(document.body, cleanLang);
        }

        const selectEl = document.getElementById('agriGlobalLangSelect');
        if (selectEl && selectEl.value !== cleanLang) {
            selectEl.value = cleanLang;
        }

        try {
            window.dispatchEvent(new CustomEvent('agri-lang-changed', { detail: { lang: cleanLang } }));
        } catch (e) {}
    }

    function injectLangSwitcherUI() {
        if (document.getElementById('agriGlobalLangSelect')) return;

        const select = document.createElement('select');
        select.id = 'agriGlobalLangSelect';
        select.setAttribute('aria-label', 'Language Switcher');
        select.title = 'تغيير اللغة / Change Language / Changer la langue';
        select.style.cssText = [
            'padding: 0.45rem 0.7rem',
            'border-radius: 12px',
            'border: 1px solid rgba(45, 106, 79, 0.35)',
            'background: var(--bg-card, #ffffff)',
            'color: var(--text-main, var(--text-light, #18241D))',
            'font-family: Cairo, sans-serif',
            'font-size: 0.82rem',
            'font-weight: 800',
            'cursor: pointer',
            'outline: none',
            'box-shadow: 0 2px 8px rgba(0,0,0,0.05)'
        ].join(';');

        select.innerHTML = [
            '<option value="ar">🇪🇬 العربية</option>',
            '<option value="en">🇬🇧 English</option>',
            '<option value="fr">🇫🇷 Français</option>'
        ].join('');

        select.value = getCurrentLang();
        select.addEventListener('change', function () {
            applyLanguage(this.value);
        });

        // Mount into the appropriate top bar on each page
        const navAuthArea = document.getElementById('navAuthArea'); // landing.html
        const topBackBar = document.querySelector('.top-back-bar'); // login.html
        const topActions = document.querySelector('.top-actions'); // mobile.html
        const headerActions = document.querySelector('.header-actions'); // simple.html
        const navContainer = document.querySelector('.nav-container'); // index.html

        if (navAuthArea) {
            navAuthArea.insertBefore(select, navAuthArea.firstChild);
        } else if (topBackBar) {
            topBackBar.appendChild(select);
        } else if (topActions) {
            select.style.padding = '4px 7px';
            select.style.fontSize = '0.74rem';
            topActions.insertBefore(select, topActions.firstChild);
        } else if (headerActions) {
            headerActions.insertBefore(select, headerActions.firstChild);
        } else if (navContainer) {
            navContainer.appendChild(select);
        }
    }

    window.AGRI_I18N = {
        getLang: getCurrentLang,
        setLang: applyLanguage,
        refresh: function () {
            applyLanguage(getCurrentLang());
        }
    };

    function init() {
        injectLangSwitcherUI();
        applyLanguage(getCurrentLang());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
