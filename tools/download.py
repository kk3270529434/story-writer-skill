#!/usr/bin/env python3
"""
微信公众号文章批量下载 & 转 Markdown 工具 (v2)

技术参考：融合 wechat-article-exporter 的 DOM 清洗策略
  - 移除 #js_content 的 style 属性（微信默认隐藏，JS 动态显示）
  - 清理广告区域 (#js_top_ad_area, #content_bottom_area 等)
  - 处理 data-src 懒加载图片
  - 清理所有 script 标签
  - 验证下载状态（区分「已删除」「异常」「成功」）

用法：
  python download.py urls.txt
  python download.py urls.txt --output ./md --delay 3 5 --retry 3
"""

import argparse
import html as html_mod
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from random import uniform
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md

# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

WECHAT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Mobile/15E148 MicroMessenger/8.0.38 "
    "NetType/WIFI Language/zh_CN"
)

REQUEST_TIMEOUT = 25
MAX_RETRIES = 3
MIN_DELAY = 3
MAX_DELAY = 5

HEADERS = {
    "User-Agent": WECHAT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Referer": "https://mp.weixin.qq.com/",
}

ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')

# 微信文章状态
ARTICLE_STATUS_SUCCESS = "success"
ARTICLE_STATUS_DELETED = "deleted"
ARTICLE_STATUS_EXCEPTION = "exception"
ARTICLE_STATUS_ERROR = "error"

# 需要从正文中移除的广告/无关元素 ID
AD_ELEMENT_IDS = [
    "js_top_ad_area",
    "js_tags_preview_toast",
    "content_bottom_area",
    "js_pc_qr_code",
    "wx_stream_article_slide_tip",
    "js_share_source",
    "content_tpl",
    "js_image_desc",
    "js_text_desc",
]

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def safe_filename(title: str, max_len: int = 80) -> str:
    name = ILLEGAL_CHARS.sub("_", title).strip().strip("._- ")
    if len(name) > max_len:
        name = name[:max_len].rstrip("._- ")
    return name or "untitled"


def is_wechat_article_url(url: str) -> bool:
    parsed = urlparse(url)
    return "mp.weixin.qq.com" in parsed.netloc


def read_urls(file_path: str) -> List[str]:
    urls = []
    with open(file_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def load_progress(progress_file: str) -> Set[str]:
    if not os.path.exists(progress_file):
        return set()
    with open(progress_file, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_progress(progress_file: str, url: str) -> None:
    with open(progress_file, "a", encoding="utf-8") as f:
        f.write(url + "\n")


def log_error(error_file: str, url: str, reason: str) -> None:
    with open(error_file, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {url}\n  → {reason}\n\n")


# ──────────────────────────────────────────────
# 文章状态检测（参考 wechat-article-exporter 的 validateHTMLContent）
# ──────────────────────────────────────────────

def detect_article_status(soup: BeautifulSoup) -> Tuple[str, Optional[str]]:
    """
    检测微信文章页面状态。
    返回 (状态, 附加信息)。
    状态: success / deleted / exception / error
    """
    js_article = soup.find(id="js_article")
    weui_msg = soup.select_one(".weui-msg")
    msg_block = soup.select_one(".mesg-block")

    if js_article:
        return ARTICLE_STATUS_SUCCESS, None

    if weui_msg:
        title_el = weui_msg.select_one(".weui-msg__title")
        if title_el:
            msg = title_el.get_text(strip=True)
            if "该内容已被发布者删除" in msg or "has been deleted" in msg.lower():
                return ARTICLE_STATUS_DELETED, msg
            return ARTICLE_STATUS_EXCEPTION, msg
        return ARTICLE_STATUS_EXCEPTION, ""

    if msg_block:
        msg = msg_block.get_text(strip=True)
        return ARTICLE_STATUS_EXCEPTION, msg

    return ARTICLE_STATUS_ERROR, None


# ──────────────────────────────────────────────
# 核心：cgiDataNew 提取（Python 实现）
# ──────────────────────────────────────────────

def extract_cgidata_from_html(html: str) -> Optional[dict]:
    """
    尝试从 HTML 中提取 window.cgiDataNew 对象。
    使用 JSON5 兼容解析来处理 JavaScript 对象字面量。

    参考 wechat-article-exporter 的 parseCgiDataNew 思路，
    但在 Python 侧用正则预清洗 + json 解析实现。
    """
    soup = BeautifulSoup(html, "lxml")

    # 找到包含 cgiDataNew 的 script 标签
    target_script = None
    for script in soup.find_all("script"):
        if not script.string:
            continue
        if "window.cgiDataNew" in script.string:
            target_script = script
            break

    if not target_script:
        return None

    code = target_script.string

    # 提取 cgiDataNew = {...} 对象
    match = re.search(r"window\.cgiDataNew\s*=\s*(\{.*?\});\s*(?:\n|$)", code, re.DOTALL)
    if not match:
        return None

    js_obj_str = match.group(1)

    try:
        return _parse_js_object(js_obj_str)
    except Exception:
        return None


def _parse_js_object(js_str: str) -> dict:
    """
    将 JavaScript 对象字面量字符串转为 Python dict。
    处理：
      - 未加引号的 key
      - 单引号字符串
      - undefined → null
      - 尾部逗号
      - 转义序列
    """
    # 1. 先加引号给 key：word: → "word":
    # 注意不能影响已在字符串内的内容
    # 简化处理：先标记所有字符串，给 key 加引号，再恢复
    strings = []

    def save_string(m):
        strings.append(m.group(0))
        return f"\x00STR{len(strings)-1}\x00"

    # 保存双引号字符串
    js_str = re.sub(r'"(?:[^"\\]|\\.)*"', save_string, js_str)
    # 保存单引号字符串
    js_str = re.sub(r"'(?:[^'\\]|\\.)*'", save_string, js_str)
    # 保存模板字符串
    js_str = re.sub(r"`(?:[^`\\]|\\.)*`", save_string, js_str)

    # 给未加引号的 key 加双引号
    js_str = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r'"\1":', js_str)

    # 处理 undefined
    js_str = re.sub(r':\s*undefined\b', ': null', js_str)

    # 去尾部逗号
    js_str = re.sub(r',(\s*[}\]])', r'\1', js_str)

    # 恢复字符串
    def restore_string(m):
        idx = int(m.group(0)[4:-1])
        return strings[idx]

    js_str = re.sub(r'\x00STR\d+\x00', restore_string, js_str)

    return json.loads(js_str)


# ──────────────────────────────────────────────
# 核心：抓取 & 清洗（增强版）
# ──────────────────────────────────────────────

def fetch_article(url: str, timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    """请求文章页面，带微信 UA cookie 预暖。"""
    session = requests.Session()
    session.headers.update(HEADERS)

    # 预暖：访问首页获取 cookie
    try:
        session.get("https://mp.weixin.qq.com/", timeout=timeout)
    except Exception:
        pass

    time.sleep(0.5)
    resp = session.get(url, headers=HEADERS, timeout=timeout)
    resp.encoding = "utf-8"
    resp.raise_for_status()
    return resp


def extract_article_v2(html: str, url: str) -> Tuple[str, dict]:
    """
    增强版文章提取。优先使用 cgiDataNew，后备 DOM 提取。
    返回 (标题, cgiData 或 None)。
    """
    cgi_data = extract_cgidata_from_html(html)

    if cgi_data:
        title = (
            cgi_data.get("title")
            or cgi_data.get("share_title")
            or "未知标题"
        )
    else:
        soup = BeautifulSoup(html, "lxml")
        title = extract_title_from_dom(soup)

    return title, cgi_data


def extract_title_from_dom(soup: BeautifulSoup) -> str:
    """从 DOM 中提取标题（后备方案）。"""
    for selector in [
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "twitter:title"}),
    ]:
        tag = soup.find(selector[0], selector[1])
        if tag and tag.get("content"):
            return tag["content"].strip()

    h_tag = soup.find(id="activity-name")
    if h_tag:
        return h_tag.get_text(strip=True)

    t = soup.find("title")
    if t:
        return t.get_text(strip=True)

    return f"unknown_{int(time.time())}"


def extract_body_html(html: str, cgi_data: Optional[dict]) -> Optional[str]:
    """
    提取正文 HTML。
    优先从 cgiDataNew.content_noencode 提取（最干净），
    否则从 #js_content DOM 提取并清洗。
    """
    # 方法 1：cgiDataNew 的 content_noencode（不含广告和样式）
    if cgi_data and cgi_data.get("content_noencode"):
        raw = cgi_data["content_noencode"]
        if raw.strip():
            # 解码 HTML 实体
            raw = html_mod.unescape(raw)
            # 移除图片标签
            raw = re.sub(r'<img[^>]*/?>', '', raw, flags=re.I)
            return raw

    # 方法 2：DOM 提取 + 深度清洗
    soup = BeautifulSoup(html, "lxml")
    content = soup.find(id="js_content")
    if not content:
        content = soup.find("div", class_="rich_media_content")

    if not content:
        return None

    return clean_content_div(content)


def clean_content_div(content: Tag) -> str:
    """
    深度清洗正文容器，参考 wechat-article-exporter normalizeHtml：
    1. 移除广告和无用元素
    2. 移除 script/style 标签
    3. 移除图片/视频/iframe
    4. 处理懒加载图片
    5. 清理内联样式和空标签
    """
    # 复制一份避免修改原始 soup
    content = BeautifulSoup(str(content), "lxml")

    # 移除广告元素
    for ad_id in AD_ELEMENT_IDS:
        for el in content.find_all(id=ad_id):
            el.decompose()

    # 移除图片、视频、iframe
    for tag in content.find_all(["img", "video", "iframe", "svg", "mpvoice",
                                   "mp-weapp", "mp-miniprogram", "mpcps",
                                   "mpproduct", "mpgongyi", "qqmusic", "mpshop"]):
        tag.decompose()

    # 移除脚本和样式
    for tag in content.find_all(["script", "style", "link"]):
        tag.decompose()

    # 处理懒加载图片（data-src → 文本占位，因为我们要去掉图片）
    for img in content.find_all("img"):
        img.decompose()

    # 移除隐藏元素
    for tag in content.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()

    # 移除所有内联 style
    for tag in content.find_all(True):
        if tag.attrs and "style" in tag.attrs:
            del tag["style"]

    # 移除空标签
    for tag in content.find_all():
        if not tag.get_text(strip=True) and tag.name not in ("br", "hr", "td", "th",
                                                               "tr", "li", "ol", "ul",
                                                               "p", "div", "section"):
            tag.decompose()

    body = str(content)
    body = html_mod.unescape(body)
    return body


def html_to_markdown(html_str: str) -> str:
    """将 HTML 正文转为 Markdown。"""
    markdown = md(
        html_str,
        heading_style="ATX",
        bullets="-",
        strip=["img", "script", "style"],
        escape_underscores=False,
        newline_style="BACKSLASH",
    )
    # 压缩连续空行（保留最多两个换行）
    markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)
    # 清理行内多余空格
    markdown = re.sub(r" {3,}", "  ", markdown)
    return markdown.strip()


def extract_metadata(cgi_data: Optional[dict], soup: BeautifulSoup) -> dict:
    """提取文章元数据。"""
    meta = {"author": "", "nick_name": "", "create_time": ""}

    if cgi_data:
        meta["author"] = cgi_data.get("author", "")
        meta["nick_name"] = cgi_data.get("nick_name", "")
        meta["create_time"] = cgi_data.get("create_time", "")

    # 后备：从 DOM 提取
    if not meta["author"]:
        author_tag = soup.find(id="js_author_name") or soup.find(
            "span", class_="rich_media_meta_text"
        )
        if author_tag:
            meta["author"] = author_tag.get_text(strip=True)

    if not meta["nick_name"]:
        nick_tag = soup.find(id="js_name") or soup.find(
            "strong", class_="rich_media_meta_text"
        )
        if nick_tag:
            meta["nick_name"] = nick_tag.get_text(strip=True)

    return meta


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def download_all(
    urls: List[str],
    output_dir: str,
    min_delay: float,
    max_delay: float,
    max_retries: int,
) -> Tuple[int, int, int]:
    os.makedirs(output_dir, exist_ok=True)

    progress_file = os.path.join(output_dir, ".progress.txt")
    downloaded = load_progress(progress_file)

    error_file = os.path.join(output_dir, "error.log")
    success_count = 0
    fail_count = 0
    skip_count = 0

    urls_to_process = [u for u in urls if u not in downloaded]
    if len(urls_to_process) < len(urls):
        skip_count = len(urls) - len(urls_to_process)
        logger.info("跳过已下载 %d 篇", skip_count)

    logger.info("待下载 %d 篇文章", len(urls_to_process))

    for idx, url in enumerate(urls_to_process, 1):
        logger.info("[%d/%d] %s", idx, len(urls_to_process), url[:100])

        if not is_wechat_article_url(url):
            logger.warning("  非公众号链接，跳过")
            log_error(error_file, url, "非 mp.weixin.qq.com 域名")
            fail_count += 1
            continue

        article_result = None
        last_error = ""

        for attempt in range(1, max_retries + 1):
            try:
                resp = fetch_article(url)
                html = resp.text

                # 检测文章状态
                soup = BeautifulSoup(html, "lxml")
                status, status_msg = detect_article_status(soup)

                if status == ARTICLE_STATUS_DELETED:
                    last_error = f"文章已删除: {status_msg}"
                    logger.warning("  %s", last_error)
                    break  # 已删除，不需要重试

                if status in (ARTICLE_STATUS_EXCEPTION, ARTICLE_STATUS_ERROR):
                    last_error = f"页面状态异常({status}): {status_msg or '未知'}"
                    logger.warning("  %s（第 %d 次）", last_error, attempt)
                    time.sleep(uniform(2, 4))
                    continue

                # 提取文章内容
                title, cgi_data = extract_article_v2(html, url)
                body_html = extract_body_html(html, cgi_data)

                if not body_html:
                    last_error = "无法提取正文内容"
                    logger.warning("  %s（第 %d 次）", last_error, attempt)
                    time.sleep(uniform(2, 4))
                    continue

                metadata = extract_metadata(cgi_data, soup)
                article_result = (title, body_html, metadata)
                break

            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP {e.response.status_code if e.response else '?'}"
                logger.warning("  HTTP 错误（第 %d 次）", attempt)
            except requests.exceptions.ConnectionError:
                last_error = "连接错误"
                logger.warning("  连接错误（第 %d 次）", attempt)
            except requests.exceptions.Timeout:
                last_error = "请求超时"
                logger.warning("  请求超时（第 %d 次）", attempt)
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning("  %s（第 %d 次）", last_error, attempt)

            if attempt < max_retries:
                wait = uniform(3, 8) * attempt
                time.sleep(wait)

        if article_result is None:
            log_error(error_file, url, last_error or "正文提取失败")
            fail_count += 1
            continue

        # 保存 Markdown
        title, body_html, metadata = article_result
        filename = safe_filename(title) + ".md"
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            base = safe_filename(title, max_len=70)
            filename = f"{base}_{int(time.time())}.md"
            filepath = os.path.join(output_dir, filename)

        md_body = html_to_markdown(body_html)

        # 组装最终 Markdown
        parts = [f"# {title}\n"]
        if metadata.get("author"):
            parts.append(f"> 作者：{metadata['author']}")
        if metadata.get("nick_name"):
            parts.append(f"> 公众号：{metadata['nick_name']}")
        if metadata.get("create_time"):
            parts.append(f"> 发布时间：{metadata['create_time']}")
        if any(metadata.values()):
            parts.append("")

        parts.append(md_body)
        parts.append("")

        final_md = "\n".join(parts)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_md)

        save_progress(progress_file, url)
        success_count += 1
        logger.info("  -> %s", filename)

        if idx < len(urls_to_process):
            delay = uniform(min_delay, max_delay)
            time.sleep(delay)

    return success_count, fail_count, skip_count


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="微信公众号文章批量下载 & 转 Markdown (v2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python download.py urls.txt
  python download.py urls.txt --output ./md --delay 3 5 -v
        """,
    )
    parser.add_argument("url_file", help="存放文章链接的文本文件（每行一个，# 注释）")
    parser.add_argument("--output", "-o", default="./output", help="输出目录（默认 ./output）")
    parser.add_argument("--delay", "-d", nargs=2, type=float,
                        default=[MIN_DELAY, MAX_DELAY], metavar=("MIN", "MAX"),
                        help="请求间隔范围（秒，默认 3 5）")
    parser.add_argument("--retry", "-r", type=int, default=MAX_RETRIES,
                        help="最大重试次数（默认 3）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    global logger
    logger = logging.getLogger("wechat-md")
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(message)s", datefmt="%H:%M:%S"
    ))
    logger.handlers.clear()
    logger.addHandler(handler)

    if not os.path.exists(args.url_file):
        logger.error("文件不存在: %s", args.url_file)
        sys.exit(1)

    urls = read_urls(args.url_file)
    if not urls:
        logger.warning("未找到任何有效 URL")
        sys.exit(0)

    logger.info("共读取 %d 个链接", len(urls))

    t0 = time.time()
    success, fail, skip = download_all(
        urls, args.output, args.delay[0], args.delay[1], args.retry
    )
    elapsed = time.time() - t0

    logger.info("=" * 50)
    logger.info("成功: %d 篇", success)
    if skip:
        logger.info("跳过: %d 篇", skip)
    logger.info("失败: %d 篇", fail)
    logger.info("耗时: %.0f 分 %.0f 秒", elapsed // 60, elapsed % 60)
    logger.info("输出: %s", os.path.abspath(args.output))
    if fail:
        logger.info("错误日志: %s", os.path.join(args.output, "error.log"))


if __name__ == "__main__":
    main()
