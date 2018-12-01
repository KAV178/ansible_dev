from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'Kostrenko A.V. (kostrenko.av@gmail.com)'
}

DOCUMENTATION = """
      lookup: file
        author: Kostrenko Andrey Valerievich <kostrenko.av@gmail.com>
        version_added: "1.0"
        short_description: mapping paths from a file according to mapping settings
        description:
            - This lookup returns the mapped list of paths described in the file according to the mapping settings.
        options:
          file:
            description: file with path(s) for mapping
            required: True
          map_dict:
            description: dictionary describing the mapping
            required: True
          
"""

EXAMPLES = """

DIR_MAP: { '/home/usr1/fs1' : ['/usr/local/home/usr1/fs1_0',
                               '/usr/local/home/usr1/fs1_1'
                              ],
           '/home/usr1/doc' : '/usr/local/home/usr1/documents',
         }

"file_with_data.txt" contains:
/home/usr1/fs1/file1.txt
/home/usr1/fs1/pic.jpg
/home/usr1/doc/document.pdf

- name: "Mapped items over lookup"
  debug: msg="Mapped paths {{ lookup('map_from_file', 'file=file_with_data.txt map_dict={{ DIR_MAP }}') }}"

- name: msg="Mapped items in loop"
  debug: msg="Mapped item: {{ item }}"
  with_map_from_file: 'file=file_with_data.txt map_dict={{ DIR_MAP }}'
"""

RETURN = """
  _list:
    description:
      - mapped paths.
    type: list
"""

from ansible.errors import AnsibleError, AnsibleParserError, AnsibleFilterError
from ansible.plugins.lookup import LookupBase
from ansible.module_utils._text import to_text
from re import match as re_match
from ast import literal_eval as l_eval

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class LookupModule(LookupBase):

    def parse_data(self, term):
        parse_res = re_match(r'(?P<F>file)=(?P<FV>.*) (?P<MP>map_dict)=(?P<MDV>.*)', term)
        setattr(self, 'f_name', parse_res.group('FV').strip())
        setattr(self, 'm_data', l_eval(parse_res.group('MDV').replace('u\'', '\'')))

    def read_file(self, variables):
        lookupfile = self.find_file_in_search_path(variables, 'files', self.f_name)
        display.vvv(u"File lookup using {0} as file".format(lookupfile))
        try:
            if lookupfile:
                b_contents, show_data = self._loader._get_file_contents(lookupfile)
                contents = to_text(b_contents, errors='surrogate_or_strict')
                setattr(self, "f_data", contents.rstrip().split())
                display.vvv(u"Received data from file: {0}".format(self.f_data))
            else:
                raise AnsibleParserError()
        except AnsibleParserError:
            raise AnsibleError(u"could not locate file: {0}".format(self.f_name))

    def map_dirs(self):
        map_res = set()
        w_ml = [(len(k.split('/')), k) for k in self.m_data.keys()]
        for s_path in self.f_data:
            map_found = False
            for t in sorted(w_ml, reverse=True):
                if t[1] in s_path:
                    if isinstance(self.m_data[t[1]], list):
                        for sub_v in self.m_data[t[1]]:
                            map_res.add(s_path.replace(t[1], sub_v))
                            display.vvv(u"Mapping result: {0} mapped to {1}".format(s_path, s_path.replace(t[1],
                                                                                                           sub_v)))
                    elif isinstance(self.m_data[t[1]], str):
                        map_res.add(s_path.replace(t[1], self.m_data[t[1]]))
                        display.vvv(u"Mapping result: {0} mapped to {1}".format(s_path,
                                                                                s_path.replace(t[1],
                                                                                               self.m_data[t[1]])))
                    else:
                        raise AnsibleFilterError(u"Invalid type of value in mapping data: {0}, must be list or "
                                                 u"str".format(self.m_data[t[1]].__class__))
                    map_found = True
                    break
            if not map_found:
                raise AnsibleError(u"Mapping not found for ""{0}"" file".format(s_path))
        return list(map_res)

    def run(self, terms, variables=None, **kwargs):
        results = []
        for term in terms:
            self.parse_data(term)
            self.read_file(variables)
            if len(self.f_data) > 0:
                results += self.map_dirs()
            else:
                raise AnsibleError("there is no data in the file: {0}".format(self.f_name))

        return results
