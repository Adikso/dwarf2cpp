import os

type_mapping = {
    'std::string': 'string'
}


def get_project_files(files):
    main_file = None

    for file in files.values():
        if not file.directory.startswith(b'/usr/'):
            main_file = file
            break

    potential_base_paths = set()

    base_path = main_file.directory
    for file in files.values():
        file.directory = os.path.realpath(file.directory)
        path = os.path.commonprefix([base_path, file.directory])
        if path != b'/':
            potential_base_paths.add(path)

    base_path = min(potential_base_paths, key=len)
    project_files = {}
    for file_id, file in files.items():
        if file.name != b'<built-in>' and file.directory.startswith(base_path):
            project_files[file_id] = file

    return base_path, project_files


def relative_path(base_path, file):
    path = os.path.relpath(file.directory, base_path) + b'/' + file.name
    if path.startswith(b'./'):
        path = path[2:]

    return path


def test_utf8(data):
    if not data:
        return False

    try:
        data.decode('utf-8')
        return True
    except:
        return False


def get_utf8(source, name, default):
    value = source.get(name, None)
    if not value or not test_utf8(value):
        return default.decode('utf-8')

    return value.decode('utf-8')
