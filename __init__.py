# 导入节点类
from .nodes.load_nodes import *
from .nodes.save_nodes import *
from .nodes.prompt_combinator import *
from .nodes.text_nodes import *

NODE_CONFIG = {
    #导入
    "SG_BatchImageLoader": {"class": BatchImageLoader, "name": "批量加载图像 (SG)"},
    #保存
    "SG_ImageWithTextSaver": {"class": ImageWithTextSaver, "name": "保存文本和图像 (SG)"},
    #提示词穷举组合
    "SG_ExhaustiveCombinator": {"class": ExhaustivePromptCombinator, "name": "提示词穷举组合 (SG)"},
    #多行文本输入
    "SG_MultiLineTextInput": {"class": MultiLineTextInput, "name": "多行文本输入 (SG)"},
}
def generate_node_mappings(node_config):
    node_class_mappings = {}
    node_display_name_mappings = {}
    for node_name, node_info in node_config.items():
        #节点名
        node_class_mappings[node_name] = node_info["class"]
        #节点显示名
        node_display_name_mappings[node_name] = node_info.get("name", node_info["class"].__name__)
    return node_class_mappings, node_display_name_mappings

NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = generate_node_mappings(NODE_CONFIG)

# 确保 ComfyUI 能够找到 Web 扩展文件
WEB_DIRECTORY = "js"

# 导出所有的映射，这是 ComfyUI 加载插件的约定
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "NODE_CONFIG"]