import difflib


def cache_line(a, b):
    print('{} => {}'.format(a, b))
    for i, s in enumerate(difflib.ndiff(a, b)):
        if s[0] == ' ':
            continue
        elif s[0] == '-':
            print(u'Delete "{}" from position {}'.format(s[-1], i))
        elif s[0] == '+':
            print(u'Add "{}" to position {}'.format(s[-1], i))
    print()


if __name__ == '__main__':
    cache_line('bash: line 1: 22123 Done                    echo ""',
               'bash: line 1: 22206 Done                    echo ""')
    cache_line('abc', 'deff')

