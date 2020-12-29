from extractdebug.converters import OriginalCPPConverter
from extractdebug.converters.common import Entry
from extractdebug.converters.original_cpp import CPPClass, CPPMethod, CPPNamespace, CPPField
from extractdebug.extractors.extractor import Type


class PointersCPPConverter(OriginalCPPConverter):
    def __init__(self, result, config):
        super().__init__(result, config, on_entry_render=self.on_entry_render)

    @staticmethod
    def name():
        return 'pointers_cpp'

    def on_entry_render(self, entry):
        output = str(entry)
        if not isinstance(entry, CPPClass):
            return output

        has_any_method = any([isinstance(x, CPPMethod) for x in entry.children.children])
        if not has_any_method:
            return output

        fields = []
        methods = []
        for sub_entry in entry.children.children:
            if not isinstance(sub_entry, CPPMethod) or sub_entry.name.startswith('~') or not sub_entry.low_pc:
                continue

            address = hex(sub_entry.low_pc)
            fields.append(CPPField(
                name=sub_entry.name,
                type=Type(name=b'unsigned long long'),
                const_value=address
            ))

            methods.append(CPPMethodDefinition(
                method=sub_entry,
                cls=entry
            ))

        if methods:
            output += '\n\nextern unsigned long long BASE_ADDRESS;\n\n'
        for method in methods:
            output += f'{method}\n\n'

        namespace = CPPNamespace(name=f'PTR_{entry.name}', elements=fields)
        output += f'\n{namespace}'

        return output


class CPPMethodDefinition(Entry):
    def __init__(self, **kwargs):
        super().__init__()
        self.cls = kwargs.get('cls', None)
        self.method = kwargs.get('method', None)

    def fill_value(self):
        return 0

    def __repr__(self):
        params_string = ''
        if not self.method.name.startswith('~'):
            params_string = ", ".join([str(x) for x in self.method.parameters])

        output = f'{self.cls.name}::{self.method.name}({params_string}) {{\n'
        address = hex(self.method.low_pc)

        if self.method.type:
            type_str = OriginalCPPConverter.type_string(self.method.type)
        else:
            type_str = 'void'

        args_string = ', '.join([x.name for x in self.method.parameters])
        if not self.method.static:
            if args_string:
                args_string = f'this, {args_string}'
            else:
                args_string = f'this'
            if params_string:
                params_string = f'{self.cls.name} *, {params_string}'
            else:
                params_string = f'{self.cls.name} *'

        output += '    '
        if self.method.type and self.method.type.name != b'void':
            output += 'return '

        output += f'(({type_str.rstrip()} (*)({params_string})) (BASE_ADDRESS + {address}))({args_string});\n'
        output += '}'

        if self.method.type:
            type_str = OriginalCPPConverter.type_string(self.method.type)
            output = f'{type_str}{output}'

        return f'inline {output}'