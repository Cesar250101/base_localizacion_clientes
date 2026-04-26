# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import math

from lxml import etree

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools import parse_date

_logger = logging.getLogger(__name__)

try:
    from num2words import num2words
except ImportError:
    _logger.warning("The num2words python library is not installed, amount-to-text features won't be fully available.")
    num2words = None


class Currency(models.Model):
    _inherit = "res.currency"

    rounding = fields.Float(string='Rounding Factor', 
                            digits=(12, 6), 
                            default=0.01,
                            help='Amounts in this currency are rounded off to the nearest multiple of the rounding factor.')

    def _compute_decimal_places(self):
        for currency in self:
            if 0 < currency.rounding < 1:
                currency.decimal_places = int(math.ceil(math.log10(1/currency.rounding)))
            else:
                currency.decimal_places = 0 
