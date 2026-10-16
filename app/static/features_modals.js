/**
 * AgriTech Advanced Modals & Feature Tools
 * 1. Tank-Mix & Dosage Calculator (حاسبة خلط المبيدات والجرعات الذكية)
 * 2. Water Quality & Salinity Advisor (فاحص ملوحة مياه الري وجودة التربة)
 * 3. Leaf Recovery & Before/After Followup (فحص المتابعة والتعافي بعد الرش)
 */

(function () {
  'use strict';

  function initModalsDOM() {
    if (document.getElementById('agri-features-modals-root')) return;

    const root = document.createElement('div');
    root.id = 'agri-features-modals-root';
    root.innerHTML = `
      <!-- STYLES -->
      <style>
        .agri-modal-overlay {
          display: none;
          position: fixed;
          inset: 0;
          background: rgba(15, 23, 42, 0.72);
          backdrop-filter: blur(6px);
          -webkit-backdrop-filter: blur(6px);
          z-index: 10000;
          align-items: center;
          justify-content: center;
          padding: 14px;
          overflow-y: auto;
        }
        .agri-modal-overlay.active {
          display: flex;
          animation: modalFadeIn 0.2s ease;
        }
        @keyframes modalFadeIn {
          from { opacity: 0; transform: scale(0.97); }
          to { opacity: 1; transform: scale(1); }
        }
        .agri-modal-card {
          background: #ffffff;
          color: #0f172a;
          border-radius: 20px;
          border: 1px solid #cbd5e1;
          box-shadow: 0 20px 40px rgba(0,0,0,0.22);
          width: 100%;
          max-width: 640px;
          max-height: 90vh;
          overflow-y: auto;
          padding: 22px;
          direction: rtl;
          text-align: right;
          font-family: inherit;
        }
        [data-theme="dark"] .agri-modal-card {
          background: #1e293b;
          color: #f8fafc;
          border-color: #334155;
        }
        .agri-modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid #e2e8f0;
        }
        [data-theme="dark"] .agri-modal-header {
          border-bottom-color: #334155;
        }
        .agri-modal-title {
          font-size: 1.15rem;
          font-weight: 800;
          color: #059669;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        [data-theme="dark"] .agri-modal-title {
          color: #34d399;
        }
        .agri-modal-close {
          background: #f1f5f9;
          border: 1px solid #cbd5e1;
          color: #64748b;
          border-radius: 10px;
          width: 34px;
          height: 34px;
          font-size: 1.2rem;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
        }
        [data-theme="dark"] .agri-modal-close {
          background: #334155;
          color: #cbd5e1;
          border-color: #475569;
        }
        .agri-form-group {
          margin-bottom: 14px;
        }
        .agri-form-label {
          display: block;
          font-size: 0.84rem;
          font-weight: 700;
          margin-bottom: 5px;
          color: #475569;
        }
        [data-theme="dark"] .agri-form-label {
          color: #94a3b8;
        }
        .agri-input, .agri-select {
          width: 100%;
          padding: 10px 12px;
          border: 1.5px solid #cbd5e1;
          border-radius: 11px;
          font-size: 0.92rem;
          font-family: inherit;
          background: #f8fafc;
          color: inherit;
          outline: none;
          box-sizing: border-box;
        }
        [data-theme="dark"] .agri-input, [data-theme="dark"] .agri-select {
          background: #0f172a;
          border-color: #475569;
        }
        .agri-input:focus, .agri-select:focus {
          border-color: #059669;
        }
        .agri-btn-submit {
          width: 100%;
          padding: 12px;
          border-radius: 12px;
          border: none;
          background: linear-gradient(135deg, #059669 0%, #047857 100%);
          color: #ffffff;
          font-size: 0.95rem;
          font-weight: 800;
          cursor: pointer;
          font-family: inherit;
          box-shadow: 0 4px 12px rgba(5,150,105,0.3);
          transition: transform 0.15s;
        }
        .agri-btn-submit:active {
          transform: scale(0.98);
        }
        .agri-result-box {
          margin-top: 18px;
          padding: 16px;
          border-radius: 14px;
          background: #f1f5f9;
          border: 1px solid #cbd5e1;
          font-size: 0.88rem;
          line-height: 1.6;
          display: none;
        }
        [data-theme="dark"] .agri-result-box {
          background: #0f172a;
          border-color: #334155;
        }
        .agri-banner-danger {
          background: #fef2f2;
          color: #991b1b;
          border: 1.5px solid #f87171;
          padding: 10px 12px;
          border-radius: 10px;
          margin-top: 10px;
          font-weight: 700;
        }
        .agri-banner-safe {
          background: #f0fdf4;
          color: #166534;
          border: 1.5px solid #86efac;
          padding: 10px 12px;
          border-radius: 10px;
          margin-top: 10px;
          font-weight: 700;
        }
        .agri-score-circle {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 72px;
          height: 72px;
          border-radius: 50%;
          font-size: 1.5rem;
          font-weight: 900;
          color: white;
          margin-bottom: 10px;
        }
      </style>

      <!-- 1. TANK-MIX MODAL -->
      <div id="tankMixModalOverlay" class="agri-modal-overlay">
        <div class="agri-modal-card">
          <div class="agri-modal-header">
            <h3 class="agri-modal-title">🧮 حاسبة خلط المبيدات والجرعات الذكية</h3>
            <button class="agri-modal-close" onclick="closeTankMixModal()">&times;</button>
          </div>
          <form onsubmit="submitTankMixForm(event)">
            <div style="display:grid; grid-template-columns: 2fr 1.5fr; gap:10px; margin-bottom:12px;">
              <div>
                <label class="agri-form-label">مساحة الأرض المراد رشها:</label>
                <input type="number" step="0.01" id="tmAreaValue" class="agri-input" value="1" required>
              </div>
              <div>
                <label class="agri-form-label">الوحدة:</label>
                <select id="tmAreaUnit" class="agri-select">
                  <option value="feddan" selected>فدان</option>
                  <option value="qirat">قيراط</option>
                  <option value="sahm">سهم</option>
                  <option value="sqm">متر مربع (م²)</option>
                </select>
              </div>
            </div>

            <div class="agri-form-group">
              <label class="agri-form-label">نوع موتور / أداة الرش:</label>
              <select id="tmTankType" class="agri-select">
                <option value="knapsack_20l" selected>رشاشة ظهرية عادية (20 لتر)</option>
                <option value="knapsack_16l">رشاشة ظهرية (16 لتر)</option>
                <option value="motor_100l">برميل رش صغير (100 لتر)</option>
                <option value="motor_300l">موتور رش أرضي متوسط (300 لتر)</option>
                <option value="motor_600l">موتور رش حقلي كبير (600 لتر)</option>
                <option value="drip_1000l">سمادة شبكة ري بالتنقيط (1000 لتر)</option>
              </select>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:12px;">
              <div>
                <label class="agri-form-label">اسم المبيد أو المركب:</label>
                <input type="text" id="tmProductName" class="agri-input" placeholder="مثلاً: كبريت ميكروني، نحاس، أميستار..." required>
              </div>
              <div>
                <label class="agri-form-label">طبيعة المركب:</label>
                <select id="tmChemicalType" class="agri-select">
                  <option value="powder" selected>مسحوق / بودرة (بالجرام)</option>
                  <option value="liquid">سائل / مستحلب (بالسم³ أو مل)</option>
                </select>
              </div>
            </div>

            <div style="display:grid; grid-template-columns: 2fr 1.5fr; gap:10px; margin-bottom:12px;">
              <div>
                <label class="agri-form-label">الجرعة الموصى بها على العبوة:</label>
                <input type="number" step="0.1" id="tmDosageRate" class="agri-input" placeholder="مثلاً: 250" required>
              </div>
              <div>
                <label class="agri-form-label">معدل الجرعة:</label>
                <select id="tmDosageUnit" class="agri-select">
                  <option value="per_feddan" selected>لكل فدان</option>
                  <option value="per_100l">لكل 100 لتر ماء</option>
                </select>
              </div>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:12px;">
              <div>
                <label class="agri-form-label">طبيعة المحصول الحقلية:</label>
                <select id="tmCropCategory" class="agri-select">
                  <option value="vegetable" selected>خضر ومحاصيل حقلية (250 لتر/فدان)</option>
                  <option value="orchard">أشجار وبساتين وفاكهة (500 لتر/فدان)</option>
                </select>
              </div>
              <div>
                <label class="agri-form-label">مركب شريك في التانك (لفحص التوافق):</label>
                <input type="text" id="tmMixPartner" class="agri-input" placeholder="مثلاً: زيت معدني، أحماض أمينية، كالسيوم">
              </div>
            </div>

            <button type="submit" id="tmSubmitBtn" class="agri-btn-submit">⚡ احسب عدد التانكات والمكيال الحقلي الآن</button>
          </form>

          <div id="tmResultBox" class="agri-result-box"></div>
        </div>
      </div>

      <!-- 2. SALINITY ADVISOR MODAL -->
      <div id="salinityModalOverlay" class="agri-modal-overlay">
        <div class="agri-modal-card">
          <div class="agri-modal-header">
            <h3 class="agri-modal-title">💧 فاحص ملوحة مياه الري وجودة التربة</h3>
            <button class="agri-modal-close" onclick="closeSalinityModal()">&times;</button>
          </div>
          <form onsubmit="submitSalinityForm(event)">
            <div style="display:grid; grid-template-columns: 2fr 1.5fr; gap:10px; margin-bottom:12px;">
              <div>
                <label class="agri-form-label">قراءة الملوحة في المعمل أو بجهاز TDS:</label>
                <input type="number" step="0.1" id="salValue" class="agri-input" placeholder="مثلاً: 1200 أو 1.8" required>
              </div>
              <div>
                <label class="agri-form-label">وحدة القياس:</label>
                <select id="salUnit" class="agri-select">
                  <option value="ppm" selected>جزء في المليون (ppm / TDS)</option>
                  <option value="ec">ديسيسيمنز (EC dS/m)</option>
                </select>
              </div>
            </div>

            <div class="agri-form-group">
              <label class="agri-form-label">المحصول المراد ريّه:</label>
              <select id="salCrop" class="agri-select">
                <option value="طماطم" selected>طماطم (عتبة 1.7 dS/m)</option>
                <option value="بطاطس">بطاطس (عتبة 1.7 dS/m)</option>
                <option value="فراولة">فراولة (حساسة جداً - عتبة 1.0 dS/m)</option>
                <option value="خيار">خيار (عتبة 1.7 dS/m)</option>
                <option value="فلفل">فلفل (عتبة 1.5 dS/m)</option>
                <option value="موالح">موالح برتقال/ليمون (عتبة 1.4 dS/m)</option>
                <option value="عنب">عنب (عتبة 1.5 dS/m)</option>
                <option value="زيتون">زيتون (متحمل عالي - عتبة 2.7 dS/m)</option>
                <option value="نخيل">نخيل بلح (متحمل جداً - عتبة 4.0 dS/m)</option>
                <option value="قمح">قمح (عتبة 3.0 dS/m)</option>
                <option value="ذرة">ذرة شامية (عتبة 1.7 dS/m)</option>
                <option value="بصل">بصل (عتبة 1.2 dS/m)</option>
                <option value="برسيم">برسيم مصري (عتبة 2.0 dS/m)</option>
              </select>
            </div>

            <div class="agri-form-group">
              <label class="agri-form-label">طريقة الري في الحقل:</label>
              <select id="salIrrigation" class="agri-select">
                <option value="تنقيط" selected>ري بالتنقيط (Drip)</option>
                <option value="غمر">ري بالغمر التقليدي (Flood)</option>
                <option value="رشاشات">ري بالرشاشات المحورية (Sprinkler)</option>
              </select>
            </div>

            <button type="submit" id="salSubmitBtn" class="agri-btn-submit">📊 فحص الملوحة ونسبة فقد المحصول</button>
          </form>

          <div id="salResultBox" class="agri-result-box"></div>
        </div>
      </div>

      <!-- 3. FOLLOWUP RECOVERY MODAL -->
      <div id="followupModalOverlay" class="agri-modal-overlay">
        <div class="agri-modal-card">
          <div class="agri-modal-header">
            <h3 class="agri-modal-title">🔄 فحص المتابعة والتعافي البصري بعد الرش</h3>
            <button class="agri-modal-close" onclick="closeFollowupModal()">&times;</button>
          </div>
          <form onsubmit="submitFollowupForm(event)">
            <div class="agri-form-group">
              <label class="agri-form-label">رقم فحص الأساس (Baseline Image ID):</label>
              <input type="number" id="fuBaselineId" class="agri-input" placeholder="مثلاً: 12" required>
            </div>

            <div class="agri-form-group">
              <label class="agri-form-label">كم يوماً مضى منذ رش العلاج؟</label>
              <input type="number" id="fuDaysElapsed" class="agri-input" min="1" max="60" value="5" required>
            </div>

            <div class="agri-form-group">
              <label class="agri-form-label">صورة الورقة الحالية للمتابعة:</label>
              <input type="file" id="fuImageFile" accept="image/*" class="agri-input" required onchange="previewFollowupImg(this)">
              <div id="fuImgPreviewWrap" style="display:none; margin-top:8px; text-align:center;">
                <img id="fuImgPreview" src="" alt="معاينة" style="max-height:160px; border-radius:10px; border:1px solid #cbd5e1;">
              </div>
            </div>

            <button type="submit" id="fuSubmitBtn" class="agri-btn-submit">🩺 مقارنة الحالتين وحساب نسبة الشفاء</button>
          </form>

          <div id="fuResultBox" class="agri-result-box"></div>
        </div>
      </div>
    `;

    document.body.appendChild(root);
  }

  // --- Modal Open/Close ---
  window.openTankMixModal = function () {
    initModalsDOM();
    document.getElementById('tankMixModalOverlay').classList.add('active');
  };
  window.closeTankMixModal = function () {
    const el = document.getElementById('tankMixModalOverlay');
    if (el) el.classList.remove('active');
  };

  window.openSalinityModal = function () {
    initModalsDOM();
    document.getElementById('salinityModalOverlay').classList.add('active');
  };
  window.closeSalinityModal = function () {
    const el = document.getElementById('salinityModalOverlay');
    if (el) el.classList.remove('active');
  };

  window.openFollowupModal = function (baselineId) {
    initModalsDOM();
    const idToUse = baselineId || window._currentBaselineImageId || window._activePrescriptionImageId || '';
    const idInp = document.getElementById('fuBaselineId');
    if (idInp && idToUse) idInp.value = idToUse;
    document.getElementById('followupModalOverlay').classList.add('active');
  };
  window.closeFollowupModal = function () {
    const el = document.getElementById('followupModalOverlay');
    if (el) el.classList.remove('active');
  };

  window.previewFollowupImg = function (input) {
    const wrap = document.getElementById('fuImgPreviewWrap');
    const img = document.getElementById('fuImgPreview');
    if (input.files && input.files[0]) {
      const reader = new FileReader();
      reader.onload = function (e) {
        img.src = e.target.result;
        wrap.style.display = 'block';
      };
      reader.readAsDataURL(input.files[0]);
    }
  };

  // --- Submissions ---
  window.submitTankMixForm = async function (e) {
    e.preventDefault();
    const btn = document.getElementById('tmSubmitBtn');
    const resBox = document.getElementById('tmResultBox');
    btn.disabled = true;
    btn.innerText = '⏳ جاري الحساب وتدقيق التوافق...';
    resBox.style.display = 'none';

    try {
      const partner = document.getElementById('tmMixPartner').value.trim();
      const payload = {
        area_value: parseFloat(document.getElementById('tmAreaValue').value),
        area_unit: document.getElementById('tmAreaUnit').value,
        tank_type: document.getElementById('tmTankType').value,
        product_name: document.getElementById('tmProductName').value.trim(),
        chemical_type: document.getElementById('tmChemicalType').value,
        dosage_rate: parseFloat(document.getElementById('tmDosageRate').value),
        dosage_unit: document.getElementById('tmDosageUnit').value,
        crop_category: document.getElementById('tmCropCategory').value,
        mix_partners: partner ? [partner] : []
      };

      const res = await fetch('/api/calculator/tank-mix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      btn.disabled = false;
      btn.innerText = '⚡ احسب عدد التانكات والمكيال الحقلي الآن';

      if (!res.ok) {
        alert(data.detail || 'حدث خطأ أثناء الحساب');
        return;
      }

      let warnHtml = '';
      if (data.compatibility_warnings && data.compatibility_warnings.length > 0) {
        warnHtml = data.compatibility_warnings.map(w => `
          <div class="agri-banner-danger">
            ${w}
          </div>
        `).join('');
      } else {
        warnHtml = `
          <div class="agri-banner-safe">
            ✅ فحص الخلط: لا توجد تعارضات كيميائية معروفة بين هذه المركبات.
          </div>
        `;
      }

      resBox.innerHTML = `
        <h4 style="color:#059669; font-size:1.05rem; margin-bottom:10px;">📋 نتيجة حساب جرعة الرش (${data.area_display}):</h4>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px;">
          <div style="background:white; padding:10px; border-radius:10px; border:1px solid #e2e8f0; text-align:center;">
            <div style="font-size:0.75rem; color:#64748b;">إجمالي ماء الرش اللازم</div>
            <div style="font-size:1.15rem; font-weight:900; color:#059669;">${data.total_water_liters} لتر</div>
            <div style="font-size:0.75rem; color:#64748b;">(${data.tanks_count_practical} ماليات تانك)</div>
          </div>
          <div style="background:white; padding:10px; border-radius:10px; border:1px solid #e2e8f0; text-align:center;">
            <div style="font-size:0.75rem; color:#64748b;">إجمالي المبيد المطلوب للمساحة</div>
            <div style="font-size:1.15rem; font-weight:900; color:#2563eb;">${data.total_chemical_amount.toFixed(1)} ${data.chemical_unit}</div>
            <div style="font-size:0.75rem; color:#64748b;">سعة التانك: ${data.tank_capacity_liters} لتر</div>
          </div>
        </div>

        <div style="background:white; border-radius:10px; padding:12px; margin-bottom:10px; border:2px solid #10b981;">
          <div style="font-weight:800; color:#064e3b; font-size:0.95rem;">🥄 المقدار المضبوط لكل تانك / مالية:</div>
          <div style="font-size:1.2rem; font-weight:900; color:#059669; margin:4px 0;">
            ${data.amount_per_tank.toFixed(1)} ${data.chemical_unit}
          </div>
          <div style="font-weight:700; color:#047857; font-size:0.86rem; background:#ecfdf5; padding:6px 10px; border-radius:8px;">
            المكيال الحقلي العملي: ${data.amount_per_tank_practical}
          </div>
        </div>

        ${warnHtml}

        <div style="margin-top:12px; font-size:0.82rem; color:#475569; background:#f8fafc; padding:10px; border-radius:8px; line-height:1.6;">
          <strong>💡 إرشادات الخلط والرش:</strong><br>
          ${(data.instructions_ar || []).map(i => `• ${i}<br>`).join('')}
        </div>
      `;
      resBox.style.display = 'block';

    } catch (err) {
      btn.disabled = false;
      btn.innerText = '⚡ احسب عدد التانكات والمكيال الحقلي الآن';
      alert('تعذر الاتصال بالخادم.');
    }
  };

  window.submitSalinityForm = async function (e) {
    e.preventDefault();
    const btn = document.getElementById('salSubmitBtn');
    const resBox = document.getElementById('salResultBox');
    btn.disabled = true;
    btn.innerText = '⏳ جاري تحليل ملوحة المياه...';
    resBox.style.display = 'none';

    try {
      const payload = {
        salinity_value: parseFloat(document.getElementById('salValue').value),
        salinity_unit: document.getElementById('salUnit').value,
        crop_name: document.getElementById('salCrop').value,
        irrigation_method: document.getElementById('salIrrigation').value
      };

      const res = await fetch('/api/calculator/salinity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      btn.disabled = false;
      btn.innerText = '📊 فحص الملوحة ونسبة فقد المحصول';

      if (!res.ok) {
        alert(data.detail || 'حدث خطأ في فحص الملوحة');
        return;
      }

      const yieldLoss = Math.max(0, 100 - data.yield_potential_percent);

      resBox.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <h4 style="color:#0369a1; font-size:1.05rem; margin:0;">📋 تقرير صلاحية مياه الري (${data.crop_name}):</h4>
          <span style="background:${data.water_quality_color || '#10b981'}; color:white; padding:4px 10px; border-radius:20px; font-weight:800; font-size:0.8rem;">
            ${data.water_quality_grade}
          </span>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px;">
          <div style="background:white; padding:10px; border-radius:10px; border:1px solid #e2e8f0; text-align:center;">
            <div style="font-size:0.75rem; color:#64748b;">الملوحة المقاسة</div>
            <div style="font-size:1.1rem; font-weight:900; color:#0f172a;">${data.tds_ppm.toFixed(0)} ppm</div>
            <div style="font-size:0.75rem; color:#0369a1;">(${data.ec_dsm.toFixed(2)} dS/m)</div>
          </div>
          <div style="background:white; padding:10px; border-radius:10px; border:1px solid #e2e8f0; text-align:center;">
            <div style="font-size:0.75rem; color:#64748b;">الإنتاجية المتوقعة</div>
            <div style="font-size:1.25rem; font-weight:900; color:${yieldLoss > 15 ? '#dc2626' : '#059669'};">
              ${data.yield_potential_percent.toFixed(1)}%
            </div>
            <div style="font-size:0.75rem; color:#dc2626;">(فقد متوقع: ${yieldLoss.toFixed(1)}%)</div>
          </div>
        </div>

        <div style="background:white; padding:12px; border-radius:10px; border:1px solid #e2e8f0; margin-bottom:10px;">
          <strong style="color:#059669; display:block; margin-bottom:4px;">💡 التقييم الفني للمحصول:</strong>
          <div style="font-size:0.88rem; color:#334155; line-height:1.6;">${data.evaluation_ar}</div>
        </div>

        <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:12px;">
          <strong style="color:#166534; display:block; margin-bottom:6px;">🛡️ بروتوكول تخفيف أضرار الملوحة حقلياً:</strong>
          <ul style="padding-right:18px; margin:0; font-size:0.84rem; color:#14532d; line-height:1.6;">
            ${(data.alleviation_protocol || []).map(p => `<li>${p}</li>`).join('')}
          </ul>
        </div>
      `;
      resBox.style.display = 'block';

    } catch (err) {
      btn.disabled = false;
      btn.innerText = '📊 فحص الملوحة ونسبة فقد المحصول';
      alert('تعذر الاتصال بالخادم.');
    }
  };

  window.submitFollowupForm = async function (e) {
    e.preventDefault();
    const btn = document.getElementById('fuSubmitBtn');
    const resBox = document.getElementById('fuResultBox');
    const fileInp = document.getElementById('fuImageFile');

    if (!fileInp.files || !fileInp.files[0]) {
      alert('يرجى التقاط أو اختيار صورة المتابعة للورقة');
      return;
    }

    btn.disabled = true;
    btn.innerText = '⏳ جاري فحص الأنسجة ومقارنة التعافي بالذكاء الاصطناعي...';
    resBox.style.display = 'none';

    try {
      const formData = new FormData();
      formData.append('baseline_image_id', document.getElementById('fuBaselineId').value);
      formData.append('days_elapsed', document.getElementById('fuDaysElapsed').value);
      formData.append('followup_image', fileInp.files[0]);

      const res = await fetch('/api/diagnose/followup', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      btn.disabled = false;
      btn.innerText = '🩺 مقارنة الحالتين وحساب نسبة الشفاء';

      if (!res.ok) {
        alert(data.detail || 'حدث خطأ أثناء فحص المتابعة');
        return;
      }

      let scoreBg = '#10b981';
      let statusAr = 'شُفيت تماماً';
      if (data.status === 'healed') {
        scoreBg = '#10b981';
        statusAr = '✅ تعافي تام (الورقة استعادت نضارتها)';
      } else if (data.status === 'recovering') {
        scoreBg = '#3b82f6';
        statusAr = '📈 قيد الشفاء (تراجع نشاط الفطر / الآفة)';
      } else if (data.status === 'active') {
        scoreBg = '#f59e0b';
        statusAr = '⚠️ نشاط مستمر (المرض ما زال حياً)';
      } else {
        scoreBg = '#ef4444';
        statusAr = '❌ تدهور (توسع الإصابة)';
      }

      resBox.innerHTML = `
        <div style="text-align:center; padding:12px 0;">
          <div class="agri-score-circle" style="background:${scoreBg};">
            ${Math.round(data.recovery_score)}%
          </div>
          <div style="font-weight:900; font-size:1.1rem; color:#0f172a; margin-bottom:4px;">
            ${statusAr}
          </div>
          <div style="font-size:0.8rem; color:#64748b;">
            تمت المتابعة بعد: <strong>${data.days_elapsed} أيام</strong> من فحص الأساس #${data.baseline_image_id}
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:12px 0;">
          <div style="background:white; padding:10px; border-radius:10px; border:1px solid #e2e8f0;">
            <div style="font-size:0.75rem; color:#64748b;">التشخيص الأساسي السابق:</div>
            <div style="font-weight:800; font-size:0.86rem; color:#dc2626;">${data.baseline_disease}</div>
          </div>
          <div style="background:white; padding:10px; border-radius:10px; border:1px solid #e2e8f0;">
            <div style="font-size:0.75rem; color:#64748b;">الحالة المرصودة حالياً:</div>
            <div style="font-weight:800; font-size:0.86rem; color:#059669;">${data.followup_disease}</div>
          </div>
        </div>

        <div style="background:white; padding:12px; border-radius:10px; border:1px solid #e2e8f0; margin-bottom:10px;">
          <strong style="color:#059669; display:block; margin-bottom:4px;">💡 التوجيه الزراعي للمتابعة:</strong>
          <div style="font-size:0.88rem; color:#334155; line-height:1.6;">${data.advice}</div>
        </div>

        <div style="text-align:center; font-weight:800; font-size:0.86rem; padding:8px; border-radius:8px; ${data.should_repeat_spray ? 'background:#fef2f2; color:#b91c1c;' : 'background:#f0fdf4; color:#15803d;'}">
          ${data.should_repeat_spray ? '⚠️ يُوصى بتكرار الرشة أو تغيير المادة الفعالة لمقاومة المناعة' : '🎉 لا داعي للرش مرة أخرى، المحصول يتعافى بشكل ممتاز!'}
        </div>
      `;
      resBox.style.display = 'block';

    } catch (err) {
      btn.disabled = false;
      btn.innerText = '🩺 مقارنة الحالتين وحساب نسبة الشفاء';
      alert('تعذر الاتصال بالخادم.');
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModalsDOM);
  } else {
    initModalsDOM();
  }
})();
