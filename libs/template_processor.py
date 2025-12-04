#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模板处理器模块
提供通用的模板解析、验证和替换功能，可被多个节点复用
"""

import re
from typing import Dict, List, Tuple, Any


class TemplateProcessor:
    """
    模板处理器类
    提供模板解析、锚点验证和内容替换等功能
    """
    
    def __init__(self, node_name: str = "TemplateProcessor"):
        """
        初始化模板处理器
        
        Args:
            node_name: 节点名称，用于日志标识
        """
        self.node_name = node_name
    
    def parse_and_validate_template(self, template_text: str, pool_data: Dict[str, str]) -> Tuple[List[List[str]], List[int]]:
        """
        解析模板，校验锚点，并返回有效的提示词池列表和锚点编号
        
        Args:
            template_text: 包含锚点的模板文本
            pool_data: 提示词池数据字典，键为pool_x_text格式
            
        Returns:
            Tuple[List[List[str]], List[int]]: 
                - 第一个元素是有效的提示词池列表（每个池是提示词列表）
                - 第二个元素是使用的锚点编号列表
        """
        # 提取所有锚点编号
        anchors = re.findall(r"\[(\d+)\]", template_text)
        anchors = sorted(list(set(map(int, anchors))))
        print(f"[DEBUG-{self.node_name}-Validator] 模板中的锚点: {anchors}")

        if not anchors:
            print(f"[DEBUG-{self.node_name}-Validator] 模板中未发现锚点，总组合数为 1。")
            return [[]], []

        max_anchor = max(anchors)
        valid_pools = []
        used_anchor_numbers = []

        # 验证并准备提示词池
        for i in range(1, max_anchor + 1):
            pool_key = f"pool_{i}_text"
            pool_text = pool_data.get(pool_key, "")
            pool_list = self._parse_pool_text(pool_text)
            
            is_anchor_used = i in anchors
            
            if is_anchor_used:
                if not pool_list:
                    raise ValueError(f"ERROR: 模板中使用了锚点 [{i}]，但提示词池 {i} 为空，请补充内容。")
                
                valid_pools.append(pool_list)
                used_anchor_numbers.append(i)
        
        print(f"[DEBUG-{self.node_name}-Validator] 参与组合的锚点编号: {used_anchor_numbers}")
        return valid_pools, used_anchor_numbers
    
    def replace_placeholders(self, template_text: str, anchor_numbers: List[int], local_indices: List[int], valid_pools: List[List[str]]) -> Tuple[str, List[str]]:
        """
        替换模板中的锚点为实际内容
        
        Args:
            template_text: 包含锚点的模板文本
            anchor_numbers: 锚点编号列表
            local_indices: 局部索引列表
            valid_pools: 有效的提示词池列表
            
        Returns:
            Tuple[str, List[str]]: 
                - 第一个元素是替换后的最终文本
                - 第二个元素是替换详情日志
        """
        final_text = template_text
        log_details = []
        
        # 遍历局部索引，进行模板替换
        for i, local_idx in enumerate(local_indices):
            pool_list = valid_pools[i]
            current_part = pool_list[local_idx]
            anchor_num = anchor_numbers[i]
            
            # 使用正则表达式进行精确替换
            final_text = re.sub(r"\[{}\]".format(anchor_num), current_part, final_text, 1)

            # 记录替换详情
            log_details.append(
                f"  - 锚点 [{anchor_num}]: 索引 {local_idx}/{len(pool_list)} -> \"{current_part}\""
            )
            
        return final_text, log_details
    
    def _parse_pool_text(self, pool_text: str) -> List[str]:
        """
        解析提示词池文本，返回提示词列表
        
        Args:
            pool_text: 提示词池文本，每行一个提示词
            
        Returns:
            List[str]: 去除空白行后的提示词列表
        """
        return [line.strip() for line in pool_text.split('\n') if line.strip()]


# 便捷函数
def create_template_processor(node_name: str = "TemplateProcessor") -> TemplateProcessor:
    """
    创建模板处理器实例
    
    Args:
        node_name: 节点名称，用于日志标识
        
    Returns:
        TemplateProcessor: 模板处理器实例
    """
    return TemplateProcessor(node_name)
