# -*- coding: utf-8 -*-
"""生成平面版部署包：所有文件在根目录，图标内联，排除子文件夹问题"""
import io, os, re, shutil, zipfile

SRC = r'E:\git-library\quanneng-zhushou-web'
OUT = os.path.join(SRC, '_deploy_flat')
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)

# 1. index.html：移除 apple-touch-icon 文件引用（manifest/sw 引用保留）
html = io.open(os.path.join(SRC, '全能助手.html'), encoding='utf-8').read()
html = re.sub(r'<link rel="apple-touch-icon"[^>]*>\s*', '', html)
io.open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8', newline='').write(html)

# 2. manifest.webmanifest：icons 改为内联 SVG data URL
svg = ("data:image/svg+xml," + "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
       "%3Crect width='24' height='24' rx='5' fill='%230F766E'/%3E"
       "%3Cpath d='M7 8.5h10M7 12h6M7 15.5h8' stroke='white' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E")
manifest = (
    '{\n  "name": "全能助手",\n  "short_name": "全能助手",\n'
    '  "description": "工作与情感双人格 AI 助手",\n  "start_url": "/",\n'
    '  "display": "standalone",\n  "background_color": "#F7F8FA",\n'
    '  "theme_color": "#0F766E",\n  "icons": [\n'
    '    { "src": "' + svg + '", "sizes": "any", "type": "image/svg+xml", "purpose": "any" }\n  ]\n}\n')
io.open(os.path.join(OUT, 'manifest.webmanifest'), 'w', encoding='utf-8', newline='').write(manifest)

# 3. sw.js：从 CORE 缓存数组去掉 icons 项
sw = io.open(os.path.join(SRC, 'sw.js'), encoding='utf-8').read()
# 把 "/icons/xxx" 形式的缓存项从数组里剔除
sw = re.sub(r',\s*"/icons/[^"]+"', '', sw)
sw = re.sub(r'"/icons/[^"]+"\s*,', '', sw)
io.open(os.path.join(OUT, 'sw.js'), 'w', encoding='utf-8', newline='').write(sw)

# 4. 打包 zip
zip_path = os.path.join(SRC, '_deploy_flat.zip')
if os.path.exists(zip_path):
    os.remove(zip_path)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for name in ('index.html', 'manifest.webmanifest', 'sw.js'):
        z.write(os.path.join(OUT, name), name)

print('flat zip ->', zip_path, os.path.getsize(zip_path), 'bytes')
print('files in pack:', sorted(os.listdir(OUT)))
sw_check = io.open(os.path.join(OUT, 'sw.js'), encoding='utf-8').read()
print('sw references /icons/:', '/icons/' in sw_check)
html_check = io.open(os.path.join(OUT, 'index.html'), encoding='utf-8').read()
print('html references /icons/:', '/icons/' in html_check)
print('html manifest link:', 'manifest.webmanifest' in html_check, '| sw register:', 'serviceWorker.register' in html_check)
