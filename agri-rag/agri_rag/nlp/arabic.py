"""Arabic text normalisation, light tokenisation, query intent analysis, and dynamic response styling."""
from __future__ import annotations

import re
from dataclasses import dataclass

_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_ALEF = re.compile("[إأآٱ]")
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"\w+(?:\.\d+)?", re.UNICODE)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_LETTER_REGEX = re.compile(r"[a-zA-Z\u0621-\u064A]")

_STOPWORDS = frozenset(
    "في من علي الي الى عن ان انا انت هو هي هم ما ماذا ده دي دا ايه اي كل قد كام لو مع او و "
    "بتاع بتاعي هل يا لا مش ممكن عندي عندك هذا هذه ذلك التي الذي على إلى".split()
)

UNINTELLIGIBLE_RESPONSE = (
    "معلش يا غالي، الكلام اللي كتبته مش واضح ليا أو مش مفهوم بالظبط 🌾\n\n"
    "أنا هنا مهندسك وخبيرك الزراعي.. عشان أقدر أساعدك صح، ياريت تقولي:\n"
    "1. **إيه هو محصولك؟** (طماطم، بطاطس، قمح، مانجو، ذرة...)\n"
    "2. **إيه المشكلة أو السؤال اللي شاغلك؟** (اصفرار ورق، بقع، حشرات، مواعيد ري، أو تسميد...)\n\n"
    "📸 أو صوّر ورقة النبات بكاميرا الموبايل من زر الفحص فوق وهشخصهالك على طول!"
)

AMBIGUOUS_CLARIFICATION_RESPONSE = (
    "تحت أمرك يا باشا وجاهز أساعدك فوراً! بس عشان أديك الحل والعلاج المظبوط:\n\n"
    "🌱 **إيه نوع الزرعة أو المحصول اللي بتسأل عنه؟**\n"
    "🔍 **وإيه العرض أو المشكلة اللي لاحظتها في الأرض؟** (زي: نشفان ورق، تسقيط زهر، عفن، أو استفسار عن تسميد معين؟)\n\n"
    "اكتبلي التفاصيل البسيطة دي أو ارفع صورة للورقة، وهقولك تعمل إيه بالظبط خطوة بخطوة."
)

CHIT_CHAT_GREETING_RESPONSE = "وعليكم السلام يا غالي! أهلاً بيك، طمني زرعتك عاملة إيه وإزاي أقدر أساعدك في الغيط النهاردة؟ 🌿"
CHIT_CHAT_THANKS_RESPONSE = "الشكر لله يا باشا، العفو في أي وقت! دا واجبي وتحت أمرك دايماً، وربنا يباركلك في زرعك ومحصولك 🌱"
CHIT_CHAT_CHECKIN_RESPONSE = "الحمد لله بخير طول ما مزارعينا بخير! جاهز لمساعدتك في أي استفسار زراعي أو فحص لمحصولك، اتفضل أنا سامعك."


@dataclass
class QueryAnalysis:
    intent: str  # "unintelligible", "needs_clarification", "chit_chat", "quick_direct", "comprehensive_protocol", "standard_agricultural"
    reason: str
    is_gibberish: bool
    requires_retrieval: bool
    suggested_fast_response: str | None = None
    suggested_max_tokens: int = 600
    dynamic_instruction: str = ""


def strip_diacritics(text: str) -> str:
    return _DIACRITICS.sub("", text)


def normalize_arabic(text: str) -> str:
    """Canonical form for matching: no diacritics/tatweel, unified alef/ya/ta-marbuta, ASCII digits."""
    text = strip_diacritics(text).translate(_DIGITS).lower()
    text = _ALEF.sub("ا", text).replace("ى", "ي").replace("ة", "ه")
    return _WS.sub(" ", text).strip()


def light_stem(token: str) -> str:
    for prefix in _PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            return token[len(prefix):]
    return token


def tokenize(text: str, *, drop_stopwords: bool = True) -> list[str]:
    tokens = [light_stem(t) for t in _TOKEN.findall(normalize_arabic(text))]
    if drop_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    return tokens


def classify_user_query(query: str, has_context: bool = False) -> QueryAnalysis:
    """Classify user query into actionable HCI intent with dynamic conciseness and clarification routing."""
    raw = (query or "").strip()

    # 1. Check for empty / too short / symbols-only
    if not raw or len(raw) < 2:
        return QueryAnalysis(
            intent="unintelligible",
            reason="نص فارغ أو قصير جداً",
            is_gibberish=True,
            requires_retrieval=False,
            suggested_fast_response=UNINTELLIGIBLE_RESPONSE,
        )

    # 2. Check if no letters exist (pure punctuation, symbols, or pure digits)
    if not _LETTER_REGEX.search(raw):
        return QueryAnalysis(
            intent="unintelligible",
            reason="رموز أو أرقام فقط دون حروف لغوية",
            is_gibberish=True,
            requires_retrieval=False,
            suggested_fast_response=UNINTELLIGIBLE_RESPONSE,
        )

    # 3. Repeated single character 4+ times with tiny charset (e.g. "ءءءءءءء", "ههههههههههه", "aaaaaa")
    cleaned_chars = raw.replace(" ", "")
    if re.search(r"(.)\1{4,}", raw) and len(set(cleaned_chars)) <= 2:
        # Check if laughing
        if set(cleaned_chars) == {"ه"}:
            return QueryAnalysis(
                intent="chit_chat",
                reason="ضحك أو تفاعل لطيف",
                is_gibberish=False,
                requires_retrieval=False,
                suggested_fast_response="دوم الضحكة والخير يا غالي! يارب دايماً في خير، قولي إيه اللي شاغلك في زرعتك وأنا معاك 🌱",
            )
        return QueryAnalysis(
            intent="unintelligible",
            reason="تكرار حرفي غير مفهوم",
            is_gibberish=True,
            requires_retrieval=False,
            suggested_fast_response=UNINTELLIGIBLE_RESPONSE,
        )

    # 4. Latin keyboard mash (e.g. "asdfghjkl", "qweqwe", "zxcvbn")
    latin_chars = re.findall(r"[a-zA-Z]", raw)
    arabic_chars = re.findall(r"[\u0621-\u064A]", raw)
    if latin_chars and not arabic_chars:
        clean_lat = raw.lower().strip()
        common_en = {"hi", "hello", "thanks", "thank you", "ok", "yes", "no", "tomato", "potato", "npk", "urea", "wheat", "corn"}
        if clean_lat not in common_en and len(clean_lat) >= 4:
            vowels = sum(1 for c in clean_lat if c in "aeiou")
            if vowels == 0 or len(clean_lat) / max(vowels, 1) > 5:
                return QueryAnalysis(
                    intent="unintelligible",
                    reason="حروف لاتينية عشوائية غير مفهومة",
                    is_gibberish=True,
                    requires_retrieval=False,
                    suggested_fast_response=UNINTELLIGIBLE_RESPONSE,
                )

    norm = normalize_arabic(raw)
    words = norm.split()

    # 5. Chit-chat & Greetings (Quick, polite social responses)
    chit_chat_greetings = [
        "سلام عليكم", "السلام عليكم", "صباح الخير", "مساء الخير", "اهلا", "أهلا",
        "مرحبا", "ازيك", "عامل ايه", "يا باشا", "يا غالي", "يا بشمهندس", "منور", "الله ينور", "هلا"
    ]
    chit_chat_thanks = [
        "شكرا", "شكراً", "تسلم", "تسلملي", "الف شكر", "ألف شكر", "الله يباركلك", "الله يخليك", "جزاك الله خير"
    ]

    # Extended agricultural, horticultural, environmental, and farming keywords
    agri_topic_keywords = {
        "مرض", "امراض", "اعراض", "عرض", "اصابة", "علاج", "دواء", "مكافحة", "وقاية",
        "رش", "رشة", "سماد", "تسميد", "مبيد", "مبيدات", "كيماوي", "عضوي", "كمبوست",
        "زرع", "زرعة", "محصول", "ارض", "غيط", "مزرعة", "حقل", "فدان", "قيراط", "شجرة", "اشجار",
        "طماطم", "بطاطس", "قمح", "ذرة", "عنب", "مانجو", "مانجا", "زيتون", "ارز", "أرز",
        "بصل", "ثوم", "تفاح", "فراولة", "فلفل", "خيار", "كوسة", "باذنجان", "برتقال", "موالح", "ليمون",
        "نخيل", "نخل", "بلح", "تمور", "رمان", "موز", "خوخ", "مشمش", "برقوق", "تين", "كنتالوب", "بطيخ",
        "فول", "لوبيا", "فاصوليا", "بسلة", "بنجر", "قصب", "قطن", "برسيم", "صويا", "فول سوداني",
        "دودة", "ديدان", "عفن", "لفحة", "ندوة", "اصفرار", "بياض", "سوسة", "سوس", "حشرة", "حشرات", "افة", "آفات",
        "فطر", "فطريات", "بكتيريا", "فيروس", "من", "تربس", "جاسيد", "ذبابة", "عناكب", "اكاروس", "نيماتودا",
        "توتا", "حفار", "سقاطة", "تبقع", "سواد", "احتراق", "نشفان", "ذبول", "تساقط", "موت", "تجعد", "كرمشة", "تيبس",
        "ري", "ريه", "سقي", "عطش", "غمر", "تنقيط", "صرف", "ملوحة", "بي اتش", "ph", "npk", "يوريا", "بوتاسيوم",
        "فوسفات", "كالسيوم", "مغنسيوم", "حديد", "زنك", "كبريت", "نحاس", "عناصر", "شتل", "شتلات", "بذور", "تقاوي",
        "تزهير", "عقد", "حصاد", "جمع", "تقليم", "خف", "عزيق", "حرث", "صوبة", "مشتل", "ورق", "ورقة", "ساق", "جذر", "ثمار",
        "طقس", "جو", "مطر", "امطار", "حرارة", "برودة", "صقيع", "رطوبة", "رياح", "انتاج", "انتاجية"
    }

    question_and_action_keywords = {
        "ازاي", "ازى", "كيف", "كيفية", "ليه", "امتى", "امتي", "متى", "فين", "أين",
        "كام", "كم", "هل", "ماهو", "ما هو", "ما هي", "ماهي", "ايه", "إيه", "شو", "ايش",
        "ينفع", "ممكن", "طريقة", "خطوات", "برنامج", "جدول", "معاد", "ميعاد", "وقت",
        "اعمل", "اسوي", "احط", "اضيف", "اشيل", "اخلط", "اجيب", "اشتري", "انصحني", "شور", "قولي"
    }

    has_agri_topic = any(kw in norm for kw in agri_topic_keywords)

    if not has_agri_topic:
        if any(norm == t or norm.startswith(t + " ") for t in chit_chat_greetings):
            return QueryAnalysis(
                intent="chit_chat",
                reason="تحية أو ترحيب",
                is_gibberish=False,
                requires_retrieval=False,
                suggested_fast_response=CHIT_CHAT_GREETING_RESPONSE,
            )
        if any(norm == t or norm.startswith(t + " ") for t in chit_chat_thanks):
            return QueryAnalysis(
                intent="chit_chat",
                reason="شكر وتقدير",
                is_gibberish=False,
                requires_retrieval=False,
                suggested_fast_response=CHIT_CHAT_THANKS_RESPONSE,
            )
        if any(norm == t for t in ["ازيك", "عامل ايه", "اخبارك", "أخبارك", "كيفك"]):
            return QueryAnalysis(
                intent="chit_chat",
                reason="سؤال عن الحال",
                is_gibberish=False,
                requires_retrieval=False,
                suggested_fast_response=CHIT_CHAT_CHECKIN_RESPONSE,
            )

    # 6. Extreme Ambiguity without Context (e.g. "اعمل ايه؟", "الحقني", "بايظة")
    vague_phrases = [
        "اعمل ايه", "الحقني", "بايظة", "بتموت", "عندي مشكلة", "ساعدني", "قولي اعمل ايه",
        "الحل ايه", "الزرعة تعبانة", "فيه مشكلة", "انقذني"
    ]
    clean_punct = re.sub(r"[؟?!.،,:\-_\s]+", " ", norm).strip()
    if not has_context and any(clean_punct == vp or clean_punct.startswith(vp + " ") for vp in vague_phrases):
        return QueryAnalysis(
            intent="needs_clarification",
            reason="استفسار مبهم بدون تحديد المحصول أو المشكلة",
            is_gibberish=False,
            requires_retrieval=False,
            suggested_fast_response=AMBIGUOUS_CLARIFICATION_RESPONSE,
        )

    # 6b. Unintelligible / Out-of-vocabulary check without context
    # If a short input has no agri keywords, no question/action words, and no chit-chat matches
    has_question_or_action = any(kw in norm for kw in question_and_action_keywords)
    if not has_context and not has_agri_topic and not has_question_or_action and len(words) <= 3 and len(raw) <= 25:
        return QueryAnalysis(
            intent="unintelligible",
            reason="نص غير مفهوم زراعياً أو لغوياً (كلمات عشوائية أو كيبورد)",
            is_gibberish=True,
            requires_retrieval=False,
            suggested_fast_response=UNINTELLIGIBLE_RESPONSE,
        )

    # 7. Quick Direct / Factual / Binary Choice (كلمتين ويسكت)
    quick_indicators = [
        "ينفع اخلط", "ينفع نخلط", "اخلط", "ارش الصبح ولا", "الصبح ولا بالليل", "الصبح ولا العصر",
        "فطر ولا بكتيريا", "حشرة ولا فطر", "مدة الامان كام", "فترة الامان كام", "يعني ايه phi",
        "اروي كل كام", "الري كل كام", "افضل وقت للرش", "ميعاد الرش", "ايه هي الندوة", "هو ده فطر"
    ]
    if any(qi in norm for qi in quick_indicators) and len(words) <= 15:
        return QueryAnalysis(
            intent="quick_direct",
            reason="سؤال مباشر ومحدد (كلمتين ويسكت)",
            is_gibberish=False,
            requires_retrieval=True,
            suggested_max_tokens=220,
            dynamic_instruction=(
                "[نمط الرد: إجابة مباشرة وموجزة جداً (كلمتين وبس)] "
                "المزارع بيسأل سؤال سريع ومحدد (توقيت أو خلط أو نعم/لا). "
                "جاوب بجملة واحدة أو جملتين بالكتير بالعامية المصرية الصريحة والمباشرة "
                "بدون مقدمات طويلة، وبدون تكرار بيانات المزرعة، وبدون خطوات مرقمة إلا لو ضرورية جداً."
            ),
        )

    # 8. Comprehensive Protocol / Full Program (رد مفصل وشامل)
    comprehensive_indicators = [
        "برنامج تسميد", "جدول تسميد", "برنامج مكافحة", "جدول مكافحة", "مكافحة متكاملة",
        "من الزراعة للحصاد", "بالتفصيل", "فصلي", "خطوة بخطوة", "برنامج كامل", "دليل كامل"
    ]
    if any(ci in norm for ci in comprehensive_indicators):
        return QueryAnalysis(
            intent="comprehensive_protocol",
            reason="طلب برنامج أو بروتوكول زراعي كامل وتفصيلي",
            is_gibberish=False,
            requires_retrieval=True,
            suggested_max_tokens=1100,
            dynamic_instruction=(
                "[نمط الرد: بروتوكول زراعي متكامل ومفصل] "
                "المزارع طالب برنامج شامل أو خطة تفصيلية. قدّم له رداً شاملاً ومنظماً بعناوين واضحة: "
                "1) التشخيص أو المرحلة العمرية، "
                "2) أسماء المواد الفعالة والمبيدات المعتمدة، "
                "3) الجرعة المحسوبة بدقة لكل فدان، "
                "4) مواعيد الرش والعمليات الزراعية وإجراءات الأمان وفترة PHI."
            ),
        )

    # 9. Standard Agricultural Query
    return QueryAnalysis(
        intent="standard_agricultural",
        reason="سؤال زراعي معتاد",
        is_gibberish=False,
        requires_retrieval=True,
        suggested_max_tokens=600,
        dynamic_instruction=(
            "[نمط الرد: نصيحة زراعية عملية متوازنة] "
            "ابدأ بسطر تشخيصي مباشر، يليه 2 إلى 3 خطوات عملية بالعامية المصرية البسيطة، "
            "وتنبيه أمان أو وقاية مختصر في النهاية."
        ),
    )
