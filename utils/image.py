from colorsys import rgb_to_hsv
import cv2
import numpy as np

from PIL import Image

## to avoid changing input image:
##   functions here open files and return images

def resize_img(img_path, max_dim):
    img = Image.open(img_path).convert('RGB')
    img.thumbnail((max_dim, max_dim), Image.ANTIALIAS)
    return img


def crop_face(img_path, face_rect):
    img = Image.open(img_path).convert('RGB')
    iwidth, iheight = img.size

    face_left = face_rect['left'] * iwidth
    face_top = face_rect['top'] * iheight
    face_width = face_rect['width'] * iwidth
    face_height = face_rect['height'] * iheight

    face_center_x = face_left + 0.5 * face_width
    face_center_y = face_top + 0.475 * face_height
    face_dim = max(face_width, face_height)

    crop_margin = 0.666
    face_dim_margin = crop_margin * face_dim

    crop_left = face_center_x - face_dim_margin
    crop_right = face_center_x + face_dim_margin
    crop_top = face_center_y - face_dim_margin
    crop_bottom = face_center_y + face_dim_margin

    return img.crop((crop_left, crop_top, crop_right, crop_bottom))


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

    # get brightest of top 3 colors
    if by_hsv:
        top3_rgb_idx = (np.argsort(-counts))[:3]
        top3_rgb = centers[top3_rgb_idx]
        top3_hsv = [rgb_to_hsv(*(rgb / [255, 255, 255])) for rgb in top3_rgb]

        dominant_v_idx = np.argsort([-hsv[2] for hsv in top3_hsv])[0]
        dominant_rgb = top3_rgb[dominant_v_idx]

    return ''.join(["%02X" % c for c in dominant_rgb])


