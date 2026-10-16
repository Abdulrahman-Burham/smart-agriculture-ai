# PlantAPI — Prioritized Continuous Improvement Plan
**Document Version:** 3.0.0  
**Planning Horizon:** Q4 2026 – Q2 2027  
**Owner:** Principal Software Architect & Lead Product Engineer  

---

## 1. Improvement Methodology & Roadmap Structure

The continuous improvement roadmap categorizes all technical recommendations into three strictly prioritized tiers based on **risk impact**, **implementation effort**, and **operational necessity**.

```
[Phase P0: Immediate / Completed] ──> [Phase P1: Short-Term Sprint] ──> [Phase P2: Long-Term Horizon]
 • Chat isolation fix & tests         • Alembic DB migrations           • Automated Active Learning retraining
 • SQLite B-Tree performance indexes   • Signed prescription tokens       • Offline-first PWA IndexedDB sync
 • CDN fallback resilience            • Cloud backup off-site sync      • Dedicated GPU inference cluster (if needed)
```

---

## 2. Priority 0 (P0) — Immediate / Delivered in Current Audit

| Improvement | Category | Implementation Summary | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **Strict Multi-Tenant Scoping** | Security | Updated `chat_repository.py` to enforce `WHERE user_id = ?` for authenticated users and `WHERE user_id IS NULL` for guests. Added `agri_chat_user_owner` in frontend `localStorage` to purge stale chat state across logins. | `test_account_isolation_security.py` passes 3/3; zero leakage across accounts. |
| **SQLite B-Tree Indexes** | Performance | Added 14 B-Tree indexes in `connection.py` on foreign keys and temporal fields (`chat_logs(user_id)`, `uploaded_images(user_id)`, `visitor_logs(created_at)`, `llm_token_logs(user_id)`). | `init_db(force=True)` executes cleanly; zero full-table scans. |
| **Cloudflare CDNJS Migration** | Reliability | Replaced unpkg with Cloudflare CDNJS for Leaflet CSS/JS on the epidemic map, adding an automatic table fallback for zero-bandwidth field environments. | Live test 1.6 (`/epidemic-map`) passes with 200 OK and 21KB payload. |
| **Dedicated Isolation Tests** | QA | Authored `tests/unit/test_account_isolation_security.py` covering multi-account isolation, IDOR prevention, token tampering, and guest isolation. | All 103 tests pass in Pytest in 29.78s. |

---

## 3. Priority 1 (P1) — Short-Term Sprint (Next 30 Days)

### 3.1 Formal Database Schema Migrations (Alembic)
- **Current State:** Schema changes rely on custom `_ensure_column` PRAGMA helper functions in `connection.py`.
- **Target State:** Introduce Alembic migration scripts to track schema versions in source control, enabling deterministic rollbacks and CI schema validation.
- **Effort:** 2 Story Points (1-2 engineering days).
- **Risk:** Low.

### 3.2 Optional Cryptographic HMAC Slugs for Prescriptions
- **Current State:** Prescriptions are accessible at `/prescription/{image_id}` to facilitate physical QR code scanning by agricultural engineers and fertilizer dealers.
- **Target State:** Provide an optional signed share URL (e.g., `/prescription/{image_id}?token={hmac}`) for confidential commercial farms requesting strict privacy.
- **Effort:** 1 Story Point.
- **Risk:** Low.

### 3.3 Off-Site Encrypted Database Backup Sync
- **Current State:** Automated SQLite backups are saved locally to `data/backups/`.
- **Target State:** Add a scheduled rclone / Azure Blob Storage sync task to copy encrypted daily database snapshots to an off-site cloud container.
- **Effort:** 2 Story Points.
- **Risk:** Low.

---

## 4. Priority 2 (P2) — Long-Term Scale & Innovation (60–180 Days)

### 4.1 Automated Active Learning Retraining Pipeline
- **Concept:** Close the loop between farmer uploads and model retraining.
- **Design:** Using labels verified by agronomists via `/api/dev/verify-image`, trigger an automated scheduled job in GitHub Actions or Azure ML to fine-tune `EfficientNetV2B2` on new Egyptian crop pathogen variations, evaluate validation accuracy against the baseline, and produce updated weights if accuracy improves.
- **Prerequisite:** Accumulating 2,000+ verified ground-truth field images.

### 4.2 Offline-First Progressive Web App with IndexedDB
- **Concept:** Enable Egyptian farmers in remote desert reclamation projects (East Oweinat, Toshka, New Delta) without cellular coverage to record leaf scans and consult first-aid guides.
- **Design:** Leverage Service Worker caching and client-side IndexedDB to store pending scans, automatically synchronizing with the central API when mobile connectivity is restored.

### 4.3 Dedicated GPU Model Serving (Triton / TorchServe)
- **Concept:** Offload deep learning vision inference from the FastAPI web worker.
- **Trigger Metric:** When concurrent active users exceed 1,000 requests/minute.
- **Design:** Deploy an NVIDIA Triton Inference Server container with TensorRT optimization for sub-20ms leaf inference, allowing the FastAPI web gateway to remain lightweight.

---

## 5. Risk Assessment & Mitigation Plan

| Risk Description | Probability | Impact | Mitigation Strategy |
| :--- | :---: | :---: | :--- |
| **Gemini API Quota Depletion (HTTP 429)** | Medium | High | Multi-key dynamic rotation pool in `llm_service.py` automatically rolls over to the next healthy API key; Edge TTS acts as immediate neural voice fallback. |
| **SQLite Concurrency Lock Contention** | Low | Medium | WAL (Write-Ahead Logging) mode enables unlimited concurrent readers alongside writers; busy timeout set to 10,000ms. |
| **Egyptian Telecom Network Intermittency** | High | Low | Cloudflare CDN caching, GZip response compression, and local HTML fallbacks for interactive maps. |
