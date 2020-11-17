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
    def __init__(self, name, members):
        self.name = name
        self.members = members

    def __repr__(self):
        return f'Class{{name={self.name}, fields={self.members}'


class Accessibility(Enum):
    private = 0
    public = 1


class Field:
    def __init__(self, name, type, accessibility, static):
        self.name = name
        self.type = type
        self.accessibility = accessibility
        self.static = static

    def __repr__(self):
        return f'Field{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'


class Parameter:
    def __init__(self, name, type):
        self.name = name
        self.type = type


class Type:
    def __init__(self, name=None, pointer=False, constant=False):
        self.name = name
        self.pointer = pointer
        self.constant = constant


class Method:
    def __init__(self, name, type, accessibility, static=False, parameters=None):
        if parameters is None:
            parameters = []

        self.name = name
        self.type = type
        self.accessibility = accessibility
        self.static = static
        self.parameters = parameters

    def __repr__(self):
        return f'Method{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'
