import csv
from io import StringIO
import json
from os import environ
from os.path import isfile, join
import pathlib
from subprocess import Popen

from PIL import Image
import requests

from utils.text import to_slug
from utils.image import resize_img, crop_face, calculate_dominant_color

IMAGES_DIR = join('.', 'imgs')
IMAGES_DIR_RAW = join(IMAGES_DIR, '00_raw')
IMAGES_DIR_HD = join(IMAGES_DIR, '01_hd')
IMAGES_DIR_THUMB = join(IMAGES_DIR, '02_thumb')
IMAGES_DIR_FACES = join(IMAGES_DIR, '00_raw_faces')

WEB_DIR = join('..', 'cordiais-web', 'public')
WEB_DIR_IMAGES = join(WEB_DIR, 'imgs', 'obras')
WEB_DIR_FACES = join(WEB_DIR, 'imgs', 'faces')
WEB_DIR_DATA = join(WEB_DIR, 'data')
WEB_DATA_FILE = join(WEB_DIR_DATA, 'obras.json')

MAX_DIM_HD = 2160
MAX_DIM_WEB = 800
MAX_DIM_WEB_FACE = 512
MAX_DIM_THUMB = 320

SHEET_URL = 'https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s' % (
    environ.get('SHEET_ID'),
    environ.get('SHEET_NAME')
)

GET_HEADERS = {
    'user-agent': 'PostmanRuntime/7.29.0'
}

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
        '--parallelism=4',
        '--',
        '%s' % link_web,
        '%s' % img_file])
    try:
        p.wait(timeout=120)
    except:
        print("%s timedout" % img_file)


def get_images(obras):
    pathlib.Path(IMAGES_DIR_RAW).mkdir(parents=True, exist_ok=True)
    pathlib.Path(IMAGES_DIR_HD).mkdir(parents=True, exist_ok=True)
    pathlib.Path(IMAGES_DIR_THUMB).mkdir(parents=True, exist_ok=True)
    pathlib.Path(WEB_DIR_IMAGES).mkdir(parents=True, exist_ok=True)

    for o in obras:
        img_slug = to_slug(o['ARTISTA'], o['TÍTULO DA OBRA'])
        img_file_raw = join(IMAGES_DIR_RAW, '%s_%s.jpg' % (img_slug, 'raw'))
        img_file_hd = join(IMAGES_DIR_HD, '%s_%s.jpg' % (img_slug, 'hd'))
        img_file_thumb = join(IMAGES_DIR_THUMB, '%s_%s.jpg' % (img_slug, 'thumb'))
        img_file_web = join(WEB_DIR_IMAGES, '%s_%s.jpg' % (img_slug, 'web'))

        if not isfile(img_file_raw):
            link_web = o['LINK EXTERNO']

            if 'artsandculture.google.com' in link_web:
                print('get %s from %s' % (img_slug[0:16], link_web))
                get_image_from_gaac(link_web, img_file_raw)
            elif link_web.lower().endswith(('.png', '.jpg', '.jpeg')):
                print('download %s from non google url' % img_slug)
                print(link_web)
                img_data = requests.get(link_web, headers=GET_HEADERS).content
                with open(img_file_raw, 'wb') as handler:
                    handler.write(img_data)

        if isfile(img_file_raw) and not isfile(img_file_web):
            print('resize %s for web' % img_slug)
            img_sized = resize_img(img_file_raw, MAX_DIM_WEB)
            img_sized.save(img_file_web, quality=90, optimize=True, progressive=True)

        if isfile(img_file_raw) and not isfile(img_file_hd):
            print('resize %s for hd' % img_slug)
            img_sized = resize_img(img_file_raw, MAX_DIM_HD)
            img_sized.save(img_file_hd, quality=80, optimize=True, progressive=True)

        if isfile(img_file_raw) and not isfile(img_file_thumb):
            print('resize %s for thumbnail' % img_slug)
            img_sized = resize_img(img_file_raw, MAX_DIM_THUMB)
            img_sized.save(img_file_thumb, quality=90, optimize=True, progressive=True)


def to_web_json(csv_json):
    web_json = {}

    ## only continue if there is an image saved
    web_json['slug'] = to_slug(csv_json['ARTISTA'], csv_json['TÍTULO DA OBRA'])
    obra_filename = join(IMAGES_DIR_HD, '%s_%s.jpg' % (web_json['slug'], 'hd'))
    if not isfile(obra_filename):
        return {}

    web_json['artist'] = csv_json['ARTISTA']
    web_json['title'] = csv_json['TÍTULO DA OBRA']
    web_json['year'] = csv_json['ANO']
    web_json['year_sort'] = int(csv_json['ANO (ordem)']) if csv_json['ANO (ordem)'] != '' else 1000
    web_json['medium'] = csv_json['TÉCNICA']
    web_json['collection'] = csv_json['ACERVO']
    web_json['artist_death'] = int(csv_json['DATA MORTE ARTISTA']) if csv_json['DATA MORTE ARTISTA'] != '' else 3000
    web_json['marcantonio'] = True if csv_json['PROJETO MARCANTONIO SITE'] == 'TRUE' else False
    web_json['nudes'] = True if csv_json['NUDES'] == 'TRUE' else False
    web_json['by_woman'] = True if csv_json['PINTADA POR MULHERES'] == 'TRUE' else False
    web_json['by_man'] = False if csv_json['PINTADA POR MULHERES'] == 'TRUE' or csv_json['ARTISTA'] == 'Anônimo' else True

    web_json['img'] = '%s_%s.jpg' % (web_json['slug'], 'web')

    web_json['dimension'] = {
        'width': float(csv_json['LARGURA cm']) if csv_json['LARGURA cm'] != '' else 0,
        'height': float(csv_json['ALTURA cm']) if csv_json['ALTURA cm'] != '' else 0,
        'unit': 'cm'
        }

    if (web_json['dimension']['width'] == 0 or web_json['dimension']['height'] == 0):
        img = Image.open(obra_filename).convert('RGB')
        image_width, image_height = img.size
        web_json['dimension'] = {
            'width': image_width,
            'height': image_height,
            'unit': 'px'
            }

    return web_json


def get_face_attributes(img_file):
    face = {}

    img = Image.open(img_file).convert('RGB')
    image_width, image_height = img.size

    files = {
        'image_file': open(img_file, 'rb')
    }

    data = {
        'api_key': environ.get('FACEPP_KEY'),
        'api_secret': environ.get('FACEPP_SECRET'),
        'return_attributes': 'emotion,gender,age,ethnicity'
    }

    res = requests.post(FACE_API_URL, files=files, data=data)
    res_o = json.loads(res.text)

    if res.ok:
        if res_o['face_num'] > 0:
            face = res_o['faces'][0]
            face['faces'] = res_o['face_num']
            face['face_rectangle'] = {
                'left': face['face_rectangle']['left'] / image_width,
                'top': face['face_rectangle']['top'] / image_height,
                'width': face['face_rectangle']['width'] / image_width,
                'height': face['face_rectangle']['height'] / image_height
            }
        else:
            face['faces'] = 0
    else:
        print('get_face_attributes ERROR: %s' % json.dumps(res_o, sort_keys=True, indent=2))

    return face


def analyze_images(obras_csv, obras_web):
    for o in obras_csv:
        obra_csv_json = to_web_json(o)
        if not obra_csv_json:
            continue

        obra_slug = obra_csv_json['slug']

        if obra_slug not in obras_web or 'faces' not in obras_web[obra_slug]:
            print('processing: %s' % obra_slug)
            obra_filename = join(IMAGES_DIR_HD, '%s_%s.jpg' % (obra_slug, 'hd'))
            face = get_face_attributes(obra_filename)

            if 'faces' in face:
                obra_csv_json['faces'] = face['faces']

            if 'face_rectangle' in face:
                obra_csv_json['face_rectangle'] = face['face_rectangle']
                obra_csv_json['gender'] = face['attributes']['gender']['value']
                obra_csv_json['age'] = face['attributes']['age']['value']
                obra_csv_json['ethnicity'] = face['attributes']['ethnicity']['value']
                obra_csv_json['emotions'] = face['attributes']['emotion']

            obras_web[obra_slug] = obra_csv_json
        else:
            print('updating fields from CSV: %s' % obra_slug)
            for k, v in obra_csv_json.items():
                obras_web[obra_slug][k] = v

    return obras_web


def export_faces(obras_web):
    pathlib.Path(IMAGES_DIR_FACES).mkdir(parents=True, exist_ok=True)
    pathlib.Path(WEB_DIR_FACES).mkdir(parents=True, exist_ok=True)

    for o_slug in obras_web:
        o = obras_web[o_slug]

        o_img_file = join(IMAGES_DIR_RAW, o['img'].replace('_web', '_raw'))
        o_face_file = join(IMAGES_DIR_FACES, o['img'].replace('_web', '_raw'))
        o_face_file_web = join(WEB_DIR_FACES, o['img'])

        have_both_faces = isfile(o_face_file) and isfile(o_face_file_web)

        if 'face_rectangle' in o and not have_both_faces:
            face = crop_face(o_img_file, o['face_rectangle'])

            if not isfile(o_face_file):
                face.save(o_face_file, quality=90, optimize=True, progressive=True)

            if not isfile(o_face_file_web):
                print('resize %s face for web' % o_slug)
                face_web = resize_img(o_face_file, MAX_DIM_WEB_FACE)
                face_web.save(o_face_file_web, quality=90, optimize=True, progressive=True)


def get_dominant_colors(obras_web):
    for o_slug in obras_web:
        obra = obras_web[o_slug]
        o_img_file = join(IMAGES_DIR_THUMB, obra['img'].replace('_web', '_thumb'))

        if 'dominant_color' not in obra:
            dom_color = calculate_dominant_color(o_img_file, by_hsv=False)
            obra['dominant_color'] = "#%s" % dom_color
            print("%s: %s" % (o_slug, obras_web[o_slug]['dominant_color']))

    return obras_web


def update_web_json(obras, json_filename=WEB_DATA_FILE):
    pathlib.Path(WEB_DIR_DATA).mkdir(parents=True, exist_ok=True)

    obras_web = {}

    if isfile(json_filename):
        with open(json_filename, 'r') as in_json:
            obras_web = json.load(in_json)

    obras_web = analyze_images(obras, obras_web)
    export_faces(obras_web)
    obras_web = get_dominant_colors(obras_web)

    with open(json_filename, 'w') as out_json:
        json.dump(obras_web, out_json, ensure_ascii=False)


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
