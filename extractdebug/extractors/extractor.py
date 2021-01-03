import os
from collections import deque
from enum import Enum


class Extractor:
    def test(self, file):
        raise NotImplementedError

    def extract(self, file):
        raise NotImplementedError


class ExtractorResult:
    def __init__(self, source_file, files, elements, base_dir):
        self.source_file = source_file
        self.files = files
        self.elements = elements
        self.base_dir = base_dir

    def __repr__(self):
        return f'ExtractorResult{self.elements}'


class Class:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.members = kwargs.get('members', None)
        self.inheritance_class = kwargs.get('inheritance_class', None)
        self.inheritance_accessibility = kwargs.get('inheritance_accessibility', None)
        self.decl_file = kwargs.get('decl_file', None)
        self.parent = kwargs.get('parent', None)

    def __repr__(self):
        return f'Class{{name={self.name}, fields={self.members}'


class Struct:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.members = kwargs.get('members', None)
        self.decl_file = kwargs.get('decl_file', None)
        self.parent = kwargs.get('parent', None)

    def __repr__(self):
        return f'Struct{{name={self.name}, fields={self.members}'


class Accessibility(Enum):
    private = 0
    public = 1
    protected = 2


class Field:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.type = kwargs.get('type', None)
        self.accessibility = kwargs.get('accessibility', Accessibility.private)
        self.static = kwargs.get('static', False)
        self.const_value = kwargs.get('const_value', None)
        self.parent = kwargs.get('parent', None)
        self.decl_file = kwargs.get('decl_file', None)

    def __repr__(self):
        return f'Field{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'


class EnumerationType:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.type = kwargs.get('type', None)
        self.enumerators = kwargs.get('enumerators', None)
        self.decl_file = kwargs.get('decl_file', None)
        self.accessibility = kwargs.get('accessibility', Accessibility.private)


class Enumerator:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.value = kwargs.get('value', None)


class Union:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.fields = kwargs.get('fields', [])
        self.accessibility = kwargs.get('accessibility', Accessibility.private)
        self.decl_file = kwargs.get('decl_file', None)
        self.parent = kwargs.get('parent', None)


class Parameter:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.type = kwargs.get('type', None)
        self.offset = kwargs.get('offset', None)


class Type:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.namespaces = kwargs.get('namespaces', deque())
        self.modifiers = kwargs.get('modifiers', [])
        self.decl_file = kwargs.get('decl_file', None)
        self.array = kwargs.get('array', False)
        self.byte_size = kwargs.get('byte_size', False)
        self.base = kwargs.get('base', False)


class TypeModifier(Enum):
    pointer = 0
    constant = 1
    volatile = 2
    reference = 3


class Method:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.type = kwargs.get('type', None)
        self.accessibility = kwargs.get('accessibility', Accessibility.private)
        self.static = kwargs.get('static', False)
        self.virtual = kwargs.get('virtual', False)
        self.parameters = kwargs.get('parameters', [])
        self.direct_parameters = kwargs.get('direct_parameters', [])
        self.parent = kwargs.get('parent', None)
        self.low_pc = kwargs.get('low_pc', None)
        self.offset = kwargs.get('offset', None)
        self.decl_file = kwargs.get('decl_file', None)
        self.fully_defined = kwargs.get('fully_defined', None)
        self.linkage_name = kwargs.get('linkage_name', None)

    def __repr__(self):
        return f'Method{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'


class Namespace:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.elements = kwargs.get('elements', [])
        self.decl_file = kwargs.get('decl_file', None)
        self.parent = kwargs.get('parent', None)


class TypeDef:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.type = kwargs.get('type', None)
        self.decl_file = kwargs.get('decl_file', None)
        self.parent = kwargs.get('parent', None)


class File:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 0)
        self.name = kwargs.get('name', None)
        self.directory = kwargs.get('directory', None)

    def full_path(self):
        return os.path.abspath(os.path.join(self.directory, self.name))

    def __repr__(self):
        return f'File{{id={self.id}, name={self.name}, directory={self.directory}'
