from re import sub
import unicodedata

# https://stackoverflow.com/a/518232
def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def to_lower_alpha(s):
    alpha_num = sub('[^0-9a-zA-Z ]+', '', s.strip())
    no_spaces = sub('[ ]+', '-', alpha_num)
    return no_spaces.lower()

def to_slug(artist, title):
    artist = to_lower_alpha(strip_accents(artist))
    title = to_lower_alpha(strip_accents(title))
    return '%s_%s' % (artist, title)
