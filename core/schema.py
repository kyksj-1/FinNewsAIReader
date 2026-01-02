from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal, Union
from datetime import datetime
import math

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
    # 允许 float 输入，通过 validator 转 int
    score: Union[int, float] = Field(..., description="利空(-10)到利好(10)")
    certainty: Union[int, float] = Field(..., description="信号确定性/信噪比")
    confidence_range: Optional[List[Union[int, float]]] = Field(default=None, description="置信区间 [min, max]")
    
    # 结构化标签
    related_stocks: List[str] = Field(default_factory=list, description="关联标的代码")
    # 放宽类型定义，通过 validator 清洗
    time_horizon: str = Field(..., description="影响时间尺度: Short, Medium, Long")
    
    # 原始引用
    source_url: str

    @field_validator('related_stocks')
    def validate_stock_codes(cls, v):
        # 简单的格式清洗，确保大写
        return [code.upper() for code in v]

    @field_validator('score', 'certainty', mode='before')
    def parse_int_fields(cls, v):
        """
        容错处理：将 float 转为 int，四舍五入
        """
        if isinstance(v, float):
            return int(round(v))
        if isinstance(v, str):
            try:
                return int(float(v))
            except:
                return v
        return v

    @field_validator('confidence_range', mode='before')
    def parse_confidence_range(cls, v):
        if not v:
            return None
        new_list = []
        for item in v:
            if isinstance(item, (float, str)):
                try:
                    new_list.append(int(round(float(item))))
                except:
                    new_list.append(item)
            else:
                new_list.append(item)
        return new_list

    @field_validator('time_horizon', mode='before')
    def normalize_time_horizon(cls, v):
        """
        模糊匹配清洗 time_horizon
        """
        if not isinstance(v, str):
            return "Medium"  # 默认值
            
        v_upper = v.upper()
        
        # 优先级匹配
        if "SHORT" in v_upper or "INTRADAY" in v_upper or "DAY" in v_upper or "HOUR" in v_upper:
            return "Short"
        if "LONG" in v_upper or "YEAR" in v_upper or "MONTH" in v_upper:
            return "Long"
        if "MEDIUM" in v_upper or "WEEK" in v_upper:
            return "Medium"
            
        # 如果都匹配不上，默认 Medium
        return "Medium"
    
    @model_validator(mode='after')
    def validate_ranges(self):
        """
        最后的数据范围校验
        """
        # Score 截断
        if self.score < -10: self.score = -10
        if self.score > 10: self.score = 10
        
        # Certainty 截断
        if self.certainty < 0: self.certainty = 0
        if self.certainty > 10: self.certainty = 10
        
        return self
