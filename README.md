# base_localizacion_clientes

Módulo de localización base para clientes Method en Odoo 16. Centraliza personalizaciones transversales aplicadas a múltiples modelos del ERP, adaptadas al contexto chileno y multi-empresa.

**Autor:** Method | **Web:** https://www.method.cl | **Versión:** 0.1

---

## Funcionalidades

### Planes y Topes
- Modelo `base_localiazcion_clientes.planes_topes` para definir planes de suscripción (ej: *Inicia*, *Emprende*) con límites de DTEs mensuales y monto máximo de ventas.
- La compañía queda vinculada a un plan. Al crear órdenes de venta o facturas se valida automáticamente que no se superen los topes del plan activo.

### Contactos (`res.partner`)
- Campo `gestioo_id` para identificador en sistema externo GestiOO.
- País por defecto: Chile.
- Campo `company_id` para soporte multi-empresa.
- Acción masiva `action_sync_company_from_transactions`: asigna empresa a contactos sin compañía revisando sus transacciones (ventas, compras, facturas, POS).

### Compañía (`res.company`)
- Campo `planes_topes_id` para vincular el plan de topes.
- Integración con **GestiOO**: campos `integrar_gestioo`, `token_gestioo` y URL de webhook calculada automáticamente.
- Campo `es_taller` para identificar empresas tipo taller.

### Productos
- `product.template`: campo `company_id`, dominio de categoría filtrado por empresa.
- `product.category`: campo `company_id` para segmentación multi-empresa.
- `product.supplierinfo`: filtros de proveedor y variante restringidos a la empresa activa.

### Categorías POS (`pos.category`)
- Campo `company_id` y `parent_id` filtrado por empresa.
- En la sesión POS se expone `company_id` al frontend.

### Órdenes de Venta (`sale.order`)
- Campo `gestioo_id` para trazabilidad en GestiOO.
- Validación de topes del plan al crear nuevas órdenes.

### Facturas (`account.move`)
- Campo `invoice_origin` editable con tracking.
- Validación de topes del plan (máx. DTEs y monto) al crear facturas.

### Pagos (`account.payment`)
- Filtrado de diarios por empresa activa.
- Cálculo de diarios disponibles segmentado por compañía.

### CRM (`crm.lead`)
- Al crear o mover un lead, la etapa se asigna automáticamente a la primera etapa configurada para la empresa activa.

### Grupos de Cuentas Personalizados
- Modelo `account.group.custom`: árbol jerárquico de agrupaciones contables con nombre compuesto y relación M2M a `account.account`.
- `account.account` extiende con campo `group_custom_ids`.

### Moneda (`res.currency`)
- Ajuste del factor de redondeo (`rounding`) con 6 decimales de precisión y cálculo de `decimal_places` para monedas sin decimales (ej: CLP).

### Importación de Líneas de Compra
- Wizard `import.purchase.lines.wizard` para cargar líneas de órdenes de compra desde archivo Excel.
- Botón directo en la orden de compra.

### Reporte de Orden de Venta
Herencia de `sale.report_saleorder_document` con las siguientes mejoras:

| Mejora | Descripción |
|---|---|
| **Tabla de cliente** | Reemplaza el bloque de dirección inline por una tabla organizada (Nombre, Dirección, Ciudad, Estado, País, RUT). |
| **Columna SKU** | Aparece solo si al menos una línea tiene `default_code` configurado. |
| **Columna Producto / Descripción** | Muestra *Producto* si todas las descripciones de línea coinciden con el nombre del producto; muestra *Descripción* si alguna difiere. |
| **Estilos** | Fuente reducida (9px), sin negrita en líneas, interlineado compacto. |
| **Totales** | "Untaxed Amount" reemplazado por "Monto Neto". |

---

## Dependencias

`base`, `stock`, `product`, `point_of_sale`, `crm`, `account`, `project`, `hr_timesheet`, `sale`, `purchase`, `repair`

---

## Instalación

```bash
# Actualizar el módulo en la base de datos
python odoo-bin --config=odoo.conf --update=base_localizacion_clientes --database=<nombre_bd>
```
