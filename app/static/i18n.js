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

    // ─── Smart Guest Usage Gate & Instant In-Page Login Modal ───────────
    let currentGuestQuota = null;

    function renderGuestQuotaPill(quota) {
        currentGuestQuota = quota;
        let pill = document.getElementById('agri-guest-quota-pill');
        if (!quota || quota.is_authenticated || !quota.enforce_login) {
            if (pill) pill.style.display = 'none';
            return;
        }
        if (window.location.pathname.startsWith('/login') || window.location.pathname.startsWith('/dev-panel')) {
            return;
        }
        if (!pill) {
            pill = document.createElement('button');
            pill.id = 'agri-guest-quota-pill';
            pill.type = 'button';
            pill.onclick = function () {
                window.openAgriGuestGateModal();
            };
            pill.style.cssText = [
                'display: inline-flex',
                'align-items: center',
                'gap: 6px',
                'padding: 5px 11px',
                'border-radius: 999px',
                'font-family: Cairo, sans-serif',
                'font-size: 0.76rem',
                'font-weight: 800',
                'cursor: pointer',
                'transition: all 0.2s ease',
                'border: 1px solid rgba(212, 163, 89, 0.55)',
                'background: rgba(212, 163, 89, 0.14)',
                'color: var(--text-main, var(--text-light, #18241D))',
                'box-shadow: 0 2px 8px rgba(0,0,0,0.06)'
            ].join(';');

            const navContainer = document.querySelector('.nav-container'); // index.html
            const topActions = document.querySelector('.top-actions'); // mobile.html
            const headerLinks = document.querySelector('.header-links'); // simple.html
            const navAuthArea = document.getElementById('navAuthArea'); // landing.html

            if (navContainer) {
                navContainer.insertBefore(pill, navContainer.firstChild);
            } else if (topActions) {
                pill.style.fontSize = '0.68rem';
                pill.style.padding = '3px 8px';
                topActions.insertBefore(pill, topActions.firstChild);
            } else if (headerLinks) {
                headerLinks.insertBefore(pill, headerLinks.firstChild);
            } else if (navAuthArea) {
                navAuthArea.insertBefore(pill, navAuthArea.firstChild);
            }
        }

        const rem = Number(quota.remaining_free ?? 3);
        const maxU = Number(quota.max_free_uses ?? 3);
        pill.style.display = 'inline-flex';
        if (rem <= 0) {
            pill.style.borderColor = 'rgba(220, 38, 38, 0.55)';
            pill.style.background = 'rgba(220, 38, 38, 0.12)';
            pill.style.color = '#dc2626';
            pill.innerHTML = `🔒 انتهت تجارب الزائر (${maxU}/${maxU}) — سجّل دخولك مجاناً`;
        } else {
            pill.style.borderColor = 'rgba(212, 163, 89, 0.55)';
            pill.style.background = 'rgba(212, 163, 89, 0.14)';
            pill.style.color = 'inherit';
            pill.innerHTML = `🎁 متبقي ${rem} من ${maxU} تجارب كزائر — سجّل مجاناً`;
        }
    }

    async function refreshGuestQuota() {
        if (window.location.pathname.startsWith('/login') || window.location.pathname.startsWith('/dev-panel')) return;
        try {
            const headers = {};
            const tok = localStorage.getItem('agri_token');
            if (tok) headers['Authorization'] = 'Bearer ' + tok;
            const res = await origFetch('/api/auth/me', { headers: headers, credentials: 'same-origin' });
            if (res.ok) {
                const data = await res.clone().json();
                if (data && data.guest_quota) {
                    renderGuestQuotaPill(data.guest_quota);
                }
            }
        } catch (e) {}
    }

    function ensureGuestGateModalExists() {
        let overlay = document.getElementById('agri-guest-gate-overlay');
        if (overlay) return overlay;

        overlay = document.createElement('div');
        overlay.id = 'agri-guest-gate-overlay';
        overlay.style.cssText = [
            'position: fixed',
            'inset: 0',
            'z-index: 99999',
            'background: rgba(15, 24, 18, 0.72)',
            'backdrop-filter: blur(6px)',
            'display: none',
            'align-items: center',
            'justify-content: center',
            'padding: 16px',
            'font-family: Cairo, sans-serif',
            'direction: rtl'
        ].join(';');

        const savedGov = localStorage.getItem('agri_gov') || 'القاهرة';
        const savedCrop = localStorage.getItem('agri_crop') || '';

        overlay.innerHTML = `
            <div style="background: var(--bg-card, #ffffff); color: var(--text-main, #18241D); border: 1px solid rgba(45, 106, 79, 0.28); border-radius: 22px; max-width: 460px; width: 100%; padding: 24px 22px; box-shadow: 0 24px 60px rgba(0,0,0,0.32); position: relative; max-height: 92vh; overflow-y: auto;">
                <button type="button" id="agri-guest-gate-close" style="position: absolute; top: 14px; left: 14px; width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(120,120,120,0.25); background: transparent; color: inherit; cursor: pointer; font-weight: 800; font-size: 0.95rem;">✕</button>
                <div style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; background: rgba(45, 106, 79, 0.12); color: #2D6A4F; font-size: 0.78rem; font-weight: 800; margin-bottom: 10px;">
                    🌱 بطاقة المزارع الذكي المجانية
                </div>
                <h3 style="font-size: 1.2rem; font-weight: 900; margin: 0 0 8px 0; line-height: 1.4;">
                    سجّل دخولك في ثوانٍ لمتابعة الفحص والاستشارة مجاناً
                </h3>
                <p id="agri-guest-gate-msg" style="font-size: 0.86rem; opacity: 0.85; line-height: 1.65; margin: 0 0 16px 0;">
                    لقد استخدمت التجارب المجانية المتاحة للزوار. سجّل دخولك الآن مجاناً لحفظ سجل تشخيصاتك ومحادثاتك الزراعية وربطها بمزرعتك وموقعك تلقائياً!
                </p>

                <!-- Option 1: 1-Click Google Login -->
                <button type="button" id="agri-gate-google-btn" style="width: 100%; display: flex; align-items: center; justify-content: center; gap: 10px; padding: 12px 16px; border-radius: 14px; border: 1px solid rgba(45, 106, 79, 0.3); background: #ffffff; color: #1f2937; font-family: Cairo, sans-serif; font-size: 0.92rem; font-weight: 800; cursor: pointer; box-shadow: 0 3px 10px rgba(0,0,0,0.06); margin-bottom: 14px;">
                    <svg width="20" height="20" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
                    <span>المتابعة بحساب Google في ثانية</span>
                </button>

                <div style="display: flex; align-items: center; gap: 10px; margin: 12px 0; font-size: 0.78rem; opacity: 0.7;">
                    <div style="flex: 1; height: 1px; background: rgba(120,120,120,0.25);"></div>
                    <span>أو سجّل سريعاً في 5 ثوانٍ بدون كلمة مرور</span>
                    <div style="flex: 1; height: 1px; background: rgba(120,120,120,0.25);"></div>
                </div>

                <!-- Option 2: Instant 5-Second Farmer Sign-In -->
                <form id="agri-gate-quick-form" style="display: flex; flex-direction: column; gap: 10px;">
                    <div>
                        <label style="display: block; font-size: 0.78rem; font-weight: 800; margin-bottom: 4px;">الاسم الكامل *</label>
                        <input type="text" id="agri-gate-name" required placeholder="مثال: م. أحمد / الحاج محمود" style="width: 100%; padding: 10px 12px; border-radius: 11px; border: 1px solid rgba(45, 106, 79, 0.3); background: var(--bg-input, rgba(0,0,0,0.03)); color: inherit; font-family: Cairo, sans-serif; font-size: 0.88rem; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.78rem; font-weight: 800; margin-bottom: 4px;">رقم الموبايل المصري أو البريد الإلكتروني *</label>
                        <input type="text" id="agri-gate-ident" required placeholder="01012345678 أو name@gmail.com" style="width: 100%; padding: 10px 12px; border-radius: 11px; border: 1px solid rgba(45, 106, 79, 0.3); background: var(--bg-input, rgba(0,0,0,0.03)); color: inherit; font-family: Cairo, sans-serif; font-size: 0.88rem; direction: ltr; text-align: right; box-sizing: border-box;">
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <div>
                            <label style="display: block; font-size: 0.75rem; font-weight: 700; margin-bottom: 3px;">المحافظة</label>
                            <select id="agri-gate-gov" style="width: 100%; padding: 9px 10px; border-radius: 11px; border: 1px solid rgba(45, 106, 79, 0.3); background: var(--bg-card, #ffffff); color: inherit; font-family: Cairo, sans-serif; font-size: 0.82rem;">
                                <option value="القاهرة">القاهرة</option>
                                <option value="الجيزة">الجيزة</option>
                                <option value="الإسكندرية">الإسكندرية</option>
                                <option value="البحيرة">البحيرة</option>
                                <option value="كفر الشيخ">كفر الشيخ</option>
                                <option value="الدقهلية">الدقهلية</option>
                                <option value="الشرقية">الشرقية</option>
                                <option value="المنوفية">المنوفية</option>
                                <option value="الغربية">الغربية</option>
                                <option value="القليوبية">القليوبية</option>
                                <option value="الفيوم">الفيوم</option>
                                <option value="بني سويف">بني سويف</option>
                                <option value="المنيا">المنيا</option>
                                <option value="أسيوط">أسيوط</option>
                                <option value="سوهاج">سوهاج</option>
                                <option value="قنا">قنا</option>
                                <option value="الأقصر">الأقصر</option>
                                <option value="أسوان">أسوان</option>
                                <option value="الإسماعيلية">الإسماعيلية</option>
                                <option value="دمياط">دمياط</option>
                                <option value="بورسعيد">بورسعيد</option>
                                <option value="السويس">السويس</option>
                                <option value="مطروح">مطروح</option>
                                <option value="الوادي الجديد">الوادي الجديد</option>
                                <option value="شمال سيناء">شمال سيناء</option>
                                <option value="جنوب سيناء">جنوب سيناء</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 0.75rem; font-weight: 700; margin-bottom: 3px;">المحصول الأساسي</label>
                            <select id="agri-gate-crop" style="width: 100%; padding: 9px 10px; border-radius: 11px; border: 1px solid rgba(45, 106, 79, 0.3); background: var(--bg-card, #ffffff); color: inherit; font-family: Cairo, sans-serif; font-size: 0.82rem;">
                                <option value="">كل المحاصيل</option>
                                <option value="طماطم">طماطم</option>
                                <option value="بطاطس">بطاطس</option>
                                <option value="قمح">قمح</option>
                                <option value="ذرة">ذرة</option>
                                <option value="مانجو">مانجو</option>
                                <option value="أرز">أرز</option>
                            </select>
                        </div>
                    </div>
                    <div id="agri-gate-error" style="display: none; font-size: 0.8rem; color: #dc2626; font-weight: 700; padding: 6px 10px; border-radius: 8px; background: rgba(220,38,38,0.08);"></div>
                    <button type="submit" id="agri-gate-submit-btn" style="width: 100%; padding: 12px 16px; border-radius: 14px; border: none; background: linear-gradient(135deg, #2D6A4F, #1B4332); color: #ffffff; font-family: Cairo, sans-serif; font-size: 0.94rem; font-weight: 800; cursor: pointer; margin-top: 4px; box-shadow: 0 6px 18px rgba(45, 106, 79, 0.32);">
                        🚀 دخول فوري ومتابعة الفحص مجاناً
                    </button>
                </form>

                <div style="text-align: center; margin-top: 12px; font-size: 0.78rem; opacity: 0.8;">
                    لديك حساب بكلمة مرور؟ <a href="/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}" style="color: #2D6A4F; font-weight: 800; text-decoration: underline;">صفحة تسجيل الدخول الكاملة</a>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const govSel = document.getElementById('agri-gate-gov');
        const cropSel = document.getElementById('agri-gate-crop');
        if (govSel && savedGov) govSel.value = savedGov;
        if (cropSel && savedCrop) cropSel.value = savedCrop;

        document.getElementById('agri-guest-gate-close').onclick = function () {
            overlay.style.display = 'none';
        };
        overlay.addEventListener('click', function (ev) {
            if (ev.target === overlay) overlay.style.display = 'none';
        });

        document.getElementById('agri-gate-google-btn').onclick = function () {
            const nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.href = '/api/auth/google/login?next=' + nextUrl;
        };

        document.getElementById('agri-gate-quick-form').onsubmit = async function (ev) {
            ev.preventDefault();
            const nameVal = (document.getElementById('agri-gate-name').value || '').trim();
            const identVal = (document.getElementById('agri-gate-ident').value || '').trim();
            const govVal = document.getElementById('agri-gate-gov').value || 'القاهرة';
            const cropVal = document.getElementById('agri-gate-crop').value || '';
            const errBox = document.getElementById('agri-gate-error');
            const submitBtn = document.getElementById('agri-gate-submit-btn');

            if (nameVal.length < 2 || identVal.length < 5) {
                errBox.style.display = 'block';
                errBox.textContent = 'يرجى كتابة الاسم ورقم الموبايل أو الإيميل الصحيح.';
                return;
            }
            errBox.style.display = 'none';
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ جاري تفعيل الحساب وربط سجل مزرعتك...';

            const isEmail = identVal.includes('@');
            try {
                const res = await origFetch('/api/auth/social', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        provider: isEmail ? 'google' : 'quick_phone',
                        identifier: identVal,
                        full_name: nameVal,
                        governorate: govVal,
                        primary_crop: cropVal
                    })
                });
                const data = await res.json();
                if (!res.ok || data.status !== 'ok') {
                    const msg = (data && data.detail) ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : 'تعذر تسجيل الدخول، تأكد من صحة رقم الموبايل أو الإيميل.';
                    errBox.style.display = 'block';
                    errBox.textContent = msg;
                    submitBtn.disabled = false;
                    submitBtn.textContent = '🚀 دخول فوري ومتابعة الفحص مجاناً';
                    return;
                }
                if (data.token) localStorage.setItem('agri_token', data.token);
                if (data.user) localStorage.setItem('agri_user', JSON.stringify(data.user));
                if (govVal) localStorage.setItem('agri_gov', govVal);
                if (cropVal) localStorage.setItem('agri_crop', cropVal);

                overlay.style.display = 'none';
                renderGuestQuotaPill({ is_authenticated: true });

                // Refresh header UI on whichever page is active
                if (typeof window.checkAuthSession === 'function') window.checkAuthSession();
                if (typeof window.initProfileAndLocation === 'function') window.initProfileAndLocation();
                if (typeof window.initSimpleAuth === 'function') window.initSimpleAuth();

                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 دخول فوري ومتابعة الفحص مجاناً';
            } catch (err) {
                errBox.style.display = 'block';
                errBox.textContent = 'حدث خطأ في الاتصال، حاول مرة أخرى.';
                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 دخول فوري ومتابعة الفحص مجاناً';
            }
        };

        return overlay;
    }

    window.openAgriGuestGateModal = function (customMessage) {
        const overlay = ensureGuestGateModalExists();
        const msgEl = document.getElementById('agri-guest-gate-msg');
        if (msgEl && customMessage) {
            msgEl.textContent = customMessage;
        }
        overlay.style.display = 'flex';
    };

    // Intercept fetch calls to /api/chat, /api/diagnose, and /api/auth/me
    const origFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
        const urlStr = typeof input === 'string' ? input : (input && input.url ? input.url : '');
        const isAiAction = urlStr.includes('/api/chat') || urlStr.includes('/api/diagnose');
        const isAuthMe = urlStr.includes('/api/auth/me');

        // Automatically attach stored Bearer token if not already present on AI actions
        if (isAiAction) {
            const tok = localStorage.getItem('agri_token');
            if (tok) {
                init = init || {};
                init.headers = init.headers || {};
                if (init.headers instanceof Headers) {
                    if (!init.headers.has('Authorization')) init.headers.set('Authorization', 'Bearer ' + tok);
                } else if (typeof init.headers === 'object' && !init.headers['Authorization']) {
                    init.headers['Authorization'] = 'Bearer ' + tok;
                }
            }
        }

        const response = await origFetch(input, init);

        if (isAuthMe && response.ok) {
            try {
                const cloneData = await response.clone().json();
                if (cloneData && cloneData.guest_quota) {
                    renderGuestQuotaPill(cloneData.guest_quota);
                }
            } catch (e) {}
        } else if (isAiAction) {
            if (response.status === 401) {
                try {
                    const errJson = await response.clone().json();
                    const detail = errJson && errJson.detail ? errJson.detail : {};
                    const msg = (typeof detail === 'object' && detail.message)
                        ? detail.message
                        : 'لقد استنفدت التجارب المجانية للزوار. سجّل دخولك الآن في ثوانٍ لمتابعة الفحص والاستشارة مجاناً وحفظ سجل مزرعتك! 🌱';
                    window.openAgriGuestGateModal(msg);
                    // Return a graceful synthetic JSON response so calling UI shows the prompt cleanly without throwing an unhandled error
                    if (urlStr.includes('/api/chat')) {
                        return new Response(JSON.stringify({
                            answer: '🔒 **يرجى تسجيل الدخول للمتابعة مجاناً:**\n' + msg,
                            sources: [],
                            confidence: 1.0,
                            latency: 0.01,
                            session_id: localStorage.getItem('agri_session_id') || ''
                        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
                    } else if (urlStr.includes('/api/diagnose')) {
                        return new Response(JSON.stringify({
                            is_plant: false,
                            rejection_reason: '🔒 ' + msg,
                            cv_result: {
                                is_plant: false,
                                rejected: true,
                                predicted_class_ar: '🔒 يرجى تسجيل الدخول للمتابعة مجاناً',
                                confidence: 0,
                                top_predictions: []
                            },
                            advice: msg,
                            sources: [],
                            confidence: 0,
                            latency: 0.01
                        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
                    }
                } catch (e) {
                    window.openAgriGuestGateModal();
                }
            } else if (response.ok) {
                setTimeout(refreshGuestQuota, 400);
            }
        }

        return response;
    };

    function init() {
        injectLangSwitcherUI();
        applyLanguage(getCurrentLang());
        setTimeout(refreshGuestQuota, 350);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
