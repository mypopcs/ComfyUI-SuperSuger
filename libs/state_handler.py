import json
import os
from pathlib import Path
from typing import Dict, Any

## 状态管理公共类, 用于管理全局索引和任务状态, 提供断点续传功能, 支持迭代限制, 提供状态持久化和加载功能
class StateHandler:
    @staticmethod
    # 加载JSON文件读取状态文件, 如果文件不存在或损坏, 返回默认状态
    def load_state(state_file: Path) -> Dict[str, Any]:
        """
        参数：
            state_file: 状态文件路径
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
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果文件存在，读取内容
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    print(f"[状态加载] 成功加载状态: {state}")
                    return state
            else:
                print(f"[状态加载] 状态文件不存在，使用默认状态")
                return default_state
                
        except Exception as e:
            print(f"[状态加载] 读取状态文件失败: {e}，使用默认状态")
            return default_state
    
    @staticmethod
    # 保存状态到JSON持久化文件, 确保目录存在, 处理写入异常
    def save_state(state_file: Path, state: Dict[str, Any]) -> None:
        """
        参数：
            state_file: 状态文件路径
            state: 要保存的状态字典
        """
        try:
            # 确保目录存在
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入 JSON 文件，使用缩进提高可读性
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            print(f"[状态保存] 成功保存状态: {state}")
            
        except Exception as e:
            print(f"[状态保存] 保存状态文件失败: {e}")
    
    @staticmethod
    # 重置状态到初始值, 清除所有任务状态, 重置全局索引为0, 并保存到文件
    def reset_state(state_file: Path) -> Dict[str, Any]:
        """
        参数：
            state_file: 状态文件路径
        返回：
            重置后的状态字典
        """
        default_state = {
            "global_index": 0,
            "last_input_hash": "",
            "is_completed": False,
            "workflow_started": False,
            "last_mode": "",
            "last_start_index": -1
        }
        
        StateHandler.save_state(state_file, default_state)
        print(f"[状态重置] 成功重置状态到初始值")
        return default_state