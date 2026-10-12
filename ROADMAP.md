# Rate Labs — ROADMAP

> Fuente de verdad: *Documento Maestro — Rate Labs: Plataforma de Diagnóstico y Estrategia de Revenue* (30/09/2026).

## Posicionamiento
Rate Labs **no es un RMS**: es la capa de diagnóstico y estrategia que se acopla a cualquier PMS/RMS
(Kross Booking, Guesty, Beyond, PriceLabs…). No calcula el precio del día: explica por qué una propiedad
no vende y qué palanca tocar.

## Reglas del proyecto
1. Rate Labs no calcula el precio diario: eso es trabajo del RMS del cliente.
2. Las reglas diagnostican; la IA explica. La IA no inventa causas ni sugiere precios por debajo del Bottom Rate.
3. Una palanca por propiedad y semana, para poder medir su efecto.
4. Toda recomendación y toda decisión quedan registradas, con su hipótesis.
5. Nada de scraping con credenciales del cliente.
6. Validar con trabajo manual antes de automatizar.

## Árbol de diagnóstico (la primera etapa que falla define la palanca)
| Pregunta | Si falla → palanca |
|---|---|
| ¿Impresiones en búsqueda OK? | Posicionamiento |
| ¿CTR del listado OK? | Escaparate |
| ¿Conversión de la ficha OK? | Ficha y condiciones |
| ¿Margen sobre el Bottom Rate? | Rentabilidad |

## Estado actual del código (oct. 2026)
- **App Streamlit** (`krossbooking_v1_1.py`): KPI/pace vs STLY, pickup, canales, costes y márgenes, Bottom Rate, calendario, análisis IA (diagnóstico + 1 palanca). Login Supabase, un cliente por sesión, datos filtrados por tenant.
- **Acceso a datos**: `db.py` (todas las consultas; paginación incluida).
- **Ingesta**: `adapter_krossbooking.py` y `adapter_generic.py` (mapeo guardado en `source_mappings`). Carga en `etl_supabase.py`, cada archivo queda en `data_imports`.
- **Costes**: `property_costs` (fijos, variables y facturas con histórico) + `property_settings` (cleaning fee, estancia mínima…). Margen en `etl_metrics.py`.
- **Comp set**: `etl_competitors.py` (Apify → `market_snapshots`, service role).
- **Email semanal**: `scripts/weekly_summary_email.py` (un email por tenant a sus owners).
- **Esquema**: `supabase/migrations/` (ejecutar en orden).

## Próximo paso
Árbol de diagnóstico → `diagnoses`; formulario semanal del embudo → `funnel_metrics`; bandeja de recomendaciones y registro de decisiones (`recommendations`, `decisions`, `outcomes`).

## Roadmap por fases (solo se pasa de fase al cumplir la puerta)
| Fase | Contenido | Puerta |
|---|---|---|
| 0 · Validar | Informe semanal a mano para 3–5 pilotos durante 1 mes (trulli Puglia como primer caso) | ¿Lo pagarían, cuánto y por cuántas propiedades? |
| 1 · Motor | Parser con mapeo guardado, modelo de datos, árbol de diagnóstico | Carga semanal en < 5 min |
| 2 · Producto | Bandeja de recomendaciones con IA, registro de decisiones, informes | Primeros clientes de pago en Pro |
| 3 · Aprender | Análisis de fin de temporada, versión Esencial para hoteles pequeños | — |

## Fuera de alcance
Motor de precio dinámico propio, escritura automática de precios en el PMS, integraciones Channex/Apaleo.
