# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'Kostrenko A.V. (kostrenko.av@gmail.com)'
}

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display

    display = Display()

from re import search as re_search


def fails_in_outs(target, conds):
    result = False
    for cl in ['STDOUT', 'STDERR']:
        if cl in conds and len(conds[cl]) > 0:
            result = has_fails(target[cl.lower()], conds[cl])
        elif cl not in conds:
            continue
        else:
            display.vvv("Condition list: {0} length: {1}".format(cl, len(conds[cl])))
        if result:
            break
    return result


def has_fails(target, conds):
    result = False
    for c in conds:
        display.vvv("=>" * 10)
        display.vvv(u"Checking data:\n{1}\n{0}{1}\n".format(target, "-" * 6))
        display.vvv(u"Condition type: \"{0}\"{1}".format(c['cond'], " data: \"{0}\"".
                                                         format(c['data'].encode('utf-8')) if 'data' in c.keys() else ""))

        if c['cond'] == 'in':
            result = c['data'].encode('utf-8') in target
        elif c['cond'] == 'not in':
            result = c['data'].encode('utf-8') not in target
        elif c['cond'] == '>':
            result = target > c['data']
        elif c['cond'] == '<':
            result = target < c['data']
        elif c['cond'] == '==':
            result = target == c['data'].encode('utf-8')
        elif c['cond'] == '!=':
            result = target != c['data'].encode('utf-8')
        elif c['cond'] == 'not empty':
            result = len(target) > 0
        elif c['cond'] == 'regex':
            result = re_search(c['data'], target) is not None
        else:
            display.warning("Unknown condition \"{0}\"".format(c['cond']))
            result = True
        if result:
            break
        display.vvv("Checking result: {0}".format(result))
        display.vvv("{0}".format("<=" * 10))
    return result


class TestModule:
    def tests(self):
        return {
            'fails_in_outs': fails_in_outs,
            'has_fails': has_fails,
        }
