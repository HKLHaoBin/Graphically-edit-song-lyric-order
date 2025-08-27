import re

def parse_time(time_str):
    """将时间字符串转换为秒数"""
    match = re.match(r'\[(\d+):(\d+\.\d+)\]', time_str)
    if match:
        minutes = int(match.group(1))
        seconds = float(match.group(2))
        return minutes * 60 + seconds
    return 0

def sort_lrc_file(filename):
    """排序LRC文件中的翻译行"""
    
    # 读取文件
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 解析每行，提取时间戳和内容
    parsed_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 匹配时间戳和内容
        time_match = re.search(r'(\[\d+:\d+\.\d+\])', line)
        if time_match:
            time_str = time_match.group(1)
            content = line.replace(time_str, '').strip()
            # 移除行号部分（如果有）
            content = re.sub(r'^\s*\d+→', '', content).strip()
            time_seconds = parse_time(time_str)
            parsed_lines.append({
                'time_str': time_str,
                'content': content,
                'time_seconds': time_seconds
            })
    
    # 按时间排序，如果时间相同则按原始顺序
    for i, item in enumerate(parsed_lines):
        item['original_index'] = i
    sorted_lines = sorted(parsed_lines, key=lambda x: (x['time_seconds'], x['original_index']))
    
    # 去除重复行（相同时间戳和内容）
    seen = set()
    unique_lines = []
    for item in sorted_lines:
        key = (item['time_str'], item['content'])
        if key not in seen:
            seen.add(key)
            unique_lines.append(item)
        else:
            print(f"发现重复行并移除: {item['time_str']}{item['content']}")
    
    # 生成排序后的内容
    sorted_content = []
    for item in unique_lines:
        sorted_content.append(f"{item['time_str']}{item['content']}")
    
    # 写回文件
    with open(filename, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(sorted_content))
    
    print(f"已成功排序 {len(unique_lines)} 行翻译（去除了 {len(sorted_lines) - len(unique_lines)} 行重复内容）")

if __name__ == "__main__":
    sort_lrc_file("翻译.lrc")