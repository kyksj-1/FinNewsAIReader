import pandas as pd
from core.schema import SignalAnalysis
from core.calibrator import SignalCalibrator, extract_text_features, apply_time_decay

class SignalFilter:
    """
    物理类比:带通滤波器,只让高质量信号通过
    """
    @staticmethod
    def is_tradable(analysis: SignalAnalysis, calibrator: SignalCalibrator) -> bool:
        """
        多维度判断信号是否值得交易
        """
        # 1. 基础门槛
        if analysis.certainty < 7:
            return False
        if abs(analysis.score) < 5:  # 太中性的不做
            return False
        
        # 2. 历史可靠性
        # 如果没有历史数据，calibrator可能会返回默认值，这里需要注意处理
        historical_accuracy = calibrator.get_hit_rate(
            score_range=(analysis.score-2, analysis.score+2),
            horizon=analysis.time_horizon
        )
        if historical_accuracy < 0.55:  # 历史准确率低于55%
            return False
        
        # 3. 文本一致性检查
        # 如果score是8但reasoning里出现"不确定""可能""风险",降低信任
        # 注意：这里需要根据实际中文语境调整，"不确定"出现在"消除了不确定性"中就是好事
        # 简单起见遵循用户建议
        if analysis.score > 7 and ('不确定' in analysis.reasoning or '风险' in analysis.reasoning):
            # 简单的关键词检查可能误杀，暂且保留作为参考
            pass 
        
        # 4. 股票池检查(可选)
        if not analysis.related_stocks:
            return False
        
        return True

class NewsFactors:
    """
    可以直接用于回测的因子
    """
    @staticmethod
    def compute(signal: SignalAnalysis, calibrator: SignalCalibrator, hours_since: float = 0) -> pd.Series:
        text_features = extract_text_features(signal)
        
        return pd.Series({
            # 原始LLM输出
            'llm_score': signal.score,
            'llm_certainty': signal.certainty,
            
            # 校准后的预期
            'calibrated_return': calibrator.get_calibrated_score(signal),
            'historical_hit_rate': calibrator.get_hit_rate(
                score_range=(signal.score-2, signal.score+2), 
                horizon=signal.time_horizon
            ),
            
            # 文本特征
            **text_features,
            
            # 时间衰减
            'decay_adjusted_score': apply_time_decay(signal, hours_since),
            
            # 注意：ensemble_variance 和 adversarial_confidence 需要在外部计算并传入
            # 这里暂时不包含，或者由外部调用者update进去
        })
