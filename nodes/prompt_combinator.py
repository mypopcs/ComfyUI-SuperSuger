import json
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import math

# 尝试导入 PromptServer，如果失败则在运行时捕获
try:
    from server import PromptServer
except ImportError:
    class MockPromptServer:
        def send_sync(self, *args, **kwargs):
            pass
    PromptServer = MockPromptServer
    print("[WARN] 无法导入 PromptServer，自动队列功能将无法工作。")

# 定义节点所在的目录，用于状态文件和日志
EXTENSION_DIR = Path(os.path.dirname(__file__))

#ComfyUI 提示词穷举组合节点 (ExhaustivePromptCombinator)
class ExhaustivePromptCombinator:
    # 节点配置
    NODE_NAME = "ExhaustivePromptCombinator"
    # 节点描述
    CATEGORY = "SuperSuger/提示词"
    # 节点描述
    DESCRIPTION = "对多个提示词池进行穷举组合，生成所有可能的组合提示词。"
    # 节点输出参数
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("提示词", "运行日志")
    
    FUNCTION = "execute"
    OUTPUT_NODE = False
    
    def __init__(self):
        """初始化节点，加载或创建状态文件。"""
        self.state_file = EXTENSION_DIR / "exhaustive_state.json"
        self.state = self._load_state()

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

    def _load_state(self) -> Dict[str, Any]:
        """【DEBUG】加载状态文件 (模块 1: 状态持久化)"""
        default_state = {"global_index": 0, "last_input_hash": "", "is_completed": False}
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    print(f"[DEBUG-State-Load] 状态文件载入成功。Index: {state.get('global_index', 0)}, Completed: {state.get('is_completed', False)}")
                    return state
            except Exception as e:
                print(f"[ERROR-State] 无法加载状态文件 {self.state_file}: {e}，将使用默认状态。")
                return default_state
        
        print(f"[DEBUG-State-Load] 状态文件不存在，创建默认状态。")
        return default_state

    def _save_state(self):
        """【DEBUG】保存状态文件 (模块 5: ACID 状态更新)"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
            print(f"[DEBUG-State-Save] 状态已成功保存。Index: {self.state['global_index']}, Hash: {self.state['last_input_hash'][:8]}...")
        except Exception as e:
            print(f"[ERROR-State] 无法保存状态文件: {e}，请检查文件权限。")

    def _calculate_input_hash(self, all_inputs: Dict[str, Any]) -> str:
        """计算所有关键输入的哈希值 (模块 2: 输入一致性校验)"""
        m = hashlib.md5()
        data_string = f"{all_inputs['template_text']}|{all_inputs['max_combinations']}"
        for i in range(1, 16):
            data_string += f"|{all_inputs.get(f'pool_{i}_text', '')}"
        m.update(data_string.encode('utf-8'))
        return m.hexdigest()

    def _parse_and_validate_template(self, all_inputs: Dict[str, Any]) -> Tuple[List[List[str]], List[int]]:
        """解析模板，校验锚点，并返回有效的提示词池列表和锚点编号。"""
        template_text = all_inputs["template_text"]
        
        anchors = sorted(list(set(map(int, re.findall(r"\[(\d+)\]", template_text)))))
        
        if not anchors:
            print("[DEBUG-Validator] 模板中未发现锚点，总组合数为 1。")
            return [[]], [] 

        max_anchor = max(anchors)
        
        valid_pools = []
        used_anchor_numbers = []

        for i in range(1, max_anchor + 1):
            pool_text = all_inputs.get(f"pool_{i}_text", "")
            pool_list = [line.strip() for line in pool_text.split('\n') if line.strip()]
            
            is_anchor_used = i in anchors
            
            if is_anchor_used:
                if not pool_list:
                    raise ValueError(f"ERROR: 模板中使用了锚点 [{i}]，但提示词池 {i} 为空，请补充内容。")
                
                valid_pools.append(pool_list)
                used_anchor_numbers.append(i)
            
        print(f"[DEBUG-Validator] 参与组合的锚点编号: {used_anchor_numbers}")
        return valid_pools, used_anchor_numbers

    def _get_mixed_radix_indices(self, global_index: int, pool_sizes: List[int]) -> List[int]:
        """【DEBUG】根据全局索引和各池大小，计算每个池的局部索引。"""
        if not pool_sizes:
            return []
            
        current_index = global_index
        local_indices = []
        
        # 混合基数寻址核心算法
        for size in reversed(pool_sizes):
            if size == 0: continue
            
            local_idx = current_index % size
            current_index //= size
            
            local_indices.append(local_idx)

        # 反转列表，使其顺序与 [1], [2], ... 锚点顺序一致
        local_indices.reverse()
        return local_indices

    def _send_frontend_signal(self, event_name: str, data: Dict[str, Any]):
        """发送 WebSocket 信号给前端。"""
        try:
            if data.get('node_id'):
                 print(f"[DEBUG-Signal-Send] 尝试发送信号: {event_name}, 目标ID: {data['node_id']}")
            PromptServer.instance.send_sync(event_name, data)
        except Exception as e:
            # 捕获异常，防止影响主流程
            pass 

    def _update_frontend_widget(self, node_id: str, widget_name: str, value: Any):
        """更新前端节点上的 Widget 显示。"""
        if not node_id or not isinstance(PromptServer.instance, PromptServer):
            return 
        
        self._send_frontend_signal("exhaustive-node-feedback", {
            "node_id": node_id, 
            "widget_name": widget_name, 
            "type": type(value).__name__, 
            "value": value
        })

    @classmethod
    def IS_CHANGED(cls, auto_queue: bool, **kwargs):
        """【关键修复】强制 ComfyUI 重新执行，实现自动循环。"""
        if auto_queue:
            return float("nan")
        
        return 0

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
        current_hash = self._calculate_input_hash(all_inputs)

        print(f"\n[DEBUG-Execute-Start] ========== 第 {self.state['global_index'] + 1} 次执行开始 ==========")
        print(f"[DEBUG-Execute] 节点 Unique ID: {unique_id}")
        print(f"[DEBUG-Hash] 当前输入哈希: {current_hash}")
        print(f"[DEBUG-Hash] 上次保存哈希: {self.state['last_input_hash']}")
        print(f"[DEBUG-IndexLoad] 当前载入索引: {self.state['global_index']}, UI期望起始索引: {start_index}")

        
        # 1. 输入一致性校验与重置 (模块 2)
        should_hard_reset = (current_hash != self.state["last_input_hash"])
        should_soft_reset = (start_index != self.state["global_index"] and start_index != 0)
        
        if should_hard_reset:
            self.state["global_index"] = start_index if start_index > 0 else 0
            self.state["last_input_hash"] = current_hash
            self.state["is_completed"] = False
            print(f"[DEBUG-Reset] **硬重置触发** (输入/哈希变化), 索引设为 {self.state['global_index']}.")
        elif should_soft_reset:
            self.state["global_index"] = start_index
            self.state["is_completed"] = False
            print(f"[DEBUG-Reset] **软重置触发** (手动修改 start_index), 索引设为 {start_index}.")

        current_index = self.state["global_index"]
        is_completed = self.state["is_completed"]
        
        # 2. 解析和校验模板/池
        try:
            valid_pools, used_anchor_numbers = self._parse_and_validate_template(all_inputs) 
        except ValueError as e:
            error_msg = str(e)
            print(f"[ERROR-Validation] 校验失败: {error_msg}")
            return (template_text, error_msg, current_index, 0, True)

        # 3. 计算总组合数
        pool_sizes = [len(pool) for pool in valid_pools]
        total_combinations = math.prod(pool_sizes) if pool_sizes else 1
        
        if max_combinations > 0 and total_combinations > max_combinations:
            total_combinations = max_combinations
            
        print(f"[DEBUG-Combinator] 有效池大小列表: {pool_sizes}，总组合数 (限制后): {total_combinations}")
        
        # 4. 循环终止判定
        if current_index >= total_combinations or is_completed:
            log_msg = f"[INFO] 穷举组合已完成或达到 {total_combinations} 的限制，停止循环。"
            self.state["is_completed"] = True
            self.state["global_index"] = 0
            self._save_state()
            print(log_msg)
            return (template_text, log_msg, 0, total_combinations, True)

        # 5. 混合基数寻址与模板替换
        local_indices = self._get_mixed_radix_indices(current_index, pool_sizes)
        
        print(f"[DEBUG-Combinator] 【核心】全局索引 {current_index} 映射到局部索引: {local_indices}")
        
        final_prompt = template_text
        log_details = []
        
        # 遍历局部索引，进行模板替换
        for i, local_idx in enumerate(local_indices):
            
            pool_list = valid_pools[i]
            # 完整获取提示词部分，不再截断
            current_prompt_part = pool_list[local_idx]
            anchor_num = used_anchor_numbers[i]
            
            # 使用正则表达式进行精确替换
            final_prompt = re.sub(r"\[{}\]".format(anchor_num), current_prompt_part, final_prompt, 1)

            # 【DEBUG】打印完整的提示词内容
            log_details.append(
                f"  - 锚点 [{anchor_num}]: 索引 {local_idx}/{len(pool_list)} -> \"{current_prompt_part}\""
            )

        # 6. 生成日志
        progress_percent = ((current_index + 1) / total_combinations) * 100
        log_info = f"[任务进程]: {current_index + 1} / {total_combinations} ({progress_percent:.2f}%)\n"
        log_info += "当前索引位置: " + str(current_index) + "\n"
        log_info += "总组合数: " + str(total_combinations) + "\n"
        log_info += "任务是否全部完成（防止再次循环）: " + str(is_completed) + "\n"
        log_info += "[任务拼接详情]:\n" + "\n".join(log_details)
        
        print(f"[DEBUG-Prompt] 最终生成的提示词 (开头): {final_prompt[:150]}...")
        print(f"[DEBUG-Log] 组合详情已生成。")

        # 7. 循环分支判定
        is_last_item = current_index >= total_combinations - 1

        # 8. ACID 状态步进与序列化
        
        next_index = 0
        if not is_last_item:
            next_index = current_index + 1
            self.state["global_index"] = next_index
            self.state["is_completed"] = False
            print(f"[DEBUG-IndexStep] 索引步进: {current_index} -> {next_index}")
        else:
            self.state["is_completed"] = True
            self.state["global_index"] = 0
            print(f"[DEBUG-IndexStep] 最后一项，重置索引为 0")
        
        # 立即保存状态
        self._save_state()
        
        # 9. 异步信令分发
        if auto_queue and not is_last_item:
            print(f"[DEBUG-Signal-Queue] 准备发送自动队列信号 (下一索引: {next_index})...")
            
            self._send_frontend_signal("exhaustive-add-queue", {
                "node_id": unique_id
            })
            
            if unique_id:
                self._update_frontend_widget(unique_id, "start_index", next_index)
            
            print(f"[DEBUG-Signal-Queue] 信号发送完成。")
        else:
            print(f"[DEBUG-Signal-Queue] 自动队列已停止。")


        return (final_prompt, log_info)