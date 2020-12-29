from extractdebug.converters import all_converters
from extractdebug.extractors import all_extractors


def process(file):
    extractor_class = find_extractor(file)
    if not extractor_class:
        return None

    extractor = extractor_class()
    return extractor.extract(file)


def convert(result, format):
    converter = find_converter(format)
    if not converter:
        return None

    return converter(result).convert()


def find_extractor(file):
    for extractor in all_extractors:
        if extractor().test(file):
            return extractor

    return None


def find_converter(format):
    for converter in all_converters:
        if converter.name() == format:
            return converter

    return None
