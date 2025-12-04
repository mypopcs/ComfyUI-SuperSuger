import json
import hashlib
import os
from typing import Dict, Any, Callable
from pathlib import Path

class StateManager:
    """
    通用状态管理器，负责状态的加载、保存和一致性校验
    可在多个ComfyUI自定义节点中复用
    """
    
    def __init__(self, state_file_path: str, default_state: Dict[str, Any] = None):
        """
        初始化状态管理器
        
        Args:
            state_file_path: 状态文件路径
            default_state: 默认状态字典
        """
        self.state_file = Path(state_file_path)
        self.default_state = default_state or {"global_index": 0, "last_input_hash": "", "is_completed": False}
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """
        加载状态文件
        
        Returns:
            状态字典
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    print(f"[DEBUG-State-Load] 状态文件载入成功。Index: {state.get('global_index', 0)}, Completed: {state.get('is_completed', False)}")
                    return state
            except Exception as e:
                print(f"[ERROR-State] 无法加载状态文件 {self.state_file}: {e}，将使用默认状态。")
                return self.default_state.copy()
        
        print(f"[DEBUG-State-Load] 状态文件不存在，创建默认状态。")
        return self.default_state.copy()
    
    def save_state(self) -> None:
        """
        保存状态文件
        """
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
            print(f"[DEBUG-State-Save] 状态已成功保存。Index: {self.state['global_index']}, Hash: {self.state['last_input_hash'][:8]}...")
        except Exception as e:
            print(f"[ERROR-State] 无法保存状态文件: {e}，请检查文件权限。")
    
    def calculate_input_hash(self, inputs: Dict[str, Any], include_keys: list = None) -> str:
        """
        计算输入的哈希值，用于检测输入变化
        
        Args:
            inputs: 输入字典
            include_keys: 需要包含的键列表，如果为None则包含所有键
            
        Returns:
            哈希字符串
        """
        m = hashlib.md5()
        
        if include_keys:
            # 只包含指定的键
            data_dict = {k: inputs.get(k, "") for k in include_keys}
        else:
            # 包含所有键，但排除一些特定键
            data_dict = inputs.copy()
            exclude_keys = ["start_index", "auto_queue", "extra_pnginfo"]
            for key in exclude_keys:
                if key in data_dict:
                    del data_dict[key]
        
        # 将字典转换为排序后的字符串
        data_string = "|".join([f"{k}:{v}" for k, v in sorted(data_dict.items())])
        m.update(data_string.encode('utf-8'))
        return m.hexdigest()
    
    def reset_state(self, new_state: Dict[str, Any] = None, reset_hash: bool = True) -> None:
        """
        重置状态
        
        Args:
            new_state: 新的状态字典，如果为None则使用默认状态
            reset_hash: 是否重置哈希值
        """
        if new_state:
            self.state = new_state.copy()
        else:
            self.state = self.default_state.copy()
        
        if reset_hash:
            self.state["last_input_hash"] = ""
        
        print(f"[DEBUG-State-Reset] 状态已重置。新状态: {self.state}")
    
    def update_state(self, updates: Dict[str, Any]) -> None:
        """
        更新状态
        
        Args:
            updates: 需要更新的状态字段
        """
        self.state.update(updates)
        print(f"[DEBUG-State-Update] 状态已更新: {updates}")
    
    def check_input_change(self, current_inputs: Dict[str, Any], include_keys: list = None) -> bool:
        """
        检查输入是否发生变化
        
        Args:
            current_inputs: 当前输入字典
            include_keys: 需要包含的键列表
            
        Returns:
            如果输入发生变化返回True，否则返回False
        """
        current_hash = self.calculate_input_hash(current_inputs, include_keys)
        return current_hash != self.state["last_input_hash"]

# 便捷函数：创建基于节点目录的状态管理器
def create_node_state_manager(node_file_path: str, state_filename: str = "state.json") -> StateManager:
    """
    创建一个基于节点文件路径的状态管理器
    
    Args:
        node_file_path: 节点文件路径
        state_filename: 状态文件名
        
    Returns:
        StateManager实例
    """
    node_dir = Path(os.path.dirname(node_file_path))
    state_file_path = node_dir / state_filename
    return StateManager(str(state_file_path))
