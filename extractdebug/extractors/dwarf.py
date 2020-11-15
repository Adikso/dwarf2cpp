from dotmap import DotMap
from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from extractdebug.extractors.extractor import Extractor, Field, Class, ExtractorResult, Accessibility, Method, Parameter, Type


class Tag:
    CLASS_NAME = 'DW_TAG_class_type'
    BASE_TYPE = 'DW_TAG_base_type'
    CLASS_TYPE = 'DW_TAG_class_type'
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
            type = self._resolve_type(child)

            # Tag specific attributes
            if child.tag == Tag.SUB_PROGRAM:
                method = Method(attrs[Attribute.NAME].value, type, accessibility)
                members.append(method)
                self._subprograms[child.offset] = method
            elif child.tag == Tag.MEMBER:
                members.append(Field(attrs[Attribute.NAME].value, type, accessibility))

        return Class(class_name, members)

    def _parse_sub_program(self, die):
        attrs = die.attributes
        if Attribute.SPECIFICATION not in attrs:
            return

        existing_method = self._subprograms[attrs[Attribute.SPECIFICATION].value]
        for child in die.iter_children():
            attrs = child.attributes
            if child.tag == Tag.PARAMETER:
                type = self._resolve_type(child)
                existing_method.parameters.append(Parameter(attrs[Attribute.NAME].value, type))

    def _resolve_type(self, die):
        resolved_type = Type()

        entry = die.cu.get_DIE_from_refaddr(die.attributes[Attribute.TYPE].value)
        while Attribute.NAME not in entry.attributes:
            if entry.tag == Tag.POINTER_TYPE:
                resolved_type.pointer = True

            if Attribute.TYPE not in entry.attributes:
                return None

            entry = die.cu.get_DIE_from_refaddr(entry.attributes[Attribute.TYPE].value)

        resolved_type.name = entry.attributes[Attribute.NAME].value
        return resolved_type

    @staticmethod
    def _get_accessibility(die):
        if Attribute.ACCESSIBILITY in die.attributes:
            return die.attributes[Attribute.ACCESSIBILITY].value

        return Accessibility.private.value
