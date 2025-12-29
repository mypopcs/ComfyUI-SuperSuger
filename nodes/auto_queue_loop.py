from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from ..libs.state_handler import StateHandler
from ..libs.logs_handler import LogsHandler
from ..libs.signal_handler import SignalHandler
from ..libs.index_handler import IndexHandler

# 尝试导入 PromptServer
try:
    from server import PromptServer
    PROMPT_SERVER_AVAILABLE = True
except ImportError:
    print("[警告] PromptServer 不可用，使用 Mock 对象替代")
    PROMPT_SERVER_AVAILABLE = False
    
    class PromptServer:
        instance = None
        @classmethod
        def send_sync(cls, event: str, data: Dict[str, Any], sid: Optional[str] = None):
            print(f"[Mock PromptServer] 事件: {event}, 数据: {data}")

#自动队列循环控制器节点
class AutoQueueLoopController:
    
    # 状态文件存储路径
    STATE_FILE = Path("logs") / "auto_queue_logs.json"
    
    def __init__(self):
        pass
    #节点输入参数定义
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {
            "required": {
                "COMBO_LIST": ("LIST", {"forceInput": True}), #完整的提示词组合列表
                "TOTAL_COUNT": ("INT", {"forceInput": True}), #数据列表总数量
                "CONFIG_HASH": ("STRING", {"forceInput": True}), #上游配置哈希值
                "INDEX_MODE": (["Auto", "Specified", "From Start", "Random"], { #索引模式选择
                    "title": "索引模式",
                    "default": "Auto"
                }),
                "START_INDEX": ("INT", { #指定起始索引
                    "default": 0,
                    "min": 0,
                    "max": 99999999,
                    "step": 1,
                    "title": "起始索引ID",
                    "display": "number"
                }),
                "MAX_ITERATION_LIMIT": ("INT", { #最大循环次数限制
                    "default": 100,
                    "min": 1,
                    "max": 99999999,
                    "step": 1,
                    "title": "最大循环次数",
                    "display": "number"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("当前提示词", "日志")
    FUNCTION = "execute"
    OUTPUT_NODE = False
    CATEGORY = "SuperSuger/控制器"
    #节点主流程
    def execute(self, COMBO_LIST: List[str], TOTAL_COUNT: int, CONFIG_HASH: str,
                INDEX_MODE: str, START_INDEX: int, MAX_ITERATION_LIMIT: int) -> Tuple[str, str]:
        print(f"*********************自动队列循环开始执行************************")
        
        # 步骤 1: 加载持久化状态
        state = StateHandler.load_state(self.STATE_FILE)
        
        # 步骤 2: 计算有效的循环上限
        effective_limit = IndexHandler.calculate_effective_limit(
            MAX_ITERATION_LIMIT, TOTAL_COUNT, INDEX_MODE
        )
        
        # 步骤 3: 根据索引模式确定当前索引
        # actual_index: 实际用于访问列表的索引
        # execution_index: 用于显示和步进的索引（Random 模式下是执行次数）
        actual_index, execution_index = IndexHandler.determine_index(
            state=state,
            index_mode=INDEX_MODE,
            start_index=START_INDEX,
            config_hash=CONFIG_HASH,
            total_count=TOTAL_COUNT,
            save_callback=lambda s: StateHandler.save_state(self.STATE_FILE, s)
        )
        
        # 步骤 4: 边界检查
        is_valid, error_msg = IndexHandler.validate_index(actual_index, len(COMBO_LIST))
        if not is_valid:
            print(f"[错误] {error_msg}")
            return ("", error_msg)
        
        # 步骤 5: 提取当前提示词
        # 关键：使用 actual_index 访问列表，Random 模式下这是随机值
        current_prompt = COMBO_LIST[actual_index]
        
        # 调试日志（可选）
        if INDEX_MODE == "Random":
            print(f"[DEBUG] Random 模式 - actual_index={actual_index}, execution_index={execution_index}")
        
        # 步骤 6: 构建状态日志
        # 使用统一的日志构建方法，根据不同索引模式自动选择合适的日志格式
        status_log = LogsHandler.build_status_log(
            global_index=execution_index,
            total_count=TOTAL_COUNT,
            effective_limit=effective_limit,
            index_mode=INDEX_MODE,
            config_hash=CONFIG_HASH,
            start_index=START_INDEX,
            state=state,
            current_prompt=current_prompt,
            max_iter=MAX_ITERATION_LIMIT,
            random_index=actual_index if INDEX_MODE == "Random" else None
        )
        
        status_log = status_log.strip()
        
        print(status_log)
        
        # 步骤 7: 处理索引步进和终止判断
        # 对于 Random 模式：使用 execution_index（执行次数）
        # 对于其他模式：使用 actual_index（实际索引位置）
        step_index_value = execution_index if INDEX_MODE == "Random" else actual_index
        should_continue = IndexHandler.step_index(
            state=state,
            index_mode=INDEX_MODE,
            current_index=step_index_value,
            total_count=TOTAL_COUNT,
            effective_limit=effective_limit,
            config_hash=CONFIG_HASH,
            save_callback=lambda s: StateHandler.save_state(self.STATE_FILE, s)
        )
        
        # 步骤 8: 发送队列信号和进度反馈
        # Random 模式：发送执行次数作为进度
        # 其他模式：发送索引位置作为进度
        progress_value = execution_index if INDEX_MODE == "Random" else actual_index
        SignalHandler.send_signal(
            node_id=id(self),
            global_index=progress_value,
            total_count=TOTAL_COUNT if INDEX_MODE != "Random" else effective_limit,
            should_continue=should_continue
        )
        
        return (current_prompt, status_log) #返回(当前提示词, 状态日志)
    #判断节点是否需要重新执行，实现自动循环的核心机制
    @classmethod
    def IS_CHANGED(cls, COMBO_LIST: List[str], TOTAL_COUNT: int, CONFIG_HASH: str,
                   INDEX_MODE: str, START_INDEX: int, MAX_ITERATION_LIMIT: int) -> float:
        try:
            # 防御性检查
            if MAX_ITERATION_LIMIT is None or TOTAL_COUNT is None:
                print(f"[IS_CHANGED] 参数异常: MAX_ITERATION_LIMIT={MAX_ITERATION_LIMIT}, TOTAL_COUNT={TOTAL_COUNT}")
                return float("nan")
            
            # 加载当前状态
            state = StateHandler.load_state(cls.STATE_FILE)
            
            # 计算有效上限
            effective_limit = IndexHandler.calculate_effective_limit(
                MAX_ITERATION_LIMIT, TOTAL_COUNT, INDEX_MODE
            )
            
            # 获取当前索引和完成状态
            current_index = state.get("global_index", 0)
            is_completed = state.get("is_completed", False)
            
            # 如果未完成且索引在有效范围内，强制重新执行
            if not is_completed and current_index < effective_limit:
                return float("NaN") #当循环未完成时，返回 NaN 强制触发重新执行
            
            # 否则，使用配置哈希作为缓存键
            return hash(CONFIG_HASH)
            return hash(CONFIG_HASH)
            
        except Exception as e:
            print(f"[IS_CHANGED] 检查失败: {e}")
            import traceback
            traceback.print_exc()
            return float("nan")