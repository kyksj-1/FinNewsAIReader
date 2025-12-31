import aiohttp
import asyncio
import json
import re
from typing import Optional
from loguru import logger
from config.settings import settings
from core.schema import NewsPayload, SignalAnalysis

class LLMEngine:
    """
    推理引擎：管理 4060 显存资源与模型交互
    """
    def __init__(self):
        self.api_url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        # 显存是稀缺资源，必须排队访问
        self.gpu_lock = asyncio.Lock() if settings.MAX_GPU_CONCURRENCY == 1 else asyncio.Semaphore(settings.MAX_GPU_CONCURRENCY)

    async def _call_ollama(self, prompt: str, temp: float, max_tokens: int = 2048) -> str:
        """
        底层 API 调用，受 GPU 锁保护
        """
        payload = {
            "model": settings.MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_ctx": settings.CONTEXT_WINDOW,
                "num_predict": max_tokens
            }
        }

        async with self.gpu_lock: # <--- 物理瓶颈：显存锁
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(self.api_url, json=payload, timeout=60) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        return data.get("response", "")
                except Exception as e:
                    logger.error(f"Inference Failure: {e}")
                    return ""


     # 修改 core/engine.py
    async def fast_path_filter(self, news: NewsPayload) -> bool:
        """
        快通道：基于标题的快速二分类 (High-Pass Filter)
        修复版：使用中文 Prompt，降低阈值，增加 Debug 日志
        """
        # 1. 极简规则：如果标题包含特定硬关键词，直接通过（旁路机制）
        # 物理直觉：有些信号太明显，不需要过模型
        keywords = ["A股", "股市", "人民币", "央行", "美联储", "利好", "利空", "GDP", "CPI", "监管"
        "芯片", "半导体", "财报", "增持", "回购", "AI", "金融", "算力", "半导体",
        "沪指", "板块", "概念股", "股票", "涨停", "跌停", "回调", "反弹", "市场情绪"]
        if any(k in news.title for k in keywords):
            logger.info(f"⚡ [Fast Path] Keyword Bypass | {news.title[:20]}...")
            return True

        # 2. LLM 判别
        prompt = f"""
        你是A股量化交易员。判断以下新闻标题是否属于"金融、宏观经济、股市、科技、政策"范畴。
        
        标题："{news.title}"
        
        如果是，请回答"是"。
        如果完全无关（如娱乐、体育、纯八卦、小型社会事件等），请回答"否"。
        只回答一个字。
        """
        
        # 稍微调高一点 temp，让它敢于回答
        res = await self._call_ollama(prompt, temp=0.1, max_tokens=5)
        
        # 清洗输出：去掉标点和空格
        clean_res = res.strip().replace("。", "").replace(".", "")
        
        # 3. 宽松判别逻辑
        is_relevant = "是" in clean_res or "Yes" in clean_res or "相关" in clean_res
        
        status = "Relevant" if is_relevant else "Noise"
        # 关键：打印出模型到底说了什么，方便调试
        logger.info(f"🔍 [Fast Path] Model said: '{clean_res}' -> {status} | Title: {news.title[:30]}...")
        
        return is_relevant

    async def slow_path_analyze(self, news: NewsPayload) -> Optional[SignalAnalysis]:
        """
        慢通道：深度思维链分析 (System 2 Reasoning)
        """
        # 增加 max_tokens，给思考留出空间
        max_tokens_limit = 4096 
        safe_content = news.content[:6000] if news.content else ""
        
        prompt = f"""
        [Role]
        你是一个资深量化研究员。你需要分析新闻对A股市场的影响。

        [Input News]
        {safe_content}

        [Instructions]
        1. **Deep Thinking (关键步骤)**: 
           在输出 JSON 之前，必须先在一个 <think> 标签内进行深度推演。
           - 分析事件的一阶影响（直接受益/受损）。
           - 分析二阶影响（供应链、竞争对手、替代品）。
           - 结合当前宏观环境（流动性、政策周期）评估信号强度。
           - 像解决物理方程一样，推导最终的 Score。

        2. **Output Format**:
           思考结束后，输出严格的 JSON。
           
        [Example Output]
        <think>
        这里写你的深度推理过程...
        1. 事件核心是...
        2. 传导路径是...
        3. 市场预期在于...
        </think>
        {{
            "reasoning": "总结上述思考的简练结论...",
            "score": 7,
            "certainty": 8,
            "related_stocks": ["sh.600XXX"],
            "time_horizon": "Medium"
        }}
        """
        
        # 调高一点 Temperature，增加思维的发散性
        raw_res = await self._call_ollama(prompt, temp=0.8, max_tokens=max_tokens_limit)
        
        try:
            # 解析逻辑升级：先提取 JSON
            match = re.search(r"\{.*\}", raw_res, re.DOTALL)
            if not match:
                raise ValueError("No JSON found")
            
            json_str = match.group(0)
            data = json.loads(json_str)
            
            # 可选：如果你想把 <think> 内容也存下来，可以在这里正则提取
            # think_content = re.search(r"<think>(.*?)</think>", raw_res, re.DOTALL)
            
            analysis = SignalAnalysis(source_url=news.url, **data)
            return analysis
            
        except Exception as e:
            logger.warning(f"[Slow Path] Parse Error: {e}")
            return None
