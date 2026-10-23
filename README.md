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
- Campo `company_id` para soporte multi-empresa: es la compania principal del contacto (Many2one).
- Campo `partner_company_ids` ("Companias", Many2many, tabla `res_partner_company_rel`): todas las companias del contacto. Un contacto puede pertenecer a varias; sin companias es global. La compania principal siempre esta incluida en la lista (se sincroniza en `create`/`write`). Si se quita de la lista, la principal pasa a la compania de menor id que quede; si se vacia la lista se repone; si se vacia la compania principal, el contacto vuelve a ser global.
- La lista alimenta los dominios de la accion Contactos (`contacts.action_contacts`), de Clientes (`account.res_partner_action_customer`), el filtro "Contactos de la Compania", la regla de seguridad `base.res_partner_rule` (redefinida en `security/res_partner_rule.xml`), la busqueda MatchPoint, el dominio de proveedor de `product.supplierinfo` y el asistente de fusion de contactos (que une las companias). El webhook GestiOO y los selectores de contacto de facturas y pagos siguen usando `company_id` (la compania principal): `account.move` y `account.payment` rechazan al guardar un contacto cuya principal es otra compania, y la factura que sale de una orden del webhook es un `account.move`.
- `-i` y la migracion 0.8 comparten `hooks.populate_partner_companies`; al desinstalar, `uninstall_hook` devuelve la regla `base.res_partner_rule` del core y limpia los dominios de las acciones de Contactos y Clientes.
- Comportamientos a tener en cuenta: (a) cambiar la compania principal conserva la anterior en la lista (un usuario portal creado para B desde la compania 1 queda visible en ambas hasta quitar la etiqueta); (b) un contacto con lista [A, B] pero sin compania principal sigue visible en todas las companias por la regla (`company_id` vacio) y solo se oculta en las acciones; (c) la lista no se propaga a los contactos hijos.
- Accion masiva `action_sync_company_from_transactions`: asigna empresa a contactos sin compania (y sin companias en `partner_company_ids`) revisando sus transacciones (ventas, compras, facturas, POS).

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
- Opción por compañía para conservar el nombre original del contacto al publicar
  facturas, rectificativas y recibos, aunque el contacto sea renombrado después.

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
| **Columnas Producto (x2)** | Dos columnas siempre visibles: "SKU" muestra `default_code` del producto, "Producto" muestra el campo `name` de la linea de venta (`sale.order.line`). En bases donde la vista base trae una columna de nombre de producto extra (caso `clicksale`), se elimina automaticamente al cargar el modulo. |
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
