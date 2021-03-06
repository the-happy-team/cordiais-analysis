from colorsys import rgb_to_hsv
import csv
import cv2
from io import StringIO
import json
import numpy as np
import os
from os.path import isfile, join
import pathlib
from subprocess import Popen

from PIL import Image
import requests

from cordiais_utils import to_slug

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


def resize_img(img_file_in, max_dim):
    img = Image.open(img_file_in).convert('RGB')
    img.thumbnail((max_dim, max_dim), Image.ANTIALIAS)
    return img

# TODO: refactor resize_img to be like this
def _resize_img(img, max_dim):
    img.thumbnail((max_dim, max_dim), Image.ANTIALIAS)
    return img


def get_images(obras):
    pathlib.Path(IMAGES_DIR_RAW).mkdir(parents=True, exist_ok=True)
    pathlib.Path(IMAGES_DIR_HD).mkdir(parents=True, exist_ok=True)
    pathlib.Path(IMAGES_DIR_THUMB).mkdir(parents=True, exist_ok=True)
    pathlib.Path(WEB_DIR_IMAGES).mkdir(parents=True, exist_ok=True)

    for o in obras:
        img_slug = to_slug(o['ARTISTA'], o['T??TULO DA OBRA'])
        img_file_raw = join(IMAGES_DIR_RAW, '%s_%s.jpg' % (img_slug, 'raw'))
        img_file_hd = join(IMAGES_DIR_HD, '%s_%s.jpg' % (img_slug, 'hd'))
        img_file_thumb = join(IMAGES_DIR_THUMB, '%s_%s.jpg' % (img_slug, 'thumb'))
        img_file_web = join(WEB_DIR_IMAGES, '%s_%s.jpg' % (img_slug, 'web'))

        if not isfile(img_file_raw):
            link_web = o['LINK EXTERNO']

            if 'artsandculture.google.com' in link_web:
                print('get %s from %s' % (img_slug[0:16], link_web))
                get_image_from_gaac(link_web, img_file_raw)
            elif link_web != '':
                print('download %s from non google url' % img_slug)
                # TODO: refactor this into a get_image_from_url()
                img_data = requests.get(link_web).content
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
    web_json['artist'] = csv_json['ARTISTA']
    web_json['title'] = csv_json['T??TULO DA OBRA']
    web_json['year'] = csv_json['ANO']
    web_json['year_sort'] = int(csv_json['ANO (ordem)'])
    web_json['medium'] = csv_json['T??CNICA']
    web_json['collection'] = csv_json['ACERVO']
    web_json['artist_death'] = int(csv_json['DATA MORTE ARTISTA']) if csv_json['DATA MORTE ARTISTA'] != '' else 3000
    web_json['marcantonio'] = True if csv_json['PROJETO MARCANTONIO SITE'] == 'TRUE' else False
    web_json['nudes'] = True if csv_json['NUDES'] == 'TRUE' else False
    web_json['by_woman'] = True if csv_json['PINTADA POR MULHERES'] == 'TRUE' else False
    web_json['by_man'] = False if csv_json['PINTADA POR MULHERES'] == 'TRUE' or csv_json['ARTISTA'] == 'An??nimo' else True

    web_json['dimension'] = {
        'width': float(csv_json['LARGURA cm']) if csv_json['LARGURA cm'] != '' else 0,
        'height': float(csv_json['ALTURA cm']) if csv_json['ALTURA cm'] != '' else 0,
        'unit': 'cm'
        }
    web_json['slug'] = to_slug(web_json['artist'], web_json['title'])
    web_json['img'] = '%s_%s.jpg' % (web_json['slug'], 'web')

    if (web_json['dimension']['width'] == 0 or web_json['dimension']['height'] == 0):
        obra_filename = join(IMAGES_DIR_HD, '%s_%s.jpg' % (web_json['slug'], 'hd'))
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

    if isfile(img_file):
        img = Image.open(img_file).convert('RGB')
        image_width, image_height = img.size

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
                face['face_rectangle'] = {
                    'left': face['face_rectangle']['left'] / image_width,
                    'top': face['face_rectangle']['top'] / image_height,
                    'width': face['face_rectangle']['width'] / image_width,
                    'height': face['face_rectangle']['height'] / image_height
                }
        else:
            print('get_face_attributes ERROR: %s' % json.dumps(res_o, sort_keys=True, indent=2))

    return face


def analyze_images(obras_csv, obras_web):
    for o in obras_csv:
        obra_csv_json = to_web_json(o)
        obra_slug = obra_csv_json['slug']

        if obra_slug not in obras_web:
            print('processing: %s' % obra_slug)
            obra_filename = join(IMAGES_DIR_HD, '%s_%s.jpg' % (obra_slug, 'hd'))
            face = get_face_attributes(obra_filename)

            if 'face_token' in face:
                obra_csv_json['gender'] = face['attributes']['gender']['value']
                obra_csv_json['age'] = face['attributes']['age']['value']
                obra_csv_json['ethnicity'] = face['attributes']['ethnicity']['value']
                obra_csv_json['face_rectangle'] = face['face_rectangle']
                obra_csv_json['emotions'] = face['attributes']['emotion']

            obras_web[obra_slug] = obra_csv_json
        else:
            print('updating fields from CSV: %s' % obra_slug)
            for k, v in obra_csv_json.items():
                obras_web[obra_slug][k] = v

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


def crop_face(img, face_rect):
    iwidth, iheight = img.size

    face_left = face_rect['left'] * iwidth
    face_top = face_rect['top'] * iheight
    face_width = face_rect['width'] * iwidth
    face_height = face_rect['height'] * iheight

    face_center_x = face_left + 0.5 * face_width
    face_center_y = face_top + 0.475 * face_height
    face_dim = max (face_width, face_height)

    crop_margin = 0.666
    crop_left = face_center_x - crop_margin * face_dim
    crop_right = face_center_x + crop_margin * face_dim
    crop_top = face_center_y - crop_margin * face_dim
    crop_bottom = face_center_y + crop_margin * face_dim

    return img.crop((crop_left, crop_top, crop_right, crop_bottom))


def export_faces(obras_web):
    pathlib.Path(IMAGES_DIR_FACES).mkdir(parents=True, exist_ok=True)
    pathlib.Path(WEB_DIR_FACES).mkdir(parents=True, exist_ok=True)

    for o_slug in obras_web:
        o = obras_web[o_slug]

        o_img_file = join(IMAGES_DIR_RAW, o['img'].replace('_web', '_raw'))
        o_face_file = join(IMAGES_DIR_FACES, o['img'].replace('_web', '_raw'))
        o_face_file_web = join(WEB_DIR_FACES, o['img'])

        have_both_faces = isfile(o_face_file) and isfile(o_face_file_web)

        if isfile(o_img_file) and 'face_rectangle' in o and not have_both_faces:
            img = Image.open(o_img_file).convert('RGB')
            face = crop_face(img, o['face_rectangle'])

            if not isfile(o_face_file):
                face.save(o_face_file, quality=90, optimize=True, progressive=True)

            if not isfile(o_face_file_web):
                face_web = resize_img(o_face_file, 512)
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


def calculate_dominant_color(img_path, by_hsv=False):
    image = cv2.imread(img_path)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    CV_KMEANS_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    CV_KMEANS_K = 8

    pixel_values = np.float32(image.reshape((-1, 3)))
    _, labels, centers = cv2.kmeans(pixel_values, CV_KMEANS_K, None, CV_KMEANS_CRITERIA, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    _, counts = np.unique(labels, return_counts=True)
    dominant_rgb = centers[np.argmax(counts)]

    if by_hsv:
        top3_rgb_idx = (np.argsort(-counts))[:3]
        top3_rgb = centers[top3_rgb_idx]
        top3_hsv = [rgb_to_hsv(*(rgb / [255, 255, 255])) for rgb in top3_rgb]

        dominant_v_idx = np.argsort([-hsv[2] for hsv in top3_hsv])[0]
        dominant_rgb = top3_rgb[dominant_v_idx]

    return ''.join(["%02X" % c for c in dominant_rgb])


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
