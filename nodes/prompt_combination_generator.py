
"""
功能：
- 纯粹的无状态数据生成层
- 执行笛卡尔乘积生成所有可能的提示词组合
- 一次性输出完整的提示词数据集及配置信息
- 支持真正的动态输入槽(前端JS集成在节点中)
"""

import re
import hashlib
import itertools
from typing import List, Dict, Tuple, Any


class PromptCombinationGenerator:
    """
    提示词组合生成器节点
    
    功能：
    - 纯粹的无状态数据生成层
    - 执行笛卡尔乘积生成所有可能的提示词组合
    - 一次性输出完整的提示词数据集及配置信息
    - 动态输入槽：连接pool_1后显示pool_2，依次类推，最多15个
    """
    
    def __init__(self):
        """初始化节点"""
        pass
    
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        """
        定义节点的输入类型
        
        返回：
        - template_text: 提示词输入模板，使用[1],[2]等锚点位置
        - pool_1 到 pool_15: 动态提示词池输入
        
        注意：动态显示/隐藏由前端JS控制
        """
        input_config = {
            "required": {
                "template_text": ("STRING", {
                    "multiline": True,
                    "default": "A photo of [1] with [2] style",
                    "display": "text"
                })
            },
            "optional": {}
        }
        
        # 定义所有15个pool输入槽
        for i in range(1, 16):
            pool_key = f"pool_{i}"
            input_config["optional"][pool_key] = ("STRING", {
                "multiline": True,
                "default": "",
                "forceInput": True,
                "tooltip": f"提示词池 {i}，每行一个提示词。连接后会自动显示下一个输入槽。"
            })
        
        return input_config
    
    RETURN_TYPES = ("LIST", "INT", "STRING")
    RETURN_NAMES = ("COMBO_LIST", "TOTAL_COUNT", "CONFIG_HASH")
    FUNCTION = "execute"
    OUTPUT_NODE = False
    CATEGORY = "SuperSuger/效率工具"
    DESCRIPTION = """对多个提示词池进行穷举组合，生成所有可能的组合提示词。

使用方法：
1. 在 template_text 中使用 [1],[2] 等占位符标记插入位置
2. 连接 pool_1 输入，自动显示 pool_2
3. 继续连接更多 pool，最多支持 15 个提示词池
4. 每个提示词池每行一个提示词

示例模板: "A photo of [1] with [2] style"
"""
    
    def execute(self, template_text: str, **kwargs) -> Tuple[List[str], int, str]:
        """
        节点主执行方法
        
        参数：
            template_text: 提示词模板，包含占位符如 [1], [2] 等
            **kwargs: 动态接收 pool_1 到 pool_15 的提示词池
            
        返回：
            (组合列表, 总数量, 配置哈希值)
        """
        # 从 kwargs 中提取所有 pool 参数并按数字排序
        pools = self._extract_pools_from_kwargs(kwargs)
        
        # 解析并验证输入数据
        parsed_pools, config_hash = self._parse_and_validate_input(template_text, pools)
        
        # 生成所有可能的组合
        combo_list = self._generate_combinations(template_text, parsed_pools)
        
        # 输出调试信息
        print(f"[PromptCombinationGenerator] 生成完成:")
        print(f"  - 模板: {template_text[:50]}...")
        print(f"  - 总组合数: {len(combo_list)}")
        print(f"  - 配置哈希: {config_hash}")
        
        return (combo_list, len(combo_list), config_hash)
    
    def _extract_pools_from_kwargs(self, kwargs: Dict[str, Any]) -> List[str]:
        """
        从 kwargs 中提取所有 pool 参数，并按数字顺序排序
        
        参数：
            kwargs: 执行方法接收的所有关键字参数
            
        返回：
            按池编号排序的池内容列表
        """
        pools = []
        
        # 按顺序检查 pool_1 到 pool_15
        for i in range(1, 16):
            pool_key = f"pool_{i}"
            pool_content = kwargs.get(pool_key)
            
            if pool_content is not None and str(pool_content).strip():
                pools.append(str(pool_content))
            else:
                # 如果遇到空池，继续检查后续池（允许跳过）
                if pool_content is not None:
                    pools.append("")
        
        # 移除尾部的空池
        while pools and not pools[-1]:
            pools.pop()
        
        print(f"[PromptCombinationGenerator] 检测到 {len(pools)} 个提示词池输入")
        
        return pools
    
    def _parse_and_validate_input(self, template: str, pools: List[str]) -> Tuple[List[List[str]], str]:
        """
        解析并验证输入数据
        
        功能：
        1. 解析所有 POOL 为元素列表（按行分割，去除空行）
        2. 使用正则表达式查找模板中的占位符（如 [1], [2]）
        3. 校验：确保所有引用的占位符对应的 POOL 非空
        4. 计算配置哈希值用于后续变更检测
        
        参数：
            template: 提示词模板字符串
            pools: 原始提示词池列表
            
        返回：
            (解析后的提示词池列表, 配置哈希值)
            
        异常：
            ValueError: 当占位符引用的池为空时抛出
        """
        # 解析所有提示词池：按行分割，去除首尾空格，过滤空行
        parsed_pools = []
        for pool in pools:
            if pool.strip():  # 只处理非空池
                elements = [line.strip() for line in pool.split('\n') if line.strip()]
                parsed_pools.append(elements)
            else:
                parsed_pools.append([])  # 空池用空列表表示
        
        # 使用正则表达式查找模板中的所有占位符 [数字]
        placeholder_pattern = r'\[(\d+)\]'
        placeholders = re.findall(placeholder_pattern, template)
        
        # 校验：检查每个占位符对应的池是否非空
        for placeholder in placeholders:
            index = int(placeholder) - 1  # 占位符从 [1] 开始，列表索引从 0 开始
            
            # 检查索引是否在有效范围内
            if index >= len(parsed_pools):
                raise ValueError(
                    f"模板中引用了 [{placeholder}]，但只提供了 {len(parsed_pools)} 个提示词池。"
                    f"请连接 pool_{placeholder} 输入。"
                )
            
            # 检查对应的池是否为空
            if not parsed_pools[index]:
                raise ValueError(
                    f"模板中引用了 [{placeholder}]，但对应的 pool_{placeholder} 为空。"
                    f"请为 pool_{placeholder} 提供至少一个元素（每行一个）。"
                )
        
        # 计算配置哈希：基于模板和所有非空池的内容
        hash_content = template
        for i, pool in enumerate(parsed_pools):
            if pool:  # 只包含非空池
                hash_content += f"|POOL_{i+1}:" + ",".join(pool)
        
        config_hash = hashlib.md5(hash_content.encode('utf-8')).hexdigest()
        
        print(f"[PromptCombinationGenerator] 输入验证:")
        print(f"  - 发现占位符: {placeholders}")
        print(f"  - 有效提示词池数量: {sum(1 for p in parsed_pools if p)}")
        
        return parsed_pools, config_hash
    
    def _generate_combinations(self, template: str, parsed_pools: List[List[str]]) -> List[str]:
        """
        生成所有可能的提示词组合
        
        功能：
        1. 过滤出非空的提示词池
        2. 使用 itertools.product 执行笛卡尔乘积
        3. 对每个组合执行模板字符串替换
        
        参数：
            template: 提示词模板
            parsed_pools: 解析后的提示词池列表
            
        返回：
            所有组合后的提示词列表
        """
        # 过滤出非空池，并记录其原始索引（用于占位符替换）
        non_empty_pools = []
        pool_indices = []
        
        for i, pool in enumerate(parsed_pools):
            if pool:  # 只处理非空池
                non_empty_pools.append(pool)
                pool_indices.append(i + 1)  # 占位符编号从 1 开始
        
        # 如果没有非空池，返回原始模板
        if not non_empty_pools:
            print("[PromptCombinationGenerator] 警告: 没有有效的提示词池，返回原始模板")
            return [template]
        
        # 执行笛卡尔乘积：生成所有可能的组合
        combinations = list(itertools.product(*non_empty_pools))
        
        print(f"[PromptCombinationGenerator] 组合生成:")
        print(f"  - 参与组合的池数量: {len(non_empty_pools)}")
        print(f"  - 每个池的元素数: {[len(p) for p in non_empty_pools]}")
        print(f"  - 笛卡尔乘积结果数: {len(combinations)}")
        
        # 对每个组合执行模板替换
        combo_list = []
        for combo in combinations:
            # 复制模板用于替换
            result = template
            
            # 替换所有占位符：将 [1], [2] 等替换为对应的元素
            for pool_idx, element in zip(pool_indices, combo):
                placeholder = f"[{pool_idx}]"
                result = result.replace(placeholder, element)
            
            combo_list.append(result)
        
        return combo_list