import sys
import pyperclip

# 从命令行接收字符列表作为参数，以逗号分隔各个元素
text_list = sys.argv[1].split(",")

# 设置当前粘贴索引为0
current_index = 0

# 将剪贴板中的内容替换为列表中的下一个元素
pyperclip.copy(text_list[current_index])

while True:
    # 监听新的粘贴事件
    pyperclip.waitForNewPaste()

    # 更新当前粘贴索引
    current_index += 1

    print("current_index:", current_index)    

    # 输出本次执行的粘贴操作中使用的文本内容
    # print(f"粘贴的文本：{text_list[current_index]}")    

    # 如果遍历结束，就退出程序
    if current_index == len(text_list):
        print("列表遍历结束，程序即将退出。")
        break

    # 将剪贴板中的内容替换为列表中的下一个元素
    pyperclip.copy(text_list[current_index])