# -*- coding: utf-8 -*-
import re, io
P = r'E:\git-library\quanneng-zhushou-web\全能助手.html'
html = io.open(P, encoding='utf-8').read()
m = re.findall(r'<script>(.*?)</script>', html, re.S)
io.open(r'E:\git-library\quanneng-zhushou-web\_check.js', 'w', encoding='utf-8').write(m[-1])
print('checks | PROVIDERS:', html.count('PROVIDERS = {') == 1,
      '| matchProvider:', html.count('function matchProvider') == 1,
      '| dcProvider select:', html.count('id="dcProvider"') == 1,
      '| change handler:', 'dcProvider.addEventListener("change"' in html,
      '| options:', all(x in html for x in ['value="zhipu"', 'value="volc"', 'value="qwen"', 'value="custom"']))
