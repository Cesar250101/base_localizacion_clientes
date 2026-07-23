# -*- coding: utf-8 -*-


def migrate(cr, version):
    """usage_hours pasa de Float a Char.

    Postgres no convierte automaticamente una columna double precision a
    varchar (Odoo solo agrega columnas nuevas, no migra tipos existentes),
    asi que lo hacemos a mano antes de que el ORM recree los campos,
    preservando los valores ya cargados (ej. "0.00" -> "0.00").
    """
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'repair_order'
          AND column_name = 'usage_hours'
          AND data_type <> 'character varying'
    """)
    if cr.fetchone():
        cr.execute("""
            ALTER TABLE repair_order
            ALTER COLUMN usage_hours TYPE varchar
            USING usage_hours::varchar
        """)
