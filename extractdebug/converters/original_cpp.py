import os
from collections import defaultdict

from extractdebug.converters.converter import Converter, ConverterResultFile
from extractdebug.extractors.extractor import Field, Accessibility, Method, TypeModifier, Union, Namespace, Struct, Class, TypeDef, Type


class OriginalCPPConverter(Converter):
    def name(self):
        return 'cpp'

    def convert(self, result):
        base_path, project_files = self.get_project_files(result.files)
        files_contents = self._convert_elements(
            result.elements,
            decl_files=[x.id for x in project_files.values()]
        )

        converted_files = []
        for id, entries in files_contents.items():
            project_file = project_files[id]
            converted_files.append(ConverterResultFile(
                name=project_file.name,
                directory=project_file.directory,
                entries=entries,
                relative_path=project_file.directory[len(base_path):] + b'/' + project_file.name
            ))

        return converted_files

    def get_project_files(self, files):
        main_file = files[1]
        possibles = set()
        base_path = main_file.directory
        for file in files.values():
            path = os.path.commonprefix([base_path, file.directory])
            if path != b'/':
                possibles.add(path)

        base_path = min(possibles, key=len)
        project_files = {}
        for id, file in files.items():
            if file.name != b'<built-in>' and file.directory.startswith(base_path):
                project_files[id] = file

        return base_path, project_files

    def _convert_elements(self, elements, decl_files=None):
        entries = defaultdict(list)

        for element in elements:
            if decl_files and element.decl_file not in decl_files:
                continue

            if isinstance(element, Namespace):
                entries[element.decl_file].append(CPPNamespace(element.name, list(self._convert_elements(element.elements).values())[0]))

            if isinstance(element, Struct):
                entries[element.decl_file].append(CPPStruct(element.name, self._convert_members(element.members)))

            if isinstance(element, Union):
                entries[element.decl_file].append(CPPUnion(element.name, self._convert_members(element.fields), Accessibility.private))

            if isinstance(element, Class):
                entries[element.decl_file].append(self._convert_class(element))

            if isinstance(element, TypeDef):
                entries[element.decl_file].append(CPPTypeDef(element.name, element.type))

        return entries

    def _convert_class(self, cls):
        members = self._convert_members(cls.members)
        inheritance = None
        if cls.inheritance_class:
            inheritance = CPPInheritance(
                cls=cls.inheritance_class,
                accessibility=Accessibility(cls.inheritance_accessibility)
            )

        return CPPClass(cls.name, members, inheritance)

    def _convert_members(self, members):
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
                converted_members.append(CPPUnion(None, self._convert_members(member.fields), Accessibility(member.accessibility)))
            elif isinstance(member, Method):
                parameters = [CPPParameter(x.name, x.type) for x in member.parameters if x.name != b'this']
                converted_members.append(CPPMethod(
                    accessibility=Accessibility(member.accessibility),
                    type=member.type,
                    name=member.name,
                    static=member.static,
                    parameters=parameters)
                )
        return converted_members

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

    @staticmethod
    def generate_type_string(type):
        modifier_str = OriginalCPPConverter.generate_type_modifiers_str(type.modifiers)
        name_parts = [x.decode('utf-8') for x in type.namespaces] + [f'{type.name.decode("utf-8")}{modifier_str}']
        return '::'.join(name_parts)


class CPPParameter:
    def __init__(self, name, type):
        self.name = name.decode("utf-8")
        self.type = type

    def __repr__(self):
        type_str = OriginalCPPConverter.generate_type_string(self.type)
        return f'{type_str}{self.name}'


class CPPMethod:
    def __init__(self, accessibility, type, name, static, parameters):
        self.name = name.decode("utf-8")
        self.type = type
        self.static = static
        self.parameters = parameters
        self.accessibility = accessibility

    def __repr__(self):
        if self.name.startswith('~'):
            params_string = ''
        else:
            params_string = ", ".join([str(x) for x in self.parameters])
        output = f'{self.name}({params_string});'

        if self.type:
            type_str = OriginalCPPConverter.generate_type_string(self.type)
            output = f'{type_str}' + output

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
        type_str = OriginalCPPConverter.generate_type_string(self.type)
        output = f'{type_str}{self.name}'

        if self.const_value:
            output += f' = {self.const_value}'

        if self.static:
            output = 'static ' + output

        return output + ';'


class CPPBlock:
    def __init__(self, children, accessibility=True):
        self.children = children
        self.accessibility = accessibility

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
    def __init__(self, name, children, accessibility):
        super().__init__(children)
        self.name = name
        self.accessibility = accessibility

    def __repr__(self):
        output = 'union '

        if self.name:
            output += self.name.decode("utf-8") + ' '

        return output + super().__repr__()


class CPPInheritance:
    def __init__(self, cls, accessibility):
        self.cls = cls
        self.accessibility = accessibility

    def __repr__(self):
        output = self.cls.name.decode("utf-8")

        if self.accessibility != Accessibility.private:
            output = f'{self.accessibility.name} ' + output

        return output


class CPPClass:
    def __init__(self, name, children, inheritance):
        self.name = name.decode("utf-8")
        self.inheritance = inheritance
        self.children = CPPBlock(children)

    def __repr__(self):
        output = f"class {self.name}"

        if self.inheritance:
            output += f' : {self.inheritance}'

        return output + f' {self.children}'


class CPPStruct:
    def __init__(self, name, children):
        self.name = name.decode("utf-8")
        self.children = CPPBlock(children)

    def __repr__(self):
        output = f"struct {self.name}"

        return output + f' {self.children}'


class CPPNamespace:
    def __init__(self, name, sub_elements):
        self.name = name.decode("utf-8")
        self.sub_elements = CPPBlock(sub_elements, accessibility=False)

    def __repr__(self):
        output = f'namespace {self.name} '
        output += str(self.sub_elements)

        return output


class CPPTypeDef:
    def __init__(self, name, type):
        self.name = name.decode("utf-8")
        self.type = type

    def __repr__(self):
        if not self.type:
            self.type = Type(name=b'<<unknown>>')

        type_str = OriginalCPPConverter.generate_type_string(self.type)
        output = f'{type_str}{self.name}'

        return f'typedef {output};'
