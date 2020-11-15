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
                    parameters = [CPPParameter(x.name, x.type) for x in member.parameters if x.name != b'this']
                    members.append(CPPMethod(Accessibility(member.accessibility), member.type, member.name, parameters))

            classes.append(CPPClass(cls.name, members))

        return classes[0]


class CPPParameter:
    def __init__(self, name, type):
        self.name = name.decode("utf-8")
        self.type = type

    def __repr__(self):
        return f'{self.type.name.decode("utf-8")} {self.name}'


class CPPMethod:
    def __init__(self, accessibility, type, name, parameters):
        self.name = name.decode("utf-8")
        self.type = type
        self.parameters = parameters
        self.accessibility = accessibility

    def __repr__(self):
        params_string = ", ".join([str(x) for x in self.parameters])

        if self.type:
            return f'{self.type.name.decode("utf-8")} {("* " if self.type.pointer else "")}{self.name}({params_string});'
        else:
            return f'{self.name}({params_string});'


class CPPField:
    def __init__(self, accessibility, type, name):
        self.name = name.decode("utf-8")
        self.type = type
        self.accessibility = accessibility

    def __repr__(self):
        return f'{self.type.name.decode("utf-8")} {("* " if self.type.pointer else "")}{self.name};'


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
