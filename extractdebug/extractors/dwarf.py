from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from extractdebug.extractors.extractor import Extractor, Field, Class, ExtractorResult, Accessibility, Method, Parameter, Type, TypeModifier


class Tag:
    CLASS_NAME = 'DW_TAG_class_type'
    BASE_TYPE = 'DW_TAG_base_type'
    CONST_TYPE = 'DW_TAG_const_type'
    POINTER_TYPE = 'DW_TAG_pointer_type'
    MEMBER = 'DW_TAG_member'
    SUB_PROGRAM = 'DW_TAG_subprogram'
    PARAMETER = 'DW_TAG_formal_parameter'


class Attribute:
    NAME = 'DW_AT_name'
    TYPE = 'DW_AT_type'
    ACCESSIBILITY = 'DW_AT_accessibility'
    SPECIFICATION = 'DW_AT_specification'
    OBJECT_POINTER = 'DW_AT_object_pointer'
    DATA_MEMBER_LOCATION = 'DW_AT_data_member_location'
    CONST_VALUE = 'DW_AT_const_value'


class DwarfExtractor(Extractor):
    def __init__(self):
        self._classes = []
        self._types = {}
        self._subprograms = {}

    def test(self, file):
        try:
            elf_file = ELFFile(file)
            return elf_file.has_dwarf_info()
        except ELFError:
            return False

    def extract(self, file):
        elf_file = ELFFile(file)
        dwarf_info = elf_file.get_dwarf_info()

        for cu in dwarf_info.iter_CUs():
            self._parse_compilation_unit(cu)

        return ExtractorResult(file, self._classes)

    def _parse_compilation_unit(self, cu):
        top_die = cu.get_top_DIE()
        for child in top_die.iter_children():
            if child.tag == Tag.CLASS_NAME:
                self._classes.append(self._parse_class_type(child))
            elif child.tag == Tag.SUB_PROGRAM:
                self._parse_sub_program(child)

    def _parse_class_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []

        for child in die.iter_children():
            attrs = child.attributes
            accessibility = self._get_accessibility(child)
            class_type = self._resolve_type(child)

            # Tag specific attributes
            if child.tag == Tag.SUB_PROGRAM:
                method = Method(
                    name=attrs[Attribute.NAME].value,
                    type=class_type,
                    accessibility=accessibility,
                    static=Attribute.OBJECT_POINTER not in attrs
                )
                members.append(method)
                self._subprograms[child.offset] = method
            elif child.tag == Tag.MEMBER:
                field = Field(
                    name=attrs[Attribute.NAME].value,
                    type=class_type,
                    accessibility=accessibility,
                    static=Attribute.DATA_MEMBER_LOCATION not in attrs,
                    const_value=attrs[Attribute.CONST_VALUE].value if Attribute.CONST_VALUE in attrs else None
                )
                members.append(field)

        return Class(name=class_name, members=members)

    def _parse_sub_program(self, die):
        attrs = die.attributes
        if Attribute.SPECIFICATION not in attrs:
            return

        existing_method = self._subprograms[attrs[Attribute.SPECIFICATION].value]
        for child in die.iter_children():
            attrs = child.attributes
            if child.tag == Tag.PARAMETER:
                param_type = self._resolve_type(child)
                existing_method.parameters.append(Parameter(
                    name=attrs[Attribute.NAME].value,
                    type=param_type
                ))

    @staticmethod
    def _resolve_type(die):
        resolved_type = Type()
        modifiers = []

        if Attribute.TYPE not in die.attributes:
            return None

        entry = die.cu.get_DIE_from_refaddr(die.attributes[Attribute.TYPE].value)
        while Attribute.NAME not in entry.attributes:
            if entry.tag == Tag.POINTER_TYPE:
                modifiers.insert(0, TypeModifier.pointer)

            if entry.tag == Tag.CONST_TYPE:
                modifiers.insert(0, TypeModifier.constant)

            if Attribute.TYPE not in entry.attributes:
                return None

            entry = die.cu.get_DIE_from_refaddr(entry.attributes[Attribute.TYPE].value)

        resolved_type.modifiers = modifiers
        resolved_type.name = entry.attributes[Attribute.NAME].value
        return resolved_type

    @staticmethod
    def _get_accessibility(die):
        if Attribute.ACCESSIBILITY in die.attributes:
            return die.attributes[Attribute.ACCESSIBILITY].value

        return Accessibility.private.value
