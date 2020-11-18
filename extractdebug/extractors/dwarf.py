from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from extractdebug.extractors.extractor import Extractor, Field, Class, ExtractorResult, Accessibility, Method, Parameter, Type, TypeModifier, Union


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


class Attribute:
    NAME = 'DW_AT_name'
    TYPE = 'DW_AT_type'
    ACCESSIBILITY = 'DW_AT_accessibility'
    SPECIFICATION = 'DW_AT_specification'
    OBJECT_POINTER = 'DW_AT_object_pointer'
    DATA_MEMBER_LOCATION = 'DW_AT_data_member_location'
    CONST_VALUE = 'DW_AT_const_value'
    EXTERNAL = 'DW_AT_external'


class DwarfExtractor(Extractor):
    def __init__(self):
        self._classes = []
        self._unions = []
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

        for cu in dwarf_info.iter_CUs():
            self._parse_compilation_unit(cu)

        return ExtractorResult(file, self._classes, self._unions)

    def _parse_compilation_unit(self, unit):
        top_die = unit.get_top_DIE()
        for child in top_die.iter_children():
            if child.tag == Tag.CLASS_TYPE:
                self._classes.append(
                    self._parse_class_type(child)
                )
            if child.tag == Tag.UNION_TYPE:
                self._unions.append(
                    self._parse_union_type(child)
                )
            elif child.tag == Tag.SUB_PROGRAM:
                self._parse_sub_program(child)

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
            inheritance_accessibility=inheritance_accessibility
        )

    def _parse_union_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []

        for child in die.iter_children():
            members.append(self._parse_member(child))

        return Union(
            name=class_name,
            fields=members,
            accessibility=self._get_accessibility(die)
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

        return Union(fields=members, accessibility=self._get_accessibility(die))

    def _parse_sub_program(self, die):
        if Attribute.SPECIFICATION not in die.attributes:
            return

        existing_method = self._subprograms[die.attributes[Attribute.SPECIFICATION].value]
        for child in die.iter_children():
            if child.tag == Tag.PARAMETER:
                param_type = self._resolve_type(child)
                existing_method.parameters.append(Parameter(
                    name=child.attributes[Attribute.NAME].value,
                    type=param_type
                ))

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
                return None

            entry = die.cu.get_DIE_from_refaddr(entry.attributes[Attribute.TYPE].value)

        type.name = entry.attributes[Attribute.NAME].value
        return type

    @staticmethod
    def _get_accessibility(die):
        if Attribute.ACCESSIBILITY in die.attributes:
            return die.attributes[Attribute.ACCESSIBILITY].value

        return Accessibility.private.value
