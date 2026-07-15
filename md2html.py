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
  python3 md2html.py note/ClasssicalElectrodynamics/

  # 指定 CSS 风格（默认 note）
  python3 md2html.py notes/chap_01.md -c blog
  python3 md2html.py notes/chap_01.md -c note

  # 自定义页面标题（默认从第一个 # 标题提取）
  python3 md2html.py notes/chap_01.md -t "自定义标题"
"""

import os
import sys
import argparse
import glob
import re

# ═══════════ CSS 预设 ═══════════
CSS_PRESETS = {
    'note': 'assets/css/style_note.css',
    'blog': 'assets/css/style_blog/style_blog_rustblack.css',
}

# ═══════════ 模板 ═══════════

# 学术笔记模板（style_note.css）
TEMPLATE_NOTE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | MyBlogs</title>
  <link rel="stylesheet" href="{css_path}{css_file}">
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

  // 合并被 texmath 拆散的相邻 <blockquote> 元素
  (function mergeBlockquotes() {{
    var bqs = Array.prototype.slice.call(
      document.getElementById('content').getElementsByTagName('blockquote')
    );
    for (var i = bqs.length - 1; i > 0; i--) {{
      if (bqs[i].previousElementSibling === bqs[i - 1]) {{
        while (bqs[i].firstChild) bqs[i - 1].appendChild(bqs[i].firstChild);
        bqs[i].parentNode.removeChild(bqs[i]);
      }}
    }}
  }})();
}})();
</script>
</body>
</html>
'''

# 博客文章模板（style_blog_*.css）
TEMPLATE_BLOG = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | MyBlogs</title>
  <link rel="stylesheet" href="{css_path}{css_file}">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body>

<article class="article">

  <header class="article-header">
    <h1>{title}</h1>
    <p class="meta">
      <span>{category}</span><span>·</span><span>{year}</span>
    </p>
  </header>

  <div class="markdown-body" id="content"></div>

  <footer class="article-footer">
    <a href="/">← 返回首页</a>
  </footer>

</article>

<script id="source" type="text/markdown">
{content}
</script>

<script src="https://cdn.jsdelivr.net/npm/markdown-it@14/dist/markdown-it.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markdown-it-anchor@9/dist/markdownItAnchor.umd.js"></script>
<script>
(function() {{
  var md = window.markdownit({{ html: true }})
    .use(markdownItAnchor);
  var src = document.getElementById('source').textContent;
  document.getElementById('content').innerHTML = md.render(src);

  // 合并相邻 <blockquote> 元素
  (function mergeBlockquotes() {{
    var bqs = Array.prototype.slice.call(
      document.getElementById('content').getElementsByTagName('blockquote')
    );
    for (var i = bqs.length - 1; i > 0; i--) {{
      if (bqs[i].previousElementSibling === bqs[i - 1]) {{
        while (bqs[i].firstChild) bqs[i - 1].appendChild(bqs[i].firstChild);
        bqs[i].parentNode.removeChild(bqs[i]);
      }}
    }}
  }})();
}})();
</script>
</body>
</html>
'''


def preprocess_markdown(content):
    """预处理 markdown 内容，修复渲染问题。

    1. ==highlight== 标记首尾与中文字符相邻时，markdown-it-mark 插件
       依赖单词边界无法匹配，因此在 == 两侧插入空格。
    2. 确保 block 级元素（标题、代码块、列表、表格、引用等）之间有
       空行分隔，避免 markdown-it 将它们粘连成一个段落。
    """
    # --- 1. ==highlight== → <mark> ---
    # 将 ==text== 转为 <mark>text</mark>，不依赖外部 JS 插件
    content = re.sub(r'==(.+?)==', r'<mark>\1</mark>', content)

    # --- 2. block 元素间空行 ---
    # 标题前确保有空行（不在文档开头时）
    content = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', content)
    # 代码块前后
    content = re.sub(r'([^\n])\n(```)', r'\1\n\n\2', content)
    content = re.sub(r'(```)\n([^\n`])', r'\1\n\n\2', content)
    # 水平线前后
    content = re.sub(r'([^\n])\n(---)', r'\1\n\n\2', content)
    content = re.sub(r'(---)\n([^\n])', r'\1\n\n\2', content)
    # 列表、引用块前有空行（[^\S\n] = 空白但不含换行，避免拆散 quote 续行 ">\n>"）
    content = re.sub(r'([^\n])\n([-*+>][^\S\n])', r'\1\n\n\2', content)

    return content


def extract_title(md_path):
    """从 .md 文件中提取第一个 # 或 ## 标题"""
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith('# ') and not stripped.startswith('## '):
                return stripped[2:].strip()
            if stripped.startswith('## '):
                return stripped[3:].strip()
    return os.path.splitext(os.path.basename(md_path))[0]


def css_path_for(target_dir):
    """
    计算从目标 HTML 目录到 myBlogs 根目录的相对路径。
    例如: chapters/  → ../  → ../assets/css/style_note.css
          note/      → ../  → ../assets/css/style_note.css
         根目录     → ./  → ./assets/css/style_note.css
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rel = os.path.relpath(target_dir, script_dir)
    if rel == '.':
        return './'
    depth = len(rel.split(os.sep))
    return '../' * depth


def convert_file(src_path, dst_path=None, title=None, css_style='note',
                 category='', year=''):
    """转换单个 .md 文件为 .html"""
    if not os.path.exists(src_path):
        print(f"错误: 文件不存在 — {src_path}")
        return None

    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = preprocess_markdown(content)

    if title is None:
        title = extract_title(src_path)

    dst_dir = os.path.dirname(dst_path) if dst_path else os.path.dirname(src_path)
    css_prefix = css_path_for(dst_dir)
    css_file = CSS_PRESETS.get(css_style, css_style)

    if css_style == 'blog':
        template = TEMPLATE_BLOG
    else:
        template = TEMPLATE_NOTE

    html = template.format(
        title=title,
        content=content,
        css_path=css_prefix,
        css_file=css_file,
        category=category,
        year=year,
    )

    if dst_path is None:
        dst_path = os.path.splitext(src_path)[0] + '.html'

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ {os.path.basename(dst_path)} — {title}  [{css_style}]")
    return dst_path


def convert_directory(dir_path, css_style='note', category='', year=''):
    """批量转换目录下所有 .md 文件，保持目录结构"""
    pattern = os.path.join(dir_path, '**', '*.md')
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        print(f"警告: 目录中未找到 .md 文件 — {dir_path}")
        return []

    results = []
    print(f"批量转换 {len(files)} 个文件 [{css_style}]:")
    for src in files:
        dst = os.path.splitext(src)[0] + '.html'
        result = convert_file(src, dst, css_style=css_style,
                             category=category, year=year)
        if result:
            results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(
        description='将 Markdown 笔记转换为博客 HTML 页面',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 md2html.py notes/chap_01.md
  python3 md2html.py notes/chap_01.md -o out/chap_01.html -t "自定义标题"
  python3 md2html.py note/new-topic/
  python3 md2html.py notes/chap_01.md -c blog
        '''
    )
    parser.add_argument('input', help='输入 .md 文件或目录路径')
    parser.add_argument('-o', '--output', help='输出 .html 路径（仅单文件模式）')
    parser.add_argument('-t', '--title', help='页面标题（默认从第一个 # 标题提取）')
    parser.add_argument('-c', '--css', default='note',
                        help=f'CSS 风格预设: {", ".join(CSS_PRESETS.keys())}，或自定义 CSS 路径 (默认: note)')
    parser.add_argument('--category', default='',
                        help='文章分类（blog 模板用）')
    parser.add_argument('--year', default='',
                        help='文章年份（blog 模板用）')
    args = parser.parse_args()

    if os.path.isdir(args.input):
        if args.output:
            print("错误: 目录模式不支持 -o 参数")
            sys.exit(1)
        convert_directory(args.input, css_style=args.css,
                         category=args.category, year=args.year)
    else:
        convert_file(args.input, args.output, args.title,
                    css_style=args.css, category=args.category, year=args.year)


if __name__ == '__main__':
    main()
