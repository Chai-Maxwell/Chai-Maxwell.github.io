#!/usr/bin/env python3
"""
md2html.py — 将 Markdown 笔记转换为博客 HTML 页面

## 功能
  将 .md 文件包装为自包含的 .html 文件，使用客户端 markdown-it + KaTeX 渲染。
  数学公式中的 _ ' 等特殊字符不会与 markdown 解析器冲突，无需修改原文。

## 用法

  # 单个文件（输出到同目录，同名 .html）
  python3 md2html.py notes/chap_01.md

  # 指定输出路径
  python3 md2html.py notes/chap_01.md -o output/chap_01.html

  # 批量转换整个目录（保持目录结构）
  python3 md2html.py physics/electrodynamics/

  # 自定义页面标题（默认从第一个 # 标题提取）
  python3 md2html.py notes/chap_01.md -t "自定义标题"

## 示例：导入一个新专题

  # 1. 在 myBlogs 下创建目录
  mkdir -p physics/new-topic/chapters

  # 2. 从 MyNote 复制 .md 文件
  cp ../MyNote/Physics/NewTopic/chapters/*.md physics/new-topic/chapters/

  # 3. 批量转换
  python3 md2html.py physics/new-topic/chapters/

  # 4. 创建专题导航页（手动写 index.html）
  # 5. 在主页 index.html 添加入口
  # 6. git add -A && git commit -m "..." && git push
"""

import os
import sys
import argparse
import glob

TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | MyBlogs</title>
  <link rel="stylesheet" href="{css_path}assets/css/style_note.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/markdown-it@14/dist/markdown-it.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/markdown-it-anchor@9/dist/markdownItAnchor.umd.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/markdown-it-texmath@1/texmath.min.js"></script>
</head>
<body>
<div class="markdown-body" id="content"></div>

<script id="source" type="text/markdown">
{content}
</script>

<script>
(function() {{
  var md = window.markdownit({{ html: true }})
    .use(markdownItAnchor)
    .use(texmath, {{
      engine: katex,
      delimiters: 'dollars',
      katexOptions: {{ throwOnError: false }}
    }});
  var src = document.getElementById('source').textContent;
  document.getElementById('content').innerHTML = md.render(src);
}})();
</script>
</body>
</html>
'''


def extract_title(md_path):
    """从 .md 文件中提取第一个 # 或 ## 标题"""
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith('# ') and not stripped.startswith('## '):
                return stripped[2:].strip()
            if stripped.startswith('## '):
                return stripped[3:].strip()
    # 回退：用文件名
    return os.path.splitext(os.path.basename(md_path))[0]


def css_path_for(target_dir):
    """
    计算从目标 HTML 目录到 myBlogs 根目录的相对路径，
    使 <link href="{css_path}assets/css/style_note.css"> 正确指向 style_note.css。
    例如: chapters/  → ../  → ../assets/css/style_note.css
          physics/   → ../  → ../assets/css/style_note.css
         根目录     → ./  → ./assets/css/style_note.css
    """
    # 标准化为相对路径
    rel = os.path.relpath(target_dir, os.path.dirname(os.path.abspath(__file__)))
    if rel == '.':
        return './'
    depth = len(rel.split(os.sep))
    return '../' * depth


def convert_file(src_path, dst_path=None, title=None):
    """转换单个 .md 文件为 .html"""
    if not os.path.exists(src_path):
        print(f"错误: 文件不存在 — {src_path}")
        return

    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if title is None:
        title = extract_title(src_path)

    dst_dir = os.path.dirname(dst_path) if dst_path else os.path.dirname(src_path)
    css_prefix = css_path_for(dst_dir)

    html = TEMPLATE.format(title=title, content=content, css_path=css_prefix)

    if dst_path is None:
        dst_path = os.path.splitext(src_path)[0] + '.html'

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ {os.path.basename(dst_path)} — {title}")


def convert_directory(dir_path):
    """批量转换目录下所有 .md 文件，保持目录结构"""
    pattern = os.path.join(dir_path, '**', '*.md')
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        print(f"警告: 目录中未找到 .md 文件 — {dir_path}")
        return

    print(f"批量转换 {len(files)} 个文件:")
    for src in files:
        dst = os.path.splitext(src)[0] + '.html'
        convert_file(src, dst)


def main():
    parser = argparse.ArgumentParser(
        description='将 Markdown 笔记转换为博客 HTML 页面',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 md2html.py notes/chap_01.md
  python3 md2html.py notes/chap_01.md -o out/chap_01.html -t "自定义标题"
  python3 md2html.py physics/new-topic/
        '''
    )
    parser.add_argument('input', help='输入 .md 文件或目录路径')
    parser.add_argument('-o', '--output', help='输出 .html 路径（仅单文件模式）')
    parser.add_argument('-t', '--title', help='页面标题（默认从第一个 # 标题提取）')
    args = parser.parse_args()

    if os.path.isdir(args.input):
        if args.output:
            print("错误: 目录模式不支持 -o 参数")
            sys.exit(1)
        convert_directory(args.input)
    else:
        convert_file(args.input, args.output, args.title)


if __name__ == '__main__':
    main()
