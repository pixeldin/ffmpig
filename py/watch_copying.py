import pyperclip
import time

clipboard_history = []

pyperclip.copy('')

i = 0

try:
    while True:
        # 获取当前剪贴板中的内容
        pyperclip.waitForNewPaste()        
        clipboard_content = pyperclip.paste()

        # 如果该内容已经被记录则跳过
        if len(clipboard_content) == 0 or clipboard_content in clipboard_history :
            continue

        # 将该内容添加到已记录的剪贴板内容列表中
        if i % 2 == 0:
            print("From: "+clipboard_content)
        else:
            print("To: "+clipboard_content)
            print("===========================")

        i += 1
        clipboard_history.append(clipboard_content)

except KeyboardInterrupt:
    # 用户按下Ctrl+C结束程序时，打印所有已记录的剪贴板内容
	# for content in clipboard_history:
    string_to_print = "\n".join(clipboard_history)
    print("复制列表结果:\n"+string_to_print)

    time.sleep(500)
