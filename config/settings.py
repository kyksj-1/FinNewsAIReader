from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    """
    系统全局状态方程 (Configuration State)
    使用 Pydantic 确保配置的类型安全。
    """
    # 路径配置
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_RAW_DIR: Path = BASE_DIR / "data" / "raw"
    DATA_SIGNAL_DIR: Path = BASE_DIR / "data" / "signals"
    LOG_DIR: Path = BASE_DIR / "logs"


    # --- LLM 核心配置 ---
    LLM_PROVIDER: str = "local"  # 选项: 'local', 'deepseek'

    # Local Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LOCAL_MODEL_NAME: str = "qwen3:8b"

    # DeepSeek Cloud
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL_NAME: str = "deepseek-chat"
    DEEPSEEK_API_KEY: str = ""


    MAX_GPU_CONCURRENCY: int = 1
    CONTEXT_WINDOW: int = 4096
    
    # 推理参数 (Temperature)
    TEMP_FAST: float = 0.2  # 快通道：接近绝对零度，追求确定性
    TEMP_SLOW: float = 0.6  # 慢通道：微量热运动，允许少量联想

    GPU_TEMP_LIMIT: int = 80
    GPU_TEMP_RESUME: int = 65
    GPU_TEMP_CHECK_INTERVAL: int = 5

    # 爬虫配置
    JINA_READER_BASE: str
    MAX_CRAWLER_CONCURRENCY: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# 实例化单例
settings = Settings()

# 自动创建目录
settings.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
