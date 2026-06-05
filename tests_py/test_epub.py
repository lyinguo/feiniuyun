import os
import json
import re
import unittest

try:
    import ebooklib
    from ebooklib import epub
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("ebooklib is not installed") from exc
from bs4 import BeautifulSoup

# 配置项：字符到 Token 的估算乘数
# 视具体大模型而定，通常中文在 1.0 ~ 1.5 之间，取 1.2 作为安全估算值

 # 假设你的处理窗口是 8k token

def clean_html_to_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find(['h1', 'h2', 'title'])
    title = title_tag.get_text(strip=True) if title_tag else "未命名章节"
    text = soup.get_text(separator='\n', strip=True)
    return title, text

def chinese_to_arabic(cn_str):
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

def is_valid_chapter(title, char_count, min_chars=1200):
    if title == "未命名章节": return False
    junk_prefixes = ('自序', '代序', '序言', '前言', '写在', '致谢', '后记', '版权', '扉页', '目录', '引言')
    for prefix in junk_prefixes:
        if title.startswith(prefix): return False
        
    whitelist_pattern = re.compile(r'(第[\d一二三四五六七八九十百千万零]+[章节回]|楔子|引子|序章|尾声|番外|终章)')
    if whitelist_pattern.search(title): return True
    if char_count < min_chars: return False
    return True

def get_logical_chapter_index(title, last_index):
    if re.search(r'(楔子|引子|序章)', title):
        return 0
    match = re.search(r'第([\d一二三四五六七八九十百千万零]+)[章节回]', title)
    if match:
        num_str = match.group(1)
        return chinese_to_arabic(num_str)
    return last_index + 1

def process_epub_to_dataset(epub_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    CONTEXT_WINDOW_LIMIT = 8000 
    print(f"正在读取文件: {epub_path}")
    book = epub.read_epub(epub_path)
    
    # 全局统计变量
    total_book_char_count = 0
    total_book_estimated_tokens = 0
    
    metadata = {
        "book_title": book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else "Unknown Title",
        "total_char_count": 0,          # 新增：全书总字符数
        "total_estimated_tokens": 0,    # 新增：全书总Token数
        "chapters": []
    }
    
    last_main_index = 0  
    used_indices_count = {}  
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            html_content = item.get_content().decode('utf-8')
            chapter_title, raw_text = clean_html_to_text(html_content)
            char_count = len(raw_text)
            
            if not is_valid_chapter(chapter_title, char_count, min_chars=1200):
                continue
                
            logical_index = get_logical_chapter_index(chapter_title, last_main_index)
            
            if logical_index > 0:
                last_main_index = max(last_main_index, logical_index)
                
            if logical_index in used_indices_count:
                used_indices_count[logical_index] += 1
                file_name = f"chapter_{logical_index:03d}_{used_indices_count[logical_index]}.txt"
            else:
                used_indices_count[logical_index] = 0
                file_name = f"chapter_{logical_index:03d}.txt"
                
            file_path = os.path.join(output_dir, file_name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(raw_text)
            TOKEN_MULTIPLIER = 1.2 
            # --- 核心改动：Token 估算与标准字段命名 ---
            estimated_tokens = int(char_count * TOKEN_MULTIPLIER)
            total_book_char_count += char_count
            total_book_estimated_tokens += estimated_tokens
            
            chapter_info = {
                "logical_index": logical_index,
                "original_title": chapter_title,
                "file_path": f"./{file_name}",
                "char_count": char_count,
                "estimated_tokens": estimated_tokens,
                "fits_in_context": estimated_tokens <= CONTEXT_WINDOW_LIMIT
            }
            metadata["chapters"].append(chapter_info)
            
            print(f"[+] 成功提取: {file_name} -> {chapter_title} | 字数: {char_count} | 估算Token: {estimated_tokens}")

    # 更新全书统计数据
    metadata["total_char_count"] = total_book_char_count
    metadata["total_estimated_tokens"] = total_book_estimated_tokens

    json_path = os.path.join(output_dir, "metadata.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
        
    print(f"\n✅ 处理完成！")
    print(f"📊 统计概览：全书有效字符约 {total_book_char_count:,} 字，估算消耗 {total_book_estimated_tokens:,} Tokens")
    print(f"📁 数据已保存至: {output_dir}")

if __name__ == "__main__":
    TARGET_EPUB = "../data/real_book/静默的铁证(米烛光著).epub" 
    OUTPUT_FOLDER = "./test_epub"
    process_epub_to_dataset(TARGET_EPUB, OUTPUT_FOLDER)
