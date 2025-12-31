import aiohttp
import asyncio
import json
import re
import subprocess
from typing import Optional
from loguru import logger
from config.settings import settings
from core.schema import NewsPayload, SignalAnalysis


class LLMEngine:
    """
    推理引擎：支持本地 Ollama 和云端 DeepSeek
    """

    def __init__(self):
        limit = 50 if settings.LLM_PROVIDER == "deepseek" else settings.MAX_GPU_CONCURRENCY
        self.concurrency_lock = asyncio.Semaphore(limit)

    async def _get_gpu_temperature(self) -> Optional[int]:
        def runner() -> Optional[int]:
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=temperature.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                line = result.stdout.strip().splitlines()[0].strip()
                return int(line)
            except Exception:
                return None

        return await asyncio.to_thread(runner)

    async def _wait_for_safe_temperature(self) -> None:
        limit = settings.GPU_TEMP_LIMIT
        resume = settings.GPU_TEMP_RESUME
        interval = settings.GPU_TEMP_CHECK_INTERVAL
        if limit <= 0 or interval <= 0:
            return
        if resume <= 0 or resume >= limit:
            resume = max(limit - 10, 0)
        temp = await self._get_gpu_temperature()
        if temp is None:
            return
        if temp < limit:
            return
        logger.warning(f"GPU temperature {temp}°C exceeds limit {limit}°C, waiting for cooldown")
        while True:
            await asyncio.sleep(interval)
            temp = await self._get_gpu_temperature()
            if temp is None:
                logger.warning("GPU temperature check failed during cooldown, resuming inference")
                return
            if temp <= resume:
                logger.info(f"GPU temperature {temp}°C is below resume threshold {resume}°C, resuming inference")
                return

    async def _call_deepseek(self, prompt: str, temp: float, max_tokens: int) -> str:
        """
        DeepSeek API 调用 (OpenAI 兼容协议)
        """
        url = f"{settings.DEEPSEEK_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.DEEPSEEK_MODEL_NAME,
            "messages": [
                {"role": "system", "content": "You are a professional financial quantitative analyst."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temp,
            "max_tokens": max_tokens,
            "stream": False,
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"[DeepSeek] Error {resp.status}: {error_text}")
                        return ""
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"[DeepSeek] Connection Failed: {e}")
                return ""

    async def _call_ollama(self, prompt: str, temp: float, max_tokens: int) -> str:
        """
        本地 Ollama 调用
        """
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": settings.LOCAL_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_ctx": settings.CONTEXT_WINDOW,
                "num_predict": max_tokens,
            },
        }
        await self._wait_for_safe_temperature()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=60) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("response", "")
            except Exception as e:
                logger.error(f"[Ollama] Error: {e}")
                return ""

    async def call_model(self, prompt: str, temp: float, max_tokens: int = 2048) -> str:
        """
        统一入口：根据配置分发
        """
        async with self.concurrency_lock:
            if settings.LLM_PROVIDER == "deepseek":
                return await self._call_deepseek(prompt, temp, max_tokens)
            return await self._call_ollama(prompt, temp, max_tokens)

    async def fast_path_filter(self, news: NewsPayload) -> bool:
        """
        快通道：基于标题的快速二分类 (High-Pass Filter)
        修复版：使用中文 Prompt，降低阈值，增加 Debug 日志
        """
        # 1. 极简规则：如果标题包含特定硬关键词，直接通过（旁路机制）
        # 物理直觉：有些信号太明显，不需要过模型
        keywords = ["A股", "股市", "人民币", "央行", "美联储", "利好", "利空", "GDP", "CPI", "监管"
        "芯片", "半导体", "财报", "增持", "回购", "AI", "金融", "算力", "半导体",
        "沪指", "板块", "概念股", "股票", "涨停", "跌停", "回调", "反弹", "市场情绪",
        "融资", "证券", "大盘", "指数", "成交额", "北向", "外资", "特斯拉", "宁德时代"
        ]
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
        res = await self.call_model(prompt, temp=settings.TEMP_FAST, max_tokens=64)
        clean_res = res.strip().upper()
        
        # 修改点：打印原始回复，看看它到底想说什么
        logger.debug(f"Raw Model Response: {clean_res}")
        

        
        # 3. 宽松判别逻辑
        is_relevant = "是" in clean_res or "Yes" in clean_res or "相关" in clean_res
        
        status = "Relevant" if is_relevant else "Noise"
        # 关键：打印出模型到底说了什么，方便调试
        logger.info(
            f"🔍 [Fast Path] Model said: '{clean_res}' -> {status} | Title: {news.title[:30]}..."
        )
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
        你是一个资深量化研究员。你需要分析新闻对A股市场的影响。当讯息中出现股票名字的时候，必须格外注意！说明这个股票是有消息的。

        [Input News]
        {safe_content}

        [Instructions]
        1. **Deep Thinking (关键步骤)**: 
           在输出 JSON 之前，必须先在一个 <think> 标签内进行深度推演。
           - 分析事件的一阶影响（直接受益/受损）。
           - 分析二阶影响（供应链、竞争对手、替代品）。
           - 结合当前宏观环境（流动性、政策周期）评估信号强度。
           - 推导最终的 Score。

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
        # 调高一点温度，实现发散性
        raw_res = await self.call_model(prompt, temp=settings.TEMP_SLOW, max_tokens=max_tokens_limit)
        raw_res = raw_res.replace("```json", "").replace("```", "")
        try:
            match = re.search(r"\{.*\}", raw_res, re.DOTALL)
            if not match:
                raise ValueError("No JSON found")
            json_str = match.group(0)
            data = json.loads(json_str)
            analysis = SignalAnalysis(source_url=news.url, **data)
            return analysis
            
        except Exception as e:
            logger.warning(f"[Slow Path] Parse Error: {e}")
            return None
