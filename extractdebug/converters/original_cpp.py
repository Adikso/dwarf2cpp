from extractdebug.converters.converter import Converter
from extractdebug.extractors.extractor import Field, Accessibility, Method, TypeModifier


class OriginalCPPConverter(Converter):
    def name(self):
        return 'cpp'

    def convert(self, result):
        classes = []
        for cls in result.classes:
            members = []
            for member in cls.members:
                if isinstance(member, Field):
                    members.append(CPPField(Accessibility(member.accessibility), member.type, member.name, member.static, member.const_value))
                elif isinstance(member, Method):
                    parameters = [CPPParameter(x.name, x.type) for x in member.parameters if x.name != b'this']
                    members.append(CPPMethod(Accessibility(member.accessibility), member.type, member.name, member.static, parameters))

            classes.append(CPPClass(cls.name, members))

        return classes[0]

    @staticmethod
    def generate_type_modifiers_str(modifiers):
        result = ''
        for i, modifier in enumerate(modifiers):
            if modifier == TypeModifier.pointer:
                result += '*'
            elif modifier == TypeModifier.constant:
                if i > 0:
                    result += ' '
                result += 'const'
                if i != len(modifiers) - 1:
                    result += ' '

        if modifiers:
            result = ' ' + result
        return result + ' '


class CPPParameter:
    def __init__(self, name, type):
        self.name = name.decode("utf-8")
        self.type = type

    def __repr__(self):
        return f'{self.type.name.decode("utf-8")} {self.name}'


class CPPMethod:
    def __init__(self, accessibility, type, name, static, parameters):
        self.name = name.decode("utf-8")
        self.type = type
        self.static = static
        self.parameters = parameters
        self.accessibility = accessibility

    def __repr__(self):
        params_string = ", ".join([str(x) for x in self.parameters])
        basic_output = f'{self.name}({params_string});'

        if self.type:
            modifier_str = OriginalCPPConverter.generate_type_modifiers_str(self.type.modifiers)
            basic_output = f'{self.type.name.decode("utf-8")}{modifier_str}' + basic_output

        if self.static:
            basic_output = 'static ' + basic_output

        return basic_output


class CPPField:
    def __init__(self, accessibility, type, name, static, const_value):
        self.name = name.decode("utf-8")
        self.type = type
        self.accessibility = accessibility
        self.static = static
        self.const_value = const_value

    def __repr__(self):
        modifier_str = OriginalCPPConverter.generate_type_modifiers_str(self.type.modifiers)
        basic_output = f'{self.type.name.decode("utf-8")}{modifier_str}{self.name}'

        if self.const_value:
            basic_output += f' = {self.const_value}'

        if self.static:
            basic_output = 'static ' + basic_output

        return basic_output + ';'


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
