import asyncio
import sys
import aiofiles
from loguru import logger
from config.settings import settings
from core.crawler import AsyncCrawler
from core.engine import LLMEngine
from core.schema import NewsPayload, SignalAnalysis
# main.py 头部增加导入
from core.monitor import NewsMonitor

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(settings.LOG_DIR / "finnews_master.log", rotation="10 MB", level="DEBUG")

class FinNewsPipeline:
    def __init__(self):
        self.crawler = AsyncCrawler()
        self.engine = LLMEngine()
        self.queue = asyncio.Queue(maxsize=100) # 缓冲区大小
        
    async def producer(self, urls: list[str]):
        """
        生产者：负责抓取数据并放入队列
        """
        for url in urls:
            news = await self.crawler.process_url(url)
            if news:
                await self.queue.put(news)
        
        # 放置结束哨兵
        await self.queue.put(None)
        logger.info("📡 Producer finished fetching all URLs.")

    async def consumer(self):
        """
        消费者：从队列取数据，进行 LLM 双流处理
        """
        while True:
            news = await self.queue.get()
            if news is None:
                self.queue.task_done()
                break # 收到哨兵，下班
            
            try:
                # 1. Fast Path (CPU/Light LLM task)
                # 注：虽然用的是同一个LLM，但Token数极少，耗时短
                if await self.engine.fast_path_filter(news):
                    
                    # 2. Slow Path (GPU heavy task)
                    logger.info(f"⚡ Entering Slow Path: {news.title}")
                    analysis = await self.engine.slow_path_analyze(news)
                    
                    if analysis:
                        await self.save_result(analysis)
                        logger.success(f"🎯 Signal Extracted: Score {analysis.score} | {analysis.related_stocks}")
                else:
                    logger.info(f"🗑️ Discarding Noise: {news.title}")

            except Exception as e:
                logger.exception(f"Pipeline Error: {e}")
            finally:
                self.queue.task_done()

    async def save_result(self, analysis: SignalAnalysis):
        """
        保存结果到 JSONL
        """
        file_path = settings.DATA_SIGNAL_DIR / f"signals_{analysis.time_horizon}.jsonl"
        async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
            await f.write(analysis.model_dump_json() + "\n")

    async def run(self, urls: list[str]):
        logger.info("🚀 FinNewsMasterV1 System Launching...")
        logger.info(f"HARDWARE: Max GPU Concurrency = {settings.MAX_GPU_CONCURRENCY}")
        
        # 并发运行生产者和消费者
        producer_task = asyncio.create_task(self.producer(urls))
        consumer_task = asyncio.create_task(self.consumer())
        
        # 等待所有任务完成
        await asyncio.gather(producer_task, consumer_task)
        logger.info("✅ All tasks completed.")


async def main_loop():
    logger.info("🚀 FinNewsMasterV1: AUTO-PILOT MODE ENGAGED")
    
    pipeline = FinNewsPipeline()
    monitor = NewsMonitor()
    
    # 启动消费者任务 (后台一直运行，等待处理数据)
    consumer_task = asyncio.create_task(pipeline.consumer())
    
    try:
        while True:
            # 1. 雷达扫描
            logger.info("📡 Scanning markets for new intelligence...")
            new_urls = await monitor.harvest()
            
            if new_urls:
                # 2. 只有发现新链接时，才启动生产者放入队列
                logger.info(f"📥 Feeding {len(new_urls)} URLs to pipeline...")
                await pipeline.producer(new_urls)
            else:
                logger.info("💤 No new signals. Standing by.")
            
            # 3. 冷却时间 (比如每 60 秒扫一次，避免被封 IP)
            await asyncio.sleep(15)
            
    except KeyboardInterrupt:
        logger.warning("🛑 Manual Stop Signal Received.")
    finally:
        # 优雅关闭：发送空信号给消费者，让它下班
        await pipeline.queue.put(None)
        await consumer_task


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main_loop())
