#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清洗公众号导出的 .md 文件，只保留纯故事正文。

用法：python clean_stories.py
输入：./新建文件夹/*.md
输出：./cleaned_stories/*.md + _清洗报告.txt
"""

import re
from pathlib import Path

# ============================================================
# 配置
# ============================================================
INPUT_DIR = Path("./新建文件夹")
OUTPUT_DIR = Path("./cleaned_stories")

# 需要移除的微信交互关键词（整行匹配用）
WECHAT_BOTTOM_KEYWORDS = [
    "点个在看",
    "支持茶馆",
    "深夜小茶馆",  # 底部公众号名（独立成行时）
]

# 需要整行跳过的推广文案关键词
PROMO_KEYWORDS = [
    "前往喜马拉雅收听",
    "喜马拉雅收听",
    "点击**阅读原文**",
    "点击图片故事音频",
    "点击音乐伴读",
    "现已上线喜马",
    "你们要的",
]


def remove_style_blocks(text: str) -> str:
    """删除 <style>...</style> 块（含多行）。"""
    return re.sub(
        r'<style[^>]*>.*?</style>',
        '',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )


def remove_css_line(line: str) -> bool:
    """判断是否为纯 CSS 行，是则返回 True（应删除）。"""
    stripped = line.strip()
    # 行首就是 CSS 选择器模式
    if re.match(r'^\s*\*?\s*\{', stripped):
        return True
    # 包含大段 CSS 规则的特征（选择器 + 大括号 + 属性）
    if re.search(
        r'(max-width|margin|padding|font-family|line-height|text-size-adjust|user-select|white-space|word-wrap|hyphens|box-sizing|border-top)\s*:',
        stripped,
    ):
        # 确保不是误杀正文（正文很少包含这些 CSS 属性词）
        css_score = len(re.findall(r'[{};]', stripped))
        if css_score >= 5:
            return True
    return False


def count_html_tags(line: str) -> int:
    """统计一行中 HTML 标签的数量。"""
    return len(re.findall(r'<[^>]+>', line))


def remove_html_tags(line: str) -> str:
    """移除 HTML 标签和实体。"""
    line = re.sub(r'<[^>]+>', '', line)
    line = re.sub(r'&[a-z]+;|&#\d+;', '', line)
    # 移除零宽字符
    for ch in ['‍', '​', '‌', '﻿']:
        line = line.replace(ch, '')
    return line


def is_image_line(line: str) -> bool:
    """判断该行是否为图片行（应整行删除）。"""
    stripped = line.strip()
    # ![](http...) 或 ![xxx](http...)
    if re.match(r'^\s*!\[.*?\]\(https?://', stripped):
        return True
    # ![](data:image/...)
    if re.match(r'^\s*!\[.*?\]\(data:image/', stripped):
        return True
    # 行只有图片 + 可能的表情/空格
    if re.fullmatch(r'[\s‍]*!\[.*?\]\(https?://[^)]+\)[\s‍]*', stripped):
        return True
    return False


def count_images_in_line(line: str) -> int:
    """统计一行中的图片数量。"""
    return len(re.findall(r'!\[.*?\]\(https?://[^)]+\)', line)) + \
           len(re.findall(r'!\[.*?\]\(data:image/[^)]+\)', line))


def remove_images_from_line(line: str):  # -> (str, int)
    """从行中移除所有图片标记，返回（新行, 移除数量）。"""
    count = 0
    # mmbiz 图片
    mmbiz = len(re.findall(r'!\[.*?\]\(https?://mmbiz\.qpic\.cn[^)]*\)', line))
    line = re.sub(r'!\[.*?\]\(https?://mmbiz\.qpic\.cn[^)]*\)', '', line)
    count += mmbiz
    # SVG data URI 图片
    svg = len(re.findall(r'!\[.*?\]\(data:image/svg\+xml[^)]*\)', line))
    line = re.sub(r'!\[.*?\]\(data:image/svg\+xml[^)]*\)', '', line)
    count += svg
    # 其他 http 图片
    other = len(re.findall(r'!\[.*?\]\(https?://[^)]+\)', line))
    line = re.sub(r'!\[.*?\]\(https?://[^)]+\)', '', line)
    count += other
    return line, count


def should_skip_entire_line(stripped: str) -> bool:
    """判断该行是否应整行跳过。"""
    if not stripped:
        return False  # 空行不在此处理

    # 纯 CSS 行
    if remove_css_line(stripped):
        return True

    # 推广文案
    for kw in PROMO_KEYWORDS:
        if kw in stripped:
            return True

    # "原创 XXX 深夜小茶馆 日期 时间 省份"
    if re.match(r'^\s*原创\s+\S+\s+深夜小茶馆\s+\d{4}-\d{2}-\d{2}', stripped):
        return True

    # "> 原文地址: ..."
    if re.match(r'^\s*>\s*原文地址', stripped):
        return True

    # 纯图片行
    if is_image_line(stripped):
        return True

    # 往期推荐区块中的链接行 [ 【标题】 ](url)
    if re.match(r'^\s*\[\s*$', stripped):  # 单独的 `[`
        return True
    if re.match(r'^\s*】[^\)]*\]\(https?://mp\.weixin', stripped):
        return True

    # 微信互动栏残留（纯图标+文字的交互按钮组合）
    # "阅读 赞 分享 推荐 留言" 模式
    if re.fullmatch(r'[\s阅读赞分享推荐留言]+', stripped):
        return True
    # 底部图标行残留
    if stripped in ['深夜小茶馆', '阅读', '赞', '在看', '分享', '推荐', '留言']:
        return True
    if re.fullmatch(r'[\s\!\[\]\(\)data:image/svg\+xml;,\.\-_a-zA-Z0-9%#=&?+]+', stripped):
        # 纯 SVG data URI 碎片行
        if len(re.findall(r'!\[', stripped)) >= 2:
            return True

    # "点个在看支持茶馆" 等
    for kw in WECHAT_BOTTOM_KEYWORDS:
        if kw in stripped and len(stripped) < 30:
            return True

    # "[阅读原文]" 或纯链接文字
    if stripped in ['[阅读原文]', '[赞]', '[在看]', '[分享]']:
        return True

    # # 行首即是往期推荐链接的特征：全行只有一个链接
    # 【xxx】后面跟 (https://mp.weixin.qq.com/...)
    if re.match(r'^\s*【[^】]+】\s*$', stripped):
        # 可能是往期推荐里的独立标题行
        # 需要看上下文，但这里先保守处理不过滤
        return False

    return False


def collapse_blank_lines(lines):
    """合并多余空行，最多保留一个空行。"""
    result = []
    prev_blank = False
    for line in lines:
        is_blank = (line.strip() == '')
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    # 去首尾空行
    while result and result[0].strip() == '':
        result.pop(0)
    while result and result[-1].strip() == '':
        result.pop(-1)
    return result


def clean_markdown(content: str):  # -> (str, dict)
    """
    清洗单个 md 文件。

    返回: (清洗后文本, 统计信息)
    """
    stats = {
        "original_lines": 0,
        "final_lines": 0,
        "lines_removed": 0,
        "images_removed": 0,
        "html_tags_removed": 0,
    }

    # Step 1: 移除 <style>...</style> 块
    text = remove_style_blocks(content)

    lines = text.splitlines()
    stats["original_lines"] = len(lines)

    # Step 2: 逐行处理
    cleaned = []
    found_wangqi = False  # 遇到"往期推荐"标志

    for line in lines:
        # 已经过了"往期推荐"，跳过所有后续内容
        if found_wangqi:
            continue

        # 检测"往期推荐"
        stripped = line.strip()
        if re.match(r'^\s*往期推荐\s*$', stripped):
            found_wangqi = True
            continue

        # 统计并移除 HTML 标签
        stats["html_tags_removed"] += count_html_tags(line)
        line = remove_html_tags(line)
        stripped = line.strip()

        # 判断是否整行跳过
        if should_skip_entire_line(stripped):
            # 检查是否包含图片
            img_count = count_images_in_line(line)
            stats["images_removed"] += img_count
            continue

        # 处理行内图片（非整行图片的情况）
        line, img_removed = remove_images_from_line(line)
        stats["images_removed"] += img_removed

        # 移除 [阅读原文] 等微信链接标记
        line = line.replace('[阅读原文]', '')
        line = line.replace('[赞]', '')
        line = line.replace('[在看]', '')
        line = line.replace('[分享]', '')

        # 移除残留的微信互动文字（行内）
        line = re.sub(r'!\[data:image[^]]*\]\(data:image/[^)]+\)', '', line)

        # 如果处理完后整行只剩空白
        if line.strip() == '' and stripped != '':
            # 原本有内容的行变空了，说明全是垃圾内容
            continue

        cleaned.append(line)

    # Step 3: 合并多余空行
    cleaned = collapse_blank_lines(cleaned)

    stats["final_lines"] = len(cleaned)
    stats["lines_removed"] = stats["original_lines"] - len(cleaned)

    return "\n".join(cleaned), stats


def process_all_files(input_dir: Path, output_dir: Path):
    """批量处理所有 md 文件并生成报告。"""

    if not input_dir.exists():
        print(f"[ERROR] 输入文件夹不存在 —— {input_dir}")
        return

    md_files = sorted(input_dir.glob("*.md"))
    if not md_files:
        print(f"[ERROR] 在 {input_dir} 中没有找到 .md 文件")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 找到 {len(md_files)} 个 .md 文件，开始清洗...\n")

    report_lines = []
    totals = {
        "files": 0,
        "success": 0,
        "fail": 0,
        "original_lines": 0,
        "final_lines": 0,
        "lines_removed": 0,
        "images_removed": 0,
        "html_tags_removed": 0,
    }

    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            cleaned, stats = clean_markdown(content)

            out_path = output_dir / md_file.name
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(cleaned)

            detail = (
                f"  [OK] {md_file.name}\n"
                f"      {stats['original_lines']} 行 → {stats['final_lines']} 行 | "
                f"删 {stats['lines_removed']} 行, "
                f"{stats['images_removed']} 图, "
                f"{stats['html_tags_removed']} HTML标签"
            )
            report_lines.append(detail)
            print(detail)

            totals["success"] += 1
            totals["original_lines"] += stats["original_lines"]
            totals["final_lines"] += stats["final_lines"]
            totals["lines_removed"] += stats["lines_removed"]
            totals["images_removed"] += stats["images_removed"]
            totals["html_tags_removed"] += stats["html_tags_removed"]

        except Exception as e:
            err = f"  [ERROR] {md_file.name} — 失败: {e}"
            report_lines.append(err)
            print(err)
            totals["fail"] += 1

        totals["files"] += 1

    # ---- 生成报告 ----
    report = []
    report.append("=" * 72)
    report.append("   [REPORT] 公众号故事 MD 清洗报告")
    report.append("=" * 72)
    report.append(f"   输入文件夹 : {input_dir.resolve()}")
    report.append(f"   输出文件夹 : {output_dir.resolve()}")
    report.append(f"   处理文件数 : {totals['files']}（成功 {totals['success']}，失败 {totals['fail']}）")
    report.append(f"   原始总行数 : {totals['original_lines']}")
    report.append(f"   清洗后行数 : {totals['final_lines']}")
    report.append(f"   共删除行数 : {totals['lines_removed']}")
    report.append(f"   共删除图片 : {totals['images_removed']}")
    report.append(f"   共删HTML标签 : {totals['html_tags_removed']}")
    report.append("-" * 72)
    report.append("   各文件详情：")
    report.append("")
    for r in report_lines:
        report.append(r)
    report.append("")
    report.append("=" * 72)

    report_text = "\n".join(report)

    # 终端输出
    print("\n" + report_text)

    # 保存报告文件
    report_path = output_dir / "_清洗报告.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"\n[INFO] 报告已保存至: {report_path}")


if __name__ == "__main__":
    process_all_files(INPUT_DIR, OUTPUT_DIR)
