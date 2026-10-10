# -*- coding: utf-8 -*-
"""生成全能助手 PWA 图标：深青圆角方块 + 白色对话线条"""
import os
from PIL import Image, ImageDraw

BASE = r'E:\git-library\quanneng-zhushou-web\icons'
os.makedirs(BASE, exist_ok=True)

def draw(size, path):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size * 0.22
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=(15, 118, 110, 255))
    lw = max(2, int(size * 0.085))
    m = size * 0.28
    span = size - 2 * m
    y1, y2, y3 = size * 0.33, size * 0.5, size * 0.67
    d.line([m, y1, m + span, y1], fill=(255, 255, 255, 255), width=lw)
    d.line([m, y2, m + span * 0.6, y2], fill=(255, 255, 255, 255), width=lw)
    d.line([m, y3, m + span * 0.8, y3], fill=(255, 255, 255, 255), width=lw)
    d.line([m + lw, y1 + lw, m + span * 0.25, size * 0.42], fill=(255, 255, 255, 255), width=lw)
    img.save(path, 'PNG')
    print('saved', path, os.path.getsize(path))

draw(512, os.path.join(BASE, 'icon-512.png'))
draw(192, os.path.join(BASE, 'icon-192.png'))
draw(180, os.path.join(BASE, 'apple-touch-icon.png'))
draw(128, os.path.join(BASE, 'icon-128.png'))
