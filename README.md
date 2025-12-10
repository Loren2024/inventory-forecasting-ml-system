# README.md – Inventory Forecasting ML System

## 1. Descripción General

Este proyecto implementa un sistema de predicción de inventarios basado en un modelo híbrido de Machine Learning para una empresa del sector industrial. La solución combina modelos ARIMA/SARIMA, Random Forest y XGBoost, seleccionando automáticamente el algoritmo con mejor desempeño por SKU.

El sistema incluye:

- Backend en FastAPI para el cálculo de predicciones y métricas.
- Base de datos PostgreSQL como repositorio central.
- Dashboard web en HTML + JavaScript (Plotly y TailwindCSS).
- Módulo de alertas y reposición sugerida.
- Análisis interanual, ranking de rotación y KPIs ejecutivos.

---

## 2. Requisitos del Sistema

### 2.1 Software necesario

- Python 3.10+
- PostgreSQL 14+
- pip 22+
- Navegador moderno

### 2.2 Dependencias principales

```
fastapi==0.115.4
uvicorn[standard]==0.30.6
psycopg2-binary==2.9.10
python-dotenv==1.0.1
pydantic==2.9.2
```

---

## 3. Estructura del Proyecto

```
inventory-forecasting-ml-system/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── schemas.py
│   │   ├── logic.py
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── dashboard.js
│   ├── css/
│       └── custom.css
│
└── README.md
```

---

## 4. Configuración de la Base de Datos

### 4.1 Crear base y esquema

```sql
CREATE DATABASE tsp_inventory;
CREATE SCHEMA inv;
```

### 4.2 Tablas requeridas

- inv.products  
- inv.warehouses  
- inv.inventory_movements  
- inv.inventory_movements_stage  
- inv.forecast  
- inv.model_eval  
- inv.model_meta  

### 4.3 Carga de datos

Se deben cargar:

- movimientos históricos 2022–2024  
- movimientos Q1 2025  
- forecast híbrido  
- métricas ARIMA / RF / XGB  
- catálogo de productos  

---

## 5. Configuración del Backend

### 5.1 Crear entorno virtual

```
cd backend
python -m venv .venv
.\.venv\Scripts\activate
```

### 5.2 Instalar dependencias

```
pip install -r requirements.txt
```

### 5.3 Archivo `.env`

```
PG_HOST=localhost
PG_PORT=5432
PG_DB=tsp_inventory
PG_USER=tsp_app
PG_PASSWORD=1234
PG_SCHEMA=inv
```

### 5.4 Ejecutar API

```
uvicorn app.main:app --reload
```

La API queda disponible en:

```
http://127.0.0.1:8000/api
```

---

## 6. Configuración del Frontend

### 6.1 Ubicación del dashboard

```
frontend/index.html
frontend/dashboard.js
```

### 6.2 Ejecución

- Usar Live Server (VSCode), o  
- cualquier servidor estático local.

El frontend consume:

```
http://127.0.0.1:8000/api
```

---

## 7. Endpoints Disponibles

#### 7.1 KPIs y métricas

```
GET /api/kpis/global
GET /api/kpis/portfolio
```

#### 7.2 Catálogo

```
GET /api/skus
```

#### 7.3 Series y forecast

```
GET /api/history/{sku}
GET /api/forecast/{sku}
GET /api/forecast_compare?sku=...
GET /api/real/sku/{sku}
```

#### 7.4 Comparativo interanual

```
GET /api/interannual?sku=...
```

#### 7.5 Alertas y reposición

```
GET /api/replenishment/all
GET /api/alerts/reorder
```

#### 7.6 Rankings

```
GET /api/top_skus/rotation
GET /api/top_skus/error
```

#### 7.7 Cobertura por familia

```
GET /api/family_coverage
```

---

## 8. Funcionamiento del Dashboard

### 8.1 Resumen Ejecutivo

Incluye:

- KPIs técnicos y ejecutivos  
- Histórico vs pronóstico vs real  
- Alertas priorizadas  
- Top SKUs por rotación  
- Cobertura por familia  

### 8.2 Pronósticos

Visualización detallada del forecast por SKU.

### 8.3 Alertas

- Riesgo y quiebre  
- Días de cobertura proyectada  
- Reposición sugerida  
- Fecha de quiebre  

### 8.4 Comparativo Interanual

Volumen OUT 2022–2024 vs Q1-2025.

### 8.5 Errores

Ranking por MAPE y RMSE.

---

## 9. Consideraciones de Despliegue

- El sistema está diseñado para ejecución local.  
- Puede migrarse a Docker, AWS EC2, Render o Railway.  
- No se deben versionar archivos `.env`.  
- Recomendado implementar autenticación en producción.  
- Para uso empresarial, integrar con ERP y pipeline ETL.

---

## 10. Autores y Créditos

**Tesistas**  
- Angélica Lira  
- Nadia Tinoco  

**Asesor Académico**  
- Ing. Daniel Burga  

**Institución**  
Universidad Peruana de Ciencias Aplicadas (UPC)  
Facultad de Ingeniería  
Trabajo de Suficiencia Profesional – Ingeniería de Sistemas  

---
