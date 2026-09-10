# 📄 Week 1 Deliverable: Business Requirements Document (BRD Draft)
**Role:** Business & Data Analyst - AgriTech  
**Status:** Completed (Week 1)

---

## 1. Scope & Week 1 Core Focus
This document covers the functional requirements, user stories, disease evaluation criteria (aligned with the Computer Vision team), and the economic impact model tailored to the Egyptian agricultural context.

---

## 2. Functional Requirements List

### A. Computer Vision Module (Diagnostic Input)
- **FR-CV-01:** Capture direct visual images of infected plant leaves via mobile app.
- **FR-CV-02:** Display diagnostic results alongside confidence scores calculated by the model.
- **FR-CV-03:** Link diagnostic output directly to localized treatment protocols approved by the Egyptian Ministry of Agriculture.

### B. LLM-RAG Advisory Module
- **FR-RAG-01:** Support voice and text queries in Arabic and Egyptian agricultural dialects.
- **FR-RAG-02:** Restrict advisory responses exclusively to official publications from the Agricultural Research Center (ARC).
- **FR-RAG-03:** Provide fertilizer dosing recommendations based on crop type and growth stage to minimize nitrogen over-application.

### C. Management Dashboard
- **FR-DB-01:** Visualize spatial and statistical distribution of infection hot-spots per farm section.
- **FR-DB-02:** Calculate realized financial savings in pesticides and fertilizers (in EGP) compared to market benchmarks.

---

## 3. User Stories

| User Role | Goal / Need | Business Value |
| :--- | :--- | :--- |
| **Field Farmer / Supervisor** | Capture leaf images via mobile for immediate diagnostic results. | Reduces response time, prevents disease spread, and ensures correct chemical targeting. |
| **Farm Manager** | Ask the advisory agent for fertilizer doses suited to current weather conditions. | Prevents fertilizer waste and lowers input costs amidst market price spikes. |
| **Investor / Owner** | View a dashboard showing percentage infection reduction and financial savings in EGP. | Measures Return on Investment (ROI) from adopting the AI platform. |

---

## 4. Targeted Crop Disease Evaluation Framework
> **Note:** Final disease classes are selected and provided by the Computer Vision Team based on dataset availability. The Analyst's role is defining selection criteria and financial impact.

| Disease / Crop ID | Targeted Disease Name | Selection Criteria & Business Justification (Analyst) | Dataset Readiness (CV Team) |
| :---: | :--- | :--- | :--- |
| **Disease 01** | *[Provided by CV Team]* | High-impact strategic crop (e.g., Wheat/Potato) with significant yield loss risk. | *[Pending CV Input]* |
| **Disease 02** | *[Provided by CV Team]* | High prevalence in Nile Delta or reclaimed desert soils. | *[Pending CV Input]* |
| **Disease 03** | *[Provided by CV Team]* | High visual similarity to other issues, requiring CV assistance. | *[Pending CV Input]* |
| **Disease 04** | *[Provided by CV Team]* | High chemical treatment cost in the local market. | *[Pending CV Input]* |
| **Disease 05** | *[Provided by CV Team]* | Nutritional stress (e.g., Nitrogen deficiency) directly linked to fertilizer costs. | *[Pending CV Input]* |

---

## 5. Contribution to Data Inventory
- **Image Data:** Validating field-level coverage under varied Egyptian lighting, dust, and device camera qualities.
- **RAG Knowledge Base:** Indexing official Ministry of Agriculture bulletins to guarantee legal and agronomic compliance.
- **Market Data:** Linking live/market input costs for fertilizers and active ingredients.

---

## 6. Economic Impact & ROI Framework (Egyptian Market Baseline)

### Market Benchmarks:
- **Subsidized Nitrogen Fertilizers:** ~269 EGP/bag (Urea), while commercial market rates reach **7,800 – 8,650 EGP/ton**.
- **Crop Production Costs:** Wheat cultivation costs ~32,000–37,000 EGP/feddan; Potato cultivation exceeds 155,000 EGP/feddan.

### ROI Targets:
- **Input Savings:** 15% – 20% reduction in fertilizer and pesticide spending (Saving ~1,200 – 2,500 EGP/feddan for wheat; higher for export crops).
- **Yield Protection:** 10% – 15% reduction in crop loss via early detection (Protecting value between 5,500 – 18,000 EGP/feddan).
- **Decision Efficiency:** 30% reduction in field consultation overheads.
