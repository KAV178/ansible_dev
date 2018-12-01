# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function)


class FilterModule(object):
    def filters(self):
        return {
            'comp_active': lambda in_data: [i for i in in_data if i['CP_DISP_RUN_STATE'] in ('Online', 'Running')]
        }
