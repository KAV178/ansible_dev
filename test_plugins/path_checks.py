from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'Kostrenko A.V. (kostrenko.av@gmail.com)'
}

from os import path as os_path

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display

    display = Display()


class TestModule:
    def tests(self):
        return {
            'exists': lambda p: os_path.exists(p)
        }
