# -*- coding: utf-8 -*-

import base64
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import openpyxl
except ImportError:
    openpyxl = None


class ImportPurchaseLinesWizard(models.TransientModel):
    _name = 'import.purchase.lines.wizard'
    _description = 'Import Purchase Order Lines from Excel'

    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order')
    file = fields.Binary(string='Excel File')
    filename = fields.Char(string='Filename')

    def action_download_template(self):
        """Descargar plantilla de ejemplo"""
        return {
            'type': 'ir.actions.act_url',
            'url': '/base_localizacion_clientes/static/archivos/ImportPOL.xlsx',
            'target': 'new',
        }

    def action_import_lines(self):
        """Importar líneas desde el archivo Excel"""
        if not openpyxl:
            raise UserError(_('Please install openpyxl library: pip install openpyxl'))
        
        if not self.purchase_order_id:
            raise UserError(_('No se ha especificado una orden de compra.'))
        
        if not self.file:
            raise UserError(_('Por favor, cargue un archivo de Excel.'))
        
        # Decodificar el archivo
        file_content = base64.b64decode(self.file)
        workbook = openpyxl.load_workbook(io.BytesIO(file_content))
        sheet = workbook.active
        
        # Obtener la orden de compra
        purchase_order = self.purchase_order_id
        
        # Lista para almacenar las líneas a crear
        lines_to_create = []
        errors = []
        
        # Leer el archivo (comenzando desde la fila 2, asumiendo que la fila 1 son encabezados)
        for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row):  # Saltar filas vacías
                continue
            
            try:
                sku = row[0]  # Columna A: SKU
                quantity = row[1]  # Columna B: Cantidad
                price = row[2]  # Columna C: Precio
                
                # Validar que SKU no esté vacío
                if not sku or str(sku).strip() == '':
                    errors.append(_('Fila %s: El SKU es obligatorio y no puede estar vacío.') % row_num)
                    continue
                
                # Convertir SKU a string y limpiar espacios
                sku = str(sku).strip()
                
                # Buscar el producto por SKU (default_code)
                product = self.env['product.product'].search([
                    ('default_code', '=', sku),
                    '|', ('company_id', '=', False), ('company_id', '=', purchase_order.company_id.id)
                ], limit=1)
                
                if not product:
                    errors.append(_('Fila %s: No se encontró ningún producto con el SKU "%s". Verifique que el SKU existe en el sistema.') % (row_num, sku))
                    continue
                
                # Validar cantidad
                try:
                    quantity = float(quantity) if quantity else 1.0
                    if quantity <= 0:
                        errors.append(_('Fila %s: La cantidad debe ser mayor a 0.') % row_num)
                        continue
                except (ValueError, TypeError):
                    errors.append(_('Fila %s: Cantidad inválida "%s". Debe ser un número.') % (row_num, quantity))
                    continue
                
                # Validar precio
                try:
                    price = float(price) if price else 0.0
                    if price < 0:
                        errors.append(_('Fila %s: El precio no puede ser negativo.') % row_num)
                        continue
                except (ValueError, TypeError):
                    errors.append(_('Fila %s: Precio inválido "%s". Debe ser un número.') % (row_num, price))
                    continue
                
                # Preparar los valores de la línea
                line_vals = {
                    'order_id': purchase_order.id,
                    'product_id': product.id,
                    'name': product.display_name,
                    'product_qty': quantity,
                    'price_unit': price,
                    'product_uom': product.uom_po_id.id,
                    'date_planned': fields.Datetime.now(),
                }
                
                lines_to_create.append(line_vals)
                
            except Exception as e:
                errors.append(_('Fila %s: Error - %s') % (row_num, str(e)))
        
        # Mostrar errores si los hay
        if errors:
            error_message = '\n'.join(errors)
            raise UserError(_('Se encontraron errores durante la importación:\n\n%s') % error_message)
        
        # Crear las líneas
        if lines_to_create:
            self.env['purchase.order.line'].create(lines_to_create)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('%s líneas importadas exitosamente.') % len(lines_to_create),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_('No se encontraron líneas válidas para importar.'))

    def action_cancel(self):
        """Cancelar la importación"""
        return {'type': 'ir.actions.act_window_close'}
