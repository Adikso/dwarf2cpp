import os


def get_project_files(files):
    main_file = None

    for file in files.values():
        if not file.directory.startswith(b'/usr/'):
            main_file = file
            break

    potential_base_paths = set()

    base_path = main_file.directory
    for file in files.values():
        path = os.path.commonprefix([base_path, file.directory])
        if path != b'/':
            potential_base_paths.add(path)

    base_path = min(potential_base_paths, key=len)
    project_files = {}
    for file_id, file in files.items():
        if file.name != b'<built-in>' and file.directory.startswith(base_path):
            project_files[file_id] = file

    return base_path, project_files
