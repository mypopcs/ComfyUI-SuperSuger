# 导入必要的模块
import os
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 尝试导入folder_paths
folder_paths = None
try:
    import folder_paths
except ImportError:
    pass

# 颜色解析函数
def parse_color(color_str):
    """将颜色字符串解析为RGB元组"""
    # 如果是十六进制颜色代码
    if color_str.startswith('#'):
        # 移除#符号
        color_str = color_str.lstrip('#')
        # 解析不同长度的十六进制代码
        if len(color_str) == 3:
            # #RGB格式
            r = int(color_str[0] * 2, 16)
            g = int(color_str[1] * 2, 16)
            b = int(color_str[2] * 2, 16)
        elif len(color_str) == 6:
            # #RRGGBB格式
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
        elif len(color_str) == 8:
            # #RRGGBBAA格式
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
        else:
            raise ValueError(f"无效的十六进制颜色代码: {color_str}")
    elif color_str in ['white', 'WHITE']:
        r, g, b = 255, 255, 255
    elif color_str in ['black', 'BLACK']:
        r, g, b = 0, 0, 0
    elif color_str in ['red', 'RED']:
        r, g, b = 255, 0, 0
    elif color_str in ['green', 'GREEN']:
        r, g, b = 0, 255, 0
    elif color_str in ['blue', 'BLUE']:
        r, g, b = 0, 0, 255
    else:
        # 尝试解析为RGB元组字符串，如"255,0,0"
        try:
            r, g, b = map(int, color_str.split(','))
        except:
            raise ValueError(f"无法解析颜色: {color_str}")
    return (r, g, b)

class CreateTag:
    RETURN_TYPES = ("IMAGE", "MASK",)
    RETURN_NAMES = ("image", "mask",)
    FUNCTION = "create_tag"
    CATEGORY = "SuperSuger/文本"
    DESCRIPTION = "创建简单的文本标签，支持行高调节和图像载入。"

    @classmethod
    def INPUT_TYPES(cls):
        # 定义节点输入参数
        inputs = {
            "required": {
                "image": ("IMAGE",),
                "text": ("STRING", {"default": 'text', "multiline": True}),
                "position_x": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 1}),
                "position_y": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 1}),
                "height": ("INT", {"default": 90, "min": 10, "max": 2048, "step": 1}),
                "font_size": ("INT", {"default": 16, "min": 1, "max": 256, "step": 1}),
                "line_height": ("FLOAT", {"default": 1.4, "min": 0.5, "max": 5.0, "step": 0.1}),
                "font_color": ("STRING", {"default": 'white'}),
                "background_color": ("STRING", {"default": 'black'}),
                "direction": (
                    ['top', 'bottom', 'left', 'right', 'top coverage', 'bottom coverage'],
                    {"default": 'bottom'}
                ),
            }
        }
        
        # 添加字体选择器
        # 检查插件根目录下的sugar_fonts目录
        plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        font_dir = os.path.join(plugin_root, "sugar_fonts")
        
        if os.path.exists(font_dir):
            try:
                font_files = os.listdir(font_dir)
                # 过滤出字体文件
                font_files = [f for f in font_files if f.lower().endswith(('.ttf', '.otf', '.woff', '.woff2'))]
                if font_files:
                    inputs["required"]["font"] = (font_files,)
                else:
                    inputs["required"]["font"] = (["default"],)
            except:
                inputs["required"]["font"] = (["default"],)
        else:
            # 如果sugar_fonts目录不存在，使用系统默认字体
            inputs["required"]["font"] = (["default"],)
        
        return inputs

    def create_tag(self, image, text, position_x, position_y, height, font_size, line_height, font_color, background_color, font, direction='bottom'):
        # 解析颜色
        text_color = parse_color(font_color)
        bg_color = parse_color(background_color)
        
        # 将输入的图像张量转换为PIL图像
        image_np = image.cpu().numpy()[0]
        image_np = (image_np * 255).astype(np.uint8)
        pil_image = Image.fromarray(image_np, mode="RGB")
        
        # 获取字体路径
        font_path = None
        if font != "default":
            plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            font_dir = os.path.join(plugin_root, "sugar_fonts")
            font_path = os.path.join(font_dir, font)
        
        # 加载字体
        if font_path and os.path.exists(font_path):
            current_font = ImageFont.truetype(font_path, font_size)
        else:
            # 使用默认字体
            current_font = ImageFont.load_default()
        
        # 自动换行函数
        def wrap_text(text, font, max_width):
            lines = []
            words = text.split()
            if not words:
                return lines
            
            current_line = words[0]
            for word in words[1:]:
                test_line = current_line + " " + word
                width = ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(test_line, font=font)
                if width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
            return lines
        
        # 分割文本为多行并处理自动换行
        paragraphs = text.split('\n')
        lines = []
        max_text_width = 0
        
        # 计算标签宽度（根据方向决定）
        if direction in ['top', 'bottom', 'top coverage', 'bottom coverage']:
            # 水平方向的标签宽度为图片宽度减去边距
            tag_width = pil_image.width - position_x * 2
        else:  # 'left', 'right'
            # 垂直方向的标签宽度根据文本内容
            # 先估算最大宽度
            temp_lines = []
            for para in paragraphs:
                if para.strip():
                    temp_lines.extend(para.split())
            if temp_lines:
                max_temp_width = max([ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(word, font=current_font) for word in temp_lines])
                tag_width = max(int(max_temp_width * 1.5), 50)
            else:
                tag_width = 50
        
        # 处理自动换行
        for para in paragraphs:
            if para.strip():
                wrapped_lines = wrap_text(para, current_font, tag_width - 10)
                lines.extend(wrapped_lines)
                # 更新最大文本宽度
                for line in wrapped_lines:
                    line_width = ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(line, font=current_font)
                    if line_width > max_text_width:
                        max_text_width = line_width
            else:
                # 保留空行
                lines.append('')
        
        # 计算每行高度和总高度
        line_spacing = font_size * line_height
        total_text_height = len(lines) * line_spacing
        
        # 调整标签宽度
        if direction in ['left', 'right']:
            tag_width = max(int(max_text_width + 10), tag_width)
        
        # 根据方向调整图片大小和标签位置
        image_width, image_height = pil_image.size
        tag_x = tag_y = 0
        
        if direction == 'top':
            # 在图片上方添加区域
            new_height = image_height + height
            new_image = Image.new('RGB', (image_width, new_height), bg_color)
            new_image.paste(pil_image, (0, height))
            tag_x = position_x
            tag_y = position_y
        elif direction == 'bottom':
            # 在图片下方添加区域
            new_height = image_height + height
            new_image = Image.new('RGB', (image_width, new_height), bg_color)
            new_image.paste(pil_image, (0, 0))
            tag_x = position_x
            tag_y = image_height + position_y
        elif direction == 'left':
            # 在图片左侧添加区域
            new_width = image_width + tag_width
            new_image = Image.new('RGB', (new_width, image_height), bg_color)
            new_image.paste(pil_image, (tag_width, 0))
            tag_x = position_x
            tag_y = position_y
        elif direction == 'right':
            # 在图片右侧添加区域
            new_width = image_width + tag_width
            new_image = Image.new('RGB', (new_width, image_height), bg_color)
            new_image.paste(pil_image, (0, 0))
            tag_x = image_width + position_x
            tag_y = position_y
        elif direction == 'top coverage':
            # 在图片上方覆盖文字（不添加新区域）
            new_image = pil_image.copy()
            tag_x = position_x
            tag_y = position_y
            # 覆盖模式不绘制背景
            draw_background = False
        elif direction == 'bottom coverage':
            # 在图片下方覆盖文字（不添加新区域）
            new_image = pil_image.copy()
            tag_x = position_x
            tag_y = pil_image.height - total_text_height - position_y
            # 覆盖模式不绘制背景
            draw_background = False
        else:
            # 默认情况
            new_image = pil_image.copy()
            tag_x = position_x
            tag_y = position_y
            draw_background = True
        
        # 创建掩码
        mask = Image.new("L", new_image.size, 0)
        draw_image = ImageDraw.Draw(new_image)
        draw_mask = ImageDraw.Draw(mask)
        
        # 绘制背景（如果需要）
        draw_background = direction not in ['top coverage', 'bottom coverage']
        if draw_background:
            if direction in ['top', 'bottom']:
                # 水平方向的标签背景
                draw_image.rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + height], fill=bg_color)
                draw_mask.rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + height], fill=255)
            else:  # 'left', 'right'
                # 垂直方向的标签背景
                draw_image.rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + total_text_height], fill=bg_color)
                draw_mask.rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + total_text_height], fill=255)
        
        # 绘制文本
        current_y = tag_y
        for line in lines:
            if line.strip():
                # 计算文本宽度
                line_width = ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(line, font=current_font)
                
                # 根据方向调整文本位置
                if direction in ['top', 'bottom', 'top coverage', 'bottom coverage']:
                    # 水平方向居中或左对齐
                    text_x = tag_x + (tag_width - line_width) // 2
                else:  # 'left', 'right'
                    # 垂直方向左对齐
                    text_x = tag_x + 5
                
                # 绘制文本
                try:
                    draw_image.text((text_x, current_y), line, fill=text_color, font=current_font, features=['-liga'])
                    # 更新掩码
                    draw_mask.text((text_x, current_y), line, fill=255, font=current_font, features=['-liga'])
                except:
                    draw_image.text((text_x, current_y), line, fill=text_color, font=current_font)
                    draw_mask.text((text_x, current_y), line, fill=255, font=current_font)
            
            # 移动到下一行，应用行高
            current_y += line_spacing
        
        # 转换为张量
        new_image_np = np.array(new_image).astype(np.float32) / 255.0
        result_image_tensor = torch.from_numpy(new_image_np)[None, :]
        
        mask_np = np.array(mask).astype(np.float32) / 255.0
        mask_tensor = torch.from_numpy(mask_np)[None, :]
        
        return (result_image_tensor, mask_tensor,)
