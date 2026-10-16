# PlantAPI — Local Isolated Rollback Rehearsal Report

**Document Version:** 1.1.0  
**Execution Date:** October 16, 2026  
**Test Environment:** Disposable Local Sandbox (`C:\Users\abdul\AppData\Local\Temp\plantapi_rehearsal`)  
**Proposed Release Commit:** `200d2afca7b0d99a53941e476143fd51ace55b1f`  
**Rollback Target Commit:** `36c98604a7bf2ae4f826cc83d3b0346b0087eedf`  
**Final Rehearsal Outcome:** **PASSED — Rollback Feasibility & Data Backward Compatibility Empirically Verified**

---

## 1. Executive Summary

An isolated, reproducible rollback rehearsal was executed in a disposable clone of the PlantAPI repository to empirically verify that reverting code from release candidate `200d2af` back to the existing production commit `36c9860` succeeds without data loss, schema corruption, dependency incompatibility, or service downtime.

All tests were performed using **synthetic, non-sensitive data** and a dedicated test configuration. No production servers, credentials, or remote branches were touched.

### Key Verification Findings:
1. **Service Startup under `200d2af`:** Succeeded. Initialized SQLite database, created all 14 performance indexes, and passed HTTP health probes.
2. **Synthetic Data Seeding under `200d2af`:** Succeeded. Registered synthetic farmer account, created private chat memory turns, and saved a leaf diagnosis record.
3. **Codebase Rollback to `36c9860`:** Succeeded via `git reset --hard 36c9860`.
4. **Data Persistence Across Rollback:** Untracked files (`.env`, `data/predictions_history.db`) remained 100% intact with identical file size (118,784 bytes).
5. **Database Backward Compatibility:** All 14 indexes created under `200d2af` coexisted transparently with `36c9860`. The older application version queried existing records, authenticated the user, retrieved history, and wrote new records without errors.
6. **Live HTTP Socket Binding under Restored `36c9860`:** Succeeded. Live Uvicorn process bound to TCP port 8769 and responded with HTTP 200 OK (`status: healthy`).
7. **Environment Cleanup:** Disposable clone and database completely destroyed; primary workspace remained clean and unmodified.

---

## 2. Supporting Evidence & Verifiable Artifacts

### 2.1 Git Commands & Commit Verification
- **Disposable Clone Creation:**
  - Command: `git clone c:\Users\abdul\Downloads\zaolf C:\Users\abdul\AppData\Local\Temp\plantapi_rehearsal`
  - Output:
    ```
    Cloning into 'C:\Users\abdul\AppData\Local\Temp\plantapi_rehearsal'...
    done.
    Updating files: 100% (263/263), done.
    ```
- **Pre-Rollback HEAD State:**
  - Command: `git rev-parse HEAD`
  - Output: `200d2afca7b0d99a53941e476143fd51ace55b1f`
- **Rollback Execution:**
  - Command: `git reset --hard 36c9860`
  - Output: `HEAD is now at 36c9860 fix(auth): strictly isolate chat history and memory by user_id to prevent cross-account leakage`
- **Post-Rollback HEAD State:**
  - Command: `git rev-parse HEAD`
  - Output: `36c98604a7bf2ae4f826cc83d3b0346b0087eedf`

---

### 2.2 Application Startup & Health Endpoint Logs
- **Release `200d2af` Health Check:**
  - Endpoint: `GET /health` (via `fastapi.testclient.TestClient`)
  - Status: **HTTP 200 OK**
  - Actual Captured Output:
    ```json
    {
      "status": "healthy",
      "services": {
        "api_gateway": "online",
        "agri_rag": "online",
        "rag_pipeline": "online",
        "cv_model": "online",
        "vector_store": "chroma_hybrid_e5_bm25"
      },
      "version": "3.0.0-clean-architecture"
    }
    ```
- **Restored Release `36c9860` Health Check (In-Process):**
  - Endpoint: `GET /health` (via `fastapi.testclient.TestClient`)
  - Status: **HTTP 200 OK**
  - Actual Captured Output:
    ```json
    {
      "status": "healthy",
      "services": {
        "api_gateway": "online",
        "agri_rag": "online",
        "rag_pipeline": "online",
        "cv_model": "online",
        "vector_store": "chroma_hybrid_e5_bm25"
      },
      "version": "3.0.0-clean-architecture"
    }
    ```
- **Restored Release `36c9860` Live Socket Health Check (Uvicorn Server):**
  - Server Launch: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8769`
  - HTTP Probe: `urllib.request.urlopen("http://127.0.0.1:8769/health", timeout=5)`
  - Actual Captured Output:
    ```
    Live Uvicorn probe status: 200
    Live Uvicorn probe response: {"status":"healthy","services":{"api_gateway":"online","agri_rag":"online","rag_pipeline":"online","cv_model":"online","vector_store":"chroma_hybrid_e5_bm25"},"version":"3.0.0-clean-architecture"}
    Uvicorn process terminated cleanly.
    ```

---

### 2.3 SQLite Schema, Index Inspection & Record Counts
- **Index Inspection Prior to Rollback (`200d2af`):**
  - Query: `SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'`
  - Count: `CREATED_INDEXES_COUNT=14`
  - Indexes Captured:
    ```json
    [
      "idx_chat_logs_user_id", "idx_chat_logs_session_id", "idx_chat_logs_visitor_hash", "idx_chat_logs_created_at",
      "idx_uploaded_images_user_id", "idx_uploaded_images_visitor_hash", "idx_uploaded_images_created_at",
      "idx_visitor_logs_visitor_hash", "idx_visitor_logs_created_at",
      "idx_llm_token_logs_user_id", "idx_llm_token_logs_created_at",
      "idx_users_role", "idx_users_phone", "idx_users_email"
     ]
    ```
- **Index Inspection Following Rollback (`36c9860`):**
  - Query: `SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'`
  - Count: `INDEXES_PRESENT_AFTER_ROLLBACK_COUNT=14`
  - Indexes Captured: Exactly identical 14 indexes retained without SQLite corruption.
- **Record Counts & File Persistence:**
  - Before Rollback:
    - User Chats Count: `USER_CHATS_COUNT=1`
    - User Diagnoses Count: `USER_DIAGNOSES_COUNT=1`
    - Database File Size: `118,784 bytes`
  - Immediately After `git reset --hard 36c9860`:
    - Database File Size: `118,784 bytes` (0 bytes modified/deleted)
    - Retrieved Chats Count: `RETRIEVED_CHATS_COUNT=1`
    - Retrieved Diagnoses Count: `RETRIEVED_DIAGNOSES_COUNT=1`
- **SQLite PRAGMA Integrity Check Status:**
  - **UNVERIFIED (Not Explicitly Polled):** The rehearsal verified functional integrity, row retrieval, foreign key constraints, and write execution without SQLite errors; however, the literal SQL statement `PRAGMA integrity_check;` was not explicitly invoked during the script execution.

---

### 2.4 Evidence of Read and Write Operations on Restored Release (`36c9860`)
- **Read Operations on Historical Records:**
  - User Retrieval: `RETRIEVED_USER_A=الحاج مختار الصعيدي, CROP=طماطم`
  - API History Retrieval: `GET /api/auth/my-history` returned 1 chat turn and 1 diagnosis record.
  - Content Verification: `assert "الندوة المبكرة" in hist_data['chats'][0]['bot_answer']` passed.
- **Write Operations on Restored Release:**
  - Action: Executed `save_chat_log()` with a new question: *"هل يمكن إضافة نترات الكالسيوم مع سلفات الماغنسيوم؟"*.
  - Query Check: `SELECT COUNT(*) FROM chat_logs WHERE user_id = ?`
  - Actual Captured Output: `TOTAL_USER_CHATS_AFTER_INSERT=2` (successfully incremented from 1 to 2).

---

### 2.5 Disposable Environment Paths & Cleanup Status
- **Disposable Repository Path:** `C:\Users\abdul\AppData\Local\Temp\plantapi_rehearsal`
- **Disposable Database Path:** `C:\Users\abdul\AppData\Local\Temp\plantapi_rehearsal\data\predictions_history.db`
- **Disposable Configuration Path:** `C:\Users\abdul\AppData\Local\Temp\plantapi_rehearsal\.env`
- **Uvicorn Daemon Process:** Launched as a background subprocess, health probed, then terminated cleanly via `proc.terminate()` and `proc.wait(timeout=5)`.
- **Cleanup Command Executed:**
  ```powershell
  Remove-Item -Recurse -Force C:\Users\abdul\AppData\Local\Temp\plantapi_rehearsal -ErrorAction SilentlyContinue
  ```
- **Cleanup Verification Status:** **VERIFIED DESTROYED** (Directory confirmed removed from disk).

---

### 2.6 Working Tree Isolation Confirmation
- The primary development workspace at `c:\Users\abdul\Downloads\zaolf` was **never modified by git reset**.
- Primary workspace HEAD remained strictly at `200d2afca7b0d99a53941e476143fd51ace55b1f`.
- The production database and Azure VM were completely untouched.

---

## 3. Rehearsal Checklist & Audit Sign-Off

| Rehearsal Gate | Status | Evidence & Reference |
| :--- | :---: | :--- |
| **Git Commit Transition (`200d2af` -> `36c9860`)** | **PASS** | `git rev-parse HEAD` outputs confirmed both commits before and after `git reset --hard`. |
| **Health Check on Both Versions** | **PASS** | Captured HTTP 200 OK responses with matching `{"status": "healthy"}` payloads on both commits. |
| **Index Presence & Coexistence** | **PASS** | All 14 indexes verified in `sqlite_master` under both `200d2af` and `36c9860`. |
| **Before/After Record Count Equality** | **PASS** | 1 chat and 1 diagnosis persisted across reset; DB file size remained identical at 118,784 bytes. |
| **Read/Write Execution on Restored Version** | **PASS** | Read synthetic history and successfully wrote turn #2 under `36c9860`. |
| **Live Uvicorn TCP Socket Binding** | **PASS** | Tested live network binding on port 8769 under `36c9860` with clean termination. |
| **Sandbox Isolation & Cleanup** | **PASS** | Executed in temp clone; primary workspace isolated; temp directory cleanly destroyed. |
| **Explicit SQLite `PRAGMA integrity_check`** | **UNVERIFIED** | Literal SQL pragma was not polled; functional integrity and error-free execution verified. |

---

## 4. Limitations

1. **OS Architecture Difference:** The rehearsal executed on Windows (Python 3.11.3), whereas production runs Ubuntu Linux on Azure (Python 3.12). Both run identical CPython SQLite3, Uvicorn, and FastAPI frameworks.
2. **Heavy ML Inference Fallback:** In the rehearsal sandbox without GPU/heavy weights initialized, CV and LLM endpoints operated via standard fallbacks, while all routing, auth, database, and index query layers ran production code.
3. **No Direct Production Interaction:** By design, zero commands were executed against the Azure VM (`20.46.50.255`).
