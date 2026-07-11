# Reglas de Negocio y Lógica Financiera (KrossBooking Pace Pro)

## 1. Fórmulas Base y KPIs Principales
* **ADR (Lordo):** Suma de `Addebito soggiorno` / Suma de `Notti` vendidas.
* **RevPAR (Lordo):** Suma de `Addebito soggiorno` / (Días del mes * Unidades Totales). Mide la eficiencia general bruta.
* **Net RevPAR (Real):** (`Addebito soggiorno` - `Commissioni`) / Días del mes. Mide la rentabilidad diaria real descontando el coste de adquisición (OTAs).
* **L.O.S. (Length of Stay):** Promedio matemático de la columna `Notti` (`Notti.mean()`). Mide la duración media de las estancias.
* **Lead Time:** Diferencia matemática en días entre `Data inserimento` (Fecha de reserva) y `Check in`.
* **OTB (On The Books):** Captura fotográfica de los datos acumulados hasta la fecha de consulta (`fecha_hoy`). 
  * *Regla STLY (Same Time Last Year):* El histórico del año anterior se debe "recortar" calculando `fecha_hoy - 1 año`. Nunca se compara el OTB actual con el cierre final del mes pasado sin especificar el delta.

## 2. Reglas de Prorrateo (Cross-Month)
* Si una reserva cruza entre dos meses (ej. 28 de abril al 5 de mayo, 7 noches), los ingresos, las noches, las comisiones y los netos se **dividen proporcionalmente**.
* **Fórmula de proporción:** (Noches de estadía en el Mes A / Noches totales de la reserva).
* **Excepción V1.x:** Las reservas que cruzan de año (Cross-Year, ej. 28 Dic al 3 Ene) se asignan íntegras al mes de Check-in para evitar errores de parseo de años.

## 3. Reglas de Inventario y Cancelaciones
* **Cancelaciones:** Las reservas con estado "Cancellata" o "Cancellata con penale" se EXCLUYEN del cálculo de ingresos (Ricavi) y ocupación, pero se contabilizan para el KPI "% de Cancellazioni".
* **Inventario Bloqueado:** Las reservas no garantizadas pero que bloquean calendario (ej. "Opzione" o "Attesa CC") SÍ se suman a la ocupación y OTB, ya que el inventario no está disponible para la venta.

## 4. Lógica de Módulos Futuros (V2.0 y V3.0)

* **Ocupación Pesada (Weighted Occupancy):**
  * *Objetivo:* Medir el riesgo real de caída del OTB.
  * *Fórmula conceptual:* `[(Noches No Reembolsables * 1.0) + (Noches Flexibles * Factor de Riesgo)] / Días del Mes`. No todas las noches vendidas valen lo mismo hasta que pasa el periodo de cancelación gratuita.

* **Segmentación por Tipo de Apartamento (Tipología):**
  * *Objetivo:* Analizar el Pace de ventas según el tamaño del activo.
  * *Lógica:* Se creará un diccionario/mapping manual que asocie cada `unit_id` a una tipología basada en cantidad de habitaciones (ej. Monolocale, Bilocale, Trilocale). Los KPIs se podrán filtrar y agregar por esta nueva dimensión.

* **Rentabilidad PM vs Propietario:**
  * *Objetivo:* Separar claramente el margen de la agencia (PM) del beneficio del dueño del activo.
  * *Lógica Gross to Net:* 1. `Addebito soggiorno` (Bruto del cliente).
    2. `- Commissioni` (Coste OTA) = Netto Real / Ingreso de Distribución.
    3. De ese Netto Real, se divide en dos columnas maestras:
       * `Quota PM` = Ingreso bruto de la agencia de gestión.
       * `Quota proprietario` = Ingreso bruto del dueño del apartamento.
  * *Lógica de Costo Propietario:* Al total de `Quota proprietario` se le deben deducir los costos operativos pactados (Limpieza, Mantenimiento, Seguros) para obtener el Beneficio Real (Neto al bolsillo).