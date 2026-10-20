# EPUB WebP to JPG/PNG Converter

很多现代 EPUB 电子书使用了 WebP 格式图片以减小体积，但 Kindle 等老式设备并不支持 WebP，强行转换又会导致体积膨胀或封面丢失。本脚本通过智能分流和极致压缩算法，完美解决这一痛点。

## ✨ 核心特性

- 🧠 **智能格式分流**：
  - **带透明通道**的图片：自动转换为高质量 PNG，完美保留透明效果。
  - **无透明通道**的图片：调用 Google `cjpegli` 引擎，转换为极致压缩的 JPG，体积大幅缩减。
- ️ **深度 EPUB 结构修复**：
  - 自动更新 HTML/CSS/SVG 中的图片引用（完美兼容空格与 `%20` 编码）。
  - 自动更新 OPF 清单（`manifest`）中的 `href`、`media-type` 和 `id`。
  - **独家修复**：自动更新 OPF 元数据（`<meta name="cover">`），彻底解决转换后 Kindle 封面丢失的问题。
-  **安全无忧**：
  - 自动备份原文件至 `webp_backup` 文件夹（优先保留原名，冲突时智能追加时间戳）。
  - 处理失败时自动回滚，绝不损坏原书。
- 🚀 **极简交互**：支持直接拖拽文件或文件夹到脚本/EXE 图标上，一键批量处理。

## 📋 前置要求

1. **Python 3.8+**
2. **Python 依赖库**：
```bash
   pip install Pillow lxml
```
3. **cjpegli 命令行工具**
    - 将 cjpegli.exe 放入系统 PATH，或放在本脚本同级目录下。

## 使用方法

### 方式一：命令行拖拽（推荐）

直接将一个或多个 `.epub` 文件（或包含 epub 的文件夹）拖拽到 `EPUB_WebP_to_JPG_PNG.py` 图标上。

### 方式二：交互式运行

双击运行脚本，在弹出的控制台窗口中，将 epub 文件或文件夹拖入窗口，按回车即可。输入 `q` 可退出。

### 方式三：作为 EXE 运行

直接下载编译好的 `.exe` 单文件，按以上两种方法运行即可。

## ⚙️ 工作原理

1. 脚本将 EPUB 解压到临时目录。
2. 遍历所有 WebP 图片，使用 Pillow 检测 Alpha 通道。
3. 若有透明通道，使用 Pillow 最高压缩级别 (`compress_level=9`) 转为 PNG。
4. 若无透明通道，先转为临时 PNG，再调用 `cjpegli` 以 `Quality 90` 和 `4:4:4` 色度采样转为 JPG。
5. 使用正则表达式和 `lxml` 解析器，精准替换所有文本引用和 OPF 元数据。
6. 删除原 WebP 文件，重新打包 EPUB 并覆盖原文件。

## 免责声明
本工具仅供学习和交流使用。处理前脚本会自动备份原文件，但作者不对因使用本工具导致的任何数据丢失或设备损坏负责。建议在处理珍贵书籍前，自行保留一份原始备份。

## 编译

使用 `pyinstaller` 编译
```
pyinstaller --onefile --console --add-binary "cjpegli.exe;." --collect-all lxml --collect-all PIL EPUB_WebP_to_JPG_PNG.py
```

## 📄 License

MIT License
