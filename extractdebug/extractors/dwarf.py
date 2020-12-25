from elftools.common.exceptions import ELFError
from elftools.common.utils import struct_parse
from elftools.dwarf import structs
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


class DwarfExtractor(Extractor):
    def __init__(self):
        self._types = {}
        self._subprograms = {}

    def test(self, file):
        """Checks if file contains DWARF debugging data"""
        try:
            elf_file = ELFFile(file)
            return elf_file.has_dwarf_info() and elf_file.get_dwarf_info().has_debug_info
        except ELFError:
            return False

    def extract(self, file):
        elf_file = ELFFile(file)
        dwarf_info = elf_file.get_dwarf_info()

        elements = []
        files = {}
        for cu in dwarf_info.iter_CUs():
            files |= self.parse_files_info(dwarf_info, cu.structs)
            elements += self._parse_compilation_unit(cu)

        return ExtractorResult(file, files, elements)

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
            name=die.attributes[Attribute.NAME].value,
            elements=elements,
            decl_file=die.attributes[Attribute.DECL_FILE].value
        )

        return namespace

    def _parse_typedef(self, die):
        return TypeDef(
            name=die.attributes[Attribute.NAME].value,
            type=self._resolve_type(die),
            decl_file=die.attributes[Attribute.DECL_FILE].value
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
            decl_file=die.attributes[Attribute.DECL_FILE].value if Attribute.DECL_FILE in die.attributes else None
        )

    def _parse_struct_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []

        for child in die.iter_children():
            members.append(self._parse_member(child))

        return Struct(
            name=class_name,
            members=members,
            decl_file=die.attributes[Attribute.DECL_FILE].value if Attribute.DECL_FILE in die.attributes else None
        )

    def _parse_union_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []

        for child in die.iter_children():
            members.append(self._parse_member(child))

        return Union(
            name=class_name,
            fields=members,
            accessibility=self._get_accessibility(die),
            decl_file=die.attributes[Attribute.DECL_FILE].value if Attribute.DECL_FILE in die.attributes else None
        )

    def _parse_member(self, child):
        attrs = child.attributes
        accessibility = self._get_accessibility(child)
        class_type = self._resolve_type(child)

        # Tag specific attributes
        if child.tag == Tag.SUB_PROGRAM:
            self._subprograms[child.offset] = Method(
                name=attrs[Attribute.NAME].value,
                type=class_type,
                accessibility=accessibility,
                static=Attribute.OBJECT_POINTER not in attrs
            )
            return self._subprograms[child.offset]
        elif child.tag == Tag.MEMBER:
            if class_type:
                return Field(
                    name=attrs[Attribute.NAME].value,
                    type=class_type,
                    accessibility=accessibility,
                    static=Attribute.EXTERNAL in attrs,
                    const_value=attrs[Attribute.CONST_VALUE].value if Attribute.CONST_VALUE in attrs else None
                )

            type_die = child.cu.get_DIE_from_refaddr(child.attributes[Attribute.TYPE].value)
            if type_die.tag == Tag.UNION_TYPE:
                return self._parse_union(child)

        return None

    def _parse_union(self, die):
        type_die = die.cu.get_DIE_from_refaddr(die.attributes[Attribute.TYPE].value)
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
            self._parse_member(die.cu.get_DIE_from_refaddr(specification))

        existing_method = self._subprograms[die.attributes[Attribute.SPECIFICATION].value]
        for child in die.iter_children():
            if child.tag == Tag.PARAMETER:
                param_type = self._resolve_type(child)
                if Attribute.NAME in child.attributes:  # Make sure
                    existing_method.parameters.append(Parameter(
                        name=child.attributes[Attribute.NAME].value,
                        type=param_type
                    ))

    def parse_files_info(self, dwarf_info, structs):
        files = {}

        lineprog_header = struct_parse(structs.Dwarf_lineprog_header, dwarf_info.debug_line_sec.stream, 0)
        for i, entry in enumerate(lineprog_header.file_entry):
            files[i + 1] = File(id=i + 1, name=entry.name, directory=lineprog_header.include_directory[entry.dir_index - 1])

        return files

    @staticmethod
    def _resolve_type(die):
        type = Type()

        if Attribute.TYPE not in die.attributes:
            return None

        entry = die.cu.get_DIE_from_refaddr(die.attributes[Attribute.TYPE].value)
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

            entry = die.cu.get_DIE_from_refaddr(entry.attributes[Attribute.TYPE].value)

        type.name = entry.attributes[Attribute.NAME].value

        entry = entry._parent
        while entry and entry.tag == Tag.NAMESPACE:
            type.namespaces.appendleft(entry.attributes[Attribute.NAME].value)
            entry = entry._parent

        return type

    @staticmethod
    def _get_accessibility(die):
        if Attribute.ACCESSIBILITY in die.attributes:
            return die.attributes[Attribute.ACCESSIBILITY].value

        return Accessibility.private.value
