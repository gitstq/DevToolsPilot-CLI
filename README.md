# 🚀 DevToolsPilot-CLI

> **Lightweight Terminal Chrome DevTools Intelligent Control Engine**
> 轻量级终端Chrome DevTools智能控制引擎

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-success.svg)]()
[![Cross Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

---

**[简体中文](#简体中文)** · **[繁體中文](#繁體中文)** · **[English](#english)** · **[日本語](#日本語)**

---

<a id="简体中文"></a>

## 🎉 项目介绍

DevToolsPilot-CLI 是一款**轻量级终端Chrome DevTools智能控制引擎**，通过Chrome DevTools Protocol（CDP）让开发者和AI编码代理能够在命令行中完全控制浏览器。

### 💡 解决的痛点

- **AI编码代理缺乏浏览器控制能力** — 现有MCP工具链中缺少轻量级的浏览器控制方案
- **现有工具依赖过重** — Puppeteer/Playwright需要Node.js环境，安装复杂
- **终端用户被忽视** — 大量开发者工作在终端环境，缺乏原生TUI工具
- **跨浏览器兼容差** — 多数工具仅支持Chrome，Edge/Brave/Firefox支持不完善

### ✨ 自研差异化亮点

- 🔒 **零外部依赖** — 核心功能仅使用Python标准库，无需安装Node.js
- 🌐 **多浏览器全兼容** — Chrome/Edge/Brave/Firefox自动检测与适配
- 🤖 **MCP协议原生支持** — 可直接接入Claude/Cursor等AI编码助手
- 📊 **精美TUI仪表盘** — ANSI彩色终端界面，实时状态监控
- 📡 **网络流量录制** — HTTP请求录制、过滤、统计、HAR格式导出
- 🖼️ **智能截图引擎** — 视口/全页面/元素级截图

---

<a id="简体中文"></a>

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🔌 **CDP协议客户端** | 通过WebSocket连接Chrome DevTools Protocol，支持命令发送与事件监听 |
| 🌐 **多浏览器管理** | 自动检测Chrome/Edge/Brave/Firefox，跨平台启动与生命周期管理 |
| 🎯 **页面智能控制** | 页面导航、DOM操作、JavaScript执行、Cookie管理、元素等待 |
| 📡 **网络流量监控** | HTTP请求录制、URL模式过滤、按域名/方法/状态码统计、HAR导出 |
| 📋 **控制台日志捕获** | 实时捕获console.log/warn/error/info，支持级别过滤与日志流 |
| 🤖 **MCP协议服务器** | stdio传输，JSON-RPC 2.0，提供8个AI可调用的工具接口 |
| 🖥️ **TUI交互仪表盘** | ANSI彩色输出、实时状态面板、进度条、ASCII横幅 |
| 📸 **截图引擎** | 视口截图、全页面截图、元素截图，PNG/JPEG格式，Base64输出 |

---

## 🚀 快速开始

### 📋 环境要求

- **Python** 3.8 或更高版本
- **浏览器**（任选其一）：Chrome / Edge / Brave / Firefox
- **操作系统**：Windows / macOS / Linux

### 📦 安装

```bash
# 克隆仓库
git clone https://github.com/gitstq/DevToolsPilot-CLI.git
cd DevToolsPilot-CLI

# 安装（零外部依赖）
pip install -e .

# 可选：安装WebSocket优化库
pip install websockets
```

### 🏃 快速运行

```bash
# 检测系统中已安装的浏览器
devtools-pilot detect

# 启动浏览器并开启远程调试端口
devtools-pilot launch --browser chrome --port 9222

# 在另一个终端中启动MCP服务器（供AI编码助手使用）
devtools-pilot mcp --port 9222

# 检查页面信息
devtools-pilot inspect --action info --port 9222

# 截取页面截图
devtools-pilot screenshot --type full --output page.png --port 9222

# 监控网络流量（持续60秒）
devtools-pilot monitor --duration 60 --summary --port 9222

# 执行JavaScript代码
devtools-pilot eval "document.title" --port 9222
```

---

## 📖 详细使用指南

### 🔧 浏览器管理

```bash
# 自动检测并启动默认浏览器
devtools-pilot launch

# 指定浏览器和端口
devtools-pilot launch --browser edge --port 9333

# 无头模式启动
devtools-pilot launch --browser chrome --headless --port 9222

# 检测已安装的浏览器
devtools-pilot detect
```

### 🤖 MCP服务器（AI集成）

DevToolsPilot-CLI内置MCP协议服务器，可直接接入支持MCP的AI编码助手（如Claude Desktop、Cursor等）。

**配置示例（Claude Desktop `claude_desktop_config.json`）：**

```json
{
  "mcpServers": {
    "devtools-pilot": {
      "command": "devtools-pilot",
      "args": ["mcp", "--port", "9222"]
    }
  }
}
```

**可用MCP工具：**

| 工具名 | 描述 |
|--------|------|
| `navigate` | 导航到指定URL |
| `screenshot` | 截取页面截图 |
| `execute_js` | 执行JavaScript代码 |
| `get_dom` | 获取页面DOM结构 |
| `click_element` | 点击指定元素 |
| `get_network_requests` | 获取网络请求列表 |
| `get_console_messages` | 获取控制台消息 |
| `get_page_info` | 获取页面基本信息 |

### 📡 网络监控

```bash
# 实时监控网络流量
devtools-pilot monitor --port 9222

# 监控60秒并输出统计摘要
devtools-pilot monitor --duration 60 --summary --port 9222

# 仅监控特定域名的请求
devtools-pilot monitor --filter "api.example.com" --port 9222

# 导出HAR格式
devtools-pilot monitor --duration 120 --export network.har --port 9222
```

### 📸 截图功能

```bash
# 视口截图
devtools-pilot screenshot --type viewport --output viewport.png

# 全页面截图
devtools-pilot screenshot --type full --output fullpage.png

# 元素截图
devtools-pilot screenshot --type element --selector ".hero" --output hero.png

# Base64输出（适用于管道传输）
devtools-pilot screenshot --type viewport --base64
```

### 💻 JavaScript执行

```bash
# 执行表达式
devtools-pilot eval "document.title"

# 执行多行脚本
devtools-pilot eval "const links = document.querySelectorAll('a'); Array.from(links).map(a => ({text: a.textContent, href: a.href}))"
```

---

## 💡 设计思路与迭代规划

### 🎨 设计理念

DevToolsPilot-CLI遵循**「零依赖、全功能、终端优先」**的设计哲学：

1. **零依赖优先** — 核心功能仅依赖Python标准库，降低安装门槛
2. **双WebSocket引擎** — 优先使用`websockets`库，不可用时自动回退到内置`socket+ssl`实现
3. **模块化架构** — 每个功能模块独立解耦，可单独使用
4. **终端原生体验** — TUI仪表盘提供媲美GUI的终端交互体验

### 🗺️ 技术选型原因

| 技术 | 选择原因 |
|------|----------|
| Python | 终端生态最成熟，标准库丰富，AI/ML生态完善 |
| CDP协议 | Chrome/Edge/Brave通用调试协议，功能最全面 |
| MCP协议 | AI编码助手的事实标准协议，生态快速增长 |
| ANSI转义码 | 跨平台终端彩色输出，无需额外依赖 |

### 📅 后续迭代计划

- [ ] 🔄 **SSE传输支持** — MCP服务器增加Server-Sent Events传输方式
- [ ] 📊 **性能分析面板** — 页面加载性能、资源大小、渲染时序分析
- [ ] 🧪 **自动化测试录制** — 录制用户操作生成可回放的测试脚本
- [ ] 🔐 **认证代理支持** — 支持HTTP/HTTPS/SOCKS5代理认证
- [ ] 📱 **移动端远程调试** — 支持Android Chrome远程调试
- [ ] 🎨 **截图标注功能** — 在截图上添加标注、高亮、文字说明

---

## 🤝 贡献指南

我们欢迎并感谢所有形式的贡献！请遵循以下规范：

### 📝 提交规范

使用Angular提交规范：

```
feat: 新增功能
fix: 修复问题
docs: 文档更新
refactor: 代码重构
test: 测试相关
chore: 构建/工具链相关
```

### 🐛 Issue反馈

请提交Issue时包含以下信息：
- 操作系统与Python版本
- 浏览器类型与版本
- 复现步骤与预期行为
- 相关日志输出

### 🔀 PR流程

1. Fork本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m "feat: 添加某个特性"`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交Pull Request

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。

```
MIT License

Copyright (c) 2025 DevToolsPilot-CLI Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

<a id="繁體中文"></a>

## 🎉 專案介紹（繁體中文）

DevToolsPilot-CLI 是一款**輕量級終端Chrome DevTools智慧控制引擎**，透過Chrome DevTools Protocol（CDP）讓開發者和AI編碼代理能夠在命令列中完全控制瀏覽器。

### 💡 解決的痛點

- **AI編碼代理缺乏瀏覽器控制能力** — 現有MCP工具鏈中缺少輕量級的瀏覽器控制方案
- **現有工具依賴過重** — Puppeteer/Playwright需要Node.js環境，安裝複雜
- **終端使用者被忽視** — 大量開發者工作在終端環境，缺乏原生TUI工具
- **跨瀏覽器相容性差** — 多數工具僅支援Chrome，Edge/Brave/Firefox支援不完善

### ✨ 自研差異化亮點

- 🔒 **零外部依賴** — 核心功能僅使用Python標準庫，無需安裝Node.js
- 🌐 **多瀏覽器全相容** — Chrome/Edge/Brave/Firefox自動偵測與適配
- 🤖 **MCP協議原生支援** — 可直接接入Claude/Cursor等AI編碼助手
- 📊 **精美TUI儀表板** — ANSI彩色終端介面，即時狀態監控
- 📡 **網路流量錄製** — HTTP請求錄製、過濾、統計、HAR格式匯出
- 🖼️ **智慧截圖引擎** — 視窗/全頁面/元素級截圖

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🔌 **CDP協議客戶端** | 透過WebSocket連接Chrome DevTools Protocol，支援命令發送與事件監聽 |
| 🌐 **多瀏覽器管理** | 自動偵測Chrome/Edge/Brave/Firefox，跨平台啟動與生命週期管理 |
| 🎯 **頁面智慧控制** | 頁面導航、DOM操作、JavaScript執行、Cookie管理、元素等待 |
| 📡 **網路流量監控** | HTTP請求錄製、URL模式過濾、按域名/方法/狀態碼統計、HAR匯出 |
| 📋 **控制台日誌捕獲** | 即時捕獲console.log/warn/error/info，支援級別過濾與日誌流 |
| 🤖 **MCP協議伺服器** | stdio傳輸，JSON-RPC 2.0，提供8個AI可呼叫的工具介面 |
| 🖥️ **TUI互動儀表板** | ANSI彩色輸出、即時狀態面板、進度條、ASCII橫幅 |
| 📸 **截圖引擎** | 視窗截圖、全頁面截圖、元素截圖，PNG/JPEG格式，Base64輸出 |

---

## 🚀 快速開始

### 📋 環境要求

- **Python** 3.8 或更高版本
- **瀏覽器**（任選其一）：Chrome / Edge / Brave / Firefox
- **作業系統**：Windows / macOS / Linux

### 📦 安裝

```bash
# 克隆倉庫
git clone https://github.com/gitstq/DevToolsPilot-CLI.git
cd DevToolsPilot-CLI

# 安裝（零外部依賴）
pip install -e .

# 可選：安裝WebSocket最佳化庫
pip install websockets
```

### 🏃 快速執行

```bash
# 偵測系統中已安裝的瀏覽器
devtools-pilot detect

# 啟動瀏覽器並開啟遠端除錯連接埠
devtools-pilot launch --browser chrome --port 9222

# 在另一個終端中啟動MCP伺服器（供AI編碼助手使用）
devtools-pilot mcp --port 9222

# 檢查頁面資訊
devtools-pilot inspect --action info --port 9222

# 截取頁面截圖
devtools-pilot screenshot --type full --output page.png --port 9222

# 監控網路流量（持續60秒）
devtools-pilot monitor --duration 60 --summary --port 9222

# 執行JavaScript程式碼
devtools-pilot eval "document.title" --port 9222
```

---

## 📖 詳細使用指南

### 🤖 MCP伺服器（AI整合）

**設定範例（Claude Desktop `claude_desktop_config.json`）：**

```json
{
  "mcpServers": {
    "devtools-pilot": {
      "command": "devtools-pilot",
      "args": ["mcp", "--port", "9222"]
    }
  }
}
```

**可用MCP工具：**

| 工具名 | 描述 |
|--------|------|
| `navigate` | 導航到指定URL |
| `screenshot` | 截取頁面截圖 |
| `execute_js` | 執行JavaScript程式碼 |
| `get_dom` | 取得頁面DOM結構 |
| `click_element` | 點擊指定元素 |
| `get_network_requests` | 取得網路請求列表 |
| `get_console_messages` | 取得控制台訊息 |
| `get_page_info` | 取得頁面基本資訊 |

### 📡 網路監控

```bash
# 即時監控網路流量
devtools-pilot monitor --port 9222

# 監控60秒並輸出統計摘要
devtools-pilot monitor --duration 60 --summary --port 9222

# 匯出HAR格式
devtools-pilot monitor --duration 120 --export network.har --port 9222
```

### 📸 截圖功能

```bash
# 視窗截圖
devtools-pilot screenshot --type viewport --output viewport.png

# 全頁面截圖
devtools-pilot screenshot --type full --output fullpage.png

# 元素截圖
devtools-pilot screenshot --type element --selector ".hero" --output hero.png
```

---

## 💡 設計思路與迭代規劃

### 🎨 設計理念

DevToolsPilot-CLI遵循**「零依賴、全功能、終端優先」**的設計哲學：

1. **零依賴優先** — 核心功能僅依賴Python標準庫，降低安裝門檻
2. **雙WebSocket引擎** — 優先使用`websockets`庫，不可用時自動回退到內建`socket+ssl`實作
3. **模組化架構** — 每個功能模組獨立解耦，可單獨使用
4. **終端原生體驗** — TUI儀表板提供媲美GUI的終端互動體驗

### 📅 後續迭代計畫

- [ ] 🔄 **SSE傳輸支援** — MCP伺服器增加Server-Sent Events傳輸方式
- [ ] 📊 **效能分析面板** — 頁面載入效能、資源大小、渲染時序分析
- [ ] 🧪 **自動化測試錄製** — 錄製使用者操作產生可回放的測試腳本
- [ ] 🔐 **認證代理支援** — 支援HTTP/HTTPS/SOCKS5代理認證
- [ ] 📱 **行動端遠端除錯** — 支援Android Chrome遠端除錯

---

## 🤝 貢獻指南

### 📝 提交規範

```
feat: 新增功能
fix: 修復問題
docs: 文件更新
refactor: 程式碼重構
test: 測試相關
chore: 建構/工具鏈相關
```

### 🔀 PR流程

1. Fork本倉庫
2. 建立特性分支：`git checkout -b feature/amazing-feature`
3. 提交變更：`git commit -m "feat: 新增某個特性"`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交Pull Request

---

## 📄 開源協議

本專案基於 [MIT License](LICENSE) 開源。

---

<a id="english"></a>

## 🎉 Introduction (English)

DevToolsPilot-CLI is a **lightweight terminal Chrome DevTools intelligent control engine** that enables developers and AI coding agents to fully control browsers from the command line via the Chrome DevTools Protocol (CDP).

### 💡 Problems We Solve

- **AI coding agents lack browser control** — Existing MCP toolchains lack lightweight browser control solutions
- **Existing tools are too heavy** — Puppeteer/Playwright require Node.js, complex installation
- **Terminal users are underserved** — Many developers work in terminal environments without native TUI tools
- **Poor cross-browser compatibility** — Most tools only support Chrome, with incomplete Edge/Brave/Firefox support

### ✨ Differentiation Highlights

- 🔒 **Zero External Dependencies** — Core features use only Python standard library, no Node.js required
- 🌐 **Multi-Browser Support** — Auto-detection and adaptation for Chrome/Edge/Brave/Firefox
- 🤖 **Native MCP Protocol** — Direct integration with Claude/Cursor and other AI coding assistants
- 📊 **Beautiful TUI Dashboard** — ANSI-colored terminal interface with real-time status monitoring
- 📡 **Network Traffic Recording** — HTTP request recording, filtering, statistics, HAR export
- 🖼️ **Smart Screenshot Engine** — Viewport/full-page/element-level screenshots

---

## ✨ Core Features

| Feature | Description |
|---------|-------------|
| 🔌 **CDP Protocol Client** | WebSocket connection to Chrome DevTools Protocol with command dispatch and event listening |
| 🌐 **Multi-Browser Manager** | Auto-detect Chrome/Edge/Brave/Firefox, cross-platform launch and lifecycle management |
| 🎯 **Smart Page Control** | Navigation, DOM manipulation, JavaScript execution, Cookie management, element waiting |
| 📡 **Network Monitor** | HTTP request recording, URL pattern filtering, statistics by domain/method/status, HAR export |
| 📋 **Console Capture** | Real-time capture of console.log/warn/error/info with level filtering and log streaming |
| 🤖 **MCP Server** | stdio transport, JSON-RPC 2.0, 8 AI-callable tool interfaces |
| 🖥️ **TUI Dashboard** | ANSI-colored output, real-time status panel, progress bars, ASCII banner |
| 📸 **Screenshot Engine** | Viewport/full-page/element screenshots, PNG/JPEG, Base64 output |

---

## 🚀 Quick Start

### 📋 Requirements

- **Python** 3.8+
- **Browser** (any): Chrome / Edge / Brave / Firefox
- **OS**: Windows / macOS / Linux

### 📦 Installation

```bash
# Clone the repository
git clone https://github.com/gitstq/DevToolsPilot-CLI.git
cd DevToolsPilot-CLI

# Install (zero external dependencies)
pip install -e .

# Optional: Install WebSocket optimization library
pip install websockets
```

### 🏃 Quick Run

```bash
# Detect installed browsers
devtools-pilot detect

# Launch browser with remote debugging
devtools-pilot launch --browser chrome --port 9222

# Start MCP server in another terminal (for AI coding assistants)
devtools-pilot mcp --port 9222

# Inspect page info
devtools-pilot inspect --action info --port 9222

# Take a screenshot
devtools-pilot screenshot --type full --output page.png --port 9222

# Monitor network traffic (60 seconds)
devtools-pilot monitor --duration 60 --summary --port 9222

# Execute JavaScript
devtools-pilot eval "document.title" --port 9222
```

---

## 📖 Detailed Usage Guide

### 🤖 MCP Server (AI Integration)

DevToolsPilot-CLI includes a built-in MCP protocol server for direct integration with MCP-compatible AI coding assistants (Claude Desktop, Cursor, etc.).

**Configuration example (Claude Desktop `claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "devtools-pilot": {
      "command": "devtools-pilot",
      "args": ["mcp", "--port", "9222"]
    }
  }
}
```

**Available MCP Tools:**

| Tool | Description |
|------|-------------|
| `navigate` | Navigate to a URL |
| `screenshot` | Take a page screenshot |
| `execute_js` | Execute JavaScript code |
| `get_dom` | Get page DOM structure |
| `click_element` | Click a specific element |
| `get_network_requests` | Get network request list |
| `get_console_messages` | Get console messages |
| `get_page_info` | Get basic page information |

### 📡 Network Monitoring

```bash
# Real-time network monitoring
devtools-pilot monitor --port 9222

# Monitor for 60 seconds with summary
devtools-pilot monitor --duration 60 --summary --port 9222

# Filter by domain
devtools-pilot monitor --filter "api.example.com" --port 9222

# Export HAR format
devtools-pilot monitor --duration 120 --export network.har --port 9222
```

### 📸 Screenshots

```bash
# Viewport screenshot
devtools-pilot screenshot --type viewport --output viewport.png

# Full page screenshot
devtools-pilot screenshot --type full --output fullpage.png

# Element screenshot
devtools-pilot screenshot --type element --selector ".hero" --output hero.png

# Base64 output (for pipeline use)
devtools-pilot screenshot --type viewport --base64
```

---

## 💡 Design Philosophy & Roadmap

### 🎨 Design Principles

DevToolsPilot-CLI follows the philosophy of **"Zero Dependencies, Full Features, Terminal First"**:

1. **Zero Dependencies First** — Core features rely only on Python standard library
2. **Dual WebSocket Engine** — Prefers `websockets` library, auto-falls back to built-in `socket+ssl`
3. **Modular Architecture** — Each feature module is decoupled and independently usable
4. **Native Terminal Experience** — TUI dashboard provides GUI-like terminal interaction

### 📅 Roadmap

- [ ] 🔄 **SSE Transport** — Add Server-Sent Events transport for MCP server
- [ ] 📊 **Performance Panel** — Page load performance, resource sizes, render timing analysis
- [ ] 🧪 **Test Recording** — Record user actions to generate replayable test scripts
- [ ] 🔐 **Proxy Support** — HTTP/HTTPS/SOCKS5 proxy authentication
- [ ] 📱 **Mobile Debugging** — Android Chrome remote debugging support
- [ ] 🎨 **Screenshot Annotation** — Add annotations, highlights, and text to screenshots

---

## 🤝 Contributing

Contributions of all forms are welcome! Please follow these guidelines:

### 📝 Commit Convention

```
feat: new feature
fix: bug fix
docs: documentation update
refactor: code refactoring
test: test related
chore: build/toolchain related
```

### 🔀 PR Process

1. Fork this repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m "feat: add some feature"`
4. Push the branch: `git push origin feature/amazing-feature`
5. Submit a Pull Request

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<a id="日本語"></a>

## 🎉 プロジェクト紹介（日本語）

DevToolsPilot-CLIは、Chrome DevTools Protocol（CDP）を通じて開発者とAIコーディングエージェントがコマンドラインからブラウザを完全に制御できる**軽量級ターミナルChrome DevToolsインテリジェント制御エンジン**です。

### 💡 解決する課題

- **AIコーディングエージェントのブラウザ制御不足** — 既存のMCPツールチェーンには軽量なブラウザ制御ソリューションが不足
- **既存ツールの依存が重すぎる** — Puppeteer/PlaywrightはNode.js環境が必要でインストールが複雑
- **ターミナルユーザーが軽視されている** — 多くの開発者がターミナル環境で作業しており、ネイティブTUIツールが不足
- **クロスブラウザ互換性の問題** — ほとんどのツールはChromeのみをサポート

### ✨ 差別化ハイライト

- 🔒 **ゼロ外部依存** — コア機能はPython標準ライブラリのみ使用、Node.js不要
- 🌐 **マルチブラウザ対応** — Chrome/Edge/Brave/Firefoxの自動検出と適応
- 🤖 **MCPプロトコルネイティブ対応** — Claude/Cursor等のAIコーディングアシスタントに直接統合可能
- 📊 **美しいTUIダッシュボード** — ANSIカラー端末インターフェース、リアルタイム状態監視
- 📡 **ネットワークトラフィック記録** — HTTPリクエスト記録、フィルタリング、統計、HARエクスポート
- 🖼️ **スマートスクリーンショットエンジン** — ビューポート/全ページ/要素レベルのスクリーンショット

---

## ✨ コア機能

| 機能 | 説明 |
|------|------|
| 🔌 **CDPプロトコルクライアント** | WebSocket経由でChrome DevTools Protocolに接続 |
| 🌐 **マルチブラウザ管理** | Chrome/Edge/Brave/Firefoxの自動検出、クロスプラットフォーム起動 |
| 🎯 **スマートページ制御** | ナビゲーション、DOM操作、JavaScript実行、Cookie管理 |
| 📡 **ネットワークモニター** | HTTPリクエスト記録、URLパターンフィルタリング、統計、HARエクスポート |
| 📋 **コンソールキャプチャ** | console.log/warn/error/infoのリアルタイムキャプチャ |
| 🤖 **MCPサーバー** | stdioトランスポート、JSON-RPC 2.0、8つのAI呼び出し可能ツール |
| 🖥️ **TUIダッシュボード** | ANSIカラー出力、リアルタイム状態パネル、プログレスバー |
| 📸 **スクリーンショットエンジン** | ビューポート/全ページ/要素スクリーンショット、PNG/JPEG、Base64出力 |

---

## 🚀 クイックスタート

### 📋 動作環境

- **Python** 3.8以上
- **ブラウザ**（いずれか）：Chrome / Edge / Brave / Firefox
- **OS**：Windows / macOS / Linux

### 📦 インストール

```bash
# リポジトリをクローン
git clone https://github.com/gitstq/DevToolsPilot-CLI.git
cd DevToolsPilot-CLI

# インストール（ゼロ外部依存）
pip install -e .

# オプション：WebSocket最適化ライブラリ
pip install websockets
```

### 🏃 クイック実行

```bash
# ブラウザ検出
devtools-pilot detect

# ブラウザ起動（リモートデバッグ有効）
devtools-pilot launch --browser chrome --port 9222

# MCPサーバー起動（AIコーディングアシスタント用）
devtools-pilot mcp --port 9222

# ページ情報の検査
devtools-pilot inspect --action info --port 9222

# スクリーンショット
devtools-pilot screenshot --type full --output page.png --port 9222

# ネットワークモニタリング（60秒間）
devtools-pilot monitor --duration 60 --summary --port 9222

# JavaScript実行
devtools-pilot eval "document.title" --port 9222
```

---

## 📖 詳細な使用ガイド

### 🤖 MCPサーバー（AI統合）

**設定例（Claude Desktop `claude_desktop_config.json`）：**

```json
{
  "mcpServers": {
    "devtools-pilot": {
      "command": "devtools-pilot",
      "args": ["mcp", "--port", "9222"]
    }
  }
}
```

### 📡 ネットワークモニタリング

```bash
# リアルタイムモニタリング
devtools-pilot monitor --port 9222

# 60秒間モニタリングしてサマリー出力
devtools-pilot monitor --duration 60 --summary --port 9222

# HAR形式でエクスポート
devtools-pilot monitor --duration 120 --export network.har --port 9222
```

---

## 💡 設計思想とロードマップ

### 🎨 設計原則

1. **ゼロ依存優先** — コア機能はPython標準ライブラリのみに依存
2. **デュアルWebSocketエンジン** — `websockets`ライブラリを優先、不可用時は内蔵`socket+ssl`にフォールバック
3. **モジュラー設計** — 各機能モジュールは独立して使用可能
4. **ネイティブターミナル体験** — TUIダッシュボードでGUIに匹敵する端末インタラクション

### 📅 ロードマップ

- [ ] 🔄 **SSEトランスポート対応** — MCPサーバーにServer-Sent Eventsトランスポートを追加
- [ ] 📊 **パフォーマンス分析パネル** — ページ読み込みパフォーマンス、リソースサイズ分析
- [ ] 🧪 **テスト記録** — ユーザー操作を記録して再生可能なテストスクリプトを生成
- [ ] 🔐 **プロキシ対応** — HTTP/HTTPS/SOCKS5プロキシ認証サポート
- [ ] 📱 **モバイルデバッグ** — Android Chromeリモートデバッグサポート

---

## 🤝 コントリビューション

### 📝 コミット規約

```
feat: 新機能
fix: バグ修正
docs: ドキュメント更新
refactor: コードリファクタリング
test: テスト関連
chore: ビルド/ツールチェーン関連
```

### 🔀 PRプロセス

1. リポジトリをFork
2. フィーチャーブランチを作成：`git checkout -b feature/amazing-feature`
3. 変更をコミット：`git commit -m "feat: 機能を追加"`
4. ブランチをプッシュ：`git push origin feature/amazing-feature`
5. Pull Requestを提出

---

## 📄 ライセンス

このプロジェクトは [MIT License](LICENSE) の下で公開されています。

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/gitstq">gitstq</a>
</p>
