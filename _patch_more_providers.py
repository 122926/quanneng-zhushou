# -*- coding: utf-8 -*-
"""更新直连服务商预设：新增实测支持CORS的4家，商汤标注仅后端"""
import io
P = r'E:\git-library\quanneng-zhushou-web\全能助手.html'
s = io.open(P, encoding='utf-8').read()

def rep(old, new, tag):
    assert old in s, "anchor missing: " + tag
    s2 = s.replace(old, new, 1)
    assert s2 != s, "no change: " + tag
    return s2

# UI options：商汤标注仅后端，追加4家
s = rep(
'''          <option value="sensenova">商汤日日新（SenseNova）</option>''',
'''          <option value="sensenova">商汤日日新（仅云函数后端）</option>
          <option value="minimax">MiniMax（新用户送额度）</option>
          <option value="stepfun">阶跃星辰（免费模型）</option>
          <option value="qianfan">百度千帆（新用户送额度）</option>
          <option value="lingyi">零一万物</option>''',
"sensenova-option-remark"
)

# PROVIDERS：追加4家
s = rep(
'''    sensenova: { base_url: "https://token.sensenova.cn/v1/chat/completions", model: "sensenova-6.8-flash-lite" },''',
'''    sensenova: { base_url: "https://token.sensenova.cn/v1/chat/completions", model: "sensenova-6.8-flash-lite" },
    minimax: { base_url: "https://api.minimaxi.com/v1/chat/completions", model: "abab6.5s-chat" },
    stepfun: { base_url: "https://api.stepfun.com/v1/chat/completions", model: "step-1-8k" },
    qianfan: { base_url: "https://qianfan.baidubce.com/v2/chat/completions", model: "ernie-4.0-turbo-8k" },
    lingyi: { base_url: "https://api.lingyiwanwu.com/v1/chat/completions", model: "yi-lightning" },''',
"providers-extend"
)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print("patched OK, new size:", len(s))
