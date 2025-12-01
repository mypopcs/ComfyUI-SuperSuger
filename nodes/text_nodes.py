# 文本节点模块
# 多行文本输入节点 (MultiLineTextInput)
class MultiLineTextInput:
    # 节点配置
    NODE_NAME = "MultiLineTextInput"
    # 节点描述
    CATEGORY = "SuperSuger/提示词"
    # 节点描述
    DESCRIPTION = "多行文本输入节点，输出文本string。"
    # 节点输出参数
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("文本",)
    
    FUNCTION = "execute"
    OUTPUT_NODE = False
    
    @classmethod
    def INPUT_TYPES(cls):
        """定义节点输入参数"""
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "", "placeholder": "输入多行文本..."})
            }
        }
    
    def execute(self, text: str) -> tuple:
        """节点主执行逻辑"""
        return (text,)