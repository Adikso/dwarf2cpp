from elftools.common.exceptions import ELFError
from elftools.common.utils import struct_parse
from elftools.elf.elffile import ELFFile

from extractdebug.extractors.extractor import Extractor, Field, Class, ExtractorResult, Accessibility, Method, Parameter, Type, TypeModifier, Union, Struct, Namespace, TypeDef, \
    File


class Tag:
    CLASS_TYPE = 'DW_TAG_class_type'
    BASE_TYPE = 'DW_TAG_base_type'
    CONST_TYPE = 'DW_TAG_const_type'
    POINTER_TYPE = 'DW_TAG_pointer_type'
    VOLATILE_TYPE = 'DW_TAG_volatile_type'
    REFERENCE_TYPE = 'DW_TAG_reference_type'
    MEMBER = 'DW_TAG_member'
    SUB_PROGRAM = 'DW_TAG_subprogram'
    PARAMETER = 'DW_TAG_formal_parameter'
    INHERITANCE = 'DW_TAG_inheritance'
    UNION_TYPE = 'DW_TAG_union_type'
    STRUCTURE_TYPE = 'DW_TAG_structure_type'
    NAMESPACE = 'DW_TAG_namespace'
    TYPEDEF = 'DW_TAG_typedef'


class Attribute:
    NAME = 'DW_AT_name'
    TYPE = 'DW_AT_type'
    ACCESSIBILITY = 'DW_AT_accessibility'
    SPECIFICATION = 'DW_AT_specification'
    OBJECT_POINTER = 'DW_AT_object_pointer'
    DATA_MEMBER_LOCATION = 'DW_AT_data_member_location'
    CONST_VALUE = 'DW_AT_const_value'
    EXTERNAL = 'DW_AT_external'
    DECL_FILE = 'DW_AT_decl_file'
    LINKAGE_NAME = 'DW_AT_linkage_name'
    LOW_PC = 'DW_AT_low_pc'
    COMP_DIR = 'DW_AT_comp_dir'


class DwarfExtractor(Extractor):
    def __init__(self):
        self._types = {}
        self._subprograms = {}
        self.dwarf_info = None
        self.cu_files = {}

    def test(self, file):
        """Checks if file contains DWARF debugging data"""
        try:
            elf_file = ELFFile(file)
            return elf_file.has_dwarf_info() and elf_file.get_dwarf_info().has_debug_info
        except ELFError:
            return False

    def extract(self, file):
        self.elf_file = ELFFile(file)
        self.dwarf_info = self.elf_file.get_dwarf_info()

        elements = []
        cus = []
        for cu in self.dwarf_info.iter_CUs():
            top_die = cu.get_top_DIE()
            if 'DW_AT_stmt_list' in top_die.attributes:
                self.cu_files[cu.cu_offset] = self.parse_files_info(self.dwarf_info, cu.structs, top_die.attributes['DW_AT_stmt_list'].value)

            elements += self._parse_compilation_unit(cu)
            cus.append(cu)

        base_dir = cus[0].get_top_DIE().attributes[Attribute.COMP_DIR].value
        return ExtractorResult(file, self.cu_files, elements, base_dir)

    def _parse_children(self, die):
        elements = []

        for child in die.iter_children():
            if child.tag == Tag.CLASS_TYPE:
                elements.append(self._parse_class_type(child))
            elif child.tag == Tag.UNION_TYPE:
                elements.append(self._parse_union_type(child))
            elif child.tag == Tag.STRUCTURE_TYPE:
                if Attribute.NAME not in child.attributes:
                    continue

                elements.append(self._parse_struct_type(child))
            elif child.tag == Tag.SUB_PROGRAM:
                self._parse_sub_program(child)
            elif child.tag == Tag.NAMESPACE:
                elements.append(self._parse_namespace(child))
            elif child.tag == Tag.TYPEDEF:
                elements.append(self._parse_typedef(child))

        return elements

    def _parse_compilation_unit(self, unit):
        top_die = unit.get_top_DIE()
        return self._parse_children(top_die)

    def _parse_namespace(self, die):
        elements = self._parse_children(die)
        namespace = Namespace(
            name=die.attributes[Attribute.NAME].value if Attribute.NAME in die.attributes else None,
            elements=elements,
            decl_file=self.get_file(die)
        )

        return namespace

    def _parse_typedef(self, die):
        return TypeDef(
            name=die.attributes[Attribute.NAME].value,
            type=self._resolve_type(die),
            decl_file=self.get_file(die)
        )

    def _parse_class_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []
        inheritance_class = None
        inheritance_accessibility = None

        for child in die.iter_children():
            if child.tag == Tag.INHERITANCE:
                inheritance_accessibility = self._get_accessibility(child)
                inheritance_class = self._resolve_type(child)
                continue

            members.append(self._parse_member(child))

        return Class(
            name=class_name,
            members=members,
            inheritance_class=inheritance_class,
            inheritance_accessibility=inheritance_accessibility,
            decl_file=self.get_file(die)
        )

    def _parse_struct_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []

        for child in die.iter_children():
            members.append(self._parse_member(child))

        return Struct(
            name=class_name,
            members=members,
            decl_file=self.get_file(die)
        )

    def _parse_union_type(self, die):
        members = []

        for child in die.iter_children():
            members.append(self._parse_member(child))

        return Union(
            name=die.attributes[Attribute.NAME].value if Attribute.NAME in die.attributes else None,
            fields=members,
            accessibility=self._get_accessibility(die),
            decl_file=self.get_file(die)
        )

    def _parse_member(self, child):
        attrs = child.attributes
        accessibility = self._get_accessibility(child)
        class_type = self._resolve_type(child)

        # Tag specific attributes
        if child.tag == Tag.SUB_PROGRAM:
            method = Method(
                name=attrs[Attribute.NAME].value,
                type=class_type,
                accessibility=accessibility,
                static=Attribute.OBJECT_POINTER not in attrs,
                offset=child.offset,
                decl_file=self.get_file(child)
            )

            for sub_child in child.iter_children():
                if sub_child.tag == Tag.PARAMETER:
                    param_type = self._resolve_type(sub_child)
                    method.direct_parameters.append(Parameter(  # TODO
                        name=sub_child.attributes[Attribute.NAME].value if Attribute.NAME in sub_child.attributes else None,
                        type=param_type,
                        offset=sub_child.offset
                    ))

            self._subprograms[child.offset] = method
            return self._subprograms[child.offset]
        elif child.tag == Tag.MEMBER:
            if class_type:
                return Field(
                    name=attrs[Attribute.NAME].value if Attribute.NAME in attrs else b'ERROR_UNKNOWN',
                    decl_file=self.get_file(child),
                    type=class_type,
                    accessibility=accessibility,
                    static=Attribute.EXTERNAL in attrs,
                    const_value=attrs[Attribute.CONST_VALUE].value if Attribute.CONST_VALUE in attrs else None
                )

            type_die = child.get_DIE_from_attribute(Attribute.TYPE)
            if type_die.tag == Tag.UNION_TYPE:
                return self._parse_union(child)

        return None

    def _parse_union(self, die):
        type_die = die.get_DIE_from_attribute(Attribute.TYPE)
        members = []

        for child in type_die.iter_children():
            member = self._parse_member(child)
            if not member:
                continue

            member.static = Attribute.EXTERNAL in child.attributes
            members.append(member)

        return Union(
            fields=members,
            accessibility=self._get_accessibility(die)
        )

    def _parse_sub_program(self, die):
        if Attribute.SPECIFICATION not in die.attributes:
            return

        specification = die.attributes[Attribute.SPECIFICATION].value
        if specification not in self._subprograms:
            self._parse_member(die.get_DIE_from_attribute(Attribute.SPECIFICATION))

        if specification not in self._subprograms:
            return None

        existing_method = self._subprograms[die.attributes[Attribute.SPECIFICATION].value]
        for child in die.iter_children():
            if child.tag == Tag.PARAMETER:
                param_type = self._resolve_type(child)
                # if Attribute.NAME in child.attributes:  # Make sure
                existing_method.parameters.append(Parameter(
                    name=child.attributes[Attribute.NAME].value if Attribute.NAME in child.attributes else b'arg',
                    type=param_type
                ))

        if Attribute.LOW_PC in die.attributes:
            existing_method.low_pc = die.attributes[Attribute.LOW_PC].value

    def parse_files_info(self, dwarf_info, structs, offset=0):
        files = {}

        lineprog_header = struct_parse(structs.Dwarf_lineprog_header, dwarf_info.debug_line_sec.stream, offset)
        for i, entry in enumerate(lineprog_header.file_entry):
            files[i + 1] = File(id=i + 1, name=entry.name, directory=lineprog_header.include_directory[entry.dir_index - 1])

        return files

    def _resolve_type(self, die):
        type = Type()

        if Attribute.TYPE not in die.attributes:
            return None

        try:
            entry = die.get_DIE_from_attribute(Attribute.TYPE)
            while Attribute.NAME not in entry.attributes:
                if entry.tag == Tag.POINTER_TYPE:
                    type.modifiers.insert(0, TypeModifier.pointer)

                if entry.tag == Tag.CONST_TYPE:
                    type.modifiers.insert(0, TypeModifier.constant)

                if entry.tag == Tag.VOLATILE_TYPE:
                    type.modifiers.insert(0, TypeModifier.volatile)

                if entry.tag == Tag.REFERENCE_TYPE:
                    type.modifiers.insert(0, TypeModifier.reference)

                if Attribute.TYPE not in entry.attributes:
                    if Attribute.LINKAGE_NAME in entry.attributes:
                        type.name = entry.attributes[Attribute.LINKAGE_NAME].value
                        return type
                    return None

                entry = entry.get_DIE_from_attribute(Attribute.TYPE)

            type.name = entry.attributes[Attribute.NAME].value

            if Attribute.DECL_FILE in entry.attributes:
                type.decl_file = self.get_file(entry)

            entry = entry._parent
            while entry and entry.tag == Tag.NAMESPACE:
                type.namespaces.appendleft(entry.attributes[Attribute.NAME].value)
                entry = entry._parent
        except Exception as e:
            # print(e)
            return None

        return type

    @staticmethod
    def _get_accessibility(die):
        if Attribute.ACCESSIBILITY in die.attributes:
            return die.attributes[Attribute.ACCESSIBILITY].value

        return Accessibility.private.value

    def get_file(self, die):
        if Attribute.DECL_FILE not in die.attributes:
            return None

        decl_file = die.attributes[Attribute.DECL_FILE].value
        return die.cu.cu_offset, self.cu_files[die.cu.cu_offset][decl_file]
