#!/usr/bin/python
# coding: utf-8

from os import fstat, environ, path
from re import findall, match
from subprocess import Popen, PIPE, check_output
from time import sleep

from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'Kostrenko A.V. (kostrenko.av@gmail.com)'
}

DOCUMENTATION = '''
---
module: srvrmgr

short_description: A custom module to execute siebel srvrmgr commands and scripts.

version_added: "2.4"

description:
        - A custom module to execute siebel srvrmgr commands and scripts.
options:
  add_env:
    description:
      - Additional environment for siebel srvrmgr. Must be a python dictionary format
    default: None
    required: false
  cmd_stack:
    description:
        - List commands and scripts for execution
    default: None
    required: true
  creds:
    description:
        - Dictionary with credentials. Must have key 'sadmin_pw' with value of sadmin password.
          Additional can have key 'other' with value list of other credentials for hiding.
    default: None
    required: true
  sieb_path:
    description:
        - Path to siebserv directory
    default: None
    required: true
  sieb_gateway:
    description:
        - Name of siebel gateway
    default: None
    required: true
  sieb_enterprise:
    description:
        - Name of siebel enterprise
    default: None
    required: true
  skip_errors:
    description:
        - List error codes for skipping
    default: []
    required: false   
author:
    - Kostrenko Andrey (sbt-kostrenko-av@mail.ca.sbrf.ru)
'''

EXAMPLES = '''
# Simple example
    srvrmgr:
      add_env: { SIEBEL_LOG_EVENTS: 2, SIEBEL_DEBUG_FLAGS: 16 }
      cmd_stack: [ "backup namesrvr siebns.dat_test.bkp",
                  "/srvrmgr_scripts_dir",
                  "another_srvrmgr.script.cmd",
                  "Synchronize components"
                ]
      sieb_path: '/siebel/siebsrvr'
      sieb_gateway: 'test_siebel_gw'
      sieb_enterprise: 'CRM_ENTERPRISE'
      creds: { sadmin_pw: 'secrep_sadmin_password' }
      skip_errors: ['SBL-ADM-01067','SBL-ADM-01049']
      
# Simple example
    srvrmgr:
      add_env: "SIEBEL_LOG_EVENTS=2; SIEBEL_DEBUG_FLAGS=16"
      cmd_stack: [ "list servers" ]
      sieb_path: '/siebel/siebsrvr'
      sieb_gateway: 'test_siebel_gw'
      sieb_enterprise: 'CRM_ENTERPRISE'
      creds: { sadmin_pw: 'secrep_sadmin_password', other: ['another_sec_data'] }
'''

RETURN = '''
"results": [
         {
             "cmd": "", 
             "out": {
                 "lines": [], 
                 "parsed": [], 
                 "raw": ""
             },
             "err": {
                 "lines": [], 
                 "parsed": [], 
                 "raw": ""
             },
             "warn": {
                 "lines": [], 
                 "parsed": [], 
                 "raw": ""
             }
         }, 
     ]
     
WARNING! Blocks "err" and "warn", returns only if exists them.
'''


def parse_data(data):
    result = tuple()
    if len(data.strip()) > 0:
        if data.split()[0].strip() == 'Password:':
            ud = match(r'Connected to (?P<available_servers>\d+).*total of (?P<total_servers>\d+)',
                       data.split('\n')[-2])
            if ud:
                result += (ud.groupdict(),)
        elif '^$^' in data:
            ud = filter(len, map(str.strip, data.split('\n')))
            fields = tuple(filter(len, map(str.strip, ud[0].split('^$^'))))
            for line_ndx in range(2, len(ud) - 1):
                result += (dict(zip(fields, map(str.strip, ud[line_ndx].split("^$^")))),)
        else:
            result = tuple(filter(len, data.split('\n')))
    return result


def prepare_env(sieb_path, add_env=None):
    res_env = environ.copy()
    res_env['NLS_LANG'] = "AMERICAN_AMERICA.AL32UTF8"
    res_env['SIEBEL_DEBUG_FLAGS'] = "16"
    siebenv_sh = check_output('. ' + path.join(sieb_path, 'siebenv.sh') + '; set',
                              bufsize=-1, shell=True)
    for env_var in siebenv_sh.split('\n'):
        if '=' in env_var:
            var_name, var_value = env_var.split('=')
            if var_name not in ['_', 'EDITOR', 'ENV', 'FCEDIT', 'HISTCMD', 'HOME', 'IFS', 'JOBMAX', 'KSH_VERSION',
                                'LINENO', 'LOGNAME', 'MAIL', 'MAILCHECK', 'OLDPWD', 'OPTIND', 'PPID', 'PWD', 'RANDOM',
                                'SECONDS', 'SHELL', 'SHLVL', 'TERM', 'TMOUT', 'TZ', 'USER'] \
                    and var_name[:4] != 'SSH_' \
                    and len(findall(r'PS\d', var_name)) == 0:
                res_env[var_name] = var_value

    if add_env:
        res_env.update({k: unicode(v) for k, v in add_env.items()})

    return res_env


def exec_cmd(srvrmgr_pipe, stdin_cmd, skip_errors_lst, sadmin_pwd):
    def get_proc_data(trg):
        res_data = ""
        trg_size = fstat(trg.fileno()).st_size
        while trg_size > 0:
            res_data += trg.read(trg_size)
            sleep(1)
            trg_size = fstat(trg.fileno()).st_size
        trg.flush()
        return res_data

    result = {'out': '', 'err': '', 'warn': ''}
    srvrmgr_pipe.stdin.write(b'{0}\n'.format(stdin_cmd))
    srvrmgr_pipe.stdin.flush()
    output_size = 0
    while output_size == 0:
        print("Waiting for output...")
        sleep(1)
        output_size = fstat(srvrmgr_pipe.stdout.fileno()).st_size

    result['out'] = get_proc_data(srvrmgr_pipe.stdout).replace('\nsrvrmgr> ', '').replace(sadmin_pwd, "*" * 6)
    result['err'] = get_proc_data(srvrmgr_pipe.stderr).replace(sadmin_pwd, "*" * 6)

    if any(map(lambda x: x in result['err'], skip_errors_lst)):
        result['err'], result['warn'] = result['warn'], result['err']
    return result


def sec_clean(data, sec_data):
    def clean_data(sc_data, sec_str, mask='******'):
        if type(sc_data) is unicode or type(sc_data) is str:
            return sc_data.replace(sec_str, mask)
        elif type(sc_data) is list:
            return [clean_data(l, sec_str, mask) for l in sc_data]
        elif type(sc_data) is dict:
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


def main():
    result = dict(
        changed=False,
        original_message='',
        message='',
        results=[],
        rc=0
    )

    module = AnsibleModule(
        argument_spec=dict(
            add_env=dict(type='dict', default=None, required=False),
            cmd_stack=dict(type='dict', default=None, required=True),
            skip_errors=dict(type='list', default=[], required=False),
            creds=dict(type='dict', default=None, required=True),
            sieb_path=dict(type='str', default=None, required=True),
            sieb_gateway=dict(type='str', default=None, required=True),
            sieb_enterprise=dict(type='str', default=None, required=True),
        ),
        supports_check_mode=True
    )

    module.params['cmd_stack'][0.0] = module.params['creds']['sadmin_pw']
    module.params['cmd_stack'][float(max(module.params['cmd_stack'].keys())) + 1] = "quit"

    srvrmgr = Popen(args=['srvrmgr', '-g', module.params['sieb_gateway'], '-e', module.params['sieb_enterprise'], '-u',
                          'sadmin', '-k', '^$^'], stdin=PIPE, stdout=PIPE, stderr=PIPE, bufsize=-1, shell=False,
                    env=prepare_env(module.params['sieb_path'], module.params['add_env']))
    for cmd_ndx in sorted(module.params['cmd_stack'], key=float):
        try:
            res_out = exec_cmd(srvrmgr, module.params['cmd_stack'][cmd_ndx],
                               module.params['skip_errors'],
                               module.params['creds']['sadmin_pw'])

            res_out = sec_clean(res_out, module.params['creds'])

            res_data = {'cmd': module.params['cmd_stack'][cmd_ndx]}

            if module.params['cmd_stack'][cmd_ndx].split()[0] == 'read':
                res_data['cmd'] = path.basename(module.params['cmd_stack'][cmd_ndx].split()[1])
            else:
                res_data['cmd'] = module.params['cmd_stack'][cmd_ndx]

            for rd in ['out', 'err', 'warn']:
                if len(res_out[rd]) > 0:
                    res_data[rd] = dict(raw=res_out[rd], lines=res_out[rd].split('\n'), parsed=parse_data(res_out[rd]))

            res_data = sec_clean(res_data, module.params['creds'])
            result['results'].append(res_data)
            result['changed'] = True

            if 'err' in res_data.keys():
                raise RuntimeError(res_data['err']['raw'])
        except Exception as e:
            module.params['cmd_stack'][cmd_ndx] = sec_clean(module.params['cmd_stack'][cmd_ndx], module.params['creds'])
            result['changed'] = False
            result['stderr'] = '{0}'.format(e)
            result['stderr_lines'] = e.message.split('\n')
            module.fail_json(msg='Error on execute: {0}'.format(module.params['cmd_stack'][cmd_ndx]), **result)
    srvrmgr.stdin.close()
    srvrmgr.wait()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
