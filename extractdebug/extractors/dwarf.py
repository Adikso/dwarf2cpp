from dotmap import DotMap
from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from extractdebug.extractors.extractor import Extractor, Field, Class, ExtractorResult, Accessibility, Method


class Tag:
    CLASS_NAME = 'DW_TAG_class_type'
    BASE_TYPE = 'DW_TAG_base_type'
    MEMBER = 'DW_TAG_member'
    SUB_PROGRAM = 'DW_TAG_subprogram'


class Attribute:
    NAME = 'DW_AT_name'
    TYPE = 'DW_AT_type'
    ACCESSIBILITY = 'DW_AT_accessibility'


class DwarfExtractor(Extractor):
    def __init__(self):
        self._classes = []
        self._types = {}

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
            elif child.tag == Tag.BASE_TYPE:
                self._types[child.offset] = child

    def _parse_class_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []

        for child in die.iter_children():
            attrs = self._get_attributes(child)

            # Tag specific attributes
            if child.tag == Tag.SUB_PROGRAM:
                members.append(Method(attrs.name, attrs.die_type, attrs.accessibility))
            elif child.tag == Tag.MEMBER:
                members.append(Field(attrs.name, attrs.die_type, attrs.accessibility))

        return Class(class_name, members)

    # Helpers
    def _get_attributes(self, die):
        attrs = dict([(attribute.name.replace('DW_AT_', ''), attribute.value) for attribute in die.attributes.values()])
        attrs['accessibility'] = self._get_accessibility(die)
        if attrs['type'] in self._types:
            attrs['die_type'] = self._types[attrs['type']].attributes[Attribute.NAME].value
        return DotMap(attrs)

    @staticmethod
    def _get_accessibility(die):
        if Attribute.ACCESSIBILITY in die.attributes:
            return die.attributes[Attribute.ACCESSIBILITY].value

        return Accessibility.private.value
