from extractdebug.converters import OriginalCPPConverter
from extractdebug.converters.original_cpp import CPPClass, CPPMethod


class PointersCPPConverter(OriginalCPPConverter):
    def __init__(self):
        super().__init__(self.on_entry_render)

    def name(self):
        return 'pointers_cpp'

    def on_entry_render(self, entry):
        output = str(entry)
        if not isinstance(entry, CPPClass):
            return output

        has_any_method = any([isinstance(x, CPPMethod) for x in entry.children.children])
        if not has_any_method:
            return output

        output += '\n\n'
        output += f'namespace PTR {{\n'
        output += f'    namespace {entry.name} {{\n'
        for sub_entry in entry.children.children:
            if not isinstance(sub_entry, CPPMethod):
                continue
            if sub_entry.name.startswith('~'):
                continue

            address = hex(sub_entry.low_pc) if sub_entry.low_pc else "nullptr"
            params_string = ", ".join([str(x) for x in sub_entry.parameters])
            type_str = 'void'
            if sub_entry.type:
                type_str = OriginalCPPConverter.type_string(sub_entry.type)

            output += '        '
            output += f'auto {sub_entry.name} = ({type_str.rstrip()} (*)({params_string})) {address};\n'
        output += '    }\n'
        output += '}\n'

        return output
