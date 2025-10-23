import os
import glob
import numpy as np
import torch
from PIL import Image

# 辅助函数：将 PIL 图像转换为 ComfyUI/PyTorch 张量格式
def pil2tensor(image):
    """PIL Image -> PyTorch Tensor"""
    # 将图像转换为 numpy 数组，归一化到 [0, 1]，并添加一个批次维度
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

class BatchImageLoader:
    # 节点的基本信息
    # 类别是我们在 ComfyUI 菜单中找到节点的分组。
    CATEGORY = "SuperSuger/图像/加载图像" 
    # 节点运行的 Python 函数名称
    FUNCTION = "execute" 
    # 节点返回的数据类型
    RETURN_TYPES = ("IMAGE", "STRING", "INT") 

    @classmethod
    def INPUT_TYPES(cls):
        # 定义节点的输入参数
        return {
            "required": {
                # path: 图像文件夹路径。使用 STRING 类型，并设置默认值和中文显示名。
                "path": ("STRING", {"default": "E:\\输入文件夹"}),
                # mode: 批处理模式。使用列表定义下拉菜单选项。
                "mode": (["incremental_image", "randomize", "fixed"], 
                         {"default": "incremental_image"}),
                # seed: 随机种子。用于 'randomize' 模式。
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                # index: 当前批次索引。注意：这个通常由上游节点传入，是批次迭代的计数器。
                "index": ("INT", {"default": 0, "min": 0}),
                # pattern: 文件匹配模式。例如：*.png 或 image_*.jpg
                "pattern": ("STRING", {"default": "*"}),
            },
            "optional": {
                # 额外的布尔值选项
                "allow_RGBA_output": ("BOOLEAN", {"default": False}),
            }
        }
    # 节点的主要执行函数
    def execute(self, path, mode, seed, index, pattern, allow_RGBA_output):
        # 1. 查找所有匹配的文件
        search_path = os.path.join(path, pattern)
        # glob.glob 用于查找匹配给定模式的所有文件路径
        files = sorted(glob.glob(search_path, recursive=False))
        if not files:
            print(f"警告: 在路径 '{path}' 中未找到匹配模式 '{pattern}' 的文件。")
            # 如果找不到文件，返回一个空的黑色图像和提示信息
            return (torch.zeros(1, 64, 64, 3), "未找到文件", 0) 
        num_files = len(files)

        # 2. 根据 mode 确定要加载的文件索引
        if mode == "randomize":
            # 这是一个简单的随机化，实际在 ComfyUI 中需要配合外部的 Randomize 节点
            np.random.seed(seed)
            current_index = np.random.randint(0, num_files)
        elif mode == "fixed":
            # 固定模式，总是加载指定的索引 (或超出范围时循环)
            current_index = index % num_files 
        else: # incremental_image (递增模式)
            # 根据传入的 index 循环加载文件
            current_index = index % num_files 
        file_path = files[current_index]
        filename_text = os.path.basename(file_path)

        # 3. 加载图像
        try:
            img = Image.open(file_path)
            # 颜色模式处理
            if img.mode == 'RGBA' and not allow_RGBA_output:
                # 如果是 RGBA 但不允许输出，则转换为 RGB
                img = img.convert('RGB')
            elif img.mode != 'RGBA' and img.mode != 'RGB':
                # 其他模式转换为 RGB (或根据需求转换为 RGBA)
                 img = img.convert('RGBA' if allow_RGBA_output else 'RGB')
            image_tensor = pil2tensor(img)
            # 返回图像张量、文件名文本和当前使用的索引
            return (image_tensor, filename_text, current_index)
        except Exception as e:
            print(f"错误: 无法加载图像 '{file_path}': {e}")
            # 加载失败时返回一个黑色图像和错误信息
            return (torch.zeros(1, 64, 64, 3), f"加载失败: {filename_text}", current_index)