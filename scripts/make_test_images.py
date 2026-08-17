#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw, ImageFont
import argparse

NAMES = [
    'wedding_2023_01.jpg',
    'vacation_paris_2022_06.jpg',
    'birthday_mom_2021_12.jpg',
    'concert_2024_03.jpg',
    'family_reunion_2019.jpg',
    'random_001.jpg'
]

def make_images(outdir):
    os.makedirs(outdir, exist_ok=True)
    colors = [(220,20,60),(30,144,255),(34,139,34),(255,140,0),(148,0,211),(128,128,128)]
    for name, col in zip(NAMES, colors):
        img = Image.new('RGB', (800,600), color=col)
        d = ImageDraw.Draw(img)
        text = name.replace('.jpg','')
        try:
            d.text((10,10), text, fill=(255,255,255))
        except Exception:
            pass
        img.save(os.path.join(outdir, name))
    print('Created', len(NAMES), 'images in', outdir)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='ADA/test_photos')
    args = p.parse_args()
    make_images(args.out)

if __name__ == '__main__':
    main()
