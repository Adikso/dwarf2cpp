from extractdebug.converters.converter import Converter
from extractdebug.extractors.extractor import Field, Accessibility, Method, TypeModifier, Union


class OriginalCPPConverter(Converter):
    def name(self):
        return 'cpp'

    def convert(self, result):
        classes = []
        for cls in result.classes:
            members = []
            for member in cls.members:
                if isinstance(member, Field):
                    members.append(CPPField(
                        accessibility=Accessibility(member.accessibility),
                        type=member.type,
                        name=member.name,
                        static=member.static,
                        const_value=member.const_value)
                    )
                elif isinstance(member, Union):
                    def parse_union_field(depth, m):
                        fields = []
                        for x in m.fields:
                            if isinstance(x, Union):
                                nested_union = parse_union_field(depth + 1, x)
                                fields.append(CPPUnion(depth + 1, nested_union, Accessibility(m.accessibility)))
                            else:
                                fields.append(CPPField(
                                    accessibility=Accessibility(m.accessibility),
                                    type=x.type,
                                    name=x.name,
                                    static=x.static,
                                    const_value=x.const_value
                                ))
                        return fields

                    members.append(CPPUnion(2, parse_union_field(2, member), Accessibility(member.accessibility)))
                elif isinstance(member, Method):
                    parameters = [CPPParameter(x.name, x.type) for x in member.parameters if x.name != b'this']
                    members.append(CPPMethod(
                        accessibility=Accessibility(member.accessibility),
                        type=member.type,
                        name=member.name,
                        static=member.static,
                        parameters=parameters)
                    )

            inheritance = None
            if cls.inheritance_class:
                inheritance = CPPInheritance(
                    cls=cls.inheritance_class,
                    accessibility=Accessibility(cls.inheritance_accessibility)
                )

            classes.append(CPPClass(cls.name, members, inheritance))

        return classes

    @staticmethod
    def generate_type_modifiers_str(modifiers):
        def append_token(text, token):
            if i > 0:
                text += ' '
            text += token
            if i != len(modifiers) - 1:
                text += ' '

            return text

        result = ''
        for i, modifier in enumerate(modifiers):
            if modifier == TypeModifier.pointer:
                result += '*'
            elif modifier == TypeModifier.constant:
                result = append_token(result, 'const')
            elif modifier == TypeModifier.volatile:
                result = append_token(result, 'volatile')
            elif modifier == TypeModifier.reference:
                result += '&'

        if modifiers:
            result = ' ' + result
        return result + ' '


class CPPParameter:
    def __init__(self, name, type):
        self.name = name.decode("utf-8")
        self.type = type

    def __repr__(self):
        modifier_str = OriginalCPPConverter.generate_type_modifiers_str(self.type.modifiers)
        return f'{self.type.name.decode("utf-8")}{modifier_str}{self.name}'


class CPPMethod:
    def __init__(self, accessibility, type, name, static, parameters):
        self.name = name.decode("utf-8")
        self.type = type
        self.static = static
        self.parameters = parameters
        self.accessibility = accessibility

    def __repr__(self):
        params_string = ", ".join([str(x) for x in self.parameters])
        output = f'{self.name}({params_string});'

        if self.type:
            modifier_str = OriginalCPPConverter.generate_type_modifiers_str(self.type.modifiers)
            output = f'{self.type.name.decode("utf-8")}{modifier_str}' + output

        if self.static:
            output = 'static ' + output

        return output


class CPPField:
    def __init__(self, accessibility, type, name, static, const_value):
        self.name = name.decode("utf-8")
        self.type = type
        self.accessibility = accessibility
        self.static = static
        self.const_value = const_value

    def __repr__(self):
        modifier_str = OriginalCPPConverter.generate_type_modifiers_str(self.type.modifiers)
        output = f'{self.type.name.decode("utf-8")}{modifier_str}{self.name}'

        if self.const_value:
            output += f' = {self.const_value}'

        if self.static:
            output = 'static ' + output

        return output + ';'


class CPPBlock:
    def __init__(self, level, children):
        self.level = level
        self.children = children

    def _show_accessibility(self):
        return True

    def __repr__(self):
        lines = []
        last_accessibility = None

        for member in self.children:
            if self._show_accessibility() and member.accessibility != last_accessibility:
                lines.append(' ' * ((self.level - 1) * 4) + f'{member.accessibility.name}:')
                last_accessibility = member.accessibility

            lines.append(' ' * (self.level * 4) + str(member))

        return '{\n' + '\n'.join(lines) + '\n' + ' ' * ((self.level - 1) * 4) + '}'


class CPPUnion(CPPBlock):
    def __init__(self, level, children, accessibility):
        super().__init__(level, children)
        self.accessibility = accessibility

    def _show_accessibility(self):
        return False

    def __repr__(self):
        return 'union ' + super().__repr__()


class CPPInheritance:
    def __init__(self, cls, accessibility):
        self.cls = cls
        self.accessibility = accessibility

    def __repr__(self):
        return f'{self.accessibility.name} {self.cls.name.decode("utf-8")}'


class CPPClass:
    def __init__(self, name, children, inheritance):
        self.name = name.decode("utf-8")
        self.inheritance = inheritance
        self.children = CPPBlock(1, children)

    def __repr__(self):
        output = f"class {self.name}"

        if self.inheritance:
            output += f' : {self.inheritance}'

        return output + f' {self.children}'
