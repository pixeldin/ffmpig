from win10toast import ToastNotifier
toaster = ToastNotifier()
toaster.show_toast("Hello World!!!",
                   "Python is 10 seconds awsm!",
                   icon_path=None,
                   duration=2)

toaster.show_toast("Example two",
                   "This notification is in it's own thread!",
                   icon_path=None,
                   duration=3)
# Wait for threaded notification to finish
while toaster.notification_active(): time.sleep(0.1)
