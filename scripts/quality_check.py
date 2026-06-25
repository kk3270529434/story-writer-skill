#!/usr/bin/env python3
"""
西北灵异故事自动质检脚本
基于 SKILL.md v4.0 P0/P1/P2 标准，自动扫描故事文本并输出质检报告。

用法：python scripts/quality_check.py <story_file.md> [--strict] [--output report.json]
"""

import re, sys, json
from pathlib import Path

FORBIDDEN_WORDS = [
    '悄然','蓦然','倏地','璀璨','绚丽','静谧','安详',
    '弥漫着','笼罩在','心中涌起','不禁','不由得','情不自禁地',
    '综上所述','总而言之','值得一提的是','值得注意的是',
    '在遥远的','在很久很久以前','在这个充满',
    '某种意义上来说','亲爱的读者们',
    '所有人都','没人能','永远','这个故事告诉我们',
    '仿佛','宛如','犹如','与此同时','另一方面','镜头切换到',
]

CLICHE_ENDINGS = ['交给警察','一切恢复正常','再也没有发生过','原来是一场梦']
MORALIZING = ['这个故事告诉我们','这让我们明白','人生就是']

NW_PROVINCES = {
    '陕西': ['陕西','西安','宝鸡','咸阳','延安','汉中','秦岭','关中','陕北'],
    '甘肃': ['甘肃','兰州','天水','敦煌','嘉峪关','张掖','河西走廊','祁连','陇东'],
    '宁夏': ['宁夏','银川','吴忠','固原','贺兰山','西海固','西夏'],
    '青海': ['青海','西宁','格尔木','青海湖','柴达木','可可西里','三江源','塔尔寺'],
    '新疆': ['新疆','乌鲁木齐','喀什','伊犁','阿勒泰','天山','昆仑','塔克拉玛干'],
}

NW_DIALECT = [
    '咋咧','谝','麻达','攒劲','孽障','尕','巴扎','嫽','咥','瞀乱',
    '干散','乜贴','攒帮子','阿么了','毕咧','日眼','浪','谝传子',
    '劳道','皮牙子','好家伙','你琢磨琢磨','咱说','可倒好','谁知道呢',
]

NW_SENSORY = ['黄土','窑洞','戈壁','沙漠','草原','雪山','黄河','羊肉','馕','面','茶','唢呐','秦腔','巴扎','古玩','青铜']

REQUIRED_CHARS = ['马老三']
CORE_CHARS = ['刘一','陈婆']

def load_text(fp): return Path(fp).read_text(encoding='utf-8')
def count_zh(t): return len(re.findall(r'[一-鿿]', t))

def check_opening(text):
    chars = list(text[:800])
    signals = ['不对劲','奇怪','不对','怎么','为什么','死','血','哭','怕','吓','鬼','怪','没了','不见了','突然','那天晚上','谁知道']
    found = [s for s in signals if s in text[:600]]
    return {'check':'开篇300字内悬念钩子','passed':len(found)>=1,'detail':f"检测到{len(found)}个钩子信号"}

def check_ending(text):
    cliches = [c for c in CLICHE_ENDINGS if c in text]
    morals = [m for m in MORALIZING if m in text]
    return {'check':'结局反转/余味','passed':len(cliches)==0 and len(morals)==0,'detail':f"俗套:{cliches or '无'} 说教:{morals or '无'}"}

def check_forbidden(text):
    hits = {w: text.count(w) for w in FORBIDDEN_WORDS if w in text}
    total = sum(hits.values())
    return {'check':'一级禁令词','passed':total==0,'detail':f"命中{total}处" + (f":{hits}" if hits else "")}

def check_nw_region(text):
    found = []
    for prov, kws in NW_PROVINCES.items():
        for kw in kws:
            if kw in text:
                found.append(prov)
                break
    unique = list(set(found))
    return {'check':'西北地域绑定','passed':len(unique)>=1,'detail':f"涉及省份:{unique or '无'}"}

def check_characters(text):
    present = [c for c in REQUIRED_CHARS + CORE_CHARS if c in text]
    core_ok = any(c in text for c in CORE_CHARS)
    return {'check':'固定角色出场','passed':'马老三' in text and core_ok,'detail':f"出场:{present}"}

def check_dialect(text):
    found = [(w, text.count(w)) for w in NW_DIALECT if w in text]
    return {'check':'西北方言融入','passed':len(found)>=3,'detail':f"使用{len(found)}种方言词"}

def check_sensory(text):
    found = [w for w in NW_SENSORY if w in text]
    return {'check':'西北感官细节','passed':len(found)>=2,'detail':f"感官词:{found[:8]}"}

def check_de_density(text):
    chars = count_zh(text)
    de = text.count('的')
    d = de/max(chars,1)*100
    return {'check':"'的'字密度",'passed':d<4.0,'detail':f"密度{d:.1f}%（{de}/{chars}），阈值4.0%"}

def check_details(text):
    years = len(re.findall(r'(19|20)\d{2}年', text))
    prices = len(re.findall(r'\d+块|\d+元|\d+万', text))
    return {'check':'具体细节','passed':years+prices>=2,'detail':f"年份{years}处, 价格{prices}处"}

def run_all(text):
    results = []
    results.append(check_opening(text))
    results.append({'check':'主角三要素','passed':True,'detail':'⚠ 需人工判断'})
    results.append({'check':'核心冲突递进','passed':True,'detail':'⚠ 需人工判断'})
    results.append(check_ending(text))
    results.append({'check':'恐怖强度递增','passed':True,'detail':'⚠ 需人工判断'})
    results.append({'check':'多层反转+角色灰度','passed':True,'detail':'⚠ 需人工判断'})
    results.append({'check':'灵异叙事功能','passed':True,'detail':'⚠ 需人工判断'})
    results.append(check_forbidden(text))
    results.append(check_nw_region(text))
    results.append(check_characters(text))
    results.append(check_dialect(text))
    results.append(check_sensory(text))
    results.append(check_de_density(text))
    results.append(check_details(text))
    return results

def format_report(results, wc, strict=False):
    auto = [r for r in results if '⚠' not in r.get('detail','')]
    passed = sum(1 for r in auto if r['passed'])
    lines = ["="*50,"  西北灵异故事自动质检报告","="*50,
             f"  字数:{wc} | 自动检查:{passed}/{len(auto)}"]
    for i,r in enumerate(results[:7],1):
        s = "✓" if r['passed'] else "✗"
        lines.append(f"  [{s}] P0.{i} {r['check']}: {r['detail']}")
    lines.append("")
    for i,r in enumerate(results[7:],8):
        s = "✓" if r['passed'] else "✗"
        lines.append(f"  [{s}] {r['check']}: {r['detail']}")
    if strict:
        all_pass = all(r['passed'] for r in auto)
        lines.append(f"\n  严格模式: {'PASS' if all_pass else 'FAIL'}")
    lines.append("="*50)
    return '\n'.join(lines)

def main():
    if len(sys.argv) < 2:
        print("用法: python quality_check.py <story.md> [--strict] [--output report.json]")
        sys.exit(1)
    fp = sys.argv[1]
    strict = '--strict' in sys.argv
    out = next((sys.argv[i+1] for i,a in enumerate(sys.argv) if a=='--output' and i+1<len(sys.argv)), None)
    if not Path(fp).exists():
        print(f"错误: 文件不存在 - {fp}")
        sys.exit(1)
    text = load_text(fp)
    wc = count_zh(text)
    results = run_all(text)
    print(format_report(results, wc, strict))
    if out:
        json.dump({'file':fp,'word_count':wc,'results':results}, open(out,'w',encoding='utf-8'), ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
