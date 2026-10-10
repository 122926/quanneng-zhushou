# -*- coding: utf-8 -*-
"""加商汤日日新到直连服务商预设"""
import io
P = r'E:\git-library\quanneng-zhushou-web\全能助手.html'
s = io.open(P, encoding='utf-8').read()

def rep(old, new, tag):
    assert old in s, "anchor missing: " + tag
    s2 = s.replace(old, new, 1)
    assert s2 != s, "no change: " + tag
    return s2

# UI option
s = rep(
'''          <option value="qwen">通义（阿里百炼，备用）</option>''',
'''          <option value="qwen">通义（阿里百炼，备用）</option>
          <option value="sensenova">商汤日日新（SenseNova）</option>''',
"sensenova-option"
)

# PROVIDERS 预设
s = rep(
'''    qwen: { base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", model: "qwen-turbo" },''',
'''    qwen: { base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", model: "qwen-turbo" },
    sensenova: { base_url: "https://token.sensenova.cn/v1/chat/completions", model: "sensenova-6.7-flash-lite" },''',
"sensenova-provider"
)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print("patched OK, new size:", len(s))
