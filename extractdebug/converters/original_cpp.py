from extractdebug.converters.converter import Converter
from extractdebug.extractors.extractor import Field, Accessibility, Method


class OriginalCPPConverter(Converter):
    def name(self):
        return 'cpp'

    def convert(self, result):
        classes = []
        for cls in result.classes:
            members = []
            for member in cls.members:
                if isinstance(member, Field):
                    members.append(CPPField(Accessibility(member.accessibility), member.type, member.name))
                elif isinstance(member, Method):
                    members.append(CPPMethod(Accessibility(member.accessibility), member.type, member.name))

            classes.append(CPPClass(cls.name, members))

        return classes[0]


class CPPMethod:
    def __init__(self, accessibility, type, name):
        self.name = name.decode("utf-8")
        self.type = type.decode("utf-8")
        self.accessibility = accessibility

    def __repr__(self):
        return f'{self.type} {self.name}();'


class CPPField:
    def __init__(self, accessibility, type, name):
        self.name = name.decode("utf-8")
        self.type = type.decode("utf-8")
        self.accessibility = accessibility

    def __repr__(self):
        return f'{self.type} {self.name};'


class CPPBlock:
    def __init__(self, level, children):
        self.level = level
        self.children = children

    def __repr__(self):
        lines = []
        last_accessibility = None

        for member in self.children:
            if member.accessibility != last_accessibility:
                lines.append(' ' * ((self.level - 1) * 4) + f'{member.accessibility.name}:')
                last_accessibility = member.accessibility

            lines.append(' ' * (self.level * 4) + str(member))

        return '{\n' + '\n'.join(lines) + '\n}'


class CPPClass:
    def __init__(self, name, children):
        self.name = name.decode("utf-8")
        self.children = CPPBlock(1, children)

    def __repr__(self):
        return f"class {self.name} {self.children}"
