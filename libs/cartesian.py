import math
from typing import List, Tuple


def calculate_total_combinations(pool_sizes: List[int]) -> int:
    """
    计算笛卡尔积的总组合数
    
    Args:
        pool_sizes: 每个提示词池的大小列表
        
    Returns:
        总组合数
    """
    if not pool_sizes:
        return 1
    return math.prod(pool_sizes)


def get_mixed_radix_indices(global_index: int, pool_sizes: List[int]) -> List[int]:
    """
    根据全局索引和各池大小，计算每个池的局部索引
    
    Args:
        global_index: 全局索引
        pool_sizes: 每个提示词池的大小列表
        
    Returns:
        每个池的局部索引列表，顺序与输入的pool_sizes一致
    """
    if not pool_sizes:
        return []
        
    current_index = global_index
    local_indices = []
    
    # 混合基数寻址核心算法
    for size in reversed(pool_sizes):
        if size == 0: 
            continue
        
        local_idx = current_index % size
        current_index //= size
        
        local_indices.append(local_idx)

    # 反转列表，使其顺序与输入的pool_sizes一致
    local_indices.reverse()
    return local_indices


def get_combination_by_index(global_index: int, pools: List[List[str]]) -> List[str]:
    """
    根据全局索引获取特定的组合
    
    Args:
        global_index: 全局索引
        pools: 提示词池列表，每个池包含多个提示词
        
    Returns:
        组合后的提示词列表，每个元素对应pools中对应池的一个提示词
    """
    pool_sizes = [len(pool) for pool in pools]
    local_indices = get_mixed_radix_indices(global_index, pool_sizes)
    
    combination = []
    for i, local_idx in enumerate(local_indices):
        if i < len(pools) and local_idx < len(pools[i]):
            combination.append(pools[i][local_idx])
    
    return combination