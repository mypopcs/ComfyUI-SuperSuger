import random
from typing import Dict, Any, Tuple


class IndexHandler:
    """
    索引处理公共类
    
    功能：
    - 管理全局索引和索引模式
    - 处理索引步进逻辑
    - 支持多种索引模式：
      * Specified: 从 START_INDEX 开始，执行到 effective_limit 停止（不支持断点续传）
      * From Start: 从 0 开始，执行到 effective_limit 停止（不支持断点续传）
      * Random: 随机索引，仅受 MAX_ITERATION_LIMIT 限制（每次都随机）
      * Auto: 断点续传，从 global_index 记录的位置继续
    """
    
    # 索引模式常量
    MODE_AUTO = "Auto"
    MODE_SPECIFIED = "Specified"
    MODE_FROM_START = "From Start"
    MODE_RANDOM = "Random"
    
    @staticmethod
    def determine_index(state: Dict[str, Any], index_mode: str, 
                       start_index: int, config_hash: str, 
                       total_count: int, save_callback) -> Tuple[int, int]:
        """
        根据索引模式确定当前索引（统一入口）
        
        核心逻辑：
        - Random: 每次都随机（不看 workflow_started）
        - From Start: 首次从 0 开始，后续递增（不看 global_index）
        - Specified: 首次从 START_INDEX 开始，后续递增（不看 global_index）
        - Auto: 检测配置变化，支持断点续传
        
        参数：
            state: 当前持久化状态
            index_mode: 索引模式
            start_index: 用户指定的起始索引
            config_hash: 当前配置哈希值
            total_count: 数据总数量
            save_callback: 保存状态的回调函数
            
        返回：
            (实际执行索引, 显示索引) 的元组
        """
        print(f"[索引确定] 模式: {index_mode}")
        
        # Random 模式：每次都随机
        if index_mode == IndexHandler.MODE_RANDOM:
            return IndexHandler._handle_random_mode(
                state, config_hash, total_count, save_callback
            )
        
        # 检测配置是否改变
        config_changed = IndexHandler._is_config_changed(state, config_hash, index_mode, start_index)
        
        # From Start 模式：配置改变时重置，否则使用临时计数器
        if index_mode == IndexHandler.MODE_FROM_START:
            return IndexHandler._handle_from_start_mode(
                state, config_hash, config_changed, save_callback
            )
        
        # Specified 模式：配置改变时重置到 START_INDEX，否则使用临时计数器
        if index_mode == IndexHandler.MODE_SPECIFIED:
            return IndexHandler._handle_specified_mode(
                state, config_hash, start_index, config_changed, save_callback
            )
        
        # Auto 模式：标准断点续传
        return IndexHandler._handle_auto_mode(
            state, config_hash, config_changed, save_callback
        )
    
    @staticmethod
    def _is_config_changed(state: Dict[str, Any], config_hash: str, 
                          index_mode: str, start_index: int) -> bool:
        """
        检测配置是否改变
        
        检测项：
        1. 配置哈希变化
        2. 索引模式变化
        3. 起始索引变化（仅 Specified 模式）
        4. 任务完成状态
        """
        last_hash = state.get("last_input_hash", "")
        last_mode = state.get("last_mode", "")
        last_start = state.get("last_start_index", -1)
        is_completed = state.get("is_completed", False)
        
        # 配置哈希改变
        if last_hash != config_hash:
            print(f"  → 检测到配置哈希改变")
            return True
        
        # 模式改变
        if last_mode != index_mode:
            print(f"  → 检测到模式改变: {last_mode} → {index_mode}")
            return True
        
        # Specified 模式下起始索引改变
        if index_mode == IndexHandler.MODE_SPECIFIED and last_start != start_index:
            print(f"  → 检测到起始索引改变: {last_start} → {start_index}")
            return True
        
        # 任务已完成
        if is_completed:
            print(f"  → 上次任务已完成")
            return True
        
        return False
    
    @staticmethod
    def _handle_random_mode(state: Dict[str, Any], config_hash: str, 
                           total_count: int, save_callback) -> Tuple[int, int]:
        """
        Random 模式：每次都随机选择索引
        
        特点：
        - 每次执行都重新随机
        - global_index 用作执行次数计数器
        - 允许索引重复
        """
        random_index = random.randint(0, total_count - 1)
        execution_count = state.get("global_index", 0)
        
        print(f"  → Random 模式：随机索引 = {random_index}, 执行次数 = {execution_count}")
        
        # 只在首次执行时初始化状态
        if not state.get("workflow_started", False):
            IndexHandler._update_state(state, {
                "global_index": 0,
                "is_completed": False,
                "workflow_started": True,
                "last_mode": IndexHandler.MODE_RANDOM,
                "last_start_index": -1,
                "last_input_hash": config_hash
            })
            save_callback(state)
        
        return (random_index, execution_count)
    
    @staticmethod
    def _handle_from_start_mode(state: Dict[str, Any], config_hash: str,
                               config_changed: bool, save_callback) -> Tuple[int, int]:
        """
        From Start 模式：从 0 开始，不支持断点续传
        
        逻辑：
        - 配置改变 → 重置为 0
        - 配置未变 → 使用 global_index 递增
        """
        if config_changed:
            print(f"  → From Start 模式：重置为索引 0")
            current_index = 0
            IndexHandler._update_state(state, {
                "global_index": 0,
                "is_completed": False,
                "workflow_started": True,
                "last_mode": IndexHandler.MODE_FROM_START,
                "last_start_index": 0,
                "last_input_hash": config_hash
            })
            save_callback(state)
        else:
            current_index = state.get("global_index", 0)
            print(f"  → From Start 模式：继续执行索引 {current_index}")
        
        return (current_index, current_index)
    
    @staticmethod
    def _handle_specified_mode(state: Dict[str, Any], config_hash: str,
                              start_index: int, config_changed: bool, 
                              save_callback) -> Tuple[int, int]:
        """
        Specified 模式：从 START_INDEX 开始，不支持断点续传
        
        逻辑：
        - 配置改变 → 重置为 START_INDEX
        - 配置未变 → 使用 global_index 递增
        """
        if config_changed:
            print(f"  → Specified 模式：重置为索引 {start_index}")
            current_index = start_index
            IndexHandler._update_state(state, {
                "global_index": start_index,
                "is_completed": False,
                "workflow_started": True,
                "last_mode": IndexHandler.MODE_SPECIFIED,
                "last_start_index": start_index,
                "last_input_hash": config_hash
            })
            save_callback(state)
        else:
            current_index = state.get("global_index", start_index)
            print(f"  → Specified 模式：继续执行索引 {current_index}")
        
        return (current_index, current_index)
    
    @staticmethod
    def _handle_auto_mode(state: Dict[str, Any], config_hash: str,
                         config_changed: bool, save_callback) -> Tuple[int, int]:
        """
        Auto 模式：标准断点续传
        
        逻辑：
        - 配置改变 → 从 0 开始
        - 配置未变 → 从 global_index 继续
        """
        if config_changed:
            print(f"  → Auto 模式：配置改变，从索引 0 开始")
            current_index = 0
            IndexHandler._update_state(state, {
                "global_index": 0,
                "is_completed": False,
                "workflow_started": True,
                "last_mode": IndexHandler.MODE_AUTO,
                "last_start_index": 0,
                "last_input_hash": config_hash
            })
            save_callback(state)
        else:
            current_index = state.get("global_index", 0)
            print(f"  → Auto 模式：断点续传，从索引 {current_index} 继续")
            # 确保工作流标志为 true
            if not state.get("workflow_started", False):
                state["workflow_started"] = True
                save_callback(state)
        
        return (current_index, current_index)
    
    @staticmethod
    def step_index(state: Dict[str, Any], index_mode: str, 
                   current_index: int, total_count: int, 
                   effective_limit: int, config_hash: str, 
                   save_callback) -> bool:
        """
        处理索引步进逻辑
        
        参数：
            state: 当前状态字典
            index_mode: 索引模式
            current_index: 当前索引（或执行次数）
            total_count: 数据总数量
            effective_limit: 有效循环上限
            config_hash: 配置哈希值
            save_callback: 保存状态的回调函数
            
        返回：
            是否应该继续循环（True=继续, False=停止）
        """
        print(f"[步进处理] 当前值: {current_index}")
        
        # Random 模式特殊处理
        if index_mode == IndexHandler.MODE_RANDOM:
            return IndexHandler._step_random_mode(
                state, current_index, effective_limit, config_hash, save_callback
            )
        
        # 常规模式处理
        return IndexHandler._step_normal_mode(
            state, current_index, total_count, effective_limit, 
            config_hash, save_callback
        )
    
    @staticmethod
    def _step_random_mode(state: Dict[str, Any], execution_count: int,
                         effective_limit: int, config_hash: str, 
                         save_callback) -> bool:
        """
        Random 模式的步进逻辑
        
        只检查执行次数，不检查索引位置
        """
        next_count = execution_count + 1
        print(f"  → Random 模式：执行次数 {execution_count} → {next_count}")
        
        # 检查是否达到迭代上限
        if next_count >= effective_limit:
            print(f"  → 达到迭代上限 {effective_limit}，任务完成")
            IndexHandler._update_state(state, {
                "global_index": 0,
                "is_completed": True,
                "workflow_started": False,
                "last_input_hash": config_hash
            })
            save_callback(state)
            return False
        
        # 继续执行
        print(f"  → 继续执行")
        IndexHandler._update_state(state, {
            "global_index": next_count,
            "is_completed": False,
            "workflow_started": True,
            "last_input_hash": config_hash
        })
        save_callback(state)
        return True
    
    @staticmethod
    def _step_normal_mode(state: Dict[str, Any], current_index: int, 
                         total_count: int, effective_limit: int, 
                         config_hash: str, save_callback) -> bool:
        """
        常规模式的步进逻辑
        
        检查索引位置和有效上限
        """
        next_index = current_index + 1
        print(f"  → 下一个索引: {next_index}")
        
        # 情况 1: 完全完成（达到数据总量）
        if next_index >= total_count:
            print(f"  → 完全完成：已处理所有 {total_count} 个数据")
            IndexHandler._update_state(state, {
                "global_index": 0,
                "is_completed": True,
                "workflow_started": False,
                "last_input_hash": config_hash
            })
            save_callback(state)
            return False
        
        # 情况 2: 限制停止（达到 effective_limit）
        elif next_index >= effective_limit:
            print(f"  → 限制停止：达到用户设置的上限 {effective_limit}")
            remaining = total_count - effective_limit
            if remaining > 0:
                print(f"     注意：仍有 {remaining} 个数据未处理")
            IndexHandler._update_state(state, {
                "global_index": next_index,
                "is_completed": False,
                "workflow_started": False,
                "last_input_hash": config_hash
            })
            save_callback(state)
            return False
        
        # 情况 3: 继续执行
        else:
            print(f"  → 继续执行")
            IndexHandler._update_state(state, {
                "global_index": next_index,
                "is_completed": False,
                "workflow_started": True,
                "last_input_hash": config_hash
            })
            save_callback(state)
            return True
    
    @staticmethod
    def calculate_effective_limit(max_iteration_limit: int, 
                                 total_count: int, 
                                 index_mode: str) -> int:
        """
        计算有效的循环上限
        
        逻辑：
        - Random 模式：上限 = MAX_ITERATION_LIMIT（允许重复）
        - 其他模式：上限 = min(MAX_ITERATION_LIMIT, total_count)
        """
        if index_mode == IndexHandler.MODE_RANDOM:
            effective_limit = max_iteration_limit
            print(f"[循环限制] Random 模式: 迭代上限 = {max_iteration_limit} (允许重复)")
        else:
            effective_limit = min(max_iteration_limit, total_count)
            print(f"[循环限制] 用户设置: {max_iteration_limit}, 数据总量: {total_count}, 有效上限: {effective_limit}")
        
        return effective_limit
    
    @staticmethod
    def _update_state(state: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """
        通用状态更新方法
        """
        state.update(updates)
    
    @staticmethod
    def validate_index(index: int, list_length: int) -> Tuple[bool, str]:
        """
        验证索引是否有效
        """
        if index < 0:
            return (False, f"索引不能为负数: {index}")
        if index >= list_length:
            return (False, f"索引越界: index={index}, 列表长度={list_length}")
        return (True, "")