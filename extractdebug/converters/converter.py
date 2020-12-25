class Converter:
    def name(self):
        raise NotImplementedError

    def convert(self, result):
        raise NotImplementedError


class ConverterResultFile:
    def __init__(self, name, directory, relative_path, entries, includes):
        self.name = name.decode('utf-8')
        self.directory = directory.decode('utf-8')
        self.relative_path = relative_path.decode('utf-8')
        self.entries = entries
        self.includes = includes
