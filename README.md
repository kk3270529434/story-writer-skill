# Story Writer Skill — 深夜小茶馆风格短篇故事创作

> 基于 143 篇"深夜小茶馆"杨湃故事蒸馏，可生成符合口语化电台叙事风格的灵异/民间传说/都市怪谈短篇故事。**兼容任意大模型。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v2.6-blue)]()

---

## 简介

这是一个**跨模型兼容的故事创作技能包**，专为**灵异/恐怖/民间传说类短篇故事**创作设计。它通过"风格蒸馏 → 规则提取 → 可执行指令"的方法论，将一位资深音频节目主播的创作风格转化为大模型可遵循的精细规则。

v2.6 全量优化重点解决了「生成故事平淡无聊、缺乏故事张力、跨模型适配性差、创作流程虚化」四大核心问题。

### 能力范围

- 🔮 撞鬼/凶宅、精怪/仙家、都市怪谈、因果报应、民间传说、奇术秘法
- 🎯 输出格式：公众号故事、音频节目文稿、民间怪谈写作
- 📏 篇幅：单集短篇(2000-3500字)、上下集(4000-6000字)、长篇连载(6000-10000字)
- 🏮 地域/年代自适应：东北/华北/华东/华南/西南 × 清代/建国初期/改革开放/当代
- 🌐 **跨模型兼容**：移除 Claude Code 专属依赖，支持 DeepSeek 等任意大模型

### 核心特色

- **故事性 P0 红线一票否决**：开篇 300 字无悬念、主角无代价、冲突未升级、结局无反转 → 强制重写
- **3幕6节点强制骨架**：每个节点有明确叙事任务、悬念设计和情绪等级，全程无"平铺区"
- **三上三下三级具象标准**：轻度恐怖→生活化缓冲、中度恐怖→黑色幽默、重度恐怖→情绪落地
- **主角三要素强制规则**：表层诉求 + 隐藏心结 + 具象失败代价，缺一不可
- **100 个桥段素材库**：灵异悬念/因果反转/精怪仙家/都市怪谈 4 大类，防剧情同质化
- **法术代价化 + 强度分级**：每个法术标注使用代价、失败反噬，初级法术不可解决终极危机
- **叙事逻辑禁令**：禁止机械降神、主角无逻辑作死、强行圆满结局、反派无动机
- **分步强制校验**：每步有明确输出标准，不达标禁止进入下一步

---

## 目录结构

```
story-writer-skill/
├── SKILL.md                     # 核心技能指令（Claude Code 入口）
├── README.md                    # 本文件
├── LICENSE
├── .gitignore
│
├── assets/                      # 资产文件（创作时加载）
│   ├── opening-templates.md     # 3类10种经典开头模板
│   ├── dialogue-examples.md     # 10 种对话模式范例
│   ├── forbidden-phrases.md     # 精简 TOP20 禁令 + 叙事逻辑禁令
│   ├── ai-detection.md          # AI 味系统性检测指南
│   ├── novel-reference.md       # 法术素材库（代价化 + 强度分级）
│   ├── quality-checklist.md     # P0一票否决 + P1/P2 分级质量清单
│   └── plot-hooks.md            # 🆕 100个民间怪谈桥段素材库
│
├── references/                  # 参考资料（风格蒸馏产物）
│   ├── style-guide.md           # 叙事风格、语言指纹、修辞手法
│   ├── character-arcs.md        # 角色分类、成长弧线、配角配置
│   └── plot-structures.md       # 结构骨架、冲突类型、转折规律
│
├── scripts/                     # 脚本
│   └── convert-to-docx.py       # Markdown → Word 转换工具
│
├── tools/                       # 工作流辅助工具
│   ├── download.py              # 微信公众号文章批量下载 & 转 Markdown
│   ├── clean_stories.py         # 公众号导出 .md 清洗为纯正文
│   └── urls.txt                 # 示例链接文件
│
└── docs/                        # 技能方法论文档
    ├── creation-guide.md        # 技能创建全流程指南
    └── optimization-notes.md    # 技能优化建议
```

---

## 安装

### 前置条件

- [Claude Code](https://claude.com/claude-code) CLI 或 IDE 扩展
- Python 3.8+（仅 `tools/` 和 `scripts/` 需要）

### 方法一：安装为项目级 Skill

```bash
# 克隆到目标项目的 .claude/skills/ 目录
git clone https://github.com/<your-username>/story-writer-skill.git .claude/skills/story-writer
```

### 方法二：安装为用户级 Skill

```bash
# 克隆到用户 .claude/skills/ 目录
git clone https://github.com/<your-username>/story-writer-skill.git ~/.claude/skills/story-writer
```

### 安装 Python 依赖（可选）

```bash
# 如需 Word 导出功能
pip install python-docx

# 如需下载公众号文章
pip install requests beautifulsoup4 markdownify lxml
```

---

## 使用

### 触发 Skill

在 Claude Code 中，只需描述你的创作需求即可触发。例如：

```
帮我写一个东北农村的保家仙故事，90年代背景，3000字左右
```

```
写一篇关于北京高校宿舍楼的都市怪谈，细思极恐型，单集短篇
```

Skill 会引导你完成：
1. **意图确认** → 主题、篇幅、年代、地域、主角、基调、结尾风格
2. **年代考据** → 自动搜索年代锚点（如需）
3. **情节骨架** → 三幕式结构提纲
4. **分步创作** → 开场 → #01-#04 → 收束，每步自检
5. **全局审查** → 对话比/句长/幽默密度/AI味扫描
6. **终审** → P0-P2 分级质量清单

### 使用辅助工具

#### 下载公众号文章作为参考素材

```bash
python tools/download.py tools/urls.txt --output ./downloaded
```

#### 清洗下载的文章（去微信UI垃圾）

```bash
python tools/clean_stories.py
```

#### 将故事导出为 Word 文档

```bash
python scripts/convert-to-docx.py 我的故事.md
```

---

## 技能方法论

本 Skill 的创建遵循"蒸馏 → 构建 → 迭代"三阶段流程：

1. **风格蒸馏**：通读 143 篇样本 → 分层分析叙事风格/语言指纹/角色塑造/情节结构/情感曲线
2. **Skill 构建**：将蒸馏结果转化为可执行指令 + 资产库 + 自检清单
3. **人机协同迭代**：生成 → 人工修改 → 差异分析 → 规则转化 → 回归验证

详见 [docs/creation-guide.md](docs/creation-guide.md)。

---

## 贡献

欢迎提交 Issue 和 Pull Request。主要贡献方向：

- 新开篇/对话模板
- 禁用词扩展
- 质量清单补充
- 新法术/民俗知识库条目

---

## 许可

MIT License — 详见 [LICENSE](LICENSE)。

---

## 致谢

- 风格样本来源：「深夜小茶馆」节目
- 参考小说素材：苗疆蛊事Ⅱ、茅山守尸人、走阴人、黄河捞尸人等 16 部灵异小说
