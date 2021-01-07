import os
from collections import defaultdict
import numpy as np

from extractdebug.converters.common import relative_path, test_utf8, get_utf8, EntriesStorage, Entry
from extractdebug.converters.converter import Converter
from extractdebug.extractors.extractor import Field, Accessibility, Method, TypeModifier, Union, Namespace, Struct, Class, TypeDef, Type, EnumerationType


class OriginalCPPConverter(Converter):
    def __init__(self, result, config, on_entry_render=None):
        super().__init__(result, config)
        self.includes = defaultdict(set)
        self.used_types = defaultdict(set)
        self.on_entry_render = on_entry_render

    @staticmethod
    def name():
        return 'cpp'

    def convert(self):
        contents = self.__convert_elements(self.result.elements)

        output = ''
        for file_path, entries in contents.items():
            file_relative_path = relative_path(self.result.base_dir, file_path).decode('utf-8')

            simple_name = os.path.splitext(os.path.basename(file_relative_path))[0].upper()
            file_output = f'// Source file: {file_relative_path}\n'
            file_output += f'#ifndef {simple_name}_H\n#define {simple_name}_H\n\n'

            if self.config['includes']:
                for included_file_path in self.includes[file_path]:
                    if included_file_path.startswith(self.result.base_dir):
                        included_relative_path = relative_path(file_path, included_file_path)
                        include_name = included_relative_path.decode('utf-8')
                        file_output += f'#include "{include_name}"\n'
                    else:
                        include_name = included_file_path.decode('utf-8')
                        file_output += f'#include <{include_name}>\n'

                if self.includes[file_path]:
                    file_output += '\n'

            for entry in entries:
                if self.on_entry_render:
                    file_output += f'{self.on_entry_render(entry)}\n\n'
                else:
                    file_output += f'{entry}\n\n'

            file_output += '#endif\n\n'

            output_dir = os.path.join('output', os.path.dirname(file_relative_path))
            os.makedirs(output_dir, exist_ok=True)
            output_file_path = os.path.join('output', file_relative_path)
            with open(output_file_path, 'w') as file:
                file.write(file_output)

            output += file_output

        return output

    def __convert_elements(self, elements):
        entries = defaultdict(EntriesStorage)

        for element in elements:
            if not element.decl_file:
                continue

            # Check if file is in project
            cu, file = element.decl_file
            decl_files = self.result.files[cu]
            if decl_files and file.id not in decl_files:
                continue

            decl_file = decl_files[file.id].full_path()
            if b'<built-in>' in decl_file or not decl_file.startswith(self.result.base_dir):
                continue

            if isinstance(element, Namespace):
                elements = list(self.__convert_elements(element.elements).values())
                entries[decl_file].send(
                    CPPNamespace(
                        name=element.name,
                        elements=elements[0] if elements else []
                    )
                )

            elif isinstance(element, Struct):
                entries[decl_file].send(
                    CPPStruct(
                        name=element.name,
                        children=self.__convert_members(element, element.members)
                    )
                )

            elif isinstance(element, Union):
                entries[decl_file].send(
                    CPPUnion(
                        name=element.name,
                        children=self.__convert_members(element, element.fields),
                        accessibility=Accessibility.private
                    )
                )

            elif isinstance(element, Class):
                entries[decl_file].send(
                    self.__convert_class(element)
                )

            elif isinstance(element, TypeDef):
                entries[decl_file].send(
                    CPPTypeDef(
                        name=element.name,
                        type=element.type
                    )
                )
            elif isinstance(element, EnumerationType):
                entries[decl_file].send(
                    CPPEnumerationType(
                        name=element.name,
                        enumerators=element.enumerators,
                        type=element.type,
                        accessibility=Accessibility(element.accessibility)
                    )
                )

        return entries

    def __convert_class(self, cls):
        members = self.__convert_members(cls, cls.members)
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

    def __convert_members(self, parent, members):
        converted_members = []
        for i, member in enumerate(members):
            if isinstance(member, Field):
                if member.type.name == b'__vtbl_ptr_type':
                    continue

                converted_members.append(CPPField(
                    accessibility=Accessibility(member.accessibility) if member.accessibility < 3 else Accessibility.public,
                    type=member.type,
                    name=member.name,
                    static=member.static,
                    const_value=member.const_value
                ))

                if member.type and member.type.decl_file and member.type.decl_file[1] != member.decl_file[1]:
                    self.includes[member.decl_file[1].full_path()].add(member.type.decl_file[1].full_path())
            elif isinstance(member, Union):
                converted_members.append(
                    CPPUnion(
                        children=self.__convert_members(member, member.fields),
                        accessibility=Accessibility(member.accessibility)
                    )
                )
            elif isinstance(member, EnumerationType):
                converted_members.append(
                    CPPEnumerationType(
                        name=member.name,
                        enumerators=member.enumerators,
                        type=member.type,
                        accessibility=Accessibility(member.accessibility)
                    )
                )
            elif isinstance(member, Method):
                if not member.fully_defined:
                    continue

                member_params = member.parameters if member.parameters else member.direct_parameters
                parameters = []
                for i, param in enumerate(member_params):
                    if not member.static and i == 0:
                        continue

                    param_name = param.name
                    if not param_name:
                        param_name = f'arg{len(parameters)}'.encode('utf-8')

                    parameters.append(CPPParameter(name=param_name, type=param.type, offset=param.offset))

                    if member.decl_file and param.type and param.type.decl_file and param.type.decl_file[1] != member.decl_file[1]:
                        self.includes[member.decl_file[1].full_path()].add(param.type.decl_file[1].full_path())

                # Handle detecting void type
                return_type = member.type
                if not return_type and member.name != parent.name and member.name != b'~' + parent.name:
                    return_type = Type(name=b'void')

                converted_members.append(CPPMethod(
                    accessibility=Accessibility(member.accessibility) if member.accessibility < 3 else Accessibility.public,
                    type=return_type,
                    name=member.name,
                    static=member.static,
                    virtual=member.virtual,
                    low_pc=member.low_pc,
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
        name_parts = [x.decode('utf-8') for x in type.namespaces]

        if type.name and test_utf8(type.name):
            name_parts.append(f'{type.name.decode("utf-8")}{modifier_str}')

        return '::'.join(name_parts)


class CPPParameter:
    def __init__(self, **kwargs):
        self.name = get_utf8(kwargs, 'name', b'<<unknown param name>>')
        self.type = kwargs.get('type', Type(name='<<unknown>>'))
        self.offset = kwargs.get('offset', 0)

    def __repr__(self):
        type_str = f'void * /*<<ERROR_UNKNOWN - {hex(self.offset if self.offset else 0)}>>*/ '
        if self.type:
            type_str = OriginalCPPConverter.type_string(self.type)

        return f'{type_str}{self.name}'


class CPPMethod:
    def __init__(self, **kwargs):
        self.name = get_utf8(kwargs, 'name', b'<<unknown method name>>')
        self.type = kwargs.get('type', Type(name='<<unknown>>'))
        self.static = kwargs.get('static', False)
        self.virtual = kwargs.get('virtual', False)
        self.parameters = kwargs.get('parameters', None)
        self.accessibility = kwargs.get('accessibility', None)
        self.low_pc = kwargs.get('low_pc', None)

    def __repr__(self):
        params_string = ''
        if not self.name.startswith('~'):
            params_string = ", ".join([str(x) for x in self.parameters])

        output = f'{self.name}({params_string});'

        if self.type:
            type_str = OriginalCPPConverter.type_string(self.type)
            output = f'{type_str}{output}'

        if self.static:
            output = f'static {output}'

        if self.virtual:
            output = f'virtual {output}'

        return output


class CPPField:
    def __init__(self, **kwargs):
        self.name = get_utf8(kwargs, 'name', b'<<unknown field name>>')
        self.type = kwargs.get('type', Type(name='<<unknown>>'))
        self.accessibility = kwargs.get('accessibility', None)
        self.static = kwargs.get('static', None)
        self.const_value = kwargs.get('const_value', None)

    def __repr__(self):
        type_str = OriginalCPPConverter.type_string(self.type)
        output = f'{type_str}{self.name}'

        if self.const_value:
            const_value_str = str(self.const_value).replace("\n", "")
            if isinstance(self.const_value, list):
                if self.type.name == b'float':
                    data_bytes = np.array(self.const_value, dtype=np.uint8)
                    data_as_float = str(data_bytes.view(dtype=np.float32))
                    output += f' = {data_as_float[1:-1]}f'
                elif self.type.array:
                    output += f'[{self.type.array_size}]'

                    if self.const_value and self.type.base and b'int' in self.type.name:
                        values = []
                        for bytes_group in self.const_value:
                            values.append(int.from_bytes(bytes(bytes_group), byteorder='little'))
                        output += f' = {{ {", ".join(map(str, values))} }}'

                else:
                    output += f' /* = {const_value_str} */'
            else:
                output += f' = {const_value_str}'
        elif self.type.array:
            output += f'[{self.type.array_size}]'

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


class CPPUnion(CPPBlock, Entry):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = get_utf8(kwargs, 'name', b'<<unknown union name>>')

    def fill_value(self):
        return len(self.children)

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
        output = '<<invalid>>'
        if self.cls and test_utf8(self.cls.name):
            output = OriginalCPPConverter.type_string(self.cls)[:-1]

        if self.accessibility != Accessibility.private:
            output = f'{self.accessibility.name} {output}'

        return output


class CPPClass(Entry):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = get_utf8(kwargs, 'name', b'<<unknown cls name>>')
        self.inheritance = kwargs.get('inheritance', None)
        self.children = CPPBlock(children=kwargs.get('children', None))

    def fill_value(self):
        return len(self.children.children)

    def __repr__(self):
        output = f"class {self.name}"

        if self.inheritance:
            output += f' : {self.inheritance}'

        return output + f' {self.children}'


class CPPStruct(Entry):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = get_utf8(kwargs, 'name', b'<<unknown struct name>>')
        self.children = CPPBlock(children=kwargs.get('children', None))

    def fill_value(self):
        return len(self.children.children)

    def __repr__(self):
        output = f"struct {self.name}"
        return f'{output} {self.children}'


class CPPNamespace(Entry):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = get_utf8(kwargs, 'name', b'<<unknown namespace name>>')
        self.elements = CPPBlock(
            children=kwargs.get('elements', None),
            accessibility=False
        )

    def fill_value(self):
        return len(self.elements.children)

    def __repr__(self):
        output = f'namespace {self.name} '
        output += str(self.elements)

        return output


class CPPTypeDef(Entry):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = get_utf8(kwargs, 'name', b'<<unknown type name>>')
        self.type = kwargs.get('type', Type(name=b'<<unknown>>'))

    def fill_value(self):
        return 1 if self.type.name else 0

    def __repr__(self):
        type_str = OriginalCPPConverter.type_string(self.type)
        return f'typedef {type_str}{self.name};'


class CPPEnumerator(Entry):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = get_utf8(kwargs, 'name', b'<<unknown type name>>')
        self.value = kwargs.get('value', None)
        self.accessibility = None

    def fill_value(self):
        return 0

    def __repr__(self):
        return f'{self.name} = {self.value},'


class CPPEnumerationType(Entry):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = get_utf8(kwargs, 'name', b'<<unknown type name>>')
        self.type = kwargs.get('type', Type(name=b'<<unknown>>'))
        self.enumerators = [CPPEnumerator(
            name=x.name,
            value=x.value
        ) for x in kwargs.get('enumerators', [])]

        self.accessibility = kwargs.get('accessibility', None)
        self.children = CPPBlock(
            children=self.enumerators,
            accessibility=self.accessibility
        )

    def fill_value(self):
        return len(self.enumerators)

    def __repr__(self):
        return f'enum {self.name} {self.children}'
