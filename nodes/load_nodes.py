import os
import glob
import numpy as np
import torch
from PIL import Image


class BatchImageLoader:
    # 节点的基本信息
    # 类别是我们在 ComfyUI 菜单中找到节点的分组。
    CATEGORY = "SuperSuger/图像/加载图像" 
    # 描述
    DESCRIPTION = "批量加载图像节点，支持增量、随机和单张模式。"
    # 节点运行的 Python 函数名称
    FUNCTION = "execute" 
    # 节点返回的数据类型
    RETURN_TYPES = ("IMAGE", "STRING", "INT") 

    def __init__(self):
        self.image_cache = {}
        self.last_paths = {}

    @classmethod
    def INPUT_TYPES(cls):
        # 定义节点的输入参数
        return {
            "required": {
                # 图像文件夹路径。使用 STRING 类型，并设置默认值和中文显示名。
                "path": ("STRING", {"default": "E:\\输入文件夹","multiline": False}),
                # 批处理模式。使用列表定义下拉菜单选项。
                "mode": (["incremental_image", "randomize", "single_image"], 
                         {"default": "incremental_image"}),
                # 随机种子。用于 'randomize' 模式。
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                # 当前批次索引。注意：这个通常由上游节点传入，是批次迭代的计数器。
                "index": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                # 批次标签。用于缓存和识别不同批次。
                "label": ("STRING", {"default": "Batch 001", "multiline": False}),
                # 文件匹配模式。例如：*.png 或 image_*.jpg
                "pattern": ("STRING", {"default": "*","multiline": False}),
            },
            "optional": {
                # 额外的布尔值选项
                "allow_RGBA_output": ("BOOLEAN", {"default": False}),
                # 文件名文本扩展名。例如：.txt
                #"filename_text_extension": ("STRING", {"default": ".","multiline": False}),
            }
        }
    # 节点的主要执行函数
    def execute(self, path, pattern='*', index=0, mode="single_image", seed=0, label="Batch 001", allow_RGBA_output=False):
        # 1. 检测路径
        if not os.path.exists(path):
            raise FileNotFoundError(f"目录 '{path}' 不存在。")
        dir_files = os.listdir(path)
        if len(dir_files) == 0:
            raise FileNotFoundError(f"目录 '{path}' 中没有文件。")

        import glob
        valid_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.bmp', '*.tga', '*.tif', '*.tiff']
        image_paths = []
        # 2. 查找所有匹配的文件
        for ext in valid_extensions:
            search_pattern = os.path.join(path, pattern if pattern != '*' else ext)
            image_paths.extend(glob.glob(search_pattern))
        # 3. 排序文件路径
        image_paths = sorted(image_paths)
        if len(image_paths) == 0:
            raise FileNotFoundError(f"目录 {path} 中没有匹配模式 {pattern} 的文件。")
        
        # 4. 根据模式选择索引
        if mode == 'single_image':
            selected_index = index % len(image_paths)
        elif mode == 'incremental_image':
            cache_key = f"{label}_{path}"
            if cache_key not in self.last_paths:
                self.last_paths[cache_key] = 0
            else:
                self.last_paths[cache_key] = (self.last_paths[cache_key] + 1) % len(image_paths)
            selected_index = self.last_paths[cache_key]
        else:
            random.seed(seed)
            selected_index = random.randint(0, len(image_paths) - 1)
        
        # 5. 加载图像
        image_path = image_paths[selected_index]
        filename = os.path.basename(image_path)
        
        # 6. 转换图像
        img = Image.open(image_path)
        # img = ImageOps.exif_transpose(img)

        # 7. 转换颜色模式
        if not allow_RGBA_output and img.mode == 'RGBA':
            img = img.convert("RGB")
        elif img.mode != 'RGB' and img.mode != 'RGBA':
            img = img.convert("RGB")

        # 8. 转换为 PyTorch 张量
        image = np.array(img).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        
        return (image, filename)
     # 10. 节点状态更新
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        path = kwargs.get('path', '')
        if os.path.exists(path):
            return os.path.getmtime(path)
        return float("NaN")