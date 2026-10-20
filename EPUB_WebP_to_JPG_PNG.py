#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB WebP -> JPG/PNG 终极混合处理脚本
- 智能判断透明通道：有透明保留为 PNG，无透明使用 cjpegli 压缩为 JPG
- 完美处理 HTML/CSS/SVG 中的 %20 和空格引用
- 统一更新 OPF 中的 href 和 media-type
- 支持拖放多个文件 / 双击后拖入控制台
- 自动备份原文件，输出保持原文件名
"""
import os
import sys
import shutil
import zipfile
import tempfile
import re
import shlex
import datetime
import subprocess
from pathlib import Path
from PIL import Image
from lxml import etree

# ==========================================
#  配置区域 🛠️
# ==========================================
# 获取 cjpegli.exe 的路径
if getattr(sys, 'frozen', False):
    # 如果是打包后的 EXE
    CJPEGLI_CMD = os.path.join(sys._MEIPASS, 'cjpegli.exe')
else:
    # 如果是直接运行 Python 脚本
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cjpegli.exe')
    CJPEGLI_CMD = local_path if os.path.exists(local_path) else 'cjpegli.exe'

WEBP_EXTENSIONS = {'.webp'}
HTML_EXTENSIONS = {'.html', '.xhtml', '.htm'}
CSS_EXTENSIONS = {'.css'}
SVG_EXTENSIONS = {'.svg'}
REFERENCE_EXTENSIONS = HTML_EXTENSIONS | CSS_EXTENSIONS | SVG_EXTENSIONS
OPF_NAMESPACES = {
    'opf': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/'
}
BACKUP_DIR_NAME = 'webp_backup'

# ==========================================
#  核心转换逻辑 🌟
# ==========================================
def process_webp_image(webp_path):
    """
    处理 WebP 图片：
    1. 有透明通道 -> 转为高质量 PNG
    2. 无透明通道 -> 通过 cjpegli 转为极致压缩的 JPG
    返回: (新文件路径, media_type) 或 (None, None)
    """
    try:
        with Image.open(webp_path) as img:
            # 检查是否有透明通道
            has_alpha = (img.mode in ('RGBA', 'LA', 'PA') or 'transparency' in img.info)
            
            if has_alpha:
                # 保留透明，转为 PNG
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                target_path = webp_path.with_suffix('.png')
                # 使用最高压缩级别
                img.save(target_path, 'PNG', compress_level=9, optimize=True)
                return target_path, 'image/png'
            else:
                # 无透明，转为 JPG
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 先保存为临时 PNG，供 cjpegli 读取
                temp_png = webp_path.with_suffix('.temp_cjpegli.png')
                img.save(temp_png, 'PNG')
                
                target_path = webp_path.with_suffix('.jpg')
                
                # 调用 cjpegli 进行极致压缩
                cmd = [
                    CJPEGLI_CMD,
                    str(temp_png),
                    str(target_path),
                    '-q', '90',
                    '--chroma_subsampling=444'
                ]
                # 执行命令，失败时抛出异常
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # 清理临时文件
                temp_png.unlink()
                return target_path, 'image/jpeg'
                
    except subprocess.CalledProcessError as e:
        print(f"⚠️ cjpegli 转换失败 {webp_path.name}: {e.stderr.strip()}")
        return None, None
    except Exception as e:
        print(f"⚠️ 图片处理出错 {webp_path.name}: {e}")
        return None, None

# ==========================================
#  文本与引用替换逻辑
# ==========================================
def read_text_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        return f.read()

def write_text_file(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)

def make_filename_patterns(old_name):
    patterns = []
    old_esc = re.escape(old_name)
    # 变体1：原始文件名（真实空格）
    patterns.append(re.compile(r'(?<!\w)' + old_esc + r'(?!\w)', re.IGNORECASE))
    if ' ' in old_name:
        # 变体2：空格 -> %20
        url_encoded_20 = old_name.replace(' ', '%20')
        url_esc_20 = re.escape(url_encoded_20)
        patterns.append(re.compile(r'(?<!\w)' + url_esc_20 + r'(?!\w)', re.IGNORECASE))
    return patterns

def get_replacement_names(old_name, new_name):
    names = [new_name]
    if ' ' in old_name:
        names.append(new_name.replace(' ', '%20'))
    return names

def replace_filename_in_reference_files(reference_files, old_name, new_name):
    patterns = make_filename_patterns(old_name)
    new_names = get_replacement_names(old_name, new_name)
    count = 0
    for ref_file in reference_files:
        try:
            content = read_text_file(ref_file)
        except Exception:
            continue
        file_count = 0
        for pattern, new_n in zip(patterns, new_names):
            content, n = pattern.subn(lambda m, _r=new_n: _r, content)
            file_count += n
        if file_count > 0:
            try:
                write_text_file(ref_file, content)
                count += file_count
            except Exception:
                pass
    return count

def update_content_opf(opf_file, old_href, new_href, new_media_type):
    try:
        parser = etree.XMLParser()
        tree = etree.parse(opf_file, parser)
        root = tree.getroot()
        
        # 提取纯文件名和核心名（去掉后缀的部分，例如 001.webp -> 001）
        old_basename = os.path.basename(old_href)
        new_basename = os.path.basename(new_href)
        old_stem = Path(old_basename).stem
        new_suffix = Path(new_basename).suffix
        
        updated = False

        # 1. 更新 manifest 中的 item (href, media-type, id)
        manifest = root.find('.//opf:manifest', OPF_NAMESPACES)
        if manifest is not None:
            for item in manifest.findall('opf:item', OPF_NAMESPACES):
                href = item.get('href', '')
                item_id = item.get('id', '')
                
                # 更新 href 和 media-type
                if href == old_href or href == old_href.replace(' ', '%20'):
                    item.set('href', new_href)
                    item.set('media-type', new_media_type)
                    print(f"✅ OPF href 更新: {href} -> {new_href}")
                    updated = True
                    
                # 2. 智能更新 id
                new_id = None
                
                # 情况 A：id 完全等于旧文件名或旧路径
                if item_id == old_href or item_id == old_basename:
                    new_id = new_href if item_id == old_href else new_basename
                
                # 情况 B：id 带有前缀，但以 .webp 结尾，且包含原文件名的核心部分
                # 例如：id="x001.webp", old_stem="001" -> 匹配成功，改为 "x001.jpg"
                elif item_id.endswith('.webp') and old_stem in item_id and len(old_stem) > 1:
                    new_id = item_id[:-5] + new_suffix  # 去掉 .webp (5个字符)，加上新后缀
                
                if new_id:
                    item.set('id', new_id)
                    print(f"✅ OPF id 更新: {item_id} -> {new_id}")
                    updated = True

        # 3. 更新 metadata 中的 meta (修复封面丢失问题)
        metadata = root.find('.//opf:metadata', OPF_NAMESPACES)
        if metadata is not None:
            for meta in metadata.findall('opf:meta', OPF_NAMESPACES):
                if meta.get('name') == 'cover':
                    content = meta.get('content', '')
                    if content == old_href or content == old_basename or content == old_href.replace(' ', '%20'):
                        if content == old_href.replace(' ', '%20'):
                            new_content = new_href.replace(' ', '%20')
                        else:
                            new_content = new_href if content == old_href else new_basename
                        meta.set('content', new_content)
                        print(f"✅ OPF meta cover 更新: {content} -> {new_content}")
                        updated = True

        # 4. 如果有更新，写回文件
        if updated:
            tree.write(opf_file, encoding='utf-8', xml_declaration=True)
            return True
        return False
    except Exception as e:
        print(f"⚠️ OPF 更新失败 {opf_file.name}: {e}")
        return False

# ==========================================
#  EPUB 解压与打包逻辑
# ==========================================
def collect_files_by_extensions(root_dir, extensions):
    result = []
    for root, _, files in os.walk(root_dir):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in extensions:
                result.append(p)
    return result

def find_opf_file(tmpdir):
    container_path = Path(tmpdir) / 'META-INF' / 'container.xml'
    if container_path.exists():
        try:
            tree = etree.parse(container_path)
            rootfile = tree.find('.//rootfile[@media-type="application/oebps-package+xml"]')
            if rootfile is not None:
                full_path = rootfile.get('full-path')
                if full_path:
                    opf = Path(tmpdir) / full_path
                    if opf.exists():
                        return opf
        except Exception:
            pass
    candidates = list(Path(tmpdir).rglob('content.op?'))
    return candidates[0] if candidates else None

def repack_epub(source_dir, output_epub):
    source_dir = Path(source_dir)
    output_epub = Path(output_epub)
    with zipfile.ZipFile(output_epub, 'w', zipfile.ZIP_DEFLATED) as zf:
        mime = source_dir / 'mimetype'
        if mime.exists():
            zf.writestr('mimetype', mime.read_bytes(), compress_type=zipfile.ZIP_STORED)
        else:
            zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        for root, dirs, files in os.walk(source_dir):
            dirs.sort()
            for f in sorted(files):
                if f == 'mimetype':
                    continue
                full = Path(root) / f
                arcname = full.relative_to(source_dir).as_posix()
                zf.write(full, arcname)
    print(f" 已打包: {output_epub}")

def backup_original(epub_path):
    try:
        backup_dir = epub_path.parent / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 优先尝试直接使用原始文件名
        backup_path = backup_dir / epub_path.name
        
        # 2. 如果已存在同名文件，才追加时间戳
        if backup_path.exists():
            stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = backup_dir / f"{epub_path.stem}_{stamp}{epub_path.suffix}"
            
            # 3. 极端情况：同一秒内运行了两次，加个序号防冲突
            n = 1
            while backup_path.exists():
                backup_path = backup_dir / f"{epub_path.stem}_{stamp}_{n}{epub_path.suffix}"
                n += 1
                
        shutil.copy2(epub_path, backup_path)
        
        # 根据是否加了时间戳，给出不同的提示，让你心里有数
        if backup_path.name == epub_path.name:
            print(f"💾 已备份原文件: {backup_path.name} (保留原名)")
        else:
            print(f"💾 发现同名旧备份，已重命名并备份: {backup_path.name}")
            
        return backup_path
    except Exception as e:
        print(f"⚠️ 备份失败: {e}")
        return None

# ==========================================
#  主处理流程
# ==========================================
def process_epub(epub_path):
    epub_path = Path(epub_path).resolve()
    if not epub_path.exists() or epub_path.suffix.lower() != '.epub':
        return

    output_path = epub_path  # 覆盖原文件
    
    # 备份
    backup_path = backup_original(epub_path)
    if not backup_path:
        return

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                zf.extractall(tmpdir)
            
            webp_files = collect_files_by_extensions(tmpdir, WEBP_EXTENSIONS)
            if not webp_files:
                print("🔍 未找到 .webp 图片，跳过。")
                backup_path.unlink() # 没处理就删掉备份
                return
                
            reference_files = collect_files_by_extensions(tmpdir, REFERENCE_EXTENSIONS)
            opf_file = find_opf_file(tmpdir)
            
            print(f"🖼️ 找到 {len(webp_files)} 个 WebP，开始转换...")
            
            for webp_path in webp_files:
                new_path, media_type = process_webp_image(webp_path)
                if not new_path:
                    continue
                
                old_name = webp_path.name
                new_name = new_path.name
                
                # 1. 替换 HTML/CSS/SVG 引用
                replaced = replace_filename_in_reference_files(reference_files, old_name, new_name)
                if replaced > 0:
                    print(f"✅ 文本替换 {replaced} 处: {old_name} -> {new_name}")
                
                # 2. 更新 OPF
                if opf_file:
                    rel_old = os.path.relpath(webp_path, opf_file.parent).replace(os.sep, '/')
                    rel_new = os.path.relpath(new_path, opf_file.parent).replace(os.sep, '/')
                    update_content_opf(opf_file, rel_old, rel_new, media_type)
                
                # 3. 删除原 WebP
                webp_path.unlink()
                
            repack_epub(tmpdir, output_path)
            print(f"🎉 完成: {epub_path.name}\n")
            
    except Exception as e:
        print(f"❌ 处理失败 {epub_path.name}: {e}")
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, epub_path)
            print("♻️ 已从备份恢复原文件。")

def process_many(epub_paths):
    tasks = []
    for p in epub_paths:
        p = Path(p).resolve()
        if p.is_dir():
            tasks.extend(sorted(p.rglob('*.epub')))
        elif p.is_file() and p.suffix.lower() == '.epub':
            tasks.append(p)
            
    if not tasks:
        print("没有可处理的 EPUB 文件。")
        return
        
    print(f" 共 {len(tasks)} 个 EPUB，将原地覆盖并备份。\n")
    for i, epub in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {epub.name}")
        process_epub(epub)

def main():
    args = sys.argv[1:]
    file_args = [a for a in args if not a.startswith('-')]
    
    if file_args:
        process_many(file_args)
        if os.name == 'nt':
            input("\n处理完成，按回车退出...")
        return

    print("=" * 60)
    print("EPUB WebP -> JPG/PNG 终极混合处理脚本")
    print("=" * 60)
    print("用法：拖入文件或文件夹到本脚本图标上，或双击后拖入控制台。")
    
    while True:
        try:
            line = input("\n请拖入文件/文件夹 (输入 q 退出): ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().lower() in ('q', 'quit', 'exit'):
            break
            
        # 简单的路径清理
        paths = [p.strip().strip('"').strip("'") for p in line.split()]
        process_many(paths)

if __name__ == '__main__':
    main()