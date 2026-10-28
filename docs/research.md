# 同类项目调研：网页内容下载与转换（2026 年 10 月）

目的：为 CourseKeep 找出值得借鉴的做法，要求**不依赖大模型**、能在用户自己的电脑上直接部署，依赖安全可靠。

调研范围分两类：

1. 抓取网页、转 Markdown 的工具，例如 Firecrawl。
2. 批量下载、网页归档、课程下载工具，主要参考它们的交互设计。

版本与许可证截至 2026-10-28，每条结论附有来源链接。

## 一句话结论

- **路线不变。** CourseKeep 的路线是：先读静态 HTML，确有需要才启动浏览器；正文用 trafilatura 抽取；不用大模型。这和 Firecrawl、Spider 等主流工具的思路一致，不需要换框架，也不需要引入大模型。
- **Firecrawl 和 Crawl4AI 只借鉴思路，不作为依赖。**
  - Firecrawl：AGPL 许可；自托管要 Redis、Postgres 和单独的 Playwright 服务；历史上多次出现 SSRF 漏洞（服务器被诱导去请求内网地址）。
  - Crawl4AI：核心依赖锁定在一个 litellm 分支，另有 Playwright、patchright、nltk、shapely 等一长串；Docker 服务端有多个 SSRF/RCE 安全公告；许可证在 Apache-2.0 之外加了署名条款。
- **交互上最值得借鉴的四点：**
  1. 失败可以直接处理，参考 ArchiveBox。
  2. 结果离开工具也能浏览的离线索引页，参考 HTTrack 和 ArchiveBox。
  3. 用台账记录已下载内容，重跑时“只取新增”，参考 yt-dlp 的 archive 文件和 moodle-dl。
  4. 下载前预览并勾选，参考 JDownloader、DownThemAll! 和 Firecrawl 的 map。

前三点已在本分支实现，第四点列为下一步。

---

## 1. 抓取 / 转 Markdown 类工具

| 项目 | 许可证 | 是否需要大模型 | 静态请求还是无头浏览器 | 可借鉴的点（都不需要大模型） |
|---|---|---|---|---|
| **Firecrawl** | 主体 AGPL-3.0；SDK 与部分 UI 为 MIT | scrape、crawl、map、batch 不需要；`json`/`summary` 抽取和 Agent 需要 | 多个引擎按质量和所需功能排序，依次回退 | 先用 map 列出 URL 再爬；include/exclude 路径过滤；状态里单独列出被 robots.txt 拦下的链接（`robotsBlocked`）；`onlyMainContent` 其实只是一份 CSS 选择器黑名单 |
| **Crawl4AI** | Apache-2.0，另加署名条款 | Markdown、fit-markdown、BM25、深度爬取不需要；LLM 抽取和 LLM 过滤需要 | 默认 Playwright，纯 HTTP 策略要手动选 | PruningContentFilter：按文本密度、链接密度给内容块打分；每个域名单独限速，遇 429/503 指数退避 |
| **Jina Reader** | 代码 Apache-2.0；ReaderLM-v2 模型 CC-BY-NC（非商用） | 默认不需要；readerlm-v2 输出和图片描述需要 | `x-engine: auto` 能用 curl 就用 curl | `x-target-selector` 指定正文区域；把链接汇总成脚注 |
| **Spider**（Rust） | MIT | 核心不需要 | smart 模式按 HTML 信号打分，超过阈值才开浏览器 | 打分式判断：`__NEXT_DATA__`、`data-reactroot`、`ng-version`、`<noscript>` 里的“请启用 JavaScript”等。MIT 许可，注明出处即可移植 |
| **MarkItDown**（微软） | MIT | 不需要（图片描述可选接 LLM） | — | 在课件或 PDF 旁生成可搜索的 `.md`。可作为可选组件，但核心依赖 magika，会带上 onnxruntime |
| **Docling**（IBM） | 代码 MIT，各模型单独授权 | 不用 LLM，但用本地机器学习模型（torch） | — | 表格多的 PDF 能高保真转换；体积大，仅 CPU 的镜像约 1.7 GB |
| **trafilatura**（在用） | Apache-2.0 | 否 | 仅静态 | 继续使用；可以开放 `favor_recall`/`favor_precision`（偏召回/偏精确）开关 |
| readability-lxml / newspaper4k / goose3 | Apache-2.0 / MIT | 否 | 静态 | readability-lxml 适合当 trafilatura 的后备 |
| ScrapeGraphAI / browser-use | MIT | **必须** | — | 反例：不符合“无大模型”的要求 |

**正文抽取准确率（F 值）：**

- trafilatura 自己的评测，990 篇：trafilatura 0.926，readability-lxml 0.853，newspaper4k 0.803。
- ScrapingHub 基准：trafilatura 0.958。
- 2026 年的 WCXB 基准：在课程索引这类列表页上，trafilatura 只有 0.550。启发式抽取器在列表页和文档页上普遍较弱，所以 CourseKeep 自己按章节收集链接的逻辑仍是核心。

**来源：**

- Firecrawl：[仓库与许可证](https://github.com/firecrawl/firecrawl)、[map](https://docs.firecrawl.dev/features/map)、[crawl](https://docs.firecrawl.dev/features/crawl)、[自托管](https://docs.firecrawl.dev/contributing/self-host)、[onlyMainContent 源码](https://github.com/firecrawl/firecrawl/blob/main/apps/api/src/scraper/scrapeURL/lib/removeUnwantedElements.ts)、[CVE-2024-56800](https://www.sentinelone.com/vulnerability-database/cve-2024-56800)、[CVE-2026-32857](https://www.sentinelone.com/vulnerability-database/cve-2026-32857)。
- Crawl4AI：[PyPI 依赖](https://pypi.org/project/crawl4ai/)、[Markdown 生成](https://docs.crawl4ai.com/core/markdown-generation/)、[多 URL 限速](https://docs.crawl4ai.com/advanced/multi-url-crawling/)、[安全公告](https://github.com/unclecode/crawl4ai/security/advisories)、[许可证](https://github.com/unclecode/crawl4ai/blob/main/LICENSE)。
- 其他：[Jina Reader](https://github.com/jina-ai/reader)、[ReaderLM-v2 许可](https://huggingface.co/jinaai/ReaderLM-v2)、[Spider page.rs](https://github.com/spider-rs/spider/blob/main/spider/src/page.rs)、[MarkItDown](https://github.com/microsoft/markitdown)、[Docling](https://github.com/docling-project/docling)、[trafilatura 评测](https://trafilatura.readthedocs.io/en/latest/evaluation.html)、[ScrapingHub 基准](https://github.com/scrapinghub/article-extraction-benchmark)、[WCXB](https://arxiv.org/abs/2605.21097)。

## 2. 批量下载 / 归档 / 课程下载工具的交互

| 工具 | 从链接到文件的流程 | 值得学的地方 | 用户反馈的痛点 |
|---|---|---|---|
| **DownThemAll!** | 选择窗口（勾选、按类型过滤）→ 重命名模板 → 下载管理器 | OneClick：沿用上次的过滤条件，一键开始 | 模板语法难懂；上百个任务一秒内全部失败，没有解释 |
| **JDownloader 2** | LinkGrabber 暂存区（分组、在线检查）→ 确认 → 下载 → 自动解压 | 自动确认倒计时：不打扰用户，又留了干预的机会 | 过滤规则让链接悄悄“消失”，官方都建议改用“视图” |
| **HTTrack** | 5 步向导 → 进度页 | 实时显示字节数、已扫描链接、错误数；可生成 index.html | 错误只记在日志里 |
| **ArchiveBox** | 添加 URL → 快照列表 → 详情页 | 每种保存方式都有成功/失败图标，可按状态筛选，可重试；能导出静态 index.html | 重试类动作有 4 个（Pull/Reset/Redo/Re-Snapshot），容易混淆 |
| **moodle-dl** | 初始化向导 → 运行 → 通知 | 只下新增；通知里列出新文件 | 同一文件每次都重下（#206）；总大小估计在运行中不断变化（#209） |
| **canvas-downloader** | 选课程 → 列出所有文件及大小 → 确认 | 下载前能看到大小；可用忽略文件排除内容 | 文件更新后默认不重下，也不提示 |
| **yt-dlp / gallery-dl** | URL 或 URL 列表 + 输出模板 + archive 文件 | `--simulate` 只预览不下载；archive 文件记录已下载，重跑只取新增 | 模板语法只适合熟手 |
| **Zotero Connector / Obsidian Web Clipper** | 在网页上点一下 → 预览 → 存入资料库 | 浏览器扩展直接和本机 127.0.0.1 上的应用通信 | 下载 PDF 超过 15 秒就报错，其实保存还在继续，报错误导用户 |

**来源：** [DownThemAll!](https://about.downthemall.org/4.0)、[JDownloader LinkGrabber](https://support.jdownloader.org/knowledgebase/article/linkgrabber-how-to-add-links)、[HTTrack](https://www.httrack.com/html/guide.html)、[ArchiveBox](https://github.com/ArchiveBox/ArchiveBox)、[moodle-dl](https://github.com/C0D3D3V/Moodle-DL)、[canvas-downloader](https://github.com/aik2mlj/canvas-downloader)、[yt-dlp](https://github.com/yt-dlp/yt-dlp)、[gallery-dl](https://gdl-org.github.io/docs/configuration.html)、[Zotero](https://www.zotero.org/support/adding_items_to_zotero)、[Obsidian Web Clipper](https://obsidian.md/help/web-clipper/capture)。

## 3. 这些工具的共性

1. **先收集，再确认，再下载。** 同时给熟手一个跳过确认的办法。
2. **两种“过滤”要分开。** 视图筛选只是隐藏行；下载规则决定哪些不下载。被规则跳过的数量必须看得到。
3. **命名模板很强大，但最容易出错。** 给预设选项，不要让用户写语法。
4. **“只取新增”靠台账。** 最大的痛点是台账和实际文件对不上，以及文件更新了却不提示。
5. **失败要能处理。** 要么能筛选、能重试，要么埋在日志里；后者会让用户失去信任。
6. **进度显示计数和正在进行的项目。** 单一的预计剩余时间往往不准。
7. **结果离开工具也能浏览。** 例如生成 index.html。

## 4. 本分支（`ui-ux-polish`）已实现

| 改进 | 借鉴自 | 说明 |
|---|---|---|
| 首页“已保存的课程”：直接读下载文件夹里的 `report.json`，不再依赖浏览器 localStorage | ArchiveBox 快照列表 | 换浏览器、端口变了都不会丢；不重新下载也能查看上次的结果、打开文件夹、检查更新 |
| “检查更新”沿用这门课当初的选项（子页面、引用页、大小上限） | gallery-dl 配置、ArchiveBox 定时任务 | **修复**：以前不带“包含子页面”重跑时，子页面的条目会从索引里消失 |
| 失败可以直接处理：结果页“重试”；超大文件一键“放宽到 500 MB”；取消后“继续下载”；打不开页面时“重试” | ArchiveBox；两份调研都把它排第一 | 每个失败都有解决办法，而不只是一条原因 |
| 下载过程中实时显示文件类型和失败原因 | HTTrack 实时计数 | **修复**：8 个下载线程同时打印时进度行会互相交错，导致条目名错乱、进度少计 |
| 结果页搜索框（按 `/` 聚焦）、每个文件的大小、总大小、用时 | canvas-downloader 显示大小 | 几十上百个文件时能快速找到 |
| 每个课程文件夹生成离线 `index.html`：不含脚本，所有文字转义，用相对链接 | HTTrack “Make an index”、ArchiveBox 静态导出 | 双击就能在任何浏览器里打开；放进 zip 或 U 盘也能直接点 |
| 刷新或关闭标签页不会再“丢掉”下载，重新打开会自动接上；再次启动应用会打开已在运行的那一个 | Zotero、ArchiveBox 的本地应用模式 | **修复**：Windows 上两个实例可能同时监听 8765 端口 |
| “全部重新下载”改为一次性开关，开始后自动关闭；可以把链接拖进页面；手机上筛选条改为横向滑动；屏幕阅读器不再逐条朗读进度 | — | 小的交互细节 |

本分支**没有新增任何第三方依赖**：前端仍是一个 HTML 文件，没有 CDN 和构建步骤；服务端只用 Python 标准库。

## 5. 建议的下一步（都不需要大模型）

按性价比排序。工作量：S 小，M 中。

1. **下载前预览和勾选（M，无新依赖）。** 默认几秒后自动开始，参考 JDownloader 的倒计时，保持“粘贴即下载”。引擎需要加两个参数：`--plan` 只发现链接并输出 JSON，`--only` 只下载选中的项。界面按周和类型分组勾选，例如不要“选读”或某个 90 MB 的数据集。
2. **打分式判断是否需要浏览器（S，无依赖）。** 移植 Spider smart 模式的信号，并把触发原因写进索引，例如“因发现 `__NEXT_DATA__` 而用浏览器打开”。
3. **“这次有什么变化”卡片（S→M）。** 显示新增、已修复、仍失败、早已保存各多少。进一步用 ETag/Last-Modified 识别课件是否更新；Firecrawl 的 changeTracking 有不依赖大模型的 git-diff 模式可参考。
4. **对每个网站礼貌限速（S，纯标准库）。** 遇到 429/503 时遵守 `Retry-After`，退避时加随机抖动，参考 Crawl4AI 的 RateLimiter。
5. **补上 SSRF 防护的一个缺口（S，已在本机验证）。**
   - 现状：重定向的每一跳、robots.txt 请求、浏览器的每个子请求都已经过内网拦截；IPv4 映射地址、6to4、`::`、`0.0.0.0` 都会被拦。
   - 缺口：NAT64 地址 `64:ff9b::/96` 如果内嵌的是内网 IPv4（例如 `64:ff9b::a00:1` 对应 10.0.0.1），Python 的 `ipaddress` 会判为公网地址，3.9 和 3.13 都一样。在使用 NAT64 的纯 IPv6 网络上，这可能被用来访问内网。
   - 修法：在 `is_private()` 里取出内嵌的 IPv4 再判断一次，并加一个回归测试。
6. **在网页里导入 cookies.txt（S–M）。** 只在失败看起来是登录页时才出现，用于 Canvas、Moodle 这类需要登录的课程；cookie 文件不放进课程文件夹或 zip。
7. **一次粘贴多个链接排队，加“全部检查更新”（M）。** 一个学期通常有 4–6 门课。
8. **正文抽取后备链（S，新依赖 readability-lxml，Apache-2.0）。** trafilatura 抽不出时改用 readability-lxml。
9. **可选的 Markdown 伴生文件（M，新依赖 `markitdown[pptx,docx,pdf]`，MIT，带 onnxruntime）。** 让课件和 PDF 可以全文搜索；建议做成可选组件，不放进默认安装包。

## 6. 依赖与安全取舍

- **不引入 Firecrawl。** 原因：AGPL；自托管需要 Redis、Postgres 和 Playwright 服务；出过 SSRF 漏洞，包括重定向到内网、只校验第一个 URL 不校验重定向目标。
- **不引入 Crawl4AI。** 原因：核心依赖锁定在 `unclecode-litellm==1.81.13`，另有 Playwright、patchright、playwright-stealth、nltk、shapely 等；Docker 服务端有多个 SSRF/RCE 公告；许可证附加了署名条款。
- **不用 Jina ReaderLM-v2。** 模型是非商用许可。
- **Docling 只适合做可选的“高保真 PDF”组件。** 它需要 torch，体积大。
- **上面两个项目出过的那几类漏洞，CourseKeep 已经覆盖：**
  - 每一跳重定向都检查是否指向内网，不只是第一个 URL；
  - 浏览器的每个子请求也走同一检查；
  - 网页应用只监听 127.0.0.1，只响应自己页面发来的请求；
  - 不保存可执行文件。

  剩下的 NAT64 缺口见第 5 节第 5 条。

## 7. 关于“直接部署”

- **现状。** 已有 Windows 和 macOS 的打包应用（不需要装 Python），从源码运行是 `python scripts/app.py`。整个过程不需要大模型，也不需要任何 API key；只有作为 Agent Skill 使用时，才需要 Claude Code 或 Codex 这类智能体。
- **不建议把网页应用直接开放到局域网或公网。** 它会去抓取任何提交给它的 URL，开放出去就成了 SSRF 跳板。比如把一个内网地址当作“课程”提交，就能读取内网页面再打包下载。Firecrawl 和 Crawl4AI 的 CVE 正是这类问题。
- **如果要在服务器或 NAS 上跑，有两种稳妥做法：**
  - 做一个只发布到宿主机 127.0.0.1 的 Docker 镜像，即 `-p 127.0.0.1:8765:8765`；
  - 加访问令牌，并对局域网访问禁用“内网课程放行”。

  需要的话可以作为下一步来做。
