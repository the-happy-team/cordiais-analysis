import csv
from io import StringIO
import json
import os
from os.path import isfile, join
from subprocess import Popen

from PIL import Image
import requests

from cordiais_utils import to_slug

IMAGES_DIR = join('.', 'imgs')
IMAGES_DIR_RAW = join(IMAGES_DIR, '00_raw')
IMAGES_DIR_WEB = join(IMAGES_DIR, '01_web')
IMAGES_DIR_THUMB = join(IMAGES_DIR, '02_thumb')

SHEET_URL = 'https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s' % (
    os.environ.get('SHEET_ID'),
    os.environ.get('SHEET_NAME')
)

# https://github.com/lovasoa/dezoomify-rs
DEZOOM = {
    'CMD': join('.', 'bin', 'dezoomify-rs'),
    'COMPRESSION': 90,
    'MAX_WIDTH': 1024 * 10
}

FACE_API_URL = 'https://api-us.faceplusplus.com/facepp/v3/detect'


def get_obras():
    obras = []
    res = requests.get(url=SHEET_URL)

    if res.ok:
        res_io = StringIO(res.content.decode('utf8'))
        for o in csv.DictReader(res_io, delimiter=','):
            obras.append(o)

    return obras


def get_images(obras):
    for o in obras:
        img_slug = to_slug(o['ARTISTA'], o['TÍTULO DA OBRA'])
        img_file_raw = join(IMAGES_DIR_RAW, '%s.jpg' % img_slug)
        img_file_web = join(IMAGES_DIR_WEB, '%s.jpg' % img_slug)
        img_file_thumb = join(IMAGES_DIR_THUMB, '%s.jpg' % img_slug)

        if not isfile(img_file_raw):
            link_web = o['LINK EXTERNO']
            link_internal = o['LINK INTERNO']

            if link_internal is not '' and 'foo' not in link_internal:
                print('TODO: download from internal url')
            elif 'artsandculture.google.com' in link_web:
                print('get %s from %s' % (img_slug[0:16], link_web))
                get_image_from_gaac(link_web, img_file_raw)
        
        if not isfile(img_file_web):
            print('TODO: resize web')

        if not isfile(img_file_thumb):
            print('TODO: resize thumb')


def get_image_from_gaac(link_web, img_file):
    p = Popen([
        '%s' % DEZOOM['CMD'],
        '--compression=%s' % DEZOOM['COMPRESSION'],
        '--max-width=%s' % DEZOOM['MAX_WIDTH'],
        '--',
        '%s' % link_web,
        '%s' % img_file])
    try:
        p.wait(timeout=120)
    except:
        print("%s timedout" % img_file)


def get_all_images_from_gaac(obras):
    for o in obras:
        img_slug = to_slug(o['ARTISTA'], o['TÍTULO DA OBRA'])
        img_file = join(IMAGES_RAW_DIR, '%s.jpg' % img_slug)
        if not isfile(img_file):
            web_link = o['LINK EXTERNO']
            if 'artsandculture.google.com' in web_link:
                print('get %s from %s' % (img_slug[0:16], web_link))
                get_image_from_gaac(web_link, img_file)


def get_faces(img_file):
    faces = []

    files = {
        'image_file': open(img_file, 'rb')
    }

    data = {
        'api_key': os.environ.get('FACEPP_KEY'),
        'api_secret': os.environ.get('FACEPP_SECRET'),
        'return_attributes': 'emotion,gender,age,ethnicity'
    }

    res = requests.post(FACE_API_URL, files=files, data=data)

    if res.ok:
        faces = json.loads(res.text)['faces']
        print('get_faces success')
    else:
        print('get_faces ERROR: %s' % json.dumps(res.text, sort_keys=True, indent=2))

    return faces


def print_results(faces):
    for face in faces:
        if 'age' in face['attributes']:
            print('age: %d' % face['attributes']['age']['value'])
        if 'gender' in face['attributes']:
            print('gender: %s' % face['attributes']['gender']['value'])
        if 'ethnicity' in face['attributes']:
            print('ethnicity: %s' % face['attributes']['ethnicity']['value'])
        if 'emotion' in face['attributes']:
            ems = face['attributes']['emotion']
            ems_not_neutral = {e:ems[e] for e in ems if e != 'neutral'}
            print('emotions: %s' % json.dumps(ems, sort_keys=True, indent=2))
            print('top: %s' % max(ems, key=ems.get))
            print('top not neutral: %s' % max(ems_not_neutral, key=ems_not_neutral.get))


# print_results(get_faces(join('imgs', 'RetratodeMulata_MASC0040.jpg')))
# print(get_obras())
