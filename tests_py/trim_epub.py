import os
import re
from bs4 import BeautifulSoup

try:
    import ebooklib
    from ebooklib import epub
except ModuleNotFoundError as exc:
    raise RuntimeError("请先安装 ebooklib 库: pip install EbookLib") from exc

def clean_html_to_text(html_content):
    """提取 HTML 中的纯文本和标题，仅用于判断章节名和字数"""
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find(['h1', 'h2', 'title'])
    title = title_tag.get_text(strip=True) if title_tag else "未命名章节"
    text = soup.get_text(separator='\n', strip=True)
    return title, text

def chinese_to_arabic(cn_str):
    """中文数字转阿拉伯数字"""
    if str(cn_str).isdigit():
        return int(cn_str)
        
    cn_num = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    cn_unit = {'十': 10, '百': 100, '千': 1000, '万': 10000}
    
    result = 0
    tmp = 0
    for char in cn_str:
        if char in cn_num:
            tmp = cn_num[char]
        elif char in cn_unit:
            if tmp == 0 and char == '十': 
                tmp = 1
            result += tmp * cn_unit[char]
            tmp = 0
    result += tmp
    return result

def get_logical_chapter_index(title, last_index):
    """获取逻辑章节号"""
    if re.search(r'(楔子|引子|序章)', title):
        return 0
    match = re.search(r'第([\d一二三四五六七八九十百千万零]+)[章节回]', title)
    if match:
        num_str = match.group(1)
        return chinese_to_arabic(num_str)
    return last_index + 1

def extract_chapters_to_epub(epub_path, output_epub_path, target_chapters):
    """
    读取原 EPUB，提取指定章节，并打包成新的 EPUB。
    :param target_chapters: list, 例如 [1, 2] 表示只提取第1章和第2章
    """
    print(f"正在读取原文件: {epub_path}")
    book = epub.read_epub(epub_path)
    
    # 1. 创建一本全新的书
    new_book = epub.EpubBook()
    
    # 获取原书名并添加后缀
    original_title = book.get_metadata('DC', 'title')
    title_str = original_title[0][0] if original_title else "未知书名"
    new_book.set_title(f"{title_str} (节选)")
    new_book.set_language('zh')
    
    last_main_index = 0  
    new_chapters = [] # 用于存放提取出来的新章节，后续构建目录用
    
    # 2. 遍历原书所有元素
    for item in book.get_items():
        # 复制原书的样式表、图片、字体，确保新书排版不乱
        if item.get_type() in [ebooklib.ITEM_STYLE, ebooklib.ITEM_IMAGE, ebooklib.ITEM_FONT, ebooklib.ITEM_COVER]:
            new_book.add_item(item)
            continue
            
        # 处理文本/HTML内容
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            html_content = item.get_content().decode('utf-8')
            chapter_title, raw_text = clean_html_to_text(html_content)
            char_count = len(raw_text)
            
            # 过滤字数过少的非正文章节
            if char_count < 500 or chapter_title == "未命名章节":
                continue
                
            logical_index = get_logical_chapter_index(chapter_title, last_main_index)
            if logical_index > 0:
                last_main_index = max(last_main_index, logical_index)
            
            # --- 如果是我们要提取的目标章节 ---
            if logical_index in target_chapters:
                print(f"[+] 成功提取: {chapter_title} (字数: {char_count})")
                
                # 创建新的章节对象，保留原来的 HTML 和排版
                new_chapter = epub.EpubHtml(
                    title=chapter_title,
                    file_name=item.file_name,
                    media_type=item.media_type
                )
                new_chapter.set_content(item.get_content()) # 注入原 HTML
                
                new_book.add_item(new_chapter)
                new_chapters.append(new_chapter)

    if not new_chapters:
        print("⚠️ 未找到匹配的章节，生成终止。")
        return

    # 3. 重新构建新书的目录 (TOC) 和导航
    new_book.toc = tuple(new_chapters)
    new_book.add_item(epub.EpubNcx())
    new_book.add_item(epub.EpubNav())
    
    # 重新构建阅读顺序 (Spine)
    new_book.spine = ['nav'] + new_chapters
    
    # 4. 导出保存
    # 确保输出目录存在
    output_dir = os.path.dirname(output_epub_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    epub.write_epub(output_epub_path, new_book)
    print(f"\n✅ 处理完成！新的 EPUB 文件已保存至: {output_epub_path}")

if __name__ == "__main__":
    # 替换为你的真实路径
    TARGET_EPUB = "../data/real_book/静默的铁证(米烛光著).epub" 
    # 输出文件现在是一个明确的 .epub 后缀文件
    OUTPUT_EPUB = "./test_epub_partial/静默的铁证_前两章节选.epub"
    
    # 指定要拆出的章节序号
    WANTED_CHAPTERS = [1, 4] 
    
    extract_chapters_to_epub(TARGET_EPUB, OUTPUT_EPUB, WANTED_CHAPTERS)