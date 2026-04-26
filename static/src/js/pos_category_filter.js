odoo.define('base_localizacion_clientes.pos_category_filter', function (require) {
    'use strict';

    const { PosGlobalState } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

    const PosCategoryFilter = (PosGlobalState) => class PosCategoryFilter extends PosGlobalState {
        async _processData(loadedData) {
            // Obtenemos la compañía actual desde los datos cargados, ya que this.config aún no se ha inicializado
            const config = loadedData['pos.config'];
            const currentCompanyId = config ? (Array.isArray(config.company_id) ? config.company_id[0] : config.company_id) : null;

            // Filtramos las categorías antes de que se carguen en el POS
            if (currentCompanyId && loadedData['pos.category']) {
                loadedData['pos.category'] = loadedData['pos.category'].filter(category => {
                    if (!category) return false;
                    const categoryCompanyId = Array.isArray(category.company_id) ? category.company_id[0] : category.company_id;
                    return !categoryCompanyId || categoryCompanyId === currentCompanyId;
                });
            }

            // Llamamos al método original para continuar con la carga
            await super._processData(loadedData);
        }
    };

    Registries.Model.extend(PosGlobalState, PosCategoryFilter);

    return PosCategoryFilter;
});