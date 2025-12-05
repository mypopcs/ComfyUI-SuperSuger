import os
import glob
import re
from PIL import Image
import numpy as np

# 辅助函数：将 ComfyUI/PyTorch 张量转换为 PIL 图像格式
def tensor2pil(t):
    """PyTorch Tensor -> PIL Image"""
    # 将张量反归一化 (0-255)，并转换为 PIL Image
    i = 255. * t.cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
    return img

class ImageWithTextSaver:
    # 节点返回的数据类型
    RETURN_TYPES = ("STRING",)
    # 节点分组
    CATEGORY = "SuperSuger/文件"
    # 节点描述
    DESCRIPTION = "按指定前缀同时保存图像和文本文件到指定目录"
    # 节点运行的 Python 函数名称
    FUNCTION = "execute"
    # 这是一个输出节点，通常用于工作流的末尾
    OUTPUT_NODE = True 

    @classmethod
    def INPUT_TYPES(cls):
        # 定义节点的输入参数
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "待保存图像"}), 
                "text": ("STRING", {"forceInput": True, "tooltip": "待保存文本"}),
                "output_path": ("STRING", {"default": "E:\\输出文件夹"}),
                "filename_prefix": ("STRING", {"default": "c_output"}),
                "filename_delimiter": ("STRING", {"default": "-"}),
                "filename_number_padding": ("INT", {"default": 4, "min": 0, "max": 8}),
                "image_extension": (["png", "jpg", "webp", "bmp"], {"default": "png"}),
                "text_extension": ("STRING", {"default": ".txt"}),
                "encoding": (["utf-8", "gbk"], {"default": "utf-8"}),
            }
        }

    def execute(self, image, text, output_path, filename_prefix, filename_delimiter, 
                filename_number_padding, image_extension, text_extension, encoding):
        
        # 1. 确保输出路径存在
        os.makedirs(output_path, exist_ok=True)
        
        # 2. 自动递增文件序号
        search_pattern = f"{filename_prefix}{filename_delimiter}*.*"
        existing_files = glob.glob(os.path.join(output_path, search_pattern))
        max_num = 0 # 从 1 开始编号，所以最大值从 0 开始
        # 构造一个正则表达式来匹配文件名中的数字部分
        # 确保只匹配前缀和分隔符后面的数字
        number_pattern = re.compile(f"^{re.escape(filename_prefix)}{re.escape(filename_delimiter)}(\\d+)")
        for f in existing_files:
            base_name = os.path.basename(f)
            match = number_pattern.match(base_name)
            if match:
                try:
                    # 匹配到的第一个捕获组是数字部分
                    max_num = max(max_num, int(match.group(1))) 
                except ValueError:
                    continue 
        current_number = max_num + 1
        
        # 3. 构造完整的文件名
        number_str = str(current_number).zfill(filename_number_padding)
        base_filename = f"{filename_prefix}{filename_delimiter}{number_str}"
        image_filename = f"{base_filename}.{image_extension}"
        text_filename = f"{base_filename}{text_extension}"
        image_path = os.path.join(output_path, image_filename)
        text_path = os.path.join(output_path, text_filename)

        # 4. 保存文本
        try:
            with open(text_path, 'w', encoding=encoding) as f:
                f.write(text)
            print(f"文本已保存到: {text_path}")
        except Exception as e:
            print(f"错误: 无法保存文本到 '{text_path}': {e}")
            
        # 5. 保存图像
        try:
            # ComfyUI 的图像张量是批次的 (batch, height, width, channels)，我们取第一张 [0]
            img = tensor2pil(image[0]) 
            img.save(image_path)
            print(f"图像已保存到: {image_path}")
        except Exception as e:
            print(f"错误: 无法保存图像到 '{image_path}': {e}")
        saved_path_info = f"图像: {image_path}, 文本: {text_path}"
        
        # 返回保存路径信息和原图像，原图像可以继续连接到其他节点
        return (saved_path_info, image,)