import click

from extractdebug.processor import process, convert


@click.command()
@click.argument('input', type=click.File('rb'))
@click.option('--format', type=click.Choice(['cpp'], case_sensitive=False))
def extract(input, format):
    result = process(input)
    output = convert(result, format)
    for cls in output:
        print(cls)


if __name__ == '__main__':
    extract()
