import csv
from io import StringIO
import json
import os
from os.path import isfile, join
import pathlib
from subprocess import Popen

from PIL import Image
import requests

from cordiais_utils import to_slug

IMAGES_DIR = join('.', 'imgs')
IMAGES_DIR_RAW = join(IMAGES_DIR, '00_raw')
IMAGES_DIR_WEB = join(IMAGES_DIR, '01_web')
IMAGES_DIR_THUMB = join(IMAGES_DIR, '02_thumb')

pathlib.Path(IMAGES_DIR_RAW).mkdir(parents=True, exist_ok=True)
pathlib.Path(IMAGES_DIR_WEB).mkdir(parents=True, exist_ok=True)
pathlib.Path(IMAGES_DIR_THUMB).mkdir(parents=True, exist_ok=True)

MAX_DIM_WEB = 1920
MAX_DIM_THUMB = 320

SHEET_URL = 'https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s' % (
    os.environ.get('SHEET_ID'),
    os.environ.get('SHEET_NAME')
)

# https://github.com/lovasoa/dezoomify-rs
DEZOOM = {
    'CMD': join('.', 'bin', 'dezoomify-rs'),
    'COMPRESSION': 16,
    'MAX_DIM': 1024 * 8
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


def get_image_from_gaac(link_web, img_file):
    p = Popen([
        '%s' % DEZOOM['CMD'],
        '--compression=%s' % DEZOOM['COMPRESSION'],
        '--max-height=%s' % DEZOOM['MAX_DIM'],
        '--max-width=%s' % DEZOOM['MAX_DIM'],
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
        img_file = join(IMAGES_DIR_RAW, '%s.jpg' % img_slug)
        if not isfile(img_file):
            web_link = o['LINK EXTERNO']
            if 'artsandculture.google.com' in web_link:
                print('get %s from %s' % (img_slug[0:16], web_link))
                get_image_from_gaac(web_link, img_file)


def resize_img(img_file_in, max_dim):
    img = Image.open(img_file_in).convert("RGB")
    width, height = img.size

    if width > max_dim:
        width, height = max_dim, max_dim * height / width
    if height > max_dim:
        width, height = max_dim * width / height, max_dim

    img.thumbnail((width, height), Image.ANTIALIAS)
    return img


def get_images(obras):
    for o in obras:
        img_slug = to_slug(o['ARTISTA'], o['TÍTULO DA OBRA'])
        img_file_raw = join(IMAGES_DIR_RAW, '%s.jpg' % img_slug)
        img_file_web = join(IMAGES_DIR_WEB, '%s.jpg' % img_slug)
        img_file_thumb = join(IMAGES_DIR_THUMB, '%s.jpg' % img_slug)

        if not isfile(img_file_raw):
            link_web = o['LINK EXTERNO']
            link_internal = o['LINK INTERNO']

            if link_internal != '' and 'foo' not in link_internal:
                print('TODO: download %s from internal url' % img_slug)
            elif 'artsandculture.google.com' in link_web:
                print('get %s from %s' % (img_slug[0:16], link_web))
                get_image_from_gaac(link_web, img_file_raw)
            elif link_web != '':
                print('download %s from non google url' % img_slug)
                img_data = requests.get(link_web).content
                with open(img_file_raw, 'wb') as handler:
                    handler.write(img_data)

        if isfile(img_file_raw) and not isfile(img_file_web):
            print('resize %s for web' % img_slug)
            img_sized = resize_img(img_file_raw, MAX_DIM_WEB)
            img_sized.save(img_file_web, quality=90, optimize=True, progressive=True)

        if isfile(img_file_raw) and not isfile(img_file_thumb):
            print('resize %s for thumbnail' % img_slug)
            img_sized = resize_img(img_file_raw, MAX_DIM_THUMB)
            img_sized.save(img_file_thumb, quality=90, optimize=True, progressive=True)


def to_web_json(csv_json):
    web_json = {}
    web_json['artist'] = csv_json['ARTISTA']
    web_json['title'] = csv_json['TÍTULO DA OBRA']
    web_json['year'] = csv_json['ANO']
    web_json['medium'] = csv_json['TÉCNICA']
    web_json['collection'] = csv_json['ACERVO']
    web_json['dimension'] = {
        'width': csv_json['LARGURA cm'],
        'height': csv_json['ALTURA cm'],
        'depth': csv_json['PROFUNDIDADE cm'],
        'unit': 'cm'
        }
    web_json['slug'] = to_slug(web_json['artist'], web_json['title'])

    return web_json


def get_face_attributes(img_file):
    face = {}

    if isfile(img_file):
        files = {
            'image_file': open(img_file, 'rb')
        }

        data = {
            'api_key': os.environ.get('FACEPP_KEY'),
            'api_secret': os.environ.get('FACEPP_SECRET'),
            'return_attributes': 'emotion,gender,age,ethnicity'
        }

        res = requests.post(FACE_API_URL, files=files, data=data)
        res_o = json.loads(res.text)

        if res.ok:
            if res_o['face_num'] > 0:
                face = res_o['faces'][0]
        else:
            print('get_face_attributes ERROR: %s' % json.dumps(res_o, sort_keys=True, indent=2))

    return face


def analyze_images(obras, web_json=None):
    # TODO: read json if it exists
    web_json = web_json if web_json is not None else {}

    for o in obras:
        obra_web_json = to_web_json(o)
        obra_slug = obra_web_json['slug']

        if obra_slug not in web_json:
            obra_filename = join(IMAGES_DIR_WEB, '%s.jpg' % obra_web_json['slug'])
            face = get_face_attributes(obra_filename)

            if 'face_token' in face:
                obra_web_json['gender'] = face['attributes']['gender']['value']
                obra_web_json['age'] = face['attributes']['age']['value']
                obra_web_json['ethnicity'] = face['attributes']['ethnicity']['value']
                obra_web_json['face_rectangle'] = face['face_rectangle']
                obra_web_json['emotions'] = face['attributes']['emotion']

            web_json[obra_slug] = obra_web_json

    return web_json


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
