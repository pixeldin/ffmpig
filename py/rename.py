import os

def rename_files_in_directory(directory):
    # 遍历当前目录及子目录
    for root, dirs, files in os.walk(directory):
        for file in files:
            # 检查文件是否以'_cut.log'结尾
            if file.endswith('_cut.log'):
                # 构造旧文件路径
                old_file_path = os.path.join(root, file)
                # 构造新文件路径，将后缀从'_cut.log'改为'_cut.plog'
                new_file_path = os.path.join(root, file.replace('_cut.log', '_cut.plog'))
                try:
                    # 重命名文件
                    os.rename(old_file_path, new_file_path)
                    print(f'Renamed: {old_file_path} -> {new_file_path}')
                except Exception as e:
                    print(f'Error renaming file {old_file_path}: {e}')

if __name__ == "__main__":
    # 获取当前目录
    current_directory = os.getcwd()
    # 执行文件重命名操作
    rename_files_in_directory(current_directory)
