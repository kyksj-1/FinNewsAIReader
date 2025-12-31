from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from datetime import datetime

class NewsPayload(BaseModel):
    """
    输入态：原始新闻数据
    """
    url: str
    title: str
    content: Optional[str] = None
    source: str = "Unknown"
    fetched_at: datetime = Field(default_factory=datetime.now)

class SignalAnalysis(BaseModel):
    """
    输出态：量化交易信号
    """
    # 思维链 (CoT)
    reasoning: str = Field(..., description="物理/逻辑推导过程")
    
    # 核心指标
    score: int = Field(..., ge=-10, le=10, description="利空(-10)到利好(10)")
    certainty: int = Field(..., ge=0, le=10, description="信号确定性/信噪比")
    
    # 结构化标签
    related_stocks: List[str] = Field(default_factory=list, description="关联标的代码")
    time_horizon: Literal["Short", "Medium", "Long"] = Field(..., description="影响时间尺度")
    
    # 原始引用
    source_url: str

    @field_validator('related_stocks')
    def validate_stock_codes(cls, v):
        # 简单的格式清洗，确保大写
        return [code.upper() for code in v]