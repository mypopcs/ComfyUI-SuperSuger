本项目为 ComfyUI 辅助插件，本插件目标是通过聚合实用的节点工具，减少安装和配置的复杂度，提高工作效率。通过参考其他插件，使用 AI 编程工具辅助完成，欢迎提供实用的节点以增加插件的功能。

# 更新日志

1. 新增指定目录批量加载图片，支持通过随机值和运行次数结合加载指定文件夹中的所有图片
2. 新增同时保存文本和图像，支持自定义文件名前缀，分隔符，后缀，文本编码，指定保存目录

# 手动安装方法

1. 下载本插件的压缩包
2. 解压压缩包到 `ComfyUI/custom_nodes` 文件夹中
3. 重启 ComfyUI 即可

# 使用方法

使用 comfyui 快速搜索框，输入关键词 SG 可快速定位节点：

- 批量加载图片的节点名为：SG_BatchImageLoader，中文名为：批量加载图像 (SG)。
- 同时保存文本和图像的节点名为：SG_ImageWithTextSaver，中文名为：保存文本和图像 (SG)。

# 支持界面中文

1. 首先需要安装汉化插件 [ComfyUI-DD-Translation](https://github.com/Dontdrunk/ComfyUI-DD-Translation)
2. 将 `translation\zh-CN\Nodes` 文件夹中的 `ComfyUI-SuperSuger.json` 文件复制到 `ComfyUI/custom_nodes/ComfyUI-DD-Translation/zh-CN/Nodes` 文件夹中
3. 重启 ComfyUI 即可

# 作者主页
