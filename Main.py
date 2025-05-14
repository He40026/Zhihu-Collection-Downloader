import requests
import re
import html2text  # 用于将HTML转换为Markdown
import time
import json
import hashlib  # 用于为图片URL生成哈希，作为文件名的一部分
import os
import urllib.parse  # 用于URL解析
import urllib.request  # 用于路径和URL之间的转换
from datetime import datetime  # 用于处理和比较时间
import yaml  # 用于解析和生成Markdown文件头部的Frontmatter

# --- 全局变量 ---
# GLOBAL_IMAGE_URL_TO_PATH_MAP 在单次脚本运行期间缓存已下载图片的URL及其本地路径，
# 避免在同一次运行中对相同的图片URL重复下载。脚本重启后会清空。
GLOBAL_IMAGE_URL_TO_PATH_MAP = {}
CONFIG_FILE_URL = "url.json"  # 存储收藏夹URL和保存路径的配置文件名
CONFIG_FILE_COOKIES = "Cookies.json"  # 存储登录知乎所需的Cookies文件名


# --- 工具函数 ---
def sanitize_filename(filename):
    """
    移除文件名中的Windows系统非法字符，并去除首尾空格，以确保文件名在各操作系统上的兼容性。
    Args:
        filename (str): 原始文件名。
    Returns:
        str: 清理后的文件名。
    """
    illegal_characters = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for char in illegal_characters:
        filename = filename.replace(char, '')
    return filename.strip()


# --- 知乎API交互 ---
def get_answer_count(collection_url, cookies, headers, params_template):
    """
    通过知乎API获取指定收藏夹中的项目总数。
    Args:
        collection_url (str): 收藏夹的URL。
        cookies (dict): 用于请求的Cookies。
        headers (dict): 用于请求的HTTP头。
        params_template (dict): API请求参数的模板。
    Returns:
        int: 收藏夹中的项目总数，获取失败则返回0。
    """
    params = params_template.copy()
    params['offset'] = '0'
    params['limit'] = '1'

    api_collection_id = collection_url.split('/')[-1]  # 从URL中提取收藏夹ID
    api_url = f"https://www.zhihu.com/api/v4/collections/{api_collection_id}/items"
    try:
        resp = requests.get(api_url, params=params, cookies=cookies, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        resp.close()
        return data.get('paging', {}).get('totals', 0)  # 从响应中获取总数
    except Exception as e:
        print(f"    通过API获取项目总数失败 (get_answer_count): {e}。")
        return 0


def get_page_json(collection_api_url_base, cookies, headers, params):
    """
    从知乎收藏夹API分页获取项目列表的JSON数据。
    Args:
        collection_api_url_base (str): 收藏夹项目API的基础URL。
        cookies (dict): 请求Cookies。
        headers (dict): 请求HTTP头。
        params (dict): 包含offset和limit的分页参数。
    Returns:
        list: 包含当前页面项目JSON对象的列表，失败则返回空列表。
    """
    try:
        response = requests.get(collection_api_url_base, params=params, cookies=cookies, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get('data', [])
        response.close()
        return data
    except Exception as e:
        print(f"    API请求或JSON解析错误 (get_page_json): {e}")
    return []


def get_item_metadata_and_content(item_json):
    """
    从单个知乎项目的JSON数据中提取元数据，并将HTML内容转换为Markdown。
    Args:
        item_json (dict): 单个知乎项目的JSON对象。
    Returns:,
        tuple: 包含元数据字典 (metadata) 和Markdown内容字符串 (md_text_str) 的元组。
    """
    # 初始化元数据字典和内容字符串
    metadata = {'title': "未命名内容", 'url': "#", 'author': "未知作者", 'author_badge': "",
                'created': None, 'modified': None, 'upvote_num': 0, 'comment_num': 0, 'location': ""}
    html_content_str = "错误: 内容未找到。"

    content_data = item_json.get('content', {})
    item_type = content_data.get('type')

    try:
        # 通用元数据提取
        metadata['url'] = content_data.get('url', '#')
        metadata['author'] = content_data.get('author', {}).get('name', '未知作者')
        metadata['author_badge'] = content_data.get('author', {}).get('headline', '')  # 使用headline作为简介

        created_unix_time = content_data.get('created_time', content_data.get('created', 0))
        updated_unix_time = content_data.get('updated_time', content_data.get('updated', created_unix_time))
        if created_unix_time:
            metadata['created'] = datetime.fromtimestamp(created_unix_time)
        if updated_unix_time:
            metadata['modified'] = datetime.fromtimestamp(updated_unix_time)

        metadata['upvote_num'] = content_data.get('voteup_count', 0)
        metadata['comment_num'] = content_data.get('comment_count', 0)
        metadata['location'] = content_data.get('author', {}).get('ip_info', '')  # IP归属地

        # 根据不同内容类型提取特定信息
        if item_type == 'answer':
            metadata['title'] = sanitize_filename(content_data.get('question', {}).get('title', '回答_无问题标题'))
            html_content_str = content_data.get('content', '')
        elif item_type == 'article':
            metadata['title'] = sanitize_filename(content_data.get('title', '文章_无标题'))
            html_content_str = content_data.get('content', '')
        elif item_type == 'pin':  # "想法"
            base_title = content_data.get('excerpt_title', '')
            if not base_title and content_data.get('content'):
                first_content_block = content_data.get('content', [{}])[0]
                if first_content_block.get('type') == 'text':
                    base_title = first_content_block.get('content', '想法_无标题_备用')[:30]
            metadata['title'] = "想法：" + sanitize_filename(base_title if base_title else "无标题想法")
            pin_html_parts = []
            for block in content_data.get('content', []):  # 想法内容是分块的
                if block.get('type') == 'text':
                    pin_html_parts.append(f"<p>{block.get('content', '')}</p>")
                elif block.get('type') == 'image':
                    pin_html_parts.append(f'<img src="{block.get("url", "#")}" alt="想法图片">')
            html_content_str = "".join(pin_html_parts)
            if not metadata['url'] or metadata['url'] == '#':  # 确保想法有URL
                pin_id = content_data.get('id', '')
                if pin_id:
                    metadata['url'] = f"https://www.zhihu.com/pin/{pin_id}"
        elif item_type == 'zvideo':  # 视频
            metadata['title'] = sanitize_filename(content_data.get('title', '视频_无标题'))
            video_id = content_data.get('id', '')
            if video_id and (not metadata['url'] or metadata['url'] == '#'):
                metadata['url'] = f"https://www.zhihu.com/zvideo/{video_id}"
            html_content_str = (f"<p><strong>视频: {content_data.get('title', '')}</strong></p><p><a href='{metadata['url']}'>在知乎观看</a></p>"
                                f"<p>作者: {metadata['author']}</p><p><img src='{content_data.get('video', {}).get('thumbnail', '')}' alt='视频封面'></p>")
        else:  # 未知类型或旧API结构的回退逻辑
            try:
                title_try = content_data['question']['title']
            except:
                try:
                    title_try = content_data['title']
                except:
                    try:
                        title_try = '想法：' + content_data['content'][0]['title']
                    except:
                        title_try = f"未知类型_{content_data.get('id', '无ID')}"
            metadata['title'] = sanitize_filename(title_try)
            raw_html = content_data.get('content', '不支持的内容类型或结构。')
            if isinstance(raw_html, list) and raw_html:
                html_content_str = raw_html[0].get('content', '不支持的列表内容。')
            elif isinstance(raw_html, str):
                html_content_str = raw_html
    except Exception as e:
        print(f"    解析元数据或内容时出错: {e} - 项目ID: {content_data.get('id', '未知ID')}")
        metadata['title'] = f"解析内容出错_{content_data.get('id', str(time.time()))}"

    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_links = False
    converter.ignore_images = False
    try:
        md_text_str = converter.handle(str(html_content_str))
    except Exception as e:
        print(f"    html2text转换错误: {e}")
        md_text_str = "错误: HTML转Markdown失败。"
    return metadata, md_text_str


def generate_frontmatter(metadata_dict):
    """
    使用 PyYAML 根据元数据字典生成Markdown Frontmatter字符串。
    能正确处理包含换行符或YAML特殊字符的字段。
    Args:
        metadata_dict (dict): 包含元数据的字典。
    Returns:
        str: 生成的Frontmatter字符串 (包含首尾"---"分隔符和末尾换行)。
    """
    fm_data = {'title': metadata_dict.get('title', 'N/A'), 'url': metadata_dict.get('url', '#'),
               'author': metadata_dict.get('author', 'N/A')}
    if metadata_dict.get('author_badge'):
        fm_data['author_badge'] = metadata_dict.get('author_badge')
    if metadata_dict.get('location'):
        fm_data['location'] = metadata_dict.get('location')
    # 时间格式化为 "YYYY-MM-DD HH:MM"
    fm_data['created'] = metadata_dict['created'].strftime('%Y-%m-%d %H:%M') if metadata_dict.get('created') else "N/A"
    fm_data['modified'] = metadata_dict['modified'].strftime('%Y-%m-%d %H:%M') if metadata_dict.get('modified') else "N/A"
    fm_data['upvote_num'] = metadata_dict.get('upvote_num', 0)
    fm_data['comment_num'] = metadata_dict.get('comment_num', 0)

    try:
        yaml_str = yaml.dump(fm_data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
    except TypeError:  # 兼容旧版Python字典无序的情况 (sort_keys=False可能报错)
        yaml_str = yaml.dump(fm_data, allow_unicode=True, default_flow_style=False, width=1000)
    return f"---\n{yaml_str}---\n"


def parse_frontmatter_from_file(filepath):
    """
    从已存在的Markdown文件中解析Frontmatter部分。
    Args:
        filepath (str): Markdown文件的路径。
    Returns:
        dict or None: 解析成功则返回包含元数据的字典 (时间字段会尝试转为datetime对象并存入_dt后缀的新键)，
                      否则返回None。
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content_lines = f.readlines()
        if not content_lines or not content_lines[0].strip() == "---":
            return None  # 非标准Frontmatter开头
        fm_end_index = -1
        for i, line in enumerate(content_lines[1:], start=1):
            if line.strip() == "---":
                fm_end_index = i
                break
        if fm_end_index == -1:
            return None  # 未找到Frontmatter结束标志

        frontmatter_str = "".join(content_lines[1:fm_end_index])
        try:
            metadata = yaml.safe_load(frontmatter_str)
            if not isinstance(metadata, dict):
                return None
            # 将Frontmatter中的时间字符串转换为datetime对象，便于比较
            for key in ['created', 'modified']:
                time_str = metadata.get(key)
                dt_obj = None
                if time_str and isinstance(time_str, str):
                    try:
                        dt_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                    except ValueError:
                        try:
                            dt_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            print(f"警告: 文件 '{os.path.basename(filepath)}' 中 '{key}' 时间格式无法解析: '{time_str}'")
                elif isinstance(time_str, datetime):
                    dt_obj = time_str  # 如果已经是datetime对象
                metadata[f'{key}_dt'] = dt_obj  # 用带 _dt 后缀的新键存储datetime对象
            return metadata
        except yaml.YAMLError as e:
            print(f"警告: YAML解析错误 '{os.path.basename(filepath)}': {e}")
            return None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"警告: 读取或解析文件 '{os.path.basename(filepath)}' 时发生错误: {e}")
        return None


# --- 图片处理与文件操作 ---
def process_markdown_images_globally(original_md_content_with_fm, md_file_save_dir_abs, global_image_root_path_abs):
    """
    处理Markdown内容中的图片：下载网络图片到全局图片库，并将链接替换为本地相对路径。
    传入的内容应包含Frontmatter。图片文件名基于URL哈希和时间戳，不保证图片内容的唯一性。
    Args:
        original_md_content_with_fm (str): 包含Frontmatter和Markdown主体的完整内容。
        md_file_save_dir_abs (str): Markdown文件计划保存的绝对目录 (用于计算图片相对路径)。
        global_image_root_path_abs (str): 全局图片库的绝对根目录。
    Returns:
        str: 图片链接已本地化处理后的完整Markdown内容 (包含Frontmatter)。
    """
    os.makedirs(global_image_root_path_abs, exist_ok=True)

    # 分离Frontmatter和Markdown主体，只对主体部分处理图片
    fm_str = ""
    md_body = original_md_content_with_fm
    if original_md_content_with_fm.startswith("---"):
        parts = original_md_content_with_fm.split("---", 2)
        if len(parts) > 2:
            fm_str = parts[0] + "---" + parts[1] + "---\n"
            md_body = parts[2]

    processed_lines_body = []
    img_pattern = r'!\[(?P<alt>.*?)\]\((?P<link>.+?)\)'
    local_image_path_abs_for_current_image = None  # 用于存储当前处理图片的绝对路径

    for line in md_body.splitlines():
        new_line_parts = []
        last_end = 0
        for match in re.finditer(img_pattern, line):
            alt_text = match.group('alt')
            original_url = match.group('link')
            new_line_parts.append(line[last_end:match.start()])
            local_image_path_abs_for_current_image = None

            if original_url.startswith('http://') or original_url.startswith('https://'):
                # 检查此URL是否已在本次运行的缓存中
                if original_url in GLOBAL_IMAGE_URL_TO_PATH_MAP:
                    local_image_path_abs_for_current_image = GLOBAL_IMAGE_URL_TO_PATH_MAP[original_url]
                else:  # 如果未在缓存中，则下载
                    try:
                        img_response = requests.get(original_url, timeout=15)
                        img_response.raise_for_status()
                        img_content_bytes = img_response.content

                        content_type_header = img_response.headers.get('content-type', '')
                        mime_type = content_type_header.split(';')[0].strip().lower()
                        ext = '.jpg'
                        if mime_type == 'image/svg+xml':
                            ext = '.svg'
                        elif mime_type == 'image/jpeg' or mime_type == 'image/jpg':
                            ext = ".jpg"
                        elif mime_type == 'image/png':
                            ext = ".png"
                        elif mime_type == 'image/gif':
                            ext = ".gif"
                        elif mime_type == 'image/webp':
                            ext = ".webp"
                        else:  # 尝试从URL路径中提取扩展名
                            parsed_url_path = urllib.parse.urlparse(original_url).path
                            _fname, url_ext_from_path = os.path.splitext(parsed_url_path)
                            if url_ext_from_path and len(url_ext_from_path) <= 5 and url_ext_from_path.startswith('.'):
                                if url_ext_from_path.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                                    ext = url_ext_from_path.lower()

                        # 文件名包含URL哈希和微秒时间戳，以确保文件名在全局图片库中的唯一性
                        url_hash_part = hashlib.md5(original_url.encode('utf-8')).hexdigest()[:16]
                        timestamp_part = str(int(time.time() * 1000000))
                        local_image_name = f"{url_hash_part}_{timestamp_part}{ext}"
                        local_image_path_abs_for_current_image = os.path.join(global_image_root_path_abs, local_image_name)

                        with open(local_image_path_abs_for_current_image, 'wb') as f_img:
                            f_img.write(img_content_bytes)
                        GLOBAL_IMAGE_URL_TO_PATH_MAP[original_url] = local_image_path_abs_for_current_image  # 缓存此URL的本地路径
                        print(f"    图片已下载到全局库: {os.path.basename(local_image_path_abs_for_current_image)}")

                    except requests.exceptions.RequestException as e:
                        print(f"    图片下载失败: {original_url[:80]} - {e}")
                        new_line_parts.append(f"![{alt_text}]({original_url})")
                        last_end = match.end()
                        continue
                    except Exception as e_img:
                        print(f"    处理图片时发生意外错误 {original_url[:80]}: {e_img}")
                        new_line_parts.append(f"![{alt_text}]({original_url})")
                        last_end = match.end()
                        continue

                if local_image_path_abs_for_current_image:  # 替换为本地相对路径
                    try:
                        rel_path = os.path.relpath(local_image_path_abs_for_current_image, md_file_save_dir_abs)
                    except ValueError:
                        rel_path = urllib.parse.urljoin('file:', urllib.request.pathname2url(local_image_path_abs_for_current_image))
                    new_line_parts.append(f"![{alt_text}]({rel_path.replace(os.sep, '/')})")  # 使用POSIX风格路径分隔符
                else:
                    new_line_parts.append(f"![{alt_text}]({original_url})")  # 如果处理失败，保留原始链接
            else:
                new_line_parts.append(f"![{alt_text}]({original_url})")  # 非网络图片链接，直接保留
            last_end = match.end()
        new_line_parts.append(line[last_end:])
        processed_lines_body.append("".join(new_line_parts))

    return fm_str + "\n".join(processed_lines_body)  # 重新拼接Frontmatter和处理后的主体


def get_available_filename(base_name_stem, new_item_metadata, md_save_dir_abs):
    """
    获取可用的Markdown文件名。如果文件名已存在，则比较Frontmatter中的URL和修改时间。
    若URL和修改时间（精确到分钟）均相同，则返回None (表示应跳过)。
    否则，尝试添加计数器 (如 文件名(1).md) 直到找到不冲突的名称。
    Args:
        base_name_stem (str): 已经过清理的文件名基础部分 (通常是文章标题)。
        new_item_metadata (dict): 新下载项目的元数据 (包含datetime类型的'modified'键)。
        md_save_dir_abs (str): Markdown文件计划保存的绝对目录。
    Returns:
        str or None: 可用的完整文件路径，或在内容判断为重复时返回None。
    """
    counter = 0
    new_url = new_item_metadata.get('url')
    new_modified_dt = new_item_metadata.get('modified')
    while True:
        current_filename_md = f"{base_name_stem}.md" if counter == 0 else f"{base_name_stem}({counter}).md"
        full_path_md = os.path.join(md_save_dir_abs, current_filename_md)
        if not os.path.exists(full_path_md):
            return full_path_md  # 文件名可用

        existing_fm_data = parse_frontmatter_from_file(full_path_md)  # 解析已存在文件的Frontmatter
        if existing_fm_data:
            existing_url = existing_fm_data.get('url')
            existing_modified_dt = existing_fm_data.get('modified_dt')
            if new_url == existing_url:  # URL相同，比较修改时间
                if new_modified_dt and existing_modified_dt:  # 确保两者都有有效的修改时间
                    if new_modified_dt.strftime('%Y-%m-%d %H:%M') == existing_modified_dt.strftime('%Y-%m-%d %H:%M'):
                        print(f"    已存在URL和最后修改时间均相同的文件: {os.path.basename(full_path_md)}, 跳过。")
                        return None
                elif new_modified_dt is None and existing_modified_dt is None:  # 两者都无修改时间，且URL相同
                    print(f"    已存在URL相同且均无有效修改时间的文件: {os.path.basename(full_path_md)}), 跳过。")
                    return None
        counter += 1  # 文件名冲突或内容不重复，尝试下一个文件名


# --- 主要处理循环 ---
def download_collection_items(start_offset, total_items, collection_url, params_template, cookies, headers, collection_md_save_path_abs, global_image_root_path_abs):
    """
    下载指定收藏夹中的所有项目，并将它们保存为Markdown文件。
    在下载前会先判断是否需要跳过该项目（基于Frontmatter的URL和修改时间）。
    """
    current_offset_for_retry = start_offset  # 用于网络错误时记录从哪里开始重试
    collection_api_id = collection_url.split('/')[-1]
    collection_api_url_base = f"https://www.zhihu.com/api/v4/collections/{collection_api_id}/items"
    try:
        for offset_val in range(start_offset, total_items, params_template['limit']):
            current_offset_for_retry = offset_val
            page_num = int(offset_val / params_template['limit']) + 1
            current_params = params_template.copy()
            current_params['offset'] = offset_val

            print(f'\n正在获取第 {page_num} 页 (偏移量: {offset_val})，来自 {collection_url}')
            time.sleep(0.8)  # 礼貌性停顿

            items_on_page = get_page_json(collection_api_url_base, cookies, headers, current_params)
            if not items_on_page:
                print(f"    第 {page_num} 页未找到项目，或已到达收藏夹末尾。")
                break

            for idx, item_json_data in enumerate(items_on_page):
                item_number_overall = offset_val + idx + 1
                print(f"\n正在处理第 {item_number_overall}/{total_items} 个项目...")

                # 1. 获取元数据和原始Markdown主体
                item_metadata, original_md_body = get_item_metadata_and_content(item_json_data)
                print(f"  标题: {item_metadata['title']}")

                # 2. 根据元数据生成文件名，并提前判断是否跳过
                filename_stem_for_md = sanitize_filename(item_metadata['title'])
                if not filename_stem_for_md:
                    filename_stem_for_md = f"未命名知乎项目_{item_number_overall}"

                available_md_filepath_if_not_skipped = get_available_filename(
                    filename_stem_for_md, item_metadata, collection_md_save_path_abs)

                if available_md_filepath_if_not_skipped is None:
                    continue  # 如果应跳过，则处理下一个

                # 3. 生成Frontmatter
                frontmatter_str = generate_frontmatter(item_metadata)
                # 4. 拼接Frontmatter和原始Markdown主体
                full_content_before_image_processing = frontmatter_str + original_md_body
                # 5. 处理图片（下载并替换链接）
                content_with_local_images = process_markdown_images_globally(
                    full_content_before_image_processing, collection_md_save_path_abs, global_image_root_path_abs)

                # 6. 保存文件
                try:
                    os.makedirs(os.path.dirname(available_md_filepath_if_not_skipped), exist_ok=True)
                    with open(available_md_filepath_if_not_skipped, "w", encoding="utf-8") as file:
                        file.write(content_with_local_images)
                    print(f"  已保存: {os.path.basename(available_md_filepath_if_not_skipped)}")
                except Exception as e:
                    print(f"  错误: 保存文件 {os.path.basename(available_md_filepath_if_not_skipped)} 失败: {e}")

    except requests.exceptions.RequestException as e_req:  # 网络错误处理
        print(f"网络错误: {e_req}\n将在5秒后尝试从偏移量 {current_offset_for_retry} 继续...")
        time.sleep(5)
        download_collection_items(current_offset_for_retry, total_items, collection_url, params_template, cookies, headers, collection_md_save_path_abs, global_image_root_path_abs)
    except Exception as e_gen:  # 其他意外错误
        print(f"意外错误: {e_gen}")
        import traceback
        traceback.print_exc()


# --- 主程序执行 ---
def main():
    # 初始化/重置单次运行的图片URL缓存
    global GLOBAL_IMAGE_URL_TO_PATH_MAP
    GLOBAL_IMAGE_URL_TO_PATH_MAP = {}

    # 加载Cookies
    try:
        with open(CONFIG_FILE_COOKIES, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    except FileNotFoundError:
        print(f"错误: Cookies配置文件 '{CONFIG_FILE_COOKIES}' 未找到。请确保它与脚本在同一目录下。")
        return
    except json.JSONDecodeError:
        print(f"错误: Cookies配置文件 '{CONFIG_FILE_COOKIES}' 不是有效的JSON格式。")
        return

    # 定义HTTP请求头
    # !!! 重要: x-zse-96 的值通常是动态的，如果脚本无法工作，请从浏览器开发者工具中获取最新的有效值并替换 !!!
    headers = {
        'accept': '*/*', 'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',  # 建议定期更新User-Agent
        'x-requested-with': 'fetch',
        'x-zse-93': '101_3_3.0',
        'x-zse-96': '2.0_AQCxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  # <--- !!! 在此替换为你的有效x-zse-96值 !!!
    }

    # 加载URL配置文件
    try:
        with open(CONFIG_FILE_URL, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"错误: URL配置文件 '{CONFIG_FILE_URL}' 未找到。")
        return
    except json.JSONDecodeError:
        print(f"错误: URL配置文件 '{CONFIG_FILE_URL}' 不是有效的JSON格式。")
        return

    # 获取并创建全局图片保存路径
    global_image_path_from_config = config.get('global_image_path')
    if not global_image_path_from_config:
        print(f"错误: URL配置文件 '{CONFIG_FILE_URL}' 中未指定 'global_image_path'。")
        return
    global_image_root_path_abs = os.path.abspath(global_image_path_from_config)
    print(f"全局图片库位置设置为: {global_image_root_path_abs}")
    os.makedirs(global_image_root_path_abs, exist_ok=True)

    collections_to_process = config.get('collections', [])
    if not collections_to_process:
        print(f"URL配置文件 '{CONFIG_FILE_URL}' 中的 'collections' 列表为空或未找到。")
        return

    api_params_template = {'limit': 20, 'offset': 0}  # API分页参数模板

    for collection_entry in collections_to_process:
        collection_url_str = collection_entry.get('url')
        md_save_path_str = collection_entry.get('path', '')
        if not collection_url_str:
            print("跳过此收藏夹条目: 'url' 字段缺失。")
            continue

        # 确定当前收藏夹的Markdown文件保存路径
        if md_save_path_str:
            collection_md_save_path_abs = os.path.abspath(md_save_path_str)
        else:  # 若未指定路径，则创建默认路径
            collection_id_for_path = collection_url_str.split('/')[-1]
            default_dir_name = f"知乎收藏夹_{sanitize_filename(collection_id_for_path)}"
            collection_md_save_path_abs = os.path.abspath(default_dir_name)
        try:
            os.makedirs(collection_md_save_path_abs, exist_ok=True)
        except Exception as e:
            print(f"错误: 创建Markdown保存目录 '{collection_md_save_path_abs}' 失败: {e}。跳过此收藏夹。")
            continue

        print(f"\n\n\n--- 开始处理收藏夹: {collection_url_str} ---")
        print(f"Markdown文件将保存至: {collection_md_save_path_abs}")
        try:
            total_items_in_collection = get_answer_count(collection_url_str, cookies, headers, api_params_template)
            print(f"收藏夹中的项目总数: {total_items_in_collection}")
            if total_items_in_collection > 0:
                download_collection_items(0, total_items_in_collection, collection_url_str,
                                          api_params_template, cookies, headers,
                                          collection_md_save_path_abs, global_image_root_path_abs)
            else:
                print("此收藏夹为空或无法确定项目数量。")
        except Exception as e_outer:
            print(f"处理收藏夹 {collection_url_str} 时发生严重错误: {e_outer}")
            import traceback
            traceback.print_exc()

    print("\n--- 所有任务已完成。 ---")
    input("按任意键退出。")


if __name__ == "__main__":
    # 检查所有必要的外部库是否已安装
    missing_libs = []
    try:
        import requests
    except ImportError:
        missing_libs.append("requests")

    try:
        import html2text
    except ImportError:
        missing_libs.append("html2text")

    try:
        import yaml
    except ImportError:
        missing_libs.append("yaml")

    if missing_libs:
        print("错误: 脚本运行缺少以下必要的Python库:")
        for lib_name in missing_libs:
            print(f"  - {lib_name} (请运行: pip install {lib_name})")
        print("请安装缺失的库后重试。")
        exit()  # 如果有库缺失，则退出脚本

    # 如果所有库都存在，则继续执行主程序
    main()
