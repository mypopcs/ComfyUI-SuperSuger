from typing import Dict, Any, Tuple, Callable, Optional

# 尝试导入 PromptServer，如果失败则在运行时捕获
try:
    from server import PromptServer
except ImportError:
    # 定义模拟的PromptServer类
    class PromptServer:
        instance = None
        
        def __init__(self):
            self.instance = self
        
        def send_sync(self, event_name, data):
            print(f"[MOCK] 发送消息到前端: {event_name} - {data}")
    
    # 创建并设置instance
    PromptServer = PromptServer()
    print("[WARN] 无法导入 PromptServer，自动队列功能将无法工作。")


class ComfyUIAutoQueue:
    """
    ComfyUI自动队列管理器，提供通用的自动队列功能
    可在多个ComfyUI自定义节点中复用
    """
    
    # 信号名称常量
    SIGNAL_ADD_QUEUE = "exhaustive-add-queue"
    SIGNAL_NODE_FEEDBACK = "exhaustive-node-feedback"
    
    def __init__(self, node_name: str = "unknown"):
        """
        初始化自动队列管理器
        
        Args:
            node_name: 节点名称，用于日志输出
        """
        self.node_name = node_name
    
    def send_signal(self, event_name: str, data: Dict[str, Any]) -> None:
        """
        发送 WebSocket 信号给前端
        
        Args:
            event_name: 事件名称
            data: 事件数据
        """
        try:
            if data.get('node_id'):
                print(f"[DEBUG-{self.node_name}-Signal] 发送信号: {event_name}, 目标ID: {data['node_id']}")
            PromptServer.instance.send_sync(event_name, data)
        except Exception as e:
            # 捕获异常，防止影响主流程
            print(f"[ERROR-{self.node_name}-Signal] 发送信号失败: {e}")
    
    def update_widget(self, node_id: str, widget_name: str, value: Any) -> None:
        """
        更新前端节点上的Widget显示
        
        Args:
            node_id: 节点ID
            widget_name: Widget名称
            value: 要更新的值
        """
        if not node_id:
            return 
        
        self.send_signal(self.SIGNAL_NODE_FEEDBACK, {
            "node_id": node_id, 
            "widget_name": widget_name, 
            "type": type(value).__name__, 
            "value": value
        })
    
    def add_to_queue(self, node_id: str, next_index: int, widget_name: str = "start_index") -> None:
        """
        将下一个任务添加到自动队列
        
        Args:
            node_id: 节点ID
            next_index: 下一个任务的索引
            widget_name: 用于更新的Widget名称
        """
        print(f"[DEBUG-{self.node_name}-Queue] 准备发送自动队列信号 (下一索引: {next_index})...")
        
        # 发送添加队列信号
        self.send_signal(self.SIGNAL_ADD_QUEUE, {
            "node_id": node_id
        })
        
        # 更新前端Widget
        if node_id:
            self.update_widget(node_id, widget_name, next_index)
        
        print(f"[DEBUG-{self.node_name}-Queue] 信号发送完成。")
    
    def check_change(self, auto_queue: bool) -> float:
        """
        检查自动队列是否需要强制重新执行
        
        Args:
            auto_queue: 是否开启自动队列
            
        Returns:
            float: 如果开启自动队列返回nan，否则返回0
        """
        return float("nan") if auto_queue else 0
    
    def process_queue(self, 
                     current_index: int, 
                     total_items: int, 
                     auto_queue: bool, 
                     node_id: Optional[str], 
                     state_manager: Any, 
                     widget_name: str = "start_index") -> Tuple[bool, int, str]:
        """
        处理自动队列的核心逻辑
        
        Args:
            current_index: 当前索引
            total_items: 总项目数
            auto_queue: 是否开启自动队列
            node_id: 节点ID
            state_manager: 状态管理器实例，需提供state属性和save_state()方法
            widget_name: 用于更新的Widget名称
            
        Returns:
            Tuple[bool, int, str]: (是否完成, 下一个索引, 日志信息)
        """
        # 循环终止判定
        if current_index >= total_items or state_manager.state.get("is_completed", False):
            log_msg = f"[INFO-{self.node_name}] 处理已完成或达到 {total_items} 的限制，停止循环。"
            state_manager.update_state({
                "is_completed": True,
                "global_index": 0
            })
            state_manager.save_state()
            print(log_msg)
            return True, 0, log_msg
        
        # 循环分支判定
        is_last_item = current_index >= total_items - 1
        
        # 索引步进
        next_index = 0
        if not is_last_item:
            next_index = current_index + 1
            state_manager.update_state({
                "global_index": next_index,
                "is_completed": False
            })
            print(f"[DEBUG-{self.node_name}-Index] 索引步进: {current_index} -> {next_index}")
        else:
            state_manager.update_state({
                "is_completed": True,
                "global_index": 0
            })
            print(f"[DEBUG-{self.node_name}-Index] 最后一项，重置索引为 0")
        
        # 保存状态
        state_manager.save_state()
        
        # 发送队列信号
        if auto_queue and not is_last_item:
            self.add_to_queue(node_id, next_index, widget_name)
        else:
            print(f"[DEBUG-{self.node_name}-Queue] 自动队列已停止。")
        
        return False, next_index, ""


# 向后兼容：保留旧的函数接口
class AutoQueueManager:
    """
    向后兼容的自动队列管理器
    """
    
    @staticmethod
    def send_frontend_signal(event_name: str, data: Dict[str, Any]):
        manager = ComfyUIAutoQueue()
        manager.send_signal(event_name, data)
    
    @staticmethod
    def update_frontend_widget(node_id: str, widget_name: str, value: Any):
        manager = ComfyUIAutoQueue()
        manager.update_widget(node_id, widget_name, value)
    
    @staticmethod
    def add_to_auto_queue(node_id: str, next_index: int):
        manager = ComfyUIAutoQueue()
        manager.add_to_queue(node_id, next_index)
    
    @staticmethod
    def check_auto_queue_change(auto_queue: bool, **kwargs) -> float:
        manager = ComfyUIAutoQueue()
        return manager.check_change(auto_queue)
    
    @staticmethod
    def process_queue_logic(current_index: int, total_combinations: int, auto_queue: bool, node_id: str, state: Dict[str, Any], save_state_func):
        # 创建临时状态管理器
        class TempStateManager:
            def __init__(self, state, save_func):
                self.state = state
                self.save_func = save_func
            def update_state(self, updates):
                self.state.update(updates)
            def save_state(self):
                self.save_func()
        
        temp_state = TempStateManager(state, save_state_func)
        manager = ComfyUIAutoQueue()
        return manager.process_queue(current_index, total_combinations, auto_queue, node_id, temp_state)


# 便捷函数
def check_auto_queue_change(auto_queue: bool, **kwargs) -> float:
    """
    检查自动队列是否需要强制重新执行（便捷函数）
    """
    manager = ComfyUIAutoQueue()
    return manager.check_change(auto_queue)
