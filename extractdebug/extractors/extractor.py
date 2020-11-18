from enum import Enum


class Extractor:
    def test(self, file):
        raise NotImplementedError

    def extract(self, file):
        raise NotImplementedError


class ExtractorResult:
    def __init__(self, source_file, classes):
        self.source_file = source_file
        self.classes = classes

    def __repr__(self):
        return f'ExtractorResult{self.classes}'


class Class:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.members = kwargs.get('members', None)
        self.inheritance_class = kwargs.get('inheritance_class', None)
        self.inheritance_accessibility = kwargs.get('inheritance_accessibility', None)

    def __repr__(self):
        return f'Class{{name={self.name}, fields={self.members}'


class Accessibility(Enum):
    private = 0
    public = 1


class Field:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.type = kwargs.get('type', None)
        self.accessibility = kwargs.get('accessibility', Accessibility.private)
        self.static = kwargs.get('static', False)
        self.const_value = kwargs.get('const_value', None)

    def __repr__(self):
        return f'Field{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'


class Union:
    def __init__(self, fields, accessibility):
        self.fields = fields
        self.accessibility = accessibility


class Parameter:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.type = kwargs.get('type', None)


class Type:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.modifiers = kwargs.get('modifiers', None)


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
        self.parameters = kwargs.get('parameters', [])

    def __repr__(self):
        return f'Method{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'
