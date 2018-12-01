from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible.plugins.action import ActionBase
from ansible.utils.unsafe_proxy import AnsibleUnsafeText
from os.path import isdir, isfile, abspath, basename as p_bn, join as p_jp
from glob import glob
from math import trunc as m_trunc
from re import findall

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


def parse_data(in_data, sec_data={}, indent_multiplier=1, filter_str=None):
    def counter(max_val):
        for c in range(1, max_val + 1):
            yield c

    def check_filter(data):
        if len(findall(filter_str, data)) > 0:
            display.v(msg="{0} checking script by filter {1}-> matched".format('*' * (indent_multiplier + 1),
                                                                               "\"{0}\"".format(filter_str)
                                                                               if filter_str else ""))
            return True
        else:
            display.v(msg="{0} checking script  by filter {1}-> not matched".format('*' * (indent_multiplier + 1),
                                                                                    "\"{0}\"".format(filter_str)
                                                                                    if filter_str else ""))
            return False

    f_list = {}
    res_data = {}
    task_num = counter(len(in_data))
    for el_v in in_data:
        if isdir(el_v):
            display.v(msg="{0} found directory - {1}".format('*' * indent_multiplier, el_v))
            _f, _t = parse_data(sorted(glob(p_jp(el_v, "*.cmd"))),
                                indent_multiplier=indent_multiplier + 1,
                                filter_str=filter_str)
            dir_task_num = next(task_num)
            for _fi, _fv in _f.items():
                f_list[float("{0}.{1}".format(dir_task_num, m_trunc(_fi)))] = _fv
        elif isfile(el_v):
            display.v(msg="{0} found script - {1}".format('*' * indent_multiplier, el_v))
            if filter_str:
                try:
                    with open(el_v, mode='r') as scr_f:
                        script_body = scr_f.read()
                        if check_filter(script_body):
                            f_list[float(next(task_num))] = abspath(el_v)
                except IOError as e:
                    display.error('Fail on checking script by filter: {0}'.format(e), True)
            else:
                f_list[float(next(task_num))] = abspath(el_v)
        else:
            display.v(msg="{0} found command - {1}".format('*' * indent_multiplier, sec_clean(el_v, sec_data)))
            res_data[float(next(task_num))] = el_v

    res_data.update(dict.fromkeys(f_list))
    return f_list, res_data


def sec_clean(data, sec_data):
    def clean_data(sc_data, sec_str, mask='******'):
        if isinstance(sc_data, (unicode, str, AnsibleUnsafeText)):
            return sc_data.replace(sec_str, mask)
        elif isinstance(sc_data, list):
            return [clean_data(l, sec_str, mask) for l in sc_data]
        elif isinstance(sc_data, dict):
            for i in sc_data:
                sc_data[i] = clean_data(sc_data[i], sec_str, mask)
            return sc_data
        else:
            return sc_data

    data = clean_data(data, sec_data['sadmin_pw'], "Authorization")
    if "other" in sec_data.keys():
        for sd in sec_data['other']:
            data = clean_data(data, sd)
    return data


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        def update_result_msg(data):
            if 'msg' in result.keys():
                result['msg'] += data + '\n'
            else:
                result['msg'] = data + '\n'

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        remote_usr = task_vars.get('ansible_ssh_user') or self._play_context.remote_user
        remote_tmp = self._task.args.get('remote_tmp', None)
        # Get module parameters
        module_args = dict()
        for a in ['add_env', 'filter', 'cmd_stack', 'creds', 'skip_errors',
                  'sieb_path', 'sieb_gateway', 'sieb_enterprise']:
            module_args[a] = self._task.args.get(a, None)

        # Analyse received parameters
        for req_p in ['cmd_stack', 'creds', 'sieb_path', 'sieb_gateway', 'sieb_enterprise']:
            if type(module_args[req_p]) is None:
                result['failed'] = True
                update_result_msg('Parameter "{0}" is required\n'.format(req_p))

        if type(module_args['cmd_stack']) is not list:
            result['failed'] = True
            update_result_msg('Parameter "cmd_stack" must be a list type, but this is {0}'.
                              format(type(module_args['cmd_stack'])))

        if type(module_args['skip_errors']) is not list and module_args['skip_errors'] is not None:
            result['failed'] = True
            update_result_msg('Parameter "skip_errors" must be a list type, but this is {0}'.
                              format(type(module_args['skip_errors'])))
        elif module_args['skip_errors'] is None:
            module_args['skip_errors'] = []

        if not remote_tmp:
            remote_tmp = self._make_tmp_path(remote_usr)
            self._cleanup_remote_tmp = True
            display.vvv('Remote temp dir is not defined!\nCreated {0}'.format(remote_tmp))
        else:
            display.vvv('{0} defined as temp dir'.format(remote_tmp))

        # Analyse "cmd_stack" parameter
        display.display(msg="Analyse tasks...", color='yellow')
        files_for_copy, module_args['cmd_stack'] = parse_data(module_args['cmd_stack'],
                                                              sec_data=module_args['creds'],
                                                              filter_str=module_args['filter']
                                                              )

        # Copy files
        for f_ndx, f_name in files_for_copy.items():
            display.v(msg="Copying file {0}".format(f_name))
            module_args['cmd_stack'][f_ndx] = 'read {0}'.format(
                self._transfer_file(f_name, p_jp(remote_tmp, p_bn(f_name))))
        display.vvv("SRVRMGR_CMD_STACK: {0}".format(module_args['cmd_stack']))
        self._fixup_perms2((remote_tmp,), remote_usr)

        display.display(msg="Execute tasks [{0}]...".format(len(module_args['cmd_stack'])), color='yellow')
        del module_args['filter']
        module_res = self._execute_module(
            module_name='srvrmgr',
            module_args=module_args,
            task_vars=task_vars,
            tmp=remote_tmp,
            delete_remote_tmp=True
        )
        result.update(module_res)
        result = sec_clean(result, module_args['creds'])

        # report of execution
        if 'results' in result.keys():
            for r in result['results']:
                prefix = "Srvrmgr task: \"{0}\" ->".format(r['cmd'])
                if 'err' in r.keys():
                    display.error('{0} Fail'.format(prefix), True)
                elif 'warn' in r.keys():
                    display.warning('{0} Skipped with errors:\n - {1}'.format(prefix,
                                                                              '\n - '.join(r['warn']['parsed'][1::])),
                                    True)
                else:
                    display.display(msg="{0} Ok".format(prefix), color='green')
        return result
