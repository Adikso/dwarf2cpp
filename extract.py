import click

from extractdebug.processor import process, convert


@click.command()
@click.option('--format', type=click.Choice(['cpp', 'pointers_cpp'], case_sensitive=False), default='cpp')
@click.option('--includes/--no-includes', default=True)
@click.argument('input', type=click.File('rb'))
def extract(input, format, includes):
    config = {
        'includes': includes
    }

    result = process(input)
    output = convert(result, format, config)

    print(output)


if __name__ == '__main__':
    extract()
