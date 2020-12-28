import os
import re
from collections import OrderedDict

type_mapping = {
    'std::string': 'string'
}


def get_project_files(result):
    base_path = result.base_dir
    project_files = {}
    for file_id, file in result.files.items():
        file.directory = os.path.abspath(file.directory)
        if file.name != b'<built-in>' and (file.directory.startswith(base_path) or not file.directory.startswith(b'/')):
            project_files[file_id] = file

    return base_path, project_files


def is_project_file(cu_offset, decl_file):
    pass


def relative_path(base_path, file_path):
    path = os.path.relpath(file_path, base_path)
    if path.startswith(b'./'):
        path = path[2:]

    return path


def test_utf8(data):
    if not data:
        return False

    try:
        data.decode('utf-8')
        return True
    except:
        return False


def get_utf8(source, name, default):
    value = source.get(name, None)
    if not value or not test_utf8(value):
        return default.decode('utf-8')

    return value.decode('utf-8')


regexes = [
    (re.compile(r'\bstd(ext)?::'), r''),
    (re.compile(r'\b(_?basic_(string|if?stream|of?stream|([io]?stringstream)))<(char|wchar_t), ?(string_)?char_traits<\4>(, ?__default_alloc_template<(true|false), ?0>)? ?>::\1'), r'\2::\2'),
    (re.compile(r'\b_?basic_(string|if?stream|of?stream|([io]?stringstream))<(char|wchar_t), ?(string_)?char_traits<\3>(, allocator<\3>)? ?>'), r'\1'),
    (re.compile(r'\b__gnu_cxx::'), r'')
]


def demangle_type(source):
    # for regex, replacement in regexes:
    #     source = regex.sub(replacement, source)
    return source


class Entry:
    def __init__(self):
        self.name = None

    def fill_value(self):
        raise NotImplementedError()

    def id(self):
        return f'{self.__class__.__name__} {self.name}'


class EntriesStorage:
    def __init__(self):
        self.quick_access = OrderedDict()

    def __iter__(self):
        return iter(list(self.quick_access.values()))

    def __len__(self):
        return len(self.quick_access.values())

    def send(self, entry):
        if entry.id() in self.quick_access:
            prev_element = self.quick_access[entry.id()]
            if prev_element.fill_value() < entry.fill_value():
                self.quick_access[entry.id()] = entry
        else:
            self.quick_access[entry.id()] = entry
