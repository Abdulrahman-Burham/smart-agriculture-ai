# 🌾 Week 2: Operational Data Exploration & Schema Architecture

**Role:** Business & Data Analyst - AgriTech  
**Project:** AI-Powered Smart Farm Management & Agriculture Decision Platform  

---

## 📌 Executive Summary
During Week 2, the focus shifted from high-level business requirements (BRD) to **data architecture design and operational analysis strategy**. Following a comprehensive evaluation of open-source datasets, significant gaps were identified regarding farm-level operational tracking. Consequently, a strategic decision was made to design a **Custom Operational Data Schema** engineered specifically for large-scale Egyptian commercial farms.

---

## 📁 Included Documents

* 📄 **[Data Assessment & Evaluation Summary](./Week_02/AgriTech_Week2_Data_Assessment_Summary.pdf):** Documents the open-source data survey, gaps identified in prediction-only datasets, and the rationale for custom schema design.
* 📄 **[Database Schema & Knowledge Base Specification](./Week_02/AgriTech_Week2_Database_Schema_KB.pdf):** Contains the relational schema across 6 core tables, synthetic data generation constraints, and required domain Knowledge Bases (KBs).

---

## 📄 1. Data Assessment & Gap Analysis

### **A. Primary Objective**
To acquire or construct an operational dataset reflecting daily field activities, IoT telemetry, and soil health for a single large-scale Egyptian farm, enabling:
* Remote operational monitoring for farm owners and managers.
* Real-time analytical dashboard integration.
* Automated alert generation (Alerts Engine) triggered by critical threshold breaches (e.g., severe soil moisture drop or high salinity).

### **B. Key Gaps in Available Open-Source Data**
* **Macro-Level Data:** National-level aggregated statistics (exports, total yield) that cannot support field-level decisions or real-time telemetry.
* **Prediction-Only Datasets:** Machine learning datasets optimized strictly for static predictions (e.g., crop recommendation, yield forecasting) lacking time-series telemetry (`Time-Series`) and daily operational logs.
* **Lack of Egyptian Farm Context:** Global datasets fail to reflect local soil properties ($pH$, salinity $EC$), climate curves, or current Egyptian market input economics.

### **C. Summary of Evaluated Datasets**

| Source / Link | Category | Assessment & Limitations |
| :--- | :--- | :--- |
| [Agriculture & Farming Dataset](https://www.kaggle.com/datasets/bhadramohit/agriculture-and-farming-dataset) | Macro Agricultural Data | High-level national stats; lacks single-farm operational granularity. |
| [Crop Recommendation & Soil Dataset](https://zenodo.org/records/19709807?preview_file=vae_dataset.csv) | Soil Analysis / Classification | ML prediction-focused; lacks time-series telemetry and operational logs. |
| [Agri Research Datasets](https://zenodo.org/records/12666667?preview_file=dadata.zip) | Foreign Research Data | Non-Egyptian climate/soil profiles; incompatible with local field operations. |
| [Crop Recommendation Dataset](https://www.kaggle.com/datasets/siddharthss/crop-recommendation-dataset) | Classification (ML) | Static NPK/pH prediction; no time-series depth or alert trigger capability. |
| [Crop Yield Prediction Dataset](https://www.kaggle.com/datasets/patelris/crop-yield-prediction-dataset?select=pesticides.csv) | Yield & Pesticide Data | Global historical stats; unusable for real-time farm sensor tracking. |

---

## 🗄️ 2. Database Schema Architecture

A relational database structure comprising **6 core tables** was designed with explicit temporal and operational relationships:

[Sectors]
│
├──► [Crop_Cycles]
│         │
│         ├──► [Soil_Telemetry]
│         ├──► [Farm_Operations]
│         └──► [Alerts_Log]
│
└──► [Weather_Telemetry]

### **Table Architecture Overview**

| Table Name | Operational Purpose | Primary Indicators / Fields |
| :--- | :--- | :--- |
| **`Sectors`** | Geographic division & irrigation systems | `sector_id`, `area_feddans`, `soil_type`, `irrigation_type` |
| **`Crop_Cycles`** | Crop lifecycle tracking per sector | `crop_name`, `planting_date`, `current_stage`, `target_yield_ton` |
| **`Soil_Telemetry`** | Time-series field sensor telemetry | `soil_moisture_10cm`, `soil_ec_ds_m`, `soil_ph`, `N`, `P`, `K` |
| **`Weather_Telemetry`** | Real-time micro-climate readings | `air_temp_c`, `relative_humidity`, `wind_speed`, `et0_mm_day` |
| **`Farm_Operations`** | Field activities (irrigation, fertigation, spraying) | `op_type`, `input_material`, `water_volume_m3`, `total_cost_egp` |
| **`Alerts_Log`** | Automated critical threshold alerts | `alert_code`, `severity`, `trigger_condition`, `action_recommendation` |

---

## 📚 3. Required Knowledge Bases (KBs) for Synthetic Data

To guide AI-assisted synthetic data generation (`Dummy Data`), 5 specific domain Knowledge Bases must be compiled:

1. **Agri-Crop KB:** Sowing/harvesting calendars, growth stages, and average yields for strategic Egyptian crops (wheat, potato, maize).
2. **Soil & Irrigation KB:** Soil profiles in Egyptian reclaimed lands (e.g., Toshka, New Delta), baseline $pH$ and $EC$ ranges, and water application rates per feddan.
3. **Fertilizers & Market KB:** Fertilizer types (Urea 46%, Ammonium Nitrate), application rates, and current local market prices (EGP) for cost calculation.
4. **Climate KB:** Regional temperature/humidity diurnal curves and Evapotranspiration ($ET_0$) rates across seasons in Egypt.
5. **Alert Thresholds KB:** Numerical triggers for stress conditions (e.g., soil moisture $<20\%$, salinity $>4.0\text{ dS/m}$, fungal risk climate formulas).

---

## 🔄 Next Steps for Week 3
* Execute synthetic data generation scripts using AI tools guided by the KB constraints.
* Develop initial wireframes for the operational analysis dashboard.
