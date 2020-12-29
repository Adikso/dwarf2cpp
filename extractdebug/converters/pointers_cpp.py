from extractdebug.converters import OriginalCPPConverter
from extractdebug.converters.original_cpp import CPPClass, CPPMethod, CPPNamespace, CPPField
from extractdebug.extractors.extractor import Type, TypeModifier


class PointersCPPConverter(OriginalCPPConverter):
    def __init__(self, result):
        super().__init__(result, on_entry_render=self.on_entry_render)

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
        for sub_entry in entry.children.children:
            if not isinstance(sub_entry, CPPMethod) or sub_entry.name.startswith('~'):
                continue

            address = hex(sub_entry.low_pc) if sub_entry.low_pc else "nullptr"
            fields.append(CPPField(
                name=sub_entry.name,
                type=Type(name=b'unsigned long long'),
                const_value=address
            ))

        namespace = CPPNamespace(name=f'PTR_{entry.name}', elements=fields)
        output += f'\n\n{namespace}'

        # output += '\n\n'
        # output += f'namespace PTR_{entry.name} {{\n'
        # for sub_entry in entry.children.children:
        #     if not isinstance(sub_entry, CPPMethod):
        #         continue
        #     if sub_entry.name.startswith('~'):
        #         continue
        #
        #     address = hex(sub_entry.low_pc) if sub_entry.low_pc else "nullptr"
        #     params_string = ", ".join([str(x) for x in sub_entry.parameters])
        #     type_str = 'void'
        #     if sub_entry.type:
        #         type_str = OriginalCPPConverter.type_string(sub_entry.type)
        #
        #     output += '    '
        #     output += f'auto {sub_entry.name} = ({type_str.rstrip()} (*)({params_string})) {address};\n'
        # output += '}'

        return output
