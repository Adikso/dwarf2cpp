import os
import re
from collections import defaultdict
import numpy as np

from elftools.common.exceptions import ELFError
from elftools.common.utils import struct_parse
from elftools.elf.elffile import ELFFile

from extractdebug.converters.common import chunks
from extractdebug.extractors.extractor import Extractor, Field, Class, ExtractorResult, Accessibility, Method, Parameter, Type, TypeModifier, Union, Struct, Namespace, TypeDef, \
    File, Enumerator, EnumerationType


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
    ENUMERATION_TYPE = 'DW_TAG_enumeration_type'
    ARRAY_TYPE = 'DW_TAG_array_type'


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
    VIRTUALITY = 'DW_AT_virtuality'
    BYTE_SIZE = 'DW_AT_byte_size'


class DwarfExtractor(Extractor):
    def __init__(self):
        self._types = {}
        self._subprograms = {}
        self._subprograms_name = defaultdict(set)
        self._subprograms_incomplete = set()
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
                self.cu_files[cu.cu_offset] = self.__parse_files_info(self.dwarf_info, cu.structs, top_die.attributes['DW_AT_stmt_list'].value)

            elements += self.__parse_compilation_unit(cu)
            cus.append(cu)

        self.__fix_constructors()

        base_dir = cus[0].get_top_DIE().attributes[Attribute.COMP_DIR].value
        first_file = cus[0].get_top_DIE().attributes[Attribute.NAME].value
        if os.path.isabs(first_file):
            base_dir = os.path.commonpath([base_dir, first_file])

        return ExtractorResult(file, self.cu_files, elements, base_dir)

    def __fix_constructors(self):
        for subprogram in self._subprograms_incomplete:
            similar = self._subprograms_name[subprogram.name]
            for other_subprogram in similar:
                if other_subprogram.low_pc:
                    subprogram.low_pc = other_subprogram.low_pc
                    break

    def __parse_children(self, die):
        elements = []

        for child in die.iter_children():
            if child.tag == Tag.CLASS_TYPE:
                elements.append(self.__parse_class_type(child))
            elif child.tag == Tag.UNION_TYPE:
                elements.append(self.__parse_union_type(child))
            elif child.tag == Tag.STRUCTURE_TYPE:
                if Attribute.NAME not in child.attributes:
                    continue

                elements.append(self.__parse_struct_type(child))
            elif child.tag == Tag.SUB_PROGRAM:
                self.__parse_sub_program(child)
            elif child.tag == Tag.NAMESPACE:
                elements.append(self.__parse_namespace(child))
            elif child.tag == Tag.TYPEDEF:
                elements.append(self.__parse_typedef(child))
            elif child.tag == Tag.ENUMERATION_TYPE:
                elements.append(self.__parse_enum(child))

        return elements

    def __parse_compilation_unit(self, unit):
        top_die = unit.get_top_DIE()
        return self.__parse_children(top_die)

    def __parse_namespace(self, die):
        elements = self.__parse_children(die)
        namespace = Namespace(
            name=die.attributes[Attribute.NAME].value if Attribute.NAME in die.attributes else None,
            elements=elements,
            decl_file=self.__get_file(die)
        )

        return namespace

    def __parse_typedef(self, die):
        return TypeDef(
            name=die.attributes[Attribute.NAME].value,
            type=self.__resolve_type(die),
            decl_file=self.__get_file(die)
        )

    def __parse_class_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []
        inheritance_class = None
        inheritance_accessibility = None

        for child in die.iter_children():
            if child.tag == Tag.INHERITANCE:
                inheritance_accessibility = self.__get_accessibility(child)
                inheritance_class = self.__resolve_type(child)
                continue

            members.append(self.__parse_member(child))

        return Class(
            name=class_name,
            members=members,
            inheritance_class=inheritance_class,
            inheritance_accessibility=inheritance_accessibility,
            decl_file=self.__get_file(die)
        )

    def __parse_struct_type(self, die):
        class_name = die.attributes[Attribute.NAME].value
        members = []

        for child in die.iter_children():
            members.append(self.__parse_member(child))

        return Struct(
            name=class_name,
            members=members,
            decl_file=self.__get_file(die)
        )

    def __parse_union_type(self, die):
        members = []

        for child in die.iter_children():
            members.append(self.__parse_member(child))

        return Union(
            name=die.attributes[Attribute.NAME].value if Attribute.NAME in die.attributes else None,
            fields=members,
            accessibility=self.__get_accessibility(die),
            decl_file=self.__get_file(die)
        )

    def __parse_member(self, child):
        attrs = child.attributes
        accessibility = self.__get_accessibility(child)
        class_type = self.__resolve_type(child)

        # Tag specific attributes
        if child.tag == Tag.SUB_PROGRAM:
            method_name = attrs[Attribute.NAME].value if Attribute.NAME in attrs else None
            method = Method(
                name=method_name,
                type=class_type,
                accessibility=accessibility,
                static=Attribute.OBJECT_POINTER not in attrs,
                virtual=Attribute.VIRTUALITY in attrs and attrs[Attribute.VIRTUALITY].value == 1,
                offset=child.offset,
                decl_file=self.__get_file(child),
                fully_defined=False,
                linkage_name=attrs[Attribute.LINKAGE_NAME].value if Attribute.LINKAGE_NAME in attrs else None,
            )

            for sub_child in child.iter_children():
                if sub_child.tag == Tag.PARAMETER:
                    param_type = self.__resolve_type(sub_child)
                    method.direct_parameters.append(Parameter(  # TODO
                        name=sub_child.attributes[Attribute.NAME].value if Attribute.NAME in sub_child.attributes else None,
                        type=param_type,
                        offset=sub_child.offset
                    ))

            self._subprograms[child.offset] = method
            if method_name:
                self._subprograms_name[method_name].add(method)

            self._subprograms_incomplete.add(method)
            return self._subprograms[child.offset]
        elif child.tag == Tag.MEMBER:
            if class_type:
                value = None
                if Attribute.CONST_VALUE in attrs:
                    value = attrs[Attribute.CONST_VALUE].value
                    if class_type.array and class_type.byte_size:
                        value = list(chunks(value, class_type.byte_size))

                return Field(
                    name=attrs[Attribute.NAME].value if Attribute.NAME in attrs else b'ERROR_UNKNOWN',
                    decl_file=self.__get_file(child),
                    type=class_type,
                    accessibility=accessibility,
                    static=Attribute.EXTERNAL in attrs,
                    const_value=value,
                    array_size=len(value) if value and isinstance(value, list) else None,
                    data_member_location=attrs[Attribute.DATA_MEMBER_LOCATION].value if Attribute.DATA_MEMBER_LOCATION in attrs else None
                )

            type_die = child.get_DIE_from_attribute(Attribute.TYPE)
            if type_die.tag == Tag.UNION_TYPE:
                return self.__parse_union(child)
        elif child.tag == Tag.ENUMERATION_TYPE:
            return self.__parse_enum(child)

        return None

    def __parse_union(self, die):
        type_die = die.get_DIE_from_attribute(Attribute.TYPE)
        members = []

        for child in type_die.iter_children():
            member = self.__parse_member(child)
            if not member:
                continue

            member.static = Attribute.EXTERNAL in child.attributes
            members.append(member)

        return Union(
            fields=members,
            accessibility=self.__get_accessibility(die)
        )

    def __parse_enum(self, die):
        if Attribute.NAME not in die.attributes:
            return None

        class_type = self.__resolve_type(die)

        enumerators = []
        for child in die.iter_children():
            child_name = child.attributes[Attribute.NAME].value
            child_value = child.attributes[Attribute.CONST_VALUE].value
            enumerators.append(Enumerator(name=child_name, value=child_value))

        return EnumerationType(
            name=die.attributes[Attribute.NAME].value,
            type=class_type,
            enumerators=enumerators,
            decl_file=self.__get_file(die),
            accessibility=self.__get_accessibility(die)
        )

    def __parse_sub_program(self, die):
        if Attribute.SPECIFICATION not in die.attributes:
            if not (Attribute.NAME not in die.attributes and Attribute.LINKAGE_NAME in die.attributes):
                return

            new_member = self.__parse_member(die)
            match = re.match('_ZN[0-9]+([a-zA-z]+)C[0-9]', die.attributes[Attribute.LINKAGE_NAME].value.decode('utf-8'))
            if not match:
                return

            new_member.name = match.group(1).encode('utf-8')
            self._subprograms_name[new_member.name].add(new_member)

            specification_die_offset = die.offset
        else:
            specification_die_offset = die.get_DIE_from_attribute(Attribute.SPECIFICATION).offset
            if specification_die_offset not in self._subprograms:
                self.__parse_member(die.get_DIE_from_attribute(Attribute.SPECIFICATION))

        existing_method = self._subprograms[specification_die_offset]
        for child in die.iter_children():
            if child.tag == Tag.PARAMETER:
                param_type = self.__resolve_type(child)
                # if Attribute.NAME in child.attributes:  # Make sure
                existing_method.parameters.append(Parameter(
                    name=child.attributes[Attribute.NAME].value if Attribute.NAME in child.attributes else b'arg',
                    type=param_type
                ))

        if Attribute.LOW_PC in die.attributes:
            existing_method.low_pc = die.attributes[Attribute.LOW_PC].value

        if existing_method.low_pc:
            existing_method.fully_defined = True
            self._subprograms_incomplete.remove(existing_method)

    def __parse_files_info(self, dwarf_info, structs, offset=0):
        files = {}

        lineprog_header = struct_parse(structs.Dwarf_lineprog_header, dwarf_info.debug_line_sec.stream, offset)
        for i, entry in enumerate(lineprog_header.file_entry):
            files[i + 1] = File(id=i + 1, name=entry.name, directory=lineprog_header.include_directory[entry.dir_index - 1])

        return files

    def __resolve_type(self, die):
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

                if entry.tag == Tag.ARRAY_TYPE:
                    type.array = True

                if Attribute.BYTE_SIZE in entry.attributes:
                    type.byte_size = entry.attributes[Attribute.BYTE_SIZE].value
                if entry.tag == Tag.BASE_TYPE:
                    type.base = True

                if Attribute.TYPE not in entry.attributes:
                    if Attribute.LINKAGE_NAME in entry.attributes:
                        type.name = entry.attributes[Attribute.LINKAGE_NAME].value
                        return type
                    return None

                entry = entry.get_DIE_from_attribute(Attribute.TYPE)
                if Attribute.BYTE_SIZE in entry.attributes:
                    type.byte_size = entry.attributes[Attribute.BYTE_SIZE].value
                if entry.tag == Tag.BASE_TYPE:
                    type.base = True

            type.name = entry.attributes[Attribute.NAME].value

            if Attribute.DECL_FILE in entry.attributes:
                type.decl_file = self.__get_file(entry)

            entry = entry._parent
            while entry and entry.tag == Tag.NAMESPACE:
                type.namespaces.appendleft(entry.attributes[Attribute.NAME].value)
                entry = entry._parent
        except Exception as e:
            # print(e)
            return None

        return type

    @staticmethod
    def __get_accessibility(die):
        if Attribute.ACCESSIBILITY in die.attributes:
            return die.attributes[Attribute.ACCESSIBILITY].value

        return Accessibility.private.value

    def __get_file(self, die):
        if Attribute.DECL_FILE not in die.attributes:
            return None

        decl_file = die.attributes[Attribute.DECL_FILE].value
        return die.cu.cu_offset, self.cu_files[die.cu.cu_offset][decl_file]
