"""Agricultural Engineering Calculations: Tank-Mix Dosage & Water Salinity Advisor.

Implements official agronomic formulas for:
1. Precision spray tank dilution, scoop conversion, and chemical incompatibility detection.
2. FAO 29 irrigation water salinity (EC/TDS) yield response and mitigation protocols.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Dict, List, Tuple

from app.schemas.calculator import (
    FertilizerRequest,
    FertilizerResponse,
    FertilizerStagePlan,
    SalinityRequest,
    SalinityResponse,
    SprayWindowRequest,
    SprayWindowResponse,
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


# ─── 3. Fertilizer Program & NPK Commercial Bag Calculations ──────────────

EGYPT_CROP_FERTILIZER_TARGETS: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "طماطم": {
        "clay_old": (140.0, 65.0, 120.0),
        "sandy_new": (180.0, 80.0, 160.0),
    },
    "بطاطس": {
        "clay_old": (120.0, 60.0, 100.0),
        "sandy_new": (150.0, 75.0, 120.0),
    },
    "قمح": {
        "clay_old": (75.0, 30.0, 24.0),
        "sandy_new": (100.0, 45.0, 48.0),
    },
    "ذرة": {
        "clay_old": (120.0, 45.0, 48.0),
        "sandy_new": (140.0, 60.0, 60.0),
    },
    "مانجو": {
        "clay_old": (100.0, 50.0, 120.0),
        "sandy_new": (130.0, 65.0, 150.0),
    },
    "بصل": {
        "clay_old": (90.0, 45.0, 50.0),
        "sandy_new": (120.0, 60.0, 75.0),
    },
    "فراولة": {
        "clay_old": (140.0, 70.0, 150.0),
        "sandy_new": (160.0, 80.0, 180.0),
    },
    "خيار": {
        "clay_old": (120.0, 60.0, 110.0),
        "sandy_new": (150.0, 75.0, 140.0),
    },
    "عنب": {
        "clay_old": (80.0, 40.0, 90.0),
        "sandy_new": (100.0, 50.0, 120.0),
    },
    "موالح": {
        "clay_old": (110.0, 45.0, 100.0),
        "sandy_new": (140.0, 60.0, 130.0),
    },
}

COMMERCIAL_NITROGEN_SOURCES: Dict[str, Tuple[str, float, float]] = {
    "nitrate": ("نترات نشادر (33.5% أزوت)", 0.335, 50.0),
    "urea": ("يوريا (46.5% أزوت)", 0.465, 50.0),
    "sulfate": ("سلفات نشادر / ملح (20.6% أزوت + 24% كبريت)", 0.206, 50.0),
}

COMMERCIAL_PHOSPHORUS_SOURCES: Dict[str, Tuple[str, float, float]] = {
    "single_super": ("سوبر فوسفات أحادي عادي (15.5% P₂O₅)", 0.155, 50.0),
    "triple_super": ("سوبر فوسفات ثلاثي تريبل (46% P₂O₅)", 0.460, 50.0),
    "phosphoric_acid": ("حمض فوسفوريك 85% سائل (61.6% P₂O₅)", 0.616, 50.0),
}

COMMERCIAL_POTASSIUM_SOURCES: Dict[str, Tuple[str, float, float]] = {
    "sulfate": ("سلفات بوتاسيوم (50% K₂O)", 0.500, 50.0),
    "nitrate_potassium": ("نترات بوتاسيوم (46% K₂O + 13% N)", 0.460, 50.0),
}


def calculate_fertilizer_needs(req: FertilizerRequest) -> FertilizerResponse:
    """Calculate exact net N-P-K nutrient units, commercial 50kg bag conversions, and growth stage plan."""
    # 1. Normalize Area (Qirat vs Feddan)
    if req.area_unit == "qirat":
        area_feddan = req.area_value / 24.0
        area_display = f"{req.area_value:g} قيراط (حوالي {area_feddan:.2f} فدان)"
    else:
        area_feddan = req.area_value
        area_display = f"{req.area_value:g} فدان"

    # 2. Normalize Crop Key
    c_raw = (req.crop_name or "").strip().lower()
    crop_key = "طماطم"
    for k in EGYPT_CROP_FERTILIZER_TARGETS:
        if k in c_raw:
            crop_key = k
            break

    soil_key = "sandy_new" if "sandy" in req.soil_type or "رمل" in req.soil_type else "clay_old"
    soil_display = "أرض رملية / استصلاح جديد" if soil_key == "sandy_new" else "أرض طينية قديمة (وادي ودلتا)"
    irrig_display = "ري بالتنقيط (تسميد بالسمادة)" if req.irrigation_method == "drip" else "ري بالغمر (تسميد تكبيش/بدار)"

    # Base net units per feddan
    base_n, base_p, base_k = EGYPT_CROP_FERTILIZER_TARGETS[crop_key][soil_key]

    # Flood irrigation has lower nutrient uptake efficiency (~15% leaching buffer)
    efficiency_factor = 1.15 if req.irrigation_method == "flood" else 1.0

    total_n = round(base_n * area_feddan * efficiency_factor, 1)
    total_p = round(base_p * area_feddan * efficiency_factor, 1)
    total_k = round(base_k * area_feddan * efficiency_factor, 1)

    # 3. Commercial Bags Conversions
    n_info = COMMERCIAL_NITROGEN_SOURCES.get(req.nitrogen_source, COMMERCIAL_NITROGEN_SOURCES["nitrate"])
    p_info = COMMERCIAL_PHOSPHORUS_SOURCES.get(req.phosphorus_source, COMMERCIAL_PHOSPHORUS_SOURCES["single_super"])
    k_info = COMMERCIAL_POTASSIUM_SOURCES.get(req.potassium_source, COMMERCIAL_POTASSIUM_SOURCES["sulfate"])

    # Bags of 50kg = Total Units / (Bag_weight_kg * Active_fraction)
    n_unit_per_bag = n_info[2] * n_info[1]
    n_bags = round(total_n / max(0.1, n_unit_per_bag), 2)
    n_kg = round(n_bags * 50.0, 1)

    p_unit_per_bag = p_info[2] * p_info[1]
    p_bags = round(total_p / max(0.1, p_unit_per_bag), 2)
    p_kg = round(p_bags * 50.0, 1)

    k_unit_per_bag = k_info[2] * k_info[1]
    k_bags = round(total_k / max(0.1, k_unit_per_bag), 2)
    k_kg = round(k_bags * 50.0, 1)

    # 4. Growth Stages Schedule
    stages: List[FertilizerStagePlan] = []
    if crop_key in ("بطاطس", "طماطم", "فراولة"):
        stages = [
            FertilizerStagePlan(
                stage_name_ar="إعداد الأرض والزراعة (خدمة الأساس)",
                stage_timing_ar="أثناء حرث الأرض وتجهيز الخطوط والشتل",
                n_percentage=20.0,
                p_percentage=100.0,
                k_percentage=20.0,
                recommendations_ar=[
                    f"نثر كامل سماد الفوسفور ({p_bags:.1f} شيكارة {p_info[0]}) خلطاً مع السماد البلدي المتحلل والكبريت الزراعي في باطن الخطوط.",
                    f"إضافة حوالي {n_bags * 0.2:.1f} شيكارة أزوتية و {k_bags * 0.2:.1f} شيكارة بوتاسية كجرعة تنشيطية مع رية الزراعة.",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="النمو الخضري والتفريع",
                stage_timing_ar="من عمر 20 إلى 45 يوماً بعد الإنبات/الشتل",
                n_percentage=40.0,
                p_percentage=0.0,
                k_percentage=20.0,
                recommendations_ar=[
                    f"توزيع {n_bags * 0.4:.1f} شيكارة من {n_info[0]} مقسمة على ريات الأسبوع لدعم تكوين المجموع الخضري والسيقان القوية.",
                    f"إضافة {k_bags * 0.2:.1f} شيكارة بوتاسيوم لدعم نشاط الجذور والتنفس الخلوي.",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="التزهير والعقد وتكوين الثمار / التدرين",
                stage_timing_ar="من عمر 45 إلى 75 يوماً (أهم مرحلة إنتاجية)",
                n_percentage=30.0,
                p_percentage=0.0,
                k_percentage=40.0,
                recommendations_ar=[
                    f"إضافة {n_bags * 0.3:.1f} شيكارة أزوت مع رفع البوتاسيوم إلى {k_bags * 0.4:.1f} شيكارة لتشجيع صب المواد الغذائية في الثمار/الدرنات.",
                    "الرش الورقي بمركب كالسيوم بورون (مفصولاً في رشة مستقلة) لمنع عفن الطرف الزهري وتثبيت العقد.",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="التحجيم النهائي والنضج",
                stage_timing_ar="من عمر 75 يوماً حتى ما قبل الحصاد بأسبوعين",
                n_percentage=10.0,
                p_percentage=0.0,
                k_percentage=20.0,
                recommendations_ar=[
                    f"إضافة المتبقي من البوتاسيوم ({k_bags * 0.2:.1f} شيكارة) مع خفض الأزوت إلى حده الأدنى ({n_bags * 0.1:.1f} شيكارة).",
                    "التوقف الكامل عن التسميد قبل الحصاد بـ 15 إلى 18 يوماً (فترة الفطام) لصلابة المحصول وجودة التخزين.",
                ],
            ),
        ]
    elif crop_key == "قمح":
        stages = [
            FertilizerStagePlan(
                stage_name_ar="تجهيز الأرض والزراعة",
                stage_timing_ar="مع الخدمة قبل بدار التقاوي",
                n_percentage=0.0,
                p_percentage=100.0,
                k_percentage=0.0,
                recommendations_ar=[
                    f"إضافة كامل كمية الفوسفور ({p_bags:.1f} شيكارة) نثراً على البلاط قبل آخر حرثة.",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="رية المحاياة (التفريع الأول)",
                stage_timing_ar="بعد 21 إلى 25 يوماً من الزراعة",
                n_percentage=40.0,
                p_percentage=0.0,
                k_percentage=50.0,
                recommendations_ar=[
                    f"إضافة {n_bags * 0.4:.1f} شيكارة من {n_info[0]} مع نصف كمية البوتاسيوم ({k_bags * 0.5:.1f} شيكارة) قبل الري مباشرة.",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="الرية الثانية (الاستطالة وبداية طرد السنابل)",
                stage_timing_ar="عند عمر 45 إلى 55 يوماً",
                n_percentage=40.0,
                p_percentage=0.0,
                k_percentage=50.0,
                recommendations_ar=[
                    f"إضافة الدفعة الثانية من الأزوت ({n_bags * 0.4:.1f} شيكارة) والمتبقي من البوتاسيوم ({k_bags * 0.5:.1f} شيكارة).",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="طرد السنابل وامتلاء الحبوب",
                stage_timing_ar="عند اكتمال طرد السنابل (عمر 70-80 يوماً)",
                n_percentage=20.0,
                p_percentage=0.0,
                k_percentage=0.0,
                recommendations_ar=[
                    f"إضافة الدفعة الأخيرة من الأزوت ({n_bags * 0.2:.1f} شيكارة)، ويمنع التسميد نهائياً بعد مرحلة طرد السنابل.",
                ],
            ),
        ]
    else:
        stages = [
            FertilizerStagePlan(
                stage_name_ar="بداية الموسم / النشاط الربيعي",
                stage_timing_ar="مع خروج العيون وانتفاخ البراعم والنمو الجديد",
                n_percentage=35.0,
                p_percentage=100.0,
                k_percentage=25.0,
                recommendations_ar=[
                    f"إضافة كامل الفوسفور ({p_bags:.1f} شيكارة) مع {n_bags * 0.35:.1f} شيكارة أزوتية لتنشيط الجذور.",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="التزهير والعقد ونمو الثمار",
                stage_timing_ar="منتصف الموسم وذروة الاحتياج المائي والسمادي",
                n_percentage=45.0,
                p_percentage=0.0,
                k_percentage=45.0,
                recommendations_ar=[
                    f"إضافة {n_bags * 0.45:.1f} شيكارة أزوت مع {k_bags * 0.45:.1f} شيكارة بوتاسيوم لدعم حجم الثمار.",
                ],
            ),
            FertilizerStagePlan(
                stage_name_ar="التحجيم والنضج النهائي",
                stage_timing_ar="قبل الجمع والحصاد بـ 3 إلى 4 أسابيع",
                n_percentage=20.0,
                p_percentage=0.0,
                k_percentage=30.0,
                recommendations_ar=[
                    f"إضافة المتبقي من البوتاسيوم ({k_bags * 0.3:.1f} شيكارة) لتحسين السكريات واللون والصلابة.",
                ],
            ),
        ]

    # 5. Compatibility Cautions
    cautions = [
        "⚠️ قاعدة خلط حاسمة: يمنع منعاً باتاً خلط نترات الكالسيوم مع سلفات البوتاسيوم أو سلفات النشادر أو حمض الفوسفوريك في نفس التانك؛ الخلط يسبب ترسب الجبس وفوسفات الكالسيوم التي تسد النقاطات وتتلف شبكة الري فوراً.",
        "⚠️ تنبيه سماد اليوريا: لا يوصى باستخدام اليوريا في الأراضي الجيرية (الكلسية) أو عند ارتفاع درجات الحرارة فوق 30°C تجنباً لتطاير النيتروجين في صورة غاز أمونيا وضياع الفائدة؛ استخدم نترات النشادر أو سلفات النشادر كبديل آمن.",
        "💡 توصية التربة المصرية: يفضل إضافة 50 إلى 100 كجم كبريت زراعي ناعم للفدان مع الخدمة الشتوية أو إعداد الأرض؛ حيث يعمل على معادلة قلوية التربة المصرية (pH 8-8.5) وتحرير الفوسفور والعناصر الصغرى وتيسير امتصاصها.",
        "💧 نصيحة الري بالتنقيط: يفضل حقن الأسمدة في الثلثين الأوسطين من فترة الري، وتشغيل المياه النقية في الربع ساعة الأخير لغسيل شبكة وخراطيم التنقيط من أي بقايا سمادية.",
    ]

    return FertilizerResponse(
        status="success",
        crop_name=crop_key,
        area_feddan=round(area_feddan, 2),
        area_display=area_display,
        soil_type_ar=soil_display,
        irrigation_method_ar=irrig_display,
        total_n_units=total_n,
        total_p_units=total_p,
        total_k_units=total_k,
        nitrogen_fertilizer_name=n_info[0],
        nitrogen_bags_50kg=n_bags,
        nitrogen_total_kg=n_kg,
        phosphorus_fertilizer_name=p_info[0],
        phosphorus_bags_50kg=p_bags,
        phosphorus_total_kg=p_kg,
        potassium_fertilizer_name=k_info[0],
        potassium_bags_50kg=k_bags,
        potassium_total_kg=k_kg,
        growth_stages_schedule=stages,
        compatibility_and_soil_cautions=cautions,
    )


# ─── 4. Spray Weather Window & Drift Risk Evaluator ────────────────────────

def evaluate_spray_window(req: SprayWindowRequest) -> SprayWindowResponse:
    """Evaluate real-time or manual weather conditions to determine safe pesticide spray windows and drift risk."""
    gov = (req.governorate or "الدقهلية").strip()

    temp_c = req.temperature_c
    wind_kmh = req.wind_speed_kmh
    humid_pct = req.humidity_pct
    rain_pct = float(req.rain_prob_pct or 0.0)

    if temp_c is None or wind_kmh is None or humid_pct is None:
        try:
            from app.services.weather_service import fetch_weather_forecast

            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                pass
            if loop and loop.is_running():
                w_res = None
            else:
                w_res = asyncio.run(fetch_weather_forecast(gov))

            if w_res and w_res.temperature is not None:
                temp_c = float(w_res.temperature) if temp_c is None else temp_c
                wind_kmh = float(w_res.wind_speed) if wind_kmh is None else wind_kmh
                humid_pct = float(w_res.humidity) if humid_pct is None else humid_pct
        except Exception:
            pass

    temp_c = 24.0 if temp_c is None else float(temp_c)
    wind_kmh = 8.0 if wind_kmh is None else float(wind_kmh)
    humid_pct = 65.0 if humid_pct is None else float(humid_pct)

    # 1. Wind & Drift Risk
    if wind_kmh < 10.0:
        drift_risk = "منخفض جداً (آمن — هدوء نسبي للرياح)"
    elif wind_kmh <= 15.0:
        drift_risk = "متوسط (احتمال تطاير طفيف؛ قرب البشبوري 40-50 سم من الورقة)"
    elif wind_kmh <= 20.0:
        drift_risk = "مرتفع (تطاير شديد وإهدار للمبيد وتلويث للحقول المجاورة)"
    else:
        drift_risk = "حرج جداً وخطير (ممنوع الرش نهائياً؛ الرياح عاصفة)"

    # 2. Temperature & Evaporation Risk
    if temp_c < 28.0:
        evap_risk = "منخفض (امتصاص ورقي مثالي دون خطر احتراق)"
    elif temp_c <= 32.0:
        evap_risk = "متوسط (تبخر سريع لقطرات الرش الدقيقة؛ رش في الصباح الباكر فقط)"
    else:
        evap_risk = "مرتفع جداً (خطر احتراق الأنسجة النباتية Phytotoxicity)"

    # 3. Rain Wash Risk
    if rain_pct < 25.0:
        rain_risk = "منخفض (لا يوجد خطر غسيل للأمطار)"
    elif rain_pct <= 45.0:
        rain_risk = "متوسط (احتمال سقوط زخات؛ يوصى باستخدام مادة لاصقة ناشرة)"
    else:
        rain_risk = "مرتفع (خطر غسيل المطر للمبيد وإهدار تكلفة الرش)"

    # 4. Overall Decision Code
    if wind_kmh > 18.0 or temp_c > 32.0 or rain_pct > 45.0:
        safety_code = "danger"
        safety_label = "🔴 تحذير شديد: غير مناسب للرش الآن (ممنوع)"
        badge_color = "#dc2626"
        optimal_window = "الانتظار حتى هدوء الرياح وانكسار الحرارة؛ أنسب توقيت غداً بين 6:30 و 9:00 صباحاً."
    elif wind_kmh >= 10.0 or temp_c >= 28.0 or rain_pct >= 25.0:
        safety_code = "caution"
        safety_label = "🟡 رش بحذر (تقريب البشبوري وخفض ضغط الرشاشة)"
        badge_color = "#d97706"
        optimal_window = "الرش فوراً في الساعات الأولى من الصباح (قبل 9:30 صباحاً) أو قبل الغروب بساعتين."
    else:
        safety_code = "ideal"
        safety_label = "🟢 وقت مثالي ومناسب جداً للرش والامتصاص الكامل"
        badge_color = "#10b981"
        optimal_window = "الظروف الجوية ممتازة حالياً؛ الصباح الباكر بعد جفاف الندى أو في العصر حتى الغروب."

    rules: List[str] = [
        "لا ترش والمطر قادم أو الندى يملأ الأوراق؛ الرش فوق الندى الكثيف يؤدي لسيلان المبيد وسقوطه على الأرض.",
        "احرص دائماً على إضافة مادة ناشرة لاصقة (Spreader/Sticker) بمعدل 50 سم³ لكل 100 لتر ماء لزيادة مساحة الالتصاق ومقاومة الغسيل.",
        "ارتدِ قناع التنفس والقفازات الواقية دائماً، ورش في اتجاه الرياح بحيث تكون الرياح في ظهرك ولا تتطاير الرذاذ نحوك.",
        "اغسل تانك الرشاشة ونظف البشابير فور الانتهاء بالماء النظيف لمنع انسداد الفوهات أو تفاعل بقايا المبيدات مع الرشة القادمة.",
    ]

    return SprayWindowResponse(
        status="success",
        governorate=gov,
        safety_code=safety_code,
        safety_label_ar=safety_label,
        safety_badge_color=badge_color,
        temperature_c=round(temp_c, 1),
        wind_speed_kmh=round(wind_kmh, 1),
        humidity_pct=round(humid_pct, 1),
        rain_prob_pct=round(rain_pct, 1),
        drift_risk_level=drift_risk,
        evaporation_scorch_risk=evap_risk,
        rain_wash_risk=rain_risk,
        optimal_time_window_ar=optimal_window,
        field_rules_ar=rules,
    )
