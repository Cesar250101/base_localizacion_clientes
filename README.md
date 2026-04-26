# base_localizacion_clientes

Modulo de localizacion base para clientes Method en Odoo 16. Centraliza personalizaciones transversales aplicadas a multiples modelos del ERP, adaptadas al contexto chileno y multi-empresa.

**Autor:** Method | **Web:** https://www.method.cl | **Version:** 0.1

---

## Funcionalidades

### Planes y Topes
- Modelo `base_localiazcion_clientes.planes_topes` para definir planes de suscripcion (ej: *Inicia*, *Emprende*) con limites de DTEs mensuales y monto maximo de ventas.
- La compania queda vinculada a un plan. Al crear ordenes de venta o facturas se valida automaticamente que no se superen los topes del plan activo.

### Contactos (`res.partner`)
- Campo `gestioo_id` para identificador en sistema externo GestiOO.
- Pais por defecto: Chile.
- Campo `company_id` para soporte multi-empresa.
- Accion masiva `action_sync_company_from_transactions`: asigna empresa a contactos sin compania revisando sus transacciones (ventas, compras, facturas, POS).

### Compania (`res.company`)
- Campo `planes_topes_id` para vincular el plan de topes.
- Integracion con **GestiOO**: campos `integrar_gestioo`, `token_gestioo` y URL de webhook calculada automaticamente.
- Campo `es_taller` para identificar empresas tipo taller.

### Productos
- `product.template`: campo `company_id`, dominio de categoria filtrado por empresa.
- `product.category`: campo `company_id` para segmentacion multi-empresa.
- `product.supplierinfo`: filtros de proveedor y variante restringidos a la empresa activa.

### Categorias POS (`pos.category`)
- Campo `company_id` y `parent_id` filtrado por empresa.
- En la sesion POS se expone `company_id` al frontend.

### Ordenes de Venta (`sale.order`)
- Campo `gestioo_id` para trazabilidad en GestiOO.
- Validacion de topes del plan al crear nuevas ordenes.

### Facturas (`account.move`)
- Campo `invoice_origin` editable con tracking.
- Validacion de topes del plan (max. DTEs y monto) al crear facturas.

### Pagos (`account.payment`)
- Filtrado de diarios por empresa activa.
- Calculo de diarios disponibles segmentado por compania.

### CRM (`crm.lead`)
- Al crear o mover un lead, la etapa se asigna automaticamente a la primera etapa configurada para la empresa activa.

### Grupos de Cuentas Personalizados
- Modelo `account.group.custom`: arbol jerarquico de agrupaciones contables con nombre compuesto y relacion M2M a `account.account`.
- `account.account` extiende con campo `group_custom_ids`.

### Moneda (`res.currency`)
- Ajuste del factor de redondeo (`rounding`) con 6 decimales de precision y calculo de `decimal_places` para monedas sin decimales (ej: CLP).

### Importacion de Lineas de Compra
- Wizard `import.purchase.lines.wizard` para cargar lineas de ordenes de compra desde archivo Excel.
- Boton directo en la orden de compra.

### Reporte de Orden de Venta
Herencia de `sale.report_saleorder_document` con las siguientes mejoras:

| Mejora | Descripcion |
|---|---|
| **Tabla de cliente** | Reemplaza el bloque de direccion inline por una tabla organizada (Nombre, Direccion, Ciudad, Estado, Pais, RUT). |
| **Columna SKU** | Aparece solo si al menos una linea tiene `default_code` configurado. |
| **Columna Producto / Descripcion** | Muestra *Producto* si todas las descripciones de linea coinciden con el nombre del producto; muestra *Descripcion* si alguna difiere. |
| **Estilos** | Fuente reducida (9px), sin negrita en lineas, interlineado compacto. |
| **Totales** | "Untaxed Amount" reemplazado por "Monto Neto". |

---

## Dependencias

`base`, `stock`, `product`, `point_of_sale`, `crm`, `account`, `project`, `hr_timesheet`, `sale`, `purchase`, `repair`

---

## Instalacion

```bash
# Actualizar el modulo en la base de datos
python odoo-bin --config=odoo.conf --update=base_localizacion_clientes --database=<nombre_bd>
```