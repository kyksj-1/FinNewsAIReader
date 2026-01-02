import json
import re
import numpy as np
from pathlib import Path
from loguru import logger
from core.schema import SignalAnalysis
from config.settings import settings

class SignalCalibrator:
    """
    用历史数据校准LLM的打分偏差
    物理类比:仪器校准曲线
    """
    def __init__(self, persistence_path: Path = None):
        self.persistence_path = persistence_path or (settings.DATA_SIGNAL_DIR / "calibration_history.json")
        self.history = self._load_history()
        
    def _load_history(self) -> list:
        if self.persistence_path.exists():
            try:
                with open(self.persistence_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load calibration history: {e}")
                return []
        return []

    def _save_history(self):
        try:
            with open(self.persistence_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save calibration history: {e}")

    def record(self, signal: SignalAnalysis, actual_return: float, days: int):
        """记录预测和实际收益"""
        record_entry = {
            'score': signal.score,
            'certainty': signal.certainty,
            'predicted': signal.score * signal.certainty / 100,  # 加权分
            'actual': actual_return,
            'horizon': signal.time_horizon,
            'days': days,
            'recorded_at': str(signal.fetched_at if hasattr(signal, 'fetched_at') else "") 
        }
        self.history.append(record_entry)
        self._save_history()
    
    def get_calibrated_score(self, signal: SignalAnalysis) -> float:
        """
        根据历史表现,给出修正后的预期收益
        """
        # 找到历史上相似的信号(score±2, 同time_horizon)
        similar = [h for h in self.history 
                   if abs(h['score'] - signal.score) <= 2 
                   and h['horizon'] == signal.time_horizon]
        
        if len(similar) >= 5:
            # 返回历史平均实际收益
            return float(np.mean([s['actual'] for s in similar]))
        
        # 没有足够历史数据时,返回原始score (归一化到[-1, 1]范围如果score是-10到10)
        # 这里直接返回 raw score / 10 对应收益率预期
        return signal.score / 10.0

    def get_hit_rate(self, score_range: tuple, horizon: str) -> float:
        """
        计算特定分数段的历史准确率 (胜率)
        """
        min_score, max_score = score_range
        relevant = [h for h in self.history 
                    if min_score <= h['score'] <= max_score 
                    and h['horizon'] == horizon]
        
        if not relevant:
            return 0.5  # 默认无信息时为 0.5
        
        # 假设 actual > 0 且 score > 0 算命中，或者 actual < 0 且 score < 0 算命中
        hits = sum(1 for h in relevant if (h['score'] > 0 and h['actual'] > 0) or (h['score'] < 0 and h['actual'] < 0))
        return hits / len(relevant)


def extract_text_features(analysis: SignalAnalysis) -> dict:
    """
    从reasoning中提取可量化的特征
    """
    reasoning = analysis.reasoning.lower()
    
    return {
        # 关键词频率
        'mentions_policy': int('政策' in reasoning or '监管' in reasoning),
        'mentions_earnings': int('业绩' in reasoning or '财报' in reasoning),
        'mentions_risk': int('风险' in reasoning or '不确定' in reasoning),
        
        # 情感强度(简单规则)
        'strong_positive': len(re.findall(r'重大利好|显著|暴涨', reasoning)),
        'strong_negative': len(re.findall(r'重大利空|暴跌|危机', reasoning)),
        
        # 推理链长度(更长的推理可能更可靠)
        'reasoning_length': len(reasoning),
        'reasoning_depth': reasoning.count('一阶') + reasoning.count('二阶'),
        
        # 股票数量(涉及标的越多可能越分散)
        'num_stocks': len(analysis.related_stocks),
    }

def apply_time_decay(signal: SignalAnalysis, hours_since: float) -> float:
    """
    根据新闻发布时间,对score应用衰减
    物理类比:放射性衰减
    """
    if signal.time_horizon == "Short":
        half_life = 12  # 短期信号12小时衰减一半
    elif signal.time_horizon == "Medium":
        half_life = 72  # 3天
    else:
        half_life = 720  # 30天
    
    decay_factor = 0.5 ** (hours_since / half_life)
    return signal.score * decay_factor
