# -*- coding: utf-8 -*-
import io
p = r'E:\git-library\quanneng-zhushou-web\全能助手.html'
s = io.open(p, encoding='utf-8').read()
old = 'sensenova-6.7-flash-lite'
new = 'sensenova-6.8-flash-lite'
assert old in s, 'anchor missing'
io.open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new))
print('html updated:', new)
