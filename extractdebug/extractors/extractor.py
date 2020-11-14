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
    def __init__(self, name, type, accessibility):
        self.name = name
        self.type = type
        self.accessibility = accessibility

    def __repr__(self):
        return f'Field{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'


class Method:
    def __init__(self, name, type, accessibility):
        self.name = name
        self.type = type
        self.accessibility = accessibility

    def __repr__(self):
        return f'Method{{name={self.name}, type={self.type}, accessibility={Accessibility(self.accessibility)}}}'
