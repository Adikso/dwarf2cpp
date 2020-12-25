from collections import defaultdict

from extractdebug.converters.common import get_project_files
from extractdebug.converters.converter import Converter, ConverterResultFile
from extractdebug.extractors.extractor import Field, Accessibility, Method, TypeModifier, Union, Namespace, Struct, Class, TypeDef, Type


class OriginalCPPConverter(Converter):
    def name(self):
        return 'cpp'

    def convert(self, result):
        base_path, project_files = get_project_files(result.files)
        contents = self.__convert_elements(
            result.elements,
            decl_files=[file.id for file in project_files.values()]
        )

        converted_files = []
        for file_id, entries in contents.items():
            project_file = project_files[file_id]
            converted_files.append(ConverterResultFile(
                name=project_file.name,
                directory=project_file.directory,
                entries=entries,
                relative_path=project_file.directory[len(base_path):] + b'/' + project_file.name
            ))

        return converted_files

    def __convert_elements(self, elements, decl_files=None):
        entries = defaultdict(list)

        for element in elements:
            if decl_files and element.decl_file not in decl_files:
                continue

            if isinstance(element, Namespace):
                elements = list(self.__convert_elements(element.elements).values())
                entries[element.decl_file].append(
                    CPPNamespace(
                        name=element.name,
                        elements=elements[0] if elements else []
                    )
                )

            if isinstance(element, Struct):
                entries[element.decl_file].append(
                    CPPStruct(
                        name=element.name,
                        children=self.__convert_members(element.members)
                    )
                )

            if isinstance(element, Union):
                entries[element.decl_file].append(
                    CPPUnion(
                        name=element.name,
                        children=self.__convert_members(element.fields),
                        accessibility=Accessibility.private
                    )
                )

            if isinstance(element, Class):
                entries[element.decl_file].append(
                    self.__convert_class(element)
                )

            if isinstance(element, TypeDef):
                entries[element.decl_file].append(
                    CPPTypeDef(
                        name=element.name,
                        type=element.type
                    )
                )

        return entries

    def __convert_class(self, cls):
        members = self.__convert_members(cls.members)
        inheritance = None
        if cls.inheritance_class:
            inheritance = CPPInheritance(
                cls=cls.inheritance_class,
                accessibility=Accessibility(cls.inheritance_accessibility)
            )

        return CPPClass(
            name=cls.name,
            children=members,
            inheritance=inheritance
        )

    def __convert_members(self, members):
        converted_members = []
        for member in members:
            if isinstance(member, Field):
                converted_members.append(CPPField(
                    accessibility=Accessibility(member.accessibility),
                    type=member.type,
                    name=member.name,
                    static=member.static,
                    const_value=member.const_value)
                )
            elif isinstance(member, Union):
                converted_members.append(
                    CPPUnion(
                        children=self.__convert_members(member.fields),
                        accessibility=Accessibility(member.accessibility)
                    )
                )
            elif isinstance(member, Method):
                parameters = [
                    CPPParameter(name=param.name, type=param.type)
                    for param in member.parameters if param.name != b'this'
                ]
                converted_members.append(CPPMethod(
                    accessibility=Accessibility(member.accessibility),
                    type=member.type,
                    name=member.name,
                    static=member.static,
                    parameters=parameters)
                )
        return converted_members

    @staticmethod
    def type_modifiers_string(modifiers):
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

    @staticmethod
    def type_string(type):
        modifier_str = OriginalCPPConverter.type_modifiers_string(type.modifiers)
        name_parts = [x.decode('utf-8') for x in type.namespaces] + [f'{type.name.decode("utf-8")}{modifier_str}']
        return '::'.join(name_parts)


class CPPParameter:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', b'').decode("utf-8")
        self.type = kwargs.get('type', None)

    def __repr__(self):
        type_str = OriginalCPPConverter.type_string(self.type)
        return f'{type_str}{self.name}'


class CPPMethod:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', b'').decode("utf-8")
        self.type = kwargs.get('type', None)
        self.static = kwargs.get('static', None)
        self.parameters = kwargs.get('parameters', None)
        self.accessibility = kwargs.get('accessibility', None)

    def __repr__(self):
        if self.name.startswith('~'):
            params_string = ''
        else:
            params_string = ", ".join([str(x) for x in self.parameters])
        output = f'{self.name}({params_string});'

        if self.type:
            type_str = OriginalCPPConverter.type_string(self.type)
            output = f'{type_str}{output}'

        if self.static:
            output = f'static {output}'

        return output


class CPPField:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', b'').decode("utf-8")
        self.type = kwargs.get('type', None)
        self.accessibility = kwargs.get('accessibility', None)
        self.static = kwargs.get('static', None)
        self.const_value = kwargs.get('const_value', None)

    def __repr__(self):
        type_str = OriginalCPPConverter.type_string(self.type)
        output = f'{type_str}{self.name}'

        if self.const_value:
            output += f' = {self.const_value}'

        if self.static:
            output = f'static {output}'

        return output + ';'


class CPPBlock:
    def __init__(self, **kwargs):
        self.children = kwargs.get('children', None)
        self.accessibility = kwargs.get('accessibility', True)

    def __repr__(self):
        lines = []
        last_accessibility = None

        for member in self.children:
            if self.accessibility:
                start_with_private = not last_accessibility and member.accessibility == Accessibility.private

                if member.accessibility != last_accessibility and not start_with_private:
                    lines.append(f'{member.accessibility.name}:')
                    last_accessibility = member.accessibility

            for line in str(member).split('\n'):
                lines.append(' ' * 4 + line)

        return '{\n' + '\n'.join(lines) + '\n' + '};'


class CPPUnion(CPPBlock):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get('name', b'').decode("utf-8")

    def __repr__(self):
        output = 'union '

        if self.name:
            output += self.name + ' '

        return output + super().__repr__()


class CPPInheritance:
    def __init__(self, **kwargs):
        self.cls = kwargs.get('cls', None)
        self.accessibility = kwargs.get('accessibility', None)

    def __repr__(self):
        output = self.cls.name.decode("utf-8")

        if self.accessibility != Accessibility.private:
            output = f'{self.accessibility.name} {output}'

        return output


class CPPClass:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', b'').decode("utf-8")
        self.inheritance = kwargs.get('inheritance', None)
        self.children = CPPBlock(children=kwargs.get('children', None))

    def __repr__(self):
        output = f"class {self.name}"

        if self.inheritance:
            output += f' : {self.inheritance}'

        return output + f' {self.children}'


class CPPStruct:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', b'').decode("utf-8")
        self.children = CPPBlock(children=kwargs.get('children', None))

    def __repr__(self):
        output = f"struct {self.name}"
        return f'{output} {self.children}'


class CPPNamespace:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', b'').decode("utf-8")
        self.elements = CPPBlock(
            children=kwargs.get('elements', None),
            accessibility=False
        )

    def __repr__(self):
        output = f'namespace {self.name} '
        output += str(self.elements)

        return output


class CPPTypeDef:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', b'').decode("utf-8")
        self.type = kwargs.get('type', None)

    def __repr__(self):
        if not self.type:
            self.type = Type(name=b'<<unknown>>')

        type_str = OriginalCPPConverter.type_string(self.type)
        return f'typedef {type_str}{self.name};'
