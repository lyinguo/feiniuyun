from ebooklib import epub

def create_micro_novel():
    # 1. 初始化书籍基本信息
    book = epub.EpubBook()
    book.set_identifier('test_mock_001')
    book.set_title('微型测试小说')
    book.set_language('zh')
    book.add_author('测试员')

    # 2. 创建第一章
    c1 = epub.EpubHtml(title='第一章', file_name='chap_01.xhtml', lang='zh')
    c1.content = '<h1>第一章</h1><p>张三走进了咖啡厅。李四坐在窗边喝茶。张三对李四说：“你来了。”</p>'
    book.add_item(c1)

    # 3. 创建第二章
    c2 = epub.EpubHtml(title='第二章', file_name='chap_02.xhtml', lang='zh')
    c2.content = '<h1>第二章</h1><p>李四点了点头。气氛变得非常沉重。</p>'
    book.add_item(c2)

    # 4. 创建第三章
    c3 = epub.EpubHtml(title='第三章', file_name='chap_03.xhtml', lang='zh')
    c3.content = '<h1>第三章</h1><p>窗外下起了大雨。故事结束了。</p>'
    book.add_item(c3)

    # 5. 组装目录 (TOC) 和导航
    book.toc = (c1, c2, c3)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # 6. 定义阅读顺序 (Spine)
    book.spine = ['nav', c1, c2, c3]

    # 7. 导出 EPUB 文件
    epub.write_epub('test_micro_novel.epub', book, {})
    print("✅ 成功生成 test_micro_novel.epub！")

if __name__ == '__main__':
    create_micro_novel()