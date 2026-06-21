# 工作流辅助工具

本目录包含与 story-writer-skill 配合使用的辅助脚本，用于素材收集和预处理。

---

## download.py — 微信公众号文章批量下载

从微信公众号批量下载文章并转为 Markdown 格式，适合收集参考素材和风格样本。

### 依赖

```bash
pip install requests beautifulsoup4 markdownify lxml
```

### 用法

```bash
# 基本用法
python tools/download.py urls.txt

# 指定输出目录和请求间隔
python tools/download.py urls.txt --output ./downloaded --delay 3 5

# 详细日志
python tools/download.py urls.txt -v
```

### urls.txt 格式

每行一个公众号文章链接，`#` 开头表示注释：

```
# 我的素材列表
https://mp.weixin.qq.com/s/xxxxx
https://mp.weixin.qq.com/s/yyyyy
```

### 功能特色

- 提取 cgiDataNew 获得最干净的正文内容
- 自动检测文章状态（已删除/异常）
- 断点续传（`.progress.txt` 记录已下载链接）
- 随机请求间隔避免被限流
- 自动清理广告、图片、SVG、视频标签

---

## clean_stories.py — 公众号导出 Markdown 清洗

清洗从微信公众号导出的 `.md` 文件，去掉所有非故事正文的内容（微信 UI 残留、推广文案、图片链接、CSS 片段等），只保留纯故事正文。

### 用法

```bash
# 默认配置：读取 ./新建文件夹/*.md，输出到 ./cleaned_stories/
python tools/clean_stories.py
```

可以通过修改脚本开头的 `INPUT_DIR` 和 `OUTPUT_DIR` 变量自定义路径。

### 清洗内容

- `<style>...</style>` CSS 块
- 微信互动栏（点赞/在看/分享）
- 推广文案（"前往喜马拉雅收听"等）
- 图片链接（`![](http...)`）
- HTML 标签和实体
- 往期推荐区块
- 多余空行

### 输出

- 清洗后的 `.md` 文件（保留原文件名）
- `_清洗报告.txt`：详细的清洗统计报告

---

## 典型工作流

```
1. 收集链接 → 编辑 urls.txt
2. 下载文章 → python tools/download.py urls.txt -o ./raw_stories
3. 清洗正文 → 修改变量 + python tools/clean_stories.py
4. 获得纯文本素材 → 用于风格蒸馏或直接参考
```
