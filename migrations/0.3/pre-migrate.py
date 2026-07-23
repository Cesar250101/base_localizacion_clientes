# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Adopta emsin.equipos y repair.order.equipo_id desde el modulo emsin,
    para que al desinstalarlo no se borren la tabla ni la columna con datos
    reales ya cargados por los usuarios.
    """
    cr.execute("SELECT id FROM ir_model WHERE model = 'emsin.equipos'")
    model_row = cr.fetchone()
    if not model_row:
        return  # instalacion nueva, emsin.equipos no existe todavia
    model_id = model_row[0]

    cr.execute("""
        SELECT id FROM ir_model_fields
        WHERE model = 'emsin.equipos'
           OR (model = 'repair.order' AND name = 'equipo_id')
    """)
    field_ids = [row[0] for row in cr.fetchall()]

    cr.execute("""
        UPDATE ir_model_data
        SET module = 'base_localizacion_clientes'
        WHERE module = 'emsin'
          AND ((model = 'ir.model' AND res_id = %s)
            OR (model = 'ir.model.fields' AND res_id = ANY(%s)))
    """, (model_id, field_ids))
