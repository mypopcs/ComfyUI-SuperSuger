import logging

# 尝试导入 PromptServer，如果失败则使用 Mock 对象
try:
    from server import PromptServer
    PROMPT_SERVER_AVAILABLE = True
except ImportError:
    logging.warning("[信号处理] PromptServer 不可用，使用 Mock 对象替代")
    PROMPT_SERVER_AVAILABLE = False
    
    class PromptServer:
        """PromptServer 的 Mock 实现，用于开发和测试环境"""
        instance = None
        
        @classmethod
        def send_sync(cls, event: str, data: dict, sid: str = None):
            """模拟发送同步消息"""
            logging.info(f"[Mock PromptServer] 事件: {event}, 数据: {data}")


class SignalHandler:
    """
    信号处理类，负责发送 WebSocket 信号到前端和队列系统
    """
    
    @staticmethod
    def send_signal(node_id: int, global_index: int, total_count: int, should_continue: bool) -> None:
        """
        发送信号到前端和队列系统
        
        参数：
            node_id: 节点ID
            global_index: 当前全局索引
            total_count: 数据总数量
            should_continue: 是否应该继续执行
        """
        if not PROMPT_SERVER_AVAILABLE:
            logging.info(f"[信号发送] PromptServer 不可用，跳过信号发送")
            return
        
        try:
            # 发送进度反馈信号
            feedback_data = {
                "node_id": node_id,  # 使用节点ID作为标识
                "progress": global_index + 1,
                "total": total_count
            }
            PromptServer.instance.send_sync("exhaustive-node-feedback", feedback_data)
            logging.info(f"[信号发送] 进度反馈: {global_index + 1}/{total_count}")
            
            # 如果应该继续，发送队列信号
            if should_continue:
                queue_data = {"node_id": node_id}  # 包含节点信息的队列信号
                PromptServer.instance.send_sync("exhaustive-add-queue", queue_data)
                logging.info(f"[信号发送] 已请求添加下一个任务到队列")
            else:
                logging.info(f"[信号发送] 循环终止，不再添加新任务")
                
        except Exception as e:
            logging.error(f"[信号发送] 发送信号失败: {e}")
