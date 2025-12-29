from typing import Dict, Any, Optional

class LogsHandler:
    """
    日志处理公共类
    
    功能：
    - 构建状态日志字符串
    - 提供格式化的日志输出
    - 支持不同类型的日志信息
    """
    
    @staticmethod
    def build_status_log(global_index: int, total_count: int, 
                        effective_limit: int, index_mode: str, config_hash: str,
                        start_index: int, state: Dict[str, Any], current_prompt: str, max_iter: int, 
                        random_index: Optional[int] = None) -> str:
        """
        构建状态日志字符串，包含当前索引、总数量、有效循环上限、索引模式、配置哈希、起始索引、当前状态和当前提示词
        
        参数：
            global_index: 当前全局索引
            total_count: 数据总数量
            effective_limit: 有效循环上限
            index_mode: 索引模式
            config_hash: 配置哈希值
            start_index: 用户设置的起始索引
            state: 当前状态字典
            current_prompt: 当前提示词内容
            max_iter: 配置的最大可迭代数
            random_index: 当索引模式为Random时，实际选择的随机索引
        
        返回：
            格式化的状态日志字符串
        """
        # 获取历史信息
        last_mode = state.get("last_mode", "无")
        last_start_index = state.get("last_start_index", "无")
        
        # 计算进度百分比
        progress_percentage = ((global_index + 1) / effective_limit * 100) if effective_limit > 0 else 0
        
        # 计算剩余任务数
        remaining_tasks = effective_limit - (global_index + 1)
        
        if index_mode == "Random":
            # Random模式特殊处理
            status_log = f"""
———自动队列执行日志———
【任务进度: {global_index + 1} / {effective_limit} ({progress_percentage:.1f}%，剩余任务数：{remaining_tasks})】
  当前索引模式: {index_mode}
  随机选择的索引: {random_index}
  执行次数: {global_index}
  配置起始索引位置: {start_index}
  实际最大可迭代数: {effective_limit}
  配置最大可迭代数: {max_iter}
  当前提示词: {current_prompt}
【任务状态】
  是否完成: {'✅ 是' if state.get("is_completed", False) else '⏳ 否'}
  配置Hash: {config_hash[:80]}...
  上次索引模式: {last_mode}
  上次索引起始: {last_start_index}
"""
        else:
            # 其他模式标准格式
            status_log = f"""
———自动队列执行日志———
【任务进度: {global_index + 1} / {effective_limit} ({progress_percentage:.1f}%，剩余任务数：{remaining_tasks})】
  当前索引模式: {index_mode}
  当前索引ID: {global_index}
  配置起始索引位置: {start_index}
  实际最大可迭代数: {effective_limit}
  配置最大可迭代数: {max_iter}
  当前提示词: {current_prompt}
【任务状态】
  是否完成: {'✅ 是' if state.get("is_completed", False) else '⏳ 否'}
  配置Hash: {config_hash[:800]}...
  上次索引模式: {last_mode}
  上次索引起始: {last_start_index}
"""
        return status_log.strip()