"""
功能：
- 管理全局索引和任务状态
- 实现断点续传功能
- 支持迭代限制
- 自动排队下一个任务
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

# 尝试导入 PromptServer，如果失败则使用 Mock 对象
try:
    from server import PromptServer
    PROMPT_SERVER_AVAILABLE = True
except ImportError:
    print("[警告] PromptServer 不可用，使用 Mock 对象替代")
    PROMPT_SERVER_AVAILABLE = False
    
    class PromptServer:
        """PromptServer 的 Mock 实现，用于开发和测试环境"""
        instance = None
        
        @classmethod
        def send_sync(cls, event: str, data: Dict[str, Any], sid: Optional[str] = None):
            """模拟发送同步消息"""
            print(f"[Mock PromptServer] 事件: {event}, 数据: {data}")


class AutoQueueLoopController:
    """
    自动队列循环控制器节点
    
    功能：
    - 管理全局索引和任务状态
    - 实现断点续传功能
    - 支持迭代限制
    - 自动排队下一个任务
    """
    
    # 状态文件存储路径
    STATE_FILE = Path("custom_nodes") / "auto_queue_state.json"
    
    def __init__(self):
        """初始化节点"""
        pass
    
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        """
        定义节点的输入类型
        
        返回：
            包含必需输入的字典
        """
        return {
            "required": {
                "COMBO_LIST": ("LIST", {"forceInput": True}),
                "TOTAL_COUNT": ("INT", {"forceInput": True}),
                "CONFIG_HASH": ("STRING", {"forceInput": True}),
                "INDEX_MODE": (["Auto", "Specified", "From Start"], {
                    "default": "Auto"
                }),
                "START_INDEX": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 9999,
                    "step": 1,
                    "display": "number"
                }),
                "MAX_ITERATION_LIMIT": ("INT", {
                    "default": 100,
                    "min": 1,
                    "max": 9999999,
                    "step": 1,
                    "display": "number"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("CURRENT_PROMPT", "STATUS_LOG")
    FUNCTION = "execute"
    OUTPUT_NODE = False
    CATEGORY = "SuperSuger/控制器"
    
    def execute(self, COMBO_LIST: List[str], TOTAL_COUNT: int, CONFIG_HASH: str,
                INDEX_MODE: str, START_INDEX: int, MAX_ITERATION_LIMIT: int) -> Tuple[str, str]:
        """
        节点主执行方法
        
        功能流程：
        1. 加载持久化状态
        2. 根据索引模式确定当前索引
        3. 提取当前提示词
        4. 处理索引步进和终止逻辑
        5. 保存状态并发送队列信号
        
        参数：
            COMBO_LIST: 完整的提示词组合列表
            TOTAL_COUNT: 列表总数量
            CONFIG_HASH: 上游配置哈希值
            INDEX_MODE: 索引模式选择
            START_INDEX: 指定起始索引（仅在 Specified 模式下有效）
            MAX_ITERATION_LIMIT: 最大循环次数限制
            
        返回：
            (当前提示词, 状态日志)
        """
        print(f"\n{'='*60}")
        print(f"[AutoQueueLoopController] 执行开始")
        print(f"{'='*60}")
        
        # 步骤 1: 加载持久化状态
        state = self._load_state()
        
        # 步骤 2: 根据索引模式确定当前索引，并处理重置逻辑
        global_index = self._determine_index_and_reset(
            state, INDEX_MODE, START_INDEX, CONFIG_HASH
        )
        
        # 步骤 3: 计算有效的循环上限
        effective_limit = self._calculate_limit(MAX_ITERATION_LIMIT, TOTAL_COUNT)
        
        # 步骤 4: 边界检查 - 确保索引在有效范围内
        if global_index >= len(COMBO_LIST):
            error_msg = f"索引越界: global_index={global_index}, 列表长度={len(COMBO_LIST)}"
            print(f"[错误] {error_msg}")
            return ("", error_msg)
        
        # 步骤 5: 从列表中提取当前索引对应的提示词
        current_prompt = COMBO_LIST[global_index]
        
        # 步骤 6: 构建状态日志
        status_log = self._build_status_log(
            global_index, TOTAL_COUNT, effective_limit, INDEX_MODE, 
            CONFIG_HASH, START_INDEX, state, current_prompt
        )
        
        print(status_log)
        
        # 步骤 7: 处理索引步进、状态保存和终止判断
        should_continue = self._handle_step_and_terminate(
            state, global_index, TOTAL_COUNT, effective_limit, CONFIG_HASH
        )
        
        # 步骤 8: 发送队列信号和进度反馈
        self._send_signal(global_index, TOTAL_COUNT, should_continue)
        
        print(f"{'='*60}\n")
        
        return (current_prompt, status_log)
    
    def _load_state(self) -> Dict[str, Any]:
        """
        加载持久化状态文件
        
        功能：
        - 从 JSON 文件读取状态数据
        - 如果文件不存在或损坏，返回默认状态
        
        返回：
            状态字典，包含 global_index, last_input_hash, is_completed, workflow_started
        """
        default_state = {
            "global_index": 0,
            "last_input_hash": "",
            "is_completed": False,
            "workflow_started": False,
            "last_mode": "",
            "last_start_index": -1
        }
        
        try:
            # 确保状态文件的目录存在
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果文件存在，读取内容
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    print(f"[状态加载] 成功加载状态: {state}")
                    return state
            else:
                print(f"[状态加载] 状态文件不存在，使用默认状态")
                return default_state
                
        except Exception as e:
            print(f"[状态加载] 读取状态文件失败: {e}，使用默认状态")
            return default_state
    
    def _save_state(self, state: Dict[str, Any]) -> None:
        """
        保存状态到持久化文件
        
        功能：
        - 将状态字典写入 JSON 文件
        - 确保目录存在
        - 处理写入异常
        
        参数：
            state: 要保存的状态字典
        """
        try:
            # 确保目录存在
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入 JSON 文件，使用缩进提高可读性
            with open(self.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            print(f"[状态保存] 成功保存状态: {state}")
            
        except Exception as e:
            print(f"[状态保存] 保存状态文件失败: {e}")
    
    def _determine_index_and_reset(self, state: Dict[str, Any], index_mode: str,
                                   start_index: int, config_hash: str) -> int:
        """
        根据索引模式确定当前索引，并处理重置逻辑
        
        简化逻辑（基于工作流运行期间参数不可变的特性）：
        1. 检查是否是"本次工作流的首次执行"（通过 workflow_started 标志）
        2. 如果是首次执行：
           - From Start → 设置索引为 0
           - Specified → 设置索引为用户指定值
           - Auto → 根据配置哈希/完成状态决定
        3. 如果不是首次执行：
           - 所有模式都使用当前保存的索引继续（自动递增）
        
        参数：
            state: 当前持久化状态
            index_mode: 索引模式
            start_index: 指定的起始索引
            config_hash: 当前配置哈希值
            
        返回：
            确定的全局索引
        """
        print(f"[索引确定] 模式: {index_mode}")
        
        # 检查是否是本次工作流的首次执行
        # 通过判断 "workflow_started" 标志来确定
        workflow_started = state.get("workflow_started", False)
        last_hash = state.get("last_input_hash", "")
        
        # 判断是否是新的工作流运行
        is_new_workflow = not workflow_started or last_hash != config_hash
        
        # === 首次执行逻辑 ===
        if is_new_workflow:
            print(f"  → 检测到新的工作流运行")
            
            # 模式 1: "From Start" - 从 0 开始
            if index_mode == "From Start":
                print(f"  → 'From Start' 模式：设置起始索引为 0")
                state["global_index"] = 0
                state["is_completed"] = False
                state["workflow_started"] = True
                state["last_mode"] = "From Start"
                state["last_start_index"] = 0
                state["last_input_hash"] = config_hash
                self._save_state(state)
                return 0
            
            # 模式 2: "Specified" - 从用户指定索引开始
            elif index_mode == "Specified":
                print(f"  → 'Specified' 模式：设置起始索引为 {start_index}")
                state["global_index"] = start_index
                state["is_completed"] = False
                state["workflow_started"] = True
                state["last_mode"] = "Specified"
                state["last_start_index"] = start_index
                state["last_input_hash"] = config_hash
                self._save_state(state)
                return start_index
            
            # 模式 3: "Auto" - 根据配置哈希和完成状态决定
            else:  # index_mode == "Auto"
                hash_changed = last_hash != config_hash
                is_completed = state.get("is_completed", False)
                
                # 配置改变或已完成 → 从 0 开始
                if hash_changed or is_completed:
                    print(f"  → 'Auto' 模式：{'配置改变' if hash_changed else '上次已完成'}，从 0 开始")
                    state["global_index"] = 0
                    state["is_completed"] = False
                    state["workflow_started"] = True
                    state["last_mode"] = "Auto"
                    state["last_start_index"] = 0
                    state["last_input_hash"] = config_hash
                    self._save_state(state)
                    return 0
                else:
                    # 断点续传
                    current_index = state.get("global_index", 0)
                    print(f"  → 'Auto' 模式：断点续传，从索引 {current_index} 继续")
                    state["workflow_started"] = True
                    state["last_mode"] = "Auto"
                    self._save_state(state)
                    return current_index
        
        # === 后续执行逻辑（工作流运行中）===
        else:
            # 工作流已启动，所有模式都使用当前索引继续（忽略模式设置）
            current_index = state.get("global_index", 0)
            print(f"  → 工作流运行中：从索引 {current_index} 继续（忽略模式设置）")
            return current_index
    
    def _calculate_limit(self, max_iteration_limit: int, total_count: int) -> int:
        """
        计算有效的循环上限
        
        功能：
        - 取用户设置的最大迭代次数和总数量的最小值
        - 确保不会超出数据边界
        
        参数：
            max_iteration_limit: 用户设置的最大迭代次数
            total_count: 数据总数量
            
        返回：
            有效的循环上限
        """
        effective_limit = min(max_iteration_limit, total_count)
        print(f"[循环限制] 用户设置: {max_iteration_limit}, 数据总量: {total_count}, 有效上限: {effective_limit}")
        return effective_limit
    
    def _build_status_log(self, global_index: int, total_count: int, 
                         effective_limit: int, index_mode: str, config_hash: str,
                         start_index: int, state: Dict[str, Any], current_prompt: str) -> str:
        """
        构建状态日志字符串
        
        参数：
            global_index: 当前全局索引
            total_count: 数据总数量
            effective_limit: 有效循环上限
            index_mode: 索引模式
            config_hash: 配置哈希值
            start_index: 用户设置的起始索引
            state: 当前状态字典
            current_prompt: 当前提示词内容
            
        返回：
            格式化的状态日志
        """
        # 获取历史信息
        last_mode = state.get("last_mode", "无")
        last_start_index = state.get("last_start_index", "无")
        workflow_started = state.get("workflow_started", False)
        
        # 计算进度百分比
        progress_percentage = ((global_index + 1) / effective_limit * 100) if effective_limit > 0 else 0
        
        # 计算剩余任务数
        remaining_tasks = effective_limit - (global_index + 1)
        
        status_log = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         自动队列循环控制器状态                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

【当前任务信息】
  ├─ 当前索引: {global_index}
  ├─ 任务进度: {global_index + 1} / {effective_limit} ({progress_percentage:.1f}%)
  ├─ 剩余任务: {remaining_tasks}
  └─ 数据总量: {total_count}

【执行模式】
  ├─ 当前模式: {index_mode}
  ├─ 起始索引: {start_index}
  ├─ 最大迭代: {effective_limit}
  └─ 工作流状态: {'🟢 运行中' if workflow_started else '🔴 已停止'}

【任务状态】
  ├─ 是否完成: {'✅ 是' if state.get("is_completed", False) else '⏳ 否'}
  └─ 配置Hash: {config_hash[:16]}...

【历史记录】
  ├─ 上次模式: {last_mode}
  └─ 上次起始: {last_start_index}

【当前提示词】
{current_prompt}

╚══════════════════════════════════════════════════════════════════════════════╝
"""
        return status_log.strip()
    
    def _handle_step_and_terminate(self, state: Dict[str, Any], global_index: int,
                                   total_count: int, effective_limit: int, 
                                   config_hash: str) -> bool:
        """
        处理索引步进、状态保存和循环终止逻辑
        
        核心逻辑：
        1. 计算下一个索引 = 当前索引 + 1
        2. 判断终止条件：
           a) 完全完成：达到数据总量 → 标记完成，重置索引，停止循环
           b) 限制停止：达到用户设置的上限 → 保持未完成状态，保存索引，停止循环
           c) 继续执行：未达到任何限制 → 更新索引，继续循环
        
        参数：
            state: 当前状态字典
            global_index: 当前全局索引
            total_count: 数据总数量
            effective_limit: 有效循环上限
            config_hash: 配置哈希值
            
        返回：
            是否应该继续循环（True=继续, False=停止）
        """
        # 计算下一个索引
        next_index = global_index + 1
        
        print(f"[步进处理] 当前索引: {global_index}, 下一个索引: {next_index}")
        
        # 情况 1: 完全完成 - 已处理完所有数据
        if global_index >= total_count - 1:
            print(f"  → 完全完成：已处理所有 {total_count} 个数据")
            state["global_index"] = 0  # 重置为 0，为下次执行做准备
            state["is_completed"] = True  # 标记为已完成
            state["workflow_started"] = False  # 重置工作流标志
            state["last_input_hash"] = config_hash
            self._save_state(state)
            return False  # 停止循环
        
        # 情况 2: 限制停止 - 达到用户设置的迭代上限
        elif global_index >= effective_limit - 1:
            print(f"  → 限制停止：达到用户设置的上限 {effective_limit}")
            print(f"     注意：仍有 {total_count - effective_limit} 个数据未处理")
            state["global_index"] = next_index  # 保存下一个索引，支持断点续传
            state["is_completed"] = False  # 保持未完成状态
            state["workflow_started"] = False  # 重置工作流标志
            state["last_input_hash"] = config_hash
            self._save_state(state)
            return False  # 停止循环
        
        # 情况 3: 继续执行 - 未达到任何限制
        else:
            print(f"  → 继续执行：索引更新为 {next_index}")
            state["global_index"] = next_index  # 更新索引
            state["is_completed"] = False
            state["workflow_started"] = True  # 保持工作流运行标志
            state["last_input_hash"] = config_hash
            self._save_state(state)
            return True  # 继续循环
    
    def _send_signal(self, global_index: int, total_count: int, should_continue: bool) -> None:
        """
        发送 WebSocket 信号到前端和队列系统
        
        功能：
        1. 发送进度反馈信号（node-feedback）
        2. 如果应该继续，发送队列信号（add-queue）
        
        参数：
            global_index: 当前全局索引
            total_count: 数据总数量
            should_continue: 是否应该继续执行
        """
        if not PROMPT_SERVER_AVAILABLE:
            print(f"[信号发送] PromptServer 不可用，跳过信号发送")
            return
        
        try:
            # 发送进度反馈信号
            feedback_data = {
                "node_id": id(self),  # 使用对象 ID 作为节点标识
                "progress": global_index + 1,
                "total": total_count
            }
            PromptServer.instance.send_sync("exhaustive-node-feedback", feedback_data)
            print(f"[信号发送] 进度反馈: {global_index + 1}/{total_count}")
            
            # 如果应该继续，发送队列信号
            if should_continue:
                queue_data = {"node_id": id(self)}  # 包含节点信息的队列信号
                PromptServer.instance.send_sync("exhaustive-add-queue", queue_data)
                print(f"[信号发送] 已请求添加下一个任务到队列")
            else:
                print(f"[信号发送] 循环终止，不再添加新任务")
                
        except Exception as e:
            print(f"[信号发送] 发送信号失败: {e}")
    
    @classmethod
    def IS_CHANGED(cls, COMBO_LIST: List[str], TOTAL_COUNT: int, CONFIG_HASH: str,
                   INDEX_MODE: str, START_INDEX: int, MAX_ITERATION_LIMIT: int) -> float:
        """
        ComfyUI 核心方法：判断节点是否需要重新执行
        
        功能：
        - 当循环未完成时，返回 NaN 强制触发重新执行
        - 实现自动循环的核心机制
        
        返回：
            float("nan"): 强制重新执行
            其他值: 使用缓存
        """
        try:
            # 加载当前状态
            state_file = Path("custom_nodes") / "auto_queue_state.json"
            if not state_file.exists():
                return float("nan")  # 首次执行，强制运行
            
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # 防御性检查：确保参数不为 None
            if MAX_ITERATION_LIMIT is None or TOTAL_COUNT is None:
                print(f"[IS_CHANGED] 参数异常: MAX_ITERATION_LIMIT={MAX_ITERATION_LIMIT}, TOTAL_COUNT={TOTAL_COUNT}")
                return float("nan")
            
            # 计算有效上限
            effective_limit = min(MAX_ITERATION_LIMIT, TOTAL_COUNT)
            
            # 获取当前索引
            current_index = state.get("global_index", 0)
            is_completed = state.get("is_completed", False)
            
            # 如果未完成且索引在有效范围内，强制重新执行
            if not is_completed and current_index < effective_limit:
                return float("nan")  # 返回 NaN 强制重新执行
            
            # 否则，使用配置哈希作为缓存键
            return hash(CONFIG_HASH)
            
        except Exception as e:
            print(f"[IS_CHANGED] 检查失败: {e}")
            import traceback
            traceback.print_exc()  # 打印完整的堆栈信息，便于调试
            return float("nan")  # 出错时强制执行


# ComfyUI 节点注册
NODE_CLASS_MAPPINGS = {
    "SG_AutoQueueLoop": AutoQueueLoopController
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SG_AutoQueueLoop": "Auto Queue Loop Controller"
}