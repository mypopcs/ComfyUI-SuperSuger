import json
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import sys

# 添加libs目录到系统路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../libs'))

# 导入核心模块
from cartesian import calculate_total_combinations, get_mixed_radix_indices
from state_manager import StateManager, create_node_state_manager
from auto_queue import ComfyUIAutoQueue, check_auto_queue_change
from template_processor import TemplateProcessor, create_template_processor



#ComfyUI 提示词穷举组合节点 (ExhaustivePromptCombinator)
class ExhaustivePromptCombinator:
    # 节点配置
    NODE_NAME = "ExhaustivePromptCombinator"
    CATEGORY = "SuperSuger/提示词"
    DESCRIPTION = "对多个提示词池进行穷举组合，生成所有可能的组合提示词。提示词池中的提示词按顺序插入提示词输入模板中使用[1],[2]等锚点位置，提示词池每个提示词占一行，提示词模板没有写的锚点的提示词池不参与组合"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("提示词", "运行日志")
    
    FUNCTION = "execute"
    OUTPUT_NODE = False
    
    def __init__(self):
        """初始化节点，加载或创建状态文件。"""
        # 创建状态管理器
        self.state_manager = create_node_state_manager(__file__, "exhaustive_state.json")
        # 创建自动队列管理器
        self.auto_queue = ComfyUIAutoQueue(self.NODE_NAME)
        # 创建模板处理器
        self.template_processor = create_template_processor(self.NODE_NAME)
        # 定义节点所在的目录
        self.extension_dir = Path(os.path.dirname(__file__))

    @classmethod
    def INPUT_TYPES(cls):
        """定义节点输入参数"""
        inputs = {
            "required": {
                "template_text": ("STRING", {"multiline": True, "default": "a photo of [1] with [2]", "tooltip": "基础提示词模板，包含锚点[1]和[2]"}),# 基础提示词模板，包含锚点
                "start_index": ("INT", {"default": 0, "min": 0, "max": 999999, "step": 1, "tooltip": "起始索引（用于恢复中断的组合）"}), # 起始索引（用于恢复中断的组合）
                "max_combinations": ("INT", {"default": 0, "min": 0, "step": 1, "tooltip": "最大组合数（0表示无限制）"}), # 最大组合数（0表示无限制）
                "auto_queue": ("BOOLEAN", {"default": True, "tooltip": "是否自动加入队列，建议默认开启"}), # 是否自动加入队列，建议默认开启
            },
            "optional": {}
        }
        for i in range(1, 16):
            inputs["optional"][f"pool_{i}_text"] = ("STRING", {"multiline": True,"forceInput": True, "default": ""})
            
        return inputs

    # ========== 模块化辅助函数 ==========

    # ========== 模板处理功能已移至 template_processor.py ==========

    @classmethod
    def IS_CHANGED(cls, auto_queue: bool, **kwargs):
        """【关键修复】强制 ComfyUI 重新执行，实现自动循环。"""
        return check_auto_queue_change(auto_queue, **kwargs)

    # ========== 主执行函数 ==========

    def execute(self, template_text: str, start_index: int, max_combinations: int, auto_queue: bool, **kwargs) -> Tuple[str, str, int, int, bool]:
        """节点主执行逻辑"""
        
        # 整合所有输入到一个字典
        all_inputs = {
            "template_text": template_text,
            "start_index": start_index,
            "max_combinations": max_combinations,
            "auto_queue": auto_queue,
            "extra_pnginfo": kwargs.get("extra_pnginfo", {}),
            **{f"pool_{i}_text": kwargs.get(f"pool_{i}_text", "") for i in range(1, 16)} 
        }
        
        unique_id = all_inputs['extra_pnginfo'].get('workflow', {}).get('last_node_id')
        
        # 检查输入变化
        include_keys = ["template_text", "max_combinations"] + [f"pool_{i}_text" for i in range(1, 16)]
        should_hard_reset = self.state_manager.check_input_change(all_inputs, include_keys)
        should_soft_reset = (start_index != self.state_manager.state["global_index"] and start_index != 0)

        print(f"\n[DEBUG-{self.NODE_NAME}-Execute] ========== 第 {self.state_manager.state['global_index'] + 1} 次执行开始 ==========")
        print(f"[DEBUG-{self.NODE_NAME}-ID] 节点 Unique ID: {unique_id}")
        print(f"[DEBUG-{self.NODE_NAME}-Index] 当前载入索引: {self.state_manager.state['global_index']}, UI期望起始索引: {start_index}")

        # 重置或更新状态
        if should_hard_reset:
            # 输入发生变化，硬重置
            new_index = start_index if start_index > 0 else 0
            self.state_manager.reset_state(
                new_state={
                    "global_index": new_index,
                    "is_completed": False
                },
                reset_hash=False
            )
            # 更新哈希值
            current_hash = self.state_manager.calculate_input_hash(all_inputs, include_keys)
            self.state_manager.update_state({"last_input_hash": current_hash})
            self.state_manager.save_state()
            print(f"[DEBUG-{self.NODE_NAME}-Reset] 硬重置触发 (输入变化), 索引设为 {new_index}")
        elif should_soft_reset:
            # 手动修改了start_index，软重置
            self.state_manager.update_state({
                "global_index": start_index,
                "is_completed": False
            })
            self.state_manager.save_state()
            print(f"[DEBUG-{self.NODE_NAME}-Reset] 软重置触发 (手动修改start_index), 索引设为 {start_index}")

        current_index = self.state_manager.state["global_index"]
        
        # 解析和校验模板/池
        try:
            valid_pools, used_anchor_numbers = self.template_processor.parse_and_validate_template(
                template_text, all_inputs
            ) 
        except ValueError as e:
            error_msg = str(e)
            print(f"[ERROR-{self.NODE_NAME}-Validation] 校验失败: {error_msg}")
            return (template_text, error_msg, current_index, 0, True)

        # 计算总组合数
        pool_sizes = [len(pool) for pool in valid_pools]
        total_combinations = calculate_total_combinations(pool_sizes)
        
        if max_combinations > 0 and total_combinations > max_combinations:
            total_combinations = max_combinations
            
        print(f"[DEBUG-{self.NODE_NAME}-Combinator] 有效池大小列表: {pool_sizes}，总组合数 (限制后): {total_combinations}")
        
        # 调用自动队列管理器处理队列逻辑
        is_completed_early, next_index, queue_log_msg = self.auto_queue.process_queue(
            current_index, total_combinations, auto_queue, unique_id, self.state_manager
        )
        
        # 如果已完成，返回完成信息
        if is_completed_early:
            return (template_text, queue_log_msg, 0, total_combinations, True)

        # 混合基数寻址与模板替换
        local_indices = get_mixed_radix_indices(current_index, pool_sizes)
        
        print(f"[DEBUG-{self.NODE_NAME}-Combinator] 全局索引 {current_index} 映射到局部索引: {local_indices}")
        
        final_prompt = template_text
        log_details = []
        
        # 遍历局部索引，进行模板替换
        if used_anchor_numbers:
            final_prompt, log_details = self.template_processor.replace_placeholders(
                template_text, used_anchor_numbers, local_indices, valid_pools
            )
        else:
            log_details.append("  - 未发现锚点，直接使用模板文本")

        # 生成日志
        progress_percent = ((current_index + 1) / total_combinations) * 100
        log_info = f"[任务进程]: {current_index + 1} / {total_combinations} ({progress_percent:.2f}%)\n"
        log_info += "当前索引位置: " + str(current_index) + "\n"
        log_info += "总组合数: " + str(total_combinations) + "\n"
        log_info += "任务是否全部完成: " + str(self.state_manager.state["is_completed"]) + "\n"
        log_info += "[任务拼接详情]:\n" + "\n".join(log_details)
        
        print(f"[DEBUG-{self.NODE_NAME}-Prompt] 最终生成的提示词 (开头): {final_prompt[:150]}...")
        print(f"[DEBUG-{self.NODE_NAME}-Log] 组合详情已生成。")

        return (final_prompt, log_info)