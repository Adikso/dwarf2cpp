from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from extractdebug.extractors.extractor import Extractor, Field, Class, ExtractorResult, Accessibility, Method


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
            top_die = cu.get_top_DIE()
            for child in top_die.iter_children():
                if child.tag == 'DW_TAG_class_type':
                    self._classes.append(self._parse_class_type(child))
                elif child.tag == 'DW_TAG_base_type':
                    self._types[child.offset] = child

        return ExtractorResult(file, self._classes)

    def _parse_class_type(self, die):
        class_name = die.attributes['DW_AT_name'].value
        members = []

        for child in die.iter_children():
            # Common attributes
            name = child.attributes['DW_AT_name'].value
            type_id = child.attributes['DW_AT_type'].value
            die_type = self._types[type_id].attributes['DW_AT_name'].value

            if 'DW_AT_accessibility' not in child.attributes:
                accessibility = Accessibility.private.value
            else:
                accessibility = child.attributes['DW_AT_accessibility'].value

            # Tag specific attributes
            if child.tag == 'DW_TAG_subprogram':
                members.append(Method(name, die_type, accessibility))
            elif child.tag == 'DW_TAG_member':
                members.append(Field(name, die_type, accessibility))

        return Class(class_name, members)
