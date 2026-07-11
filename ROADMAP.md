# KrossBooking Pace Pro — ROADMAP

## Contexto del Proyecto
- **Autor**: Consultor de Revenue Management para hoteles y apartamentos
- **Stack actual**: Python + Streamlit + Gemini AI + Plotly
- **PMS/Channel Manager**: KrossBooking (exportación Excel)
- **Mercado principal**: Property managers de apartamentos turísticos (Italia)
- **Fase actual**: Prueba privada (1 mes) → luego lanzamiento comercial
- **Objetivo estratégico**: Automatizar la consultoría de RM para escalar sin aumentar horas de trabajo

---

## Versiones Lanzadas

### v1.0 (Gemini — base original)
- Carga de dos archivos Excel (año anterior + año actual)
- KPIs básicos: Ricavi, Notti, ADR, LOS, Lead Time
- Booking Curve comparativa
- Radar de sotto-rendimento por apartamento
- Tracker de objetivos vs STLY
- Análisis IA con Gemini
- ⚠️ Problemas conocidos: API key expuesta, cálculo ocupación incorrecto, mezcla de idiomas, sin RevPAR, sin cancelaciones

### v1.1 (Claude — primera reescritura)
- ✅ API Key movida a `st.secrets` (`.streamlit/secrets.toml`)
- ✅ RevPAR con input manual de unidades en sidebar
- ✅ % Cancelaciones usando columna `Stato`
- ✅ Tab nuevo: Segmentación por Canal (Booking.com, Airbnb, Expedia Group, Diretto)
- ✅ Tab nuevo: Netto PM (Addebito soggiorno vs Quota PM vs Commissioni)
- ✅ Filtro Booking Curve: Ricavi o Prenotazioni cumulativi
- ✅ Prompt Gemini mejorado: fecha explícita, max 200 palabras, estructura fija
- ✅ Función `calcola_kpi()` centralizada
- ✅ Código unificado en italiano

### v1.2 (Claude — prorrateo)
- ✅ Prorrateo de reservas entre meses cruzados
  - Columnas prorrateadas: Addebito soggiorno, Notti, Netto PM, Commissioni
  - Proporción: noches del mes / noches totales
  - Excluye reservas cross-year (simplificación deliberada)
- ✅ RevPAR automático — PENDIENTE de implementar (acordado, no ejecutado aún)

---

## Backlog v1.x (Próximas sesiones)

| ID | Feature | Categoría | Prioridad | Notas |
|---|---|---|---|---|
| 1b | RevPAR automático + override manual | KPI | Alta | Contar unidades únicas del archivo completo; input manual como corrección |
| 4 | Ocupación pesada | Analítica predictiva | Media | Pondera valor de reserva según condiciones de cancelación |
| 12 | % Cancelaciones detallado | KPI | Media | Ya hay KPI básico, ampliar con tendencia y por canal |

---

## Backlog v2.0

| ID | Feature | Categoría | Notas |
|---|---|---|---|
| 3b | Prorrateo cross-year | Cálculo | Ignorado en v1.2, retomar cuando sea necesario |
| 7 | Competitive Set | Market Intelligence | Precios y ocupación de competidores. Muy complejo |
| 9 | Segmentación por tipo apartamento | Filtro | Trilo, bilo, monolocale, etc. |
| 10 | Histórico multi-año | Cálculo | Requiere refactor del sistema de carga |
| 11 | Cálculo completo al neto comisiones | Cálculo | Base ya hecha con Quota PM |

---

## Módulos Futuros (Grandes)

### 💰 Módulo Costing + Margen
**Objetivo**: Pasar de optimizar revenue bruto a optimizar margen real.
**Qué incluiría**:
- Costos variables por reserva: limpieza, lavandería, check-in externo
- Costos fijos por apartamento/mes: alquiler, internet, seguros, mantenimiento
- Costos semi-variables: mantenimiento correctivo (input manual)
- KPIs nuevos: GOP, NOPar (Net Operating Profit per Available Room)
- Margen % por canal → revelar si Booking.com es menos rentable que directo
- Neto propietario vs neto PM con costing aplicado
**Complejidad**: Media (con input manual de costos) → Alta (con importación automática)
**Diferenciador de mercado**: Ningún RMS accesible hace esto bien para apartamentos.

### 🏨 Mercado Hotelero (Hoteles Independientes)
**Target**: Hoteles boutique e aparthoteles de 15-40 habitaciones
**Por qué este segmento**:
- Puente natural desde el segmento apartamentos
- Misma lógica de gestor independiente
- Gap real: ninguna herramienta accesible combina precio dinámico + margen real
**Competencia existente**:
- RMS puros (IDeaS, Duetto, Atomize): caros, solo revenue bruto
- PriceLabs, RoomPriceGenie: accesibles pero sin costing
- M3, Aptech: costing para cadenas, demasiado pesados
**Fricciones a resolver**:
- Integración con PMS vía API (obligatoria para hoteles)
- Ciclo de venta más largo (GM + Revenue Manager + Controller)
- Expectativas de soporte más altas
**Prerequisito técnico**: Integración API con al menos un PMS popular (Mews, Clock, Protel)

### 🔗 Integraciones API
- KrossBooking API (eliminar exportación manual Excel — mayor salto de valor)
- PriceLabs API (enviar recomendaciones de precio directamente)
- PMS hoteleros (fase mercado hotelero)

---

## Decisiones de Arquitectura Tomadas

| Decisión | Elección | Motivo |
|---|---|---|
| Framework UI | Streamlit (fase prueba) → evaluar en fase comercial | Velocidad de desarrollo |
| IA | Gemini 2.5 Flash | Ya integrado, buena relación costo/calidad |
| Neto vs Costos | Addebito soggiorno vs Quota PM | Simplificación v1.x, expandir con módulo costing |
| RevPAR denominador | Automático (unidades únicas archivo) + override manual | Portafoglio dinámico |
| Prorrateo cross-year | Ignorado | Casos raros, complejidad no justificada en v1 |
| Idioma código | Italiano (variables y UI) | Mercado principal Italia |
| Ingesta de Datos | Patrón Adapter (Capa de adaptación) | El núcleo interno no debe depender de nombres de columnas de KrossBooking. Debe existir un "Modelo Estándar Interno". |
| Gestión de APIs | Archivo oculto (.streamlit/secrets.toml) | Ninguna API key o credencial debe estar quemada en el código principal. |
---

## Visión V3.0 (SaaS Comercial Enterprise)
**Objetivo**: Evolucionar de una herramienta de análisis interno a un ecosistema SaaS Multi-PMS y Multi-Usuario.
* **Arquitectura de Interfaz (Decoupled)**: Migrar de Streamlit a un frontend moderno (Next.js + Tailwind CSS) y un backend en Python (FastAPI).
* **Almacenamiento Centralizado**: Migrar de lectura en memoria a una Base de Datos central en la nube (ej. Supabase / PostgreSQL).
* **Construcción Modular (Las 4 Fases)**:
  1. Motor Central (Revenue & PMS estandarizado).
  2. Módulo de Costing (Filtro de rentabilidad).
  3. Módulo Competitive Set (Ingesta de APIs externas).
  4. IA Advisor (Worker autónomo para auto-pricing).

## Notas para el Agente (Antigravity / Gemini)
Cuando inicies una nueva sesión en este workspace, DEBES leer este archivo `@ROADMAP.md` completo antes de escribir una sola línea de código. 
Este archivo es la "Constitución" del proyecto. Confirma siempre que has entendido la arquitectura (Patrón Adapter, Modelo Estándar y Arquitectura Modular) antes de ejecutar cualquier tarea.
