# FinNewsMasterV1 - AI辅助金融新闻分析系统

## 写在前面

### 免责声明
本说明由AI提供，不排除有错误或不准确的地方。用户应自行验证信息的准确性。

同时，用户需要注意以下几点：
- 本系统仅用于学习和研究目的，不建议作为实际交易依据。
- 新闻分析结果仅供参考，不构成交易建议。
- 用户应根据自身风险承受能力和交易习惯，合理调整交易策略。

### 提供生成本readme的prompt：

通读我这个AI辅助阅读金融消息项目，这里是涉及到的脚本。
（在此处放上所有脚本的路径） 
 请写一个详细的、面对小白的readme文档(markdown),介绍：

1. 这个项目木的功能和目的

2. 整个项目的workflow是怎样的，先从哪一步开始做起，下一步转到哪里，会读取什么、做了怎样的处理、结果会怎样记录、如何开始、如何停止……等等。附：至少要教会小白读者“应该先运行哪个脚本，然后结果会跑到哪里，然后再运行哪个脚本”

3. 介绍项目的拓展性，如接入别的AI api、从更多的数据源爬取、通过修改prompt来完成不同的功能（此项目目前的ai prompt都是为了股票。可以换别的信息、投资标的）

4. 介绍功能时要引用：此功能的代码是xxx

5. 一图胜千言。用TD图展示工作流程、功能控制、参数调配等。在适当的位置放图片来加进理解。由于markdown不支持丰富的渲染，故符号尽量简洁

6. 指出项目还没有完成的任务（局限性），并给小白留出进一步改进、用好这个项目的空间

以markdown格式，语言为中文，放到项目的根目录下，名字为README.md


## 🎯 项目简介

FinNewsMasterV1 是一个基于AI的金融新闻智能分析系统，专门为量化交易和投资决策设计。它能够自动抓取金融新闻，使用大语言模型进行深度分析，提取交易信号，并生成结构化的投资建议。

### 核心功能
- 📡 **自动新闻监控**：实时监控多个金融新闻源
- 🤖 **AI智能分析**：使用LLM进行双通道分析（快速过滤+深度推理）
- 📊 **信号提取**：识别股票代码、影响程度、时间尺度
- 💾 **数据持久化**：原始数据和信号结果自动保存
- ⚡ **高性能**：异步处理，支持GPU并发推理

## 🚀 快速开始

### 第一步：环境配置

1. **复制环境文件**：
   ```bash
   cp .env.template .env
   ```

2. **配置API密钥**：编辑 `.env` 文件，设置你的DeepSeek API密钥：
   ```
   DEEPSEEK_API_KEY=sk-你的API密钥
   ```

3. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

### 第二步：运行系统

**启动主程序**：
```bash
python main.py
```

### 第三步：查看结果

运行后，系统会自动：
1. 扫描新闻源（每30秒一次）
2. 抓取新闻内容
3. 进行AI分析
4. 保存结果到以下目录：

- **原始数据**：`data/raw/` 目录下保存抓取的原始新闻
- **分析结果**：`data/signals/` 目录下保存JSON格式的信号分析
- **运行日志**：`logs/finnews_master.log` 记录详细运行信息

## 📋 系统架构

### 核心模块

| 模块 | 文件位置 | 功能描述 |
|------|----------|----------|
| **主控模块** | [main.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/main.py) | 系统入口，协调生产者和消费者 |
| **配置管理** | [config/settings.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/config/settings.py) | 全局配置和路径管理 |
| **爬虫模块** | [core/crawler.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/crawler.py) | 异步抓取新闻内容 |
| **AI引擎** | [core/engine.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/engine.py) | LLM推理和分析 |
| **监控模块** | [core/monitor.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/monitor.py) | 新闻源扫描和URL发现 |
| **数据模型** | [core/schema.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/schema.py) | 数据结构和验证 |

### 工作流程

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  新闻监控模块    │    │   爬虫模块      │    │   AI分析引擎    │
│ [core/monitor.py]│───▶│ [core/crawler.py]│───▶│ [core/engine.py] │
│ 扫描RSS源       │    │ 异步抓取内容    │    │ 双通道分析      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  发现新URL      │    │  原始数据保存    │    │  信号结果保存    │
│ (内存中队列)    │    │ data/raw/目录    │    │ data/signals/目录│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 详细处理流程

1. **监控阶段** ([core/monitor.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/monitor.py#L9-L40))
   - 每30秒扫描预设的RSS新闻源
   - 过滤已处理过的URL，避免重复分析
   - 返回新发现的新闻链接

2. **抓取阶段** ([core/crawler.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/crawler.py#L20-L30))
   - 使用Jina Reader服务提取网页内容
   - 异步并发处理，提高效率
   - 自动重试机制，确保稳定性

3. **分析阶段** ([core/engine.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/engine.py#L15-L25))
   - **快速通道**：初步筛选，判断新闻是否值得深度分析
   - **慢速通道**：深度推理，提取交易信号和投资建议
   - GPU温度监控，防止过热

4. **保存阶段** ([main.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/main.py#L105-L115))
   - 原始新闻保存到 `data/raw/`
   - 分析结果保存为JSONL格式到 `data/signals/`

## 🛠 配置说明

### AI提供商配置 ([config/settings.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/config/settings.py#L12-L22))

支持两种AI推理方式：
- **本地推理**：使用Ollama和本地模型
- **云端API**：使用DeepSeek云端服务

```env
# 选择推理方式
LLM_PROVIDER=deepseek  # 或 'local'

# DeepSeek配置
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_MODEL_NAME=deepseek-chat

# Ollama配置
OLLAMA_BASE_URL=http://localhost:11434
LOCAL_MODEL_NAME=qwen3:8b
```

### 性能调优 ([config/settings.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/config/settings.py#L25-L35))

```env
# GPU并发控制
MAX_GPU_CONCURRENCY=2

# 上下文窗口大小
CONTEXT_WINDOW=4096

# 温度参数（控制AI创造性）
TEMP_FAST=0.2  # 快速通道：确定性高
TEMP_SLOW=0.6  # 慢速通道：允许一定创造性
```

## 🔧 扩展性指南

### 1. 接入其他AI API

修改 [core/engine.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/engine.py) 中的 `_call_llm_api` 方法：

```python
async def _call_llm_api(self, prompt: str, temperature: float) -> str:
    if settings.LLM_PROVIDER == "openai":
        # 添加OpenAI支持
        return await self._call_openai_api(prompt, temperature)
    elif settings.LLM_PROVIDER == "claude":
        # 添加Claude支持
        return await self._call_claude_api(prompt, temperature)
    # ... 现有代码
```

### 2. 添加新闻数据源

编辑 [core/monitor.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/monitor.py#L15-L40) 中的 `rss_sources` 列表：

```python
self.rss_sources = [
    # 现有源...
    "https://新的rss源.com/rss",
    "https://另一个新闻源.com/feed",
]
```

### 3. 修改分析目标

当前的Prompt专注于股票分析，你可以修改为其他投资标的：

**加密货币分析**（修改 [core/engine.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/engine.py) 中的Prompt）：
```python
fast_prompt = """分析这条新闻对加密货币市场的影响，特别是BTC、ETH等主要币种..."""
```

**大宗商品分析**：
```python
slow_prompt = """深度分析这条新闻对黄金、原油、铜等大宗商品的价格影响..."""
```

## 📊 输出结果示例

### 原始数据格式 ([core/schema.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/schema.py#L5-L12))
```json
{
  "url": "https://example.com/news",
  "title": "央行降准对市场的影响",
  "content": "新闻内容...",
  "source": "21世纪经济报道",
  "fetched_at": "2024-01-01T12:00:00"
}
```

### 分析结果格式 ([core/schema.py](file:///d:/assignment_2025_autumn/quant_finance/FinNewsMasterV1Gemini/core/schema.py#L15-L35))
```json
{
  "reasoning": "央行降准释放流动性，利好银行股和房地产...",
  "score": 8,
  "certainty": 9,
  "related_stocks": ["601398", "000001", "600036"],
  "time_horizon": "Medium",
  "source_url": "https://example.com/news"
}
```

## ⚠️ 项目局限性

### 当前限制

1. **新闻源有限**：目前主要依赖RSS源，可能错过一些重要新闻
2. **分析深度**：AI分析可能受限于模型的理解能力
3. **实时性**：30秒的扫描间隔可能过长
4. **错误处理**：网络异常时的恢复机制有待加强
5. **数据验证**：缺乏对分析结果的回溯验证

### 改进建议

1. **增加新闻源**：
   - 添加Twitter/X的金融话题监控
   - 接入专业金融数据API（Bloomberg、Reuters）
   - 增加Reddit等社交媒体的情绪分析

2. **增强AI能力**：
   - 使用多模型投票机制提高准确性
   - 添加事实核查和溯源功能
   - 实现学习反馈机制

3. **优化性能**：
   - 实现分布式爬虫
   - 添加缓存机制减少重复分析
   - 优化GPU内存使用

4. **增加功能**：
   - 实时警报推送（邮件、短信、Telegram）
   - 可视化仪表盘
   - 回测系统验证信号有效性

## 🎯 小白进阶指南

### 第一步：理解基础
- 运行系统，观察日志输出
- 查看 `data/raw/` 和 `data/signals/` 中的文件
- 阅读日志理解处理流程

### 第二步：简单修改
- 尝试添加一个新的RSS新闻源
- 修改扫描间隔时间（调整main.py中的sleep时间）
- 测试不同的AI温度参数

### 第三步：深度定制
- 修改Prompt模板适应你的投资策略
- 添加新的数据保存格式（如CSV、数据库）
- 集成到你的交易系统中

### 第四步：扩展开发
- 添加新的新闻源类型（API、爬虫）
- 实现多语言支持
- 开发Web界面方便监控

## 📞 技术支持

如果遇到问题：

1. 检查日志文件 `logs/finnews_master.log`
2. 确认 `.env` 配置正确
3. 验证网络连接和API密钥有效性
4. 检查依赖包是否完整安装

---

** 开始你的AI金融分析之旅吧！**

记住：任何复杂的系统都是从简单的步骤开始的。先运行起来，再逐步优化和扩展。