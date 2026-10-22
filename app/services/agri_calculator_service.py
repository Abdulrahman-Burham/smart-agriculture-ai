"""Agricultural Engineering Calculations: Tank-Mix Dosage & Water Salinity Advisor.

Implements official agronomic formulas for:
1. Precision spray tank dilution, scoop conversion, and chemical incompatibility detection.
2. FAO 29 irrigation water salinity (EC/TDS) yield response and mitigation protocols.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from app.schemas.calculator import (
    SalinityRequest,
    SalinityResponse,
    TankMixRequest,
    TankMixResponse,
)

# ─── Tank Mix Constants ───────────────────────────────────────────────────

TANK_CAPACITIES: Dict[str, Tuple[float, str]] = {
    "knapsack_20l": (20.0, "رشاشة ظهرية (20 لتر)"),
    "knapsack_16l": (16.0, "رشاشة ظهرية (16 لتر)"),
    "motor_100l": (100.0, "برميل رش صغير (100 لتر)"),
    "motor_200l": (200.0, "برميل رش قياسي (200 لتر)"),
    "barrel_200l": (200.0, "برميل رش قياسي (200 لتر)"),
    "motor_300l": (300.0, "موتور رش متوسط (300 لتر)"),
    "motor_600l": (600.0, "موتور رش أرضي كبير (600 لتر)"),
    "drip_1000l": (1000.0, "سمادة شبكة ري بالتنقيط (1000 لتر)"),
}

# Realistic spray volume per feddan by tool & canopy in Egyptian agriculture:
# - Knapsack sprayers deliver fine low-volume mist (140 L/feddan in vegetables = 7 sprayers)
# - Tractor motors deliver standard high-volume spray (200-300 L/feddan in vegetables)
# - Orchards/trees require heavy foliage washing (240 L knapsack = 12 sprayers, or 600 L tractor)
SPRAY_WATER_PER_FEDDAN: Dict[str, Dict[str, float]] = {
    "vegetable": {
        "knapsack_20l": 140.0,
        "knapsack_16l": 144.0,
        "motor_100l": 200.0,
        "motor_200l": 200.0,
        "barrel_200l": 200.0,
        "motor_300l": 300.0,
        "motor_600l": 300.0,
        "drip_1000l": 1000.0,
    },
    "orchard": {
        "knapsack_20l": 240.0,
        "knapsack_16l": 240.0,
        "motor_100l": 500.0,
        "motor_200l": 600.0,
        "barrel_200l": 600.0,
        "motor_300l": 600.0,
        "motor_600l": 600.0,
        "drip_1000l": 1000.0,
    },
}


def format_practical_scoop(amount: float, chem_type: str) -> str:
    """Format practical farmer kitchen/field scoops in Egyptian agricultural terminology."""
    if chem_type == "liquid":
        ml = amount
        if ml < 2.0:
            return f"حوالي {ml:.1f} سم³ (سرنجة طبية مدرجة — نقط بسيطة)"
        elif ml < 4.0:
            return f"حوالي {ml:.1f} سم³ (سرنجة أطفال مدرجة أو نصف غطاء عبوة صغير)"
        elif ml < 7.5:
            return f"حوالي {ml:.1f} سم³ (ملعقة شاي صغيرة أو سرنجة 5 سم)"
        elif ml < 12.5:
            return f"حوالي {ml:.1f} سم³ (سرنجة 10 سم أو غطاء عبوة ممتلئ)"
        elif ml < 18.0:
            return f"حوالي {ml:.1f} سم³ (ملعقة طعام كبيرة ممسوحة أو غطاء ونصف)"
        elif ml < 25.0:
            return f"حوالي {ml:.1f} سم³ (ملعقة طعام كبيرة ممتلئة أو غطائين)"
        elif ml < 35.0:
            return f"حوالي {ml:.1f} سم³ (ملعقتين طعام كبيرتين أو 3 أغطية)"
        elif ml < 60.0:
            return f"حوالي {ml:.1f} سم³ (ثلث كوب شاي عادي أو ربع كوباية)"
        elif ml < 85.0:
            return f"حوالي {ml:.1f} سم³ (نصف كوب شاي عادي)"
        elif ml < 130.0:
            return f"حوالي {ml:.1f} سم³ (كوب شاي عادي إلا ربع)"
        elif ml < 180.0:
            return f"حوالي {ml:.1f} سم³ (كوب شاي عادي خمسينة ممتلئ)"
        elif ml < 270.0:
            return f"حوالي {ml:.1f} سم³ (مج شاي كبير أو ربع لتر)"
        elif ml < 400.0:
            return f"حوالي {ml:.0f} سم³ (مج ونصف شاي كبير)"
        elif ml < 600.0:
            return f"حوالي {ml:.0f} سم³ (نصف لتر / زجاجة مياه صغيرة)"
        elif ml < 850.0:
            return f"حوالي {ml:.0f} سم³ (ثلاثة أرباع لتر)"
        else:
            liters = ml / 1000.0
            return f"حوالي {liters:.2f} لتر (عبوة لتر كاملة)"
    else:
        g = amount
        if g < 2.0:
            return f"حوالي {g:.1f} جم (طرف ملعقة الشاي الصغيرة — ميزان حساس)"
        elif g < 4.0:
            return f"حوالي {g:.1f} جم (نصف ملعقة شاي صغيرة ممسوحة)"
        elif g < 7.5:
            return f"حوالي {g:.1f} جم (ملعقة شاي صغيرة ممسوحة)"
        elif g < 12.5:
            return f"حوالي {g:.1f} جم (ملعقتين شاي صغيرتين ممسوحتين)"
        elif g < 18.0:
            return f"حوالي {g:.1f} جم (ملعقة طعام كبيرة ممسوحة)"
        elif g < 25.0:
            return f"حوالي {g:.1f} جم (ملعقة طعام كبيرة ممتلئة هرماً)"
        elif g < 35.0:
            return f"حوالي {g:.1f} جم (ملعقتين طعام كبيرتين ممسوحتين)"
        elif g < 45.0:
            return f"حوالي {g:.1f} جم (ملعقتين ونصف طعام أو نصف كيس 100 جم)"
        elif g < 65.0:
            return f"حوالي {g:.1f} جم (3 ملاعق طعام ممتلئة أو ثلث كوب شاي)"
        elif g < 85.0:
            return f"حوالي {g:.1f} جم (نصف كوب شاي عادي)"
        elif g < 120.0:
            return f"حوالي {g:.1f} جم (كيس 100 جم كامل أو كوب شاي إلا ربع)"
        elif g < 170.0:
            return f"حوالي {g:.1f} جم (كوب شاي عادي خمسينة ممتلئ)"
        elif g < 270.0:
            return f"حوالي {g:.1f} جم (كيس 250 جم كامل أو مج شاي كبير ممتلئ)"
        elif g < 400.0:
            return f"حوالي {g:.0f} جم (مج ونصف شاي كبير أو ثلث كيلو)"
        elif g < 600.0:
            return f"حوالي {g:.0f} جم (نصف كيلو / 500 جم)"
        elif g < 850.0:
            return f"حوالي {g:.0f} جم (ثلاثة أرباع كيلو)"
        else:
            kg = g / 1000.0
            return f"حوالي {kg:.2f} كجم (كيلو كامل)"


# Incompatibility checks (pairs of keywords in chemical names or selected partners)
INCOMPATIBILITY_RULES = [
    (
        {"نحاس", "copper", "cupric"},
        {"أحماض أمينية", "amino", "amino_acids"},
        "⚠️ تحذير خلط خطير: لا يُخلط النحاس مع الأحماض الأمينية إطلاقاً؛ حيث تتكون معقدات نحاسية سامة تحرق أوراق وثمار النبات.",
    ),
    (
        {"كبريت", "sulfur", "sulphur"},
        {"زيت", "oil", "mineral_oil"},
        "⚠️ تحذير احتراق الأوراق: يمنع منعاً باتاً خلط الكبريت مع الزيوت المعدنية أو الصيفية، ويجب ترك فاصل زمني لا يقل عن 15 إلى 21 يوماً بين المعاملتين.",
    ),
    (
        {"كالسيوم", "calcium"},
        {"فوسفور", "phosphorus", "كبريتات", "sulfate", "sulphate"},
        "⚠️ تحذير ترسب وانسداد: خلط الكالسيوم مع الفوسفات أو الكبريتات ينتج راسب جبسي غير ذائب (كبريتات/فوسفات الكالسيوم) يسد الفونيات ويعدم فاعلية الرش.",
    ),
    (
        {"نحاس", "copper"},
        {"فوسفيت", "phosphite", "phosphonate"},
        "⚠️ تنبيه توافق: قد يسبب خلط الفوسفيت مع مركبات النحاس صدمة للنبات ما لم تكن هناك توصية صريحة من الشركة المصنعة.",
    ),
]


def calculate_tank_mix(req: TankMixRequest) -> TankMixResponse:
    """Calculate exact tank fills, chemical dosage per tank, and compatibility."""
    canopy = req.crop_category.lower().strip()
    tank_key = req.tank_type.lower().strip()
    tank_cap, tank_label = TANK_CAPACITIES.get(tank_key, (20.0, "رشاشة ظهرية 20 لتر"))
    chem_type = req.chemical_type.lower().strip()
    chem_unit = "مل/سم³" if chem_type == "liquid" else "جرام"
    dose_rate = req.dosage_rate
    dose_unit = req.dosage_unit.lower().strip()
    calc_mode = getattr(req, "mode", "area").lower().strip()

    # Determine water rate per feddan for this tool
    crop_rates = SPRAY_WATER_PER_FEDDAN.get(canopy, SPRAY_WATER_PER_FEDDAN["vegetable"])
    water_rate_fed = crop_rates.get(tank_key, 200.0)

    if calc_mode == "tank":
        # Mode A: Direct Single/Multiple Tanks Filling
        tanks_cnt = max(1, getattr(req, "tanks_count", 1))
        total_water = float(tank_cap * tanks_cnt)
        tanks_count_exact = float(tanks_cnt)
        tanks_count_practical = tanks_cnt
        area_fed = total_water / water_rate_fed
        area_ar = f"ملء {tanks_cnt} {tank_label}"

        if dose_unit in ("per_100l", "لكل 100 لتر", "لكل 100 لتر ماء"):
            dose_per_tank = (dose_rate / 100.0) * tank_cap
        elif dose_unit in ("per_200l", "لكل 200 لتر", "لكل برميل 200 لتر"):
            dose_per_tank = (dose_rate / 200.0) * tank_cap
        elif dose_unit in ("per_tank", "لكل تانك", "لكل رشاشة"):
            dose_per_tank = dose_rate
        else:  # per_feddan: divide feddan dose by how many tanks cover a feddan
            tanks_per_feddan = max(1.0, water_rate_fed / tank_cap)
            dose_per_tank = dose_rate / tanks_per_feddan

        total_chemical = dose_per_tank * tanks_cnt

    else:
        # Mode B: Whole Field Area Spraying
        unit = req.area_unit.lower().strip()
        val = req.area_value if req.area_value is not None else 1.0
        if unit in ("feddan", "فدان"):
            area_fed = val
            area_ar = f"{val:.2f} فدان"
        elif unit in ("qirat", "قيراط"):
            area_fed = val / 24.0
            area_ar = f"{val:.1f} قيراط ({area_fed:.3f} فدان)"
        elif unit in ("sahm", "سهم"):
            area_fed = val / 576.0
            area_ar = f"{val:.0f} سهم ({area_fed:.4f} فدان)"
        elif unit in ("sqm", "متر", "متر مربع"):
            area_fed = val / 4200.0
            area_ar = f"{val:.0f} م² ({area_fed:.3f} فدان)"
        else:
            area_fed = val
            area_ar = f"{val} {unit}"

        total_water = max(1.0, area_fed * water_rate_fed)
        tanks_count_exact = total_water / tank_cap
        tanks_count_practical = max(1, math.ceil(tanks_count_exact))

        if dose_unit in ("per_feddan", "لكل فدان"):
            total_chemical = area_fed * dose_rate
        elif dose_unit in ("per_200l", "لكل 200 لتر", "لكل برميل 200 لتر"):
            total_chemical = (total_water / 200.0) * dose_rate
        elif dose_unit in ("per_tank", "لكل تانك", "لكل رشاشة"):
            total_chemical = dose_rate * tanks_count_exact
        else:  # per 100 liters of water
            total_chemical = (total_water / 100.0) * dose_rate

        dose_per_tank = (total_chemical / total_water) * tank_cap

    # Practical spoon/cup scoop representation
    practical_scoop = format_practical_scoop(dose_per_tank, chem_type)

    # Incompatibility rules
    warnings: List[str] = []
    text_to_check = (
        (req.product_name or "").lower()
        + " "
        + " ".join(req.mix_partners or []).lower()
    )
    for kw1_set, kw2_set, warning_msg in INCOMPATIBILITY_RULES:
        has_kw1 = any(k in text_to_check for k in kw1_set)
        has_kw2 = any(k in text_to_check for k in kw2_set)
        if has_kw1 and has_kw2:
            warnings.append(warning_msg)

    # Actionable agricultural steps
    instructions: List[str] = [
        f"املأ ثلث تانك {tank_label} بماء نظيف خالي من الطين أولاً.",
        f"أذب أو خفف المقدار المخصص للرشاشة الواحدة ({dose_per_tank:.1f} {chem_unit} — {practical_scoop}) في جردل ماء خارجي صغير أولاً (التحضير المسبق).",
        "صب المحلول المخفف في تانك الرشاشة مع تشغيل التقليب، ثم أكمل باقي التانك بالماء حتى العلامة.",
        "رش النباتات حتى درجة البلل الخفيف دون الوصول لمرحلة الجريان السطحي والغسيل على الأرض.",
        "يُفضل الرش في الصباح الباكر بعد تطاير الندى أو بعد انكسار حرارة الظهيرة، مع تجنب أوقات هبوب الرياح تماماً.",
    ]

    return TankMixResponse(
        status="success",
        area_feddan=round(area_fed, 4),
        area_display=area_ar,
        tank_capacity_liters=tank_cap,
        total_water_liters=round(total_water, 1),
        total_chemical_amount=round(total_chemical, 2),
        chemical_unit=chem_unit,
        amount_per_tank=round(dose_per_tank, 2),
        amount_per_tank_practical=practical_scoop,
        tanks_count_exact=round(tanks_count_exact, 2),
        tanks_count_practical=tanks_count_practical,
        compatibility_warnings=warnings,
        instructions_ar=instructions,
    )


# ─── Salinity & Water Quality Constants (FAO 29 Standards) ────────────────

# Crop threshold EC (dS/m), Slope (% yield loss per 1 dS/m increase above threshold)
CROP_SALINITY_DATABASE: Dict[str, Dict[str, Any]] = {
    "نخيل": {
        "threshold_ec": 4.0,
        "slope": 3.6,
        "category": "فائقة التحمل",
        "max_ec": 18.0,
    },
    "نخيل البلح": {
        "threshold_ec": 4.0,
        "slope": 3.6,
        "category": "فائقة التحمل",
        "max_ec": 18.0,
    },
    "زيتون": {
        "threshold_ec": 2.7,
        "slope": 10.0,
        "category": "عالية التحمل",
        "max_ec": 10.0,
    },
    "شعير": {
        "threshold_ec": 8.0,
        "slope": 5.0,
        "category": "عالية جداً",
        "max_ec": 18.0,
    },
    "قمح": {
        "threshold_ec": 6.0,
        "slope": 7.1,
        "category": "متوسطة التحمل",
        "max_ec": 13.0,
    },
    "طماطم": {
        "threshold_ec": 2.5,
        "slope": 9.9,
        "category": "متوسطة التحمل",
        "max_ec": 7.5,
    },
    "بطاطس": {
        "threshold_ec": 1.7,
        "slope": 12.0,
        "category": "حساسة للملوحة",
        "max_ec": 6.0,
    },
    "ذرة": {
        "threshold_ec": 1.7,
        "slope": 12.0,
        "category": "متوسطة الحساسية",
        "max_ec": 6.0,
    },
    "بصل": {"threshold_ec": 1.2, "slope": 16.0, "category": "حساسة جداً", "max_ec": 4.5},
    "خيار": {
        "threshold_ec": 2.0,
        "slope": 13.0,
        "category": "حساسة للملوحة",
        "max_ec": 6.0,
    },
    "عنب": {
        "threshold_ec": 1.5,
        "slope": 9.6,
        "category": "متوسطة الحساسية",
        "max_ec": 6.5,
    },
    "مانجو": {
        "threshold_ec": 1.5,
        "slope": 15.0,
        "category": "حساسة (تسمم كلوريد)",
        "max_ec": 5.0,
    },
    "فراولة": {
        "threshold_ec": 1.0,
        "slope": 33.0,
        "category": "شديدة الحساسية",
        "max_ec": 2.5,
    },
    "برسيم": {
        "threshold_ec": 2.0,
        "slope": 7.3,
        "category": "متوسطة التحمل",
        "max_ec": 9.0,
    },
    "فول": {
        "threshold_ec": 1.6,
        "slope": 9.6,
        "category": "متوسطة الحساسية",
        "max_ec": 6.5,
    },
}


def evaluate_water_salinity(req: SalinityRequest) -> SalinityResponse:
    """Evaluate irrigation water EC/TDS, calculate crop yield loss, and provide alleviation protocol."""
    # 1. Normalize between TDS (ppm) and EC (dS/m)
    # Standard agricultural conversion: 1 dS/m = ~640 ppm TDS
    unit = req.salinity_unit.lower().strip()
    val = req.salinity_value

    if unit in ("ec", "ds/m", "ms/cm"):
        ec_dsm = val
        tds_ppm = val * 640.0
    else:  # ppm or mg/L
        tds_ppm = val
        ec_dsm = val / 640.0

    # 2. General Water Quality Classification
    if tds_ppm < 500:
        grade = "عذبة ممتازة — صالحة لكافة الزراعات"
        color = "#10b981"  # Green
    elif tds_ppm <= 1200:
        grade = "مقبولة وجيدة لمعظم الخضر والمحاصيل"
        color = "#3b82f6"  # Blue
    elif tds_ppm <= 2500:
        grade = "متوسطة الملوحة — تتطلب إدارة ري ومحسنات"
        color = "#f59e0b"  # Amber
    elif tds_ppm <= 4500:
        grade = "شديدة الملوحة — لا تلائم إلا المحاصيل المتحملة"
        color = "#ea580c"  # Orange
    else:
        grade = "فائقة الملوحة — غير صالحة للري العادي وتتطلب تحلية"
        color = "#dc2626"  # Red

    # 3. Match Crop Parameters
    crop_input = req.crop_name.strip()
    matched_crop = None
    for k in CROP_SALINITY_DATABASE:
        if k in crop_input or crop_input in k:
            matched_crop = k
            break

    if not matched_crop:
        # Default fallback: moderate vegetable crop (like tomato)
        crop_data = {
            "threshold_ec": 2.0,
            "slope": 10.0,
            "category": "متوسطة التحمل",
            "max_ec": 7.0,
        }
        display_crop = crop_input or "محصول عام"
    else:
        crop_data = CROP_SALINITY_DATABASE[matched_crop]
        display_crop = matched_crop

    thresh_ec = crop_data["threshold_ec"]
    thresh_ppm = thresh_ec * 640.0
    slope = crop_data["slope"]

    # Maas-Hoffman equation for salinity yield potential:
    # Y = 100 - slope * (EC - threshold)
    if ec_dsm <= thresh_ec:
        yield_pct = 100.0
    else:
        loss = slope * (ec_dsm - thresh_ec)
        yield_pct = max(0.0, 100.0 - loss)

    yield_pct = round(yield_pct, 1)
    is_critical = yield_pct < 65.0

    # 4. Detailed Evaluation Text
    if yield_pct >= 95.0:
        eval_text = (
            f"✅ مياه الري ممتازة جداً لمحصول {display_crop}. الملوحة المقاسة ({tds_ppm:.0f} ppm / {ec_dsm:.2f} dS/m) "
            f"تقع تماماً دون الحد الحرج لبداية انخفاض الإنتاجية ({thresh_ppm:.0f} ppm). النبات سينمو بكامل طاقته الإنتاجية دون إجهاد أسموزي."
        )
    elif yield_pct >= 75.0:
        eval_text = (
            f"⚠️ ملوحة مياه الري تسبب إجهاداً خفيفاً إلى متوسط على محصول {display_crop}. الملوحة الحالية ({tds_ppm:.0f} ppm) "
            f"تتجاوز العتبة الحرجة ({thresh_ppm:.0f} ppm)، مما قد يتسبب في نقص تقديري للإنتاجية بحوالي {100.0 - yield_pct:.1f}%. "
            f"يُوصى باتباع برنامج معالجة الملوحة والغسيل المنتظم لتفادي تراكم الأملاح حول الشعيرات الجذرية."
        )
    else:
        eval_text = (
            f"🚨 خطر شديد وإجهاد ملحي حرج على محصول {display_crop}! الملوحة المقاسة ({tds_ppm:.0f} ppm) مرتفعة جداً "
            f"مقارنة بقدرة تحمل النبات ({thresh_ppm:.0f} ppm). قد تنخفض الإنتاجية إلى {yield_pct:.1f}% أو يحدث جفاف تام واحتراق لحواف الأوراق وسقوط الأزهار "
            f"بسبب التسمم بأيونات الصوديوم والكلوريد وصعوبة امتصاص الماء."
        )

    # 5. Salinity Alleviation Treatments
    alleviation: List[str] = [
        "إضافة أحماض الهيوميك والفولفيك (Humic & Fulvic Acid) بمعدل 1.5 - 2 كجم/فدان شهرياً مع ماء الري لتحسين التبادل الكاتيوني وتفكيك معقدات الصوديوم.",
        "استخدام نترات الكالسيوم أو سلفات الكالسيوم القابلة للذوبان؛ حيث يطرد الكالسيوم (+Ca²⁺) أيونات الصوديوم الضارة من على حبيبات التربة ويحمي الجذور.",
        "زيادة المقنن المائي بنسبة 15% إلى 20% كـ 'رية غسيل' دورية كل 3 إلى 4 ريات لطرد الأملاح المتراكمة بعيداً عن منطقة الجذور الفعالة.",
        "تجنب استخدام الأسمدة التي تحتوي على كلوريد (مثل كلوريد البوتاسيوم)، والاعتماد الحصري على سلفات البوتاسيوم ونترات البوتاسيوم.",
        "الرش الورقي بالأحماض الأمينية الحرة (البرولين) مع الطحالب البحرية لرفع قدرة خلايا الأوراق على تحمل الضغط الأسموزي الملحي.",
    ]

    return SalinityResponse(
        status="success",
        crop_name=display_crop,
        tds_ppm=round(tds_ppm, 1),
        ec_dsm=round(ec_dsm, 2),
        water_quality_grade=grade,
        water_quality_color=color,
        crop_tolerance_threshold_ppm=round(thresh_ppm, 1),
        crop_tolerance_threshold_ec=round(thresh_ec, 2),
        yield_potential_percent=yield_pct,
        is_critical_risk=is_critical,
        evaluation_ar=eval_text,
        alleviation_protocol=alleviation,
    )
