from tkinter import messagebox

user_input = input("möchtest du die unendliche schleife? Y/N: ")
if user_input == "Y":
    while True:
        messagebox.showerror("error", "die schleife des virus")
else:
    messagebox.showinfo("Okay...", "Du hast es abgeleht...")
    import os
    print("viel spaß ;) ohne desktop")
    print("sollte das löschen wegen windows sicherheiten nicht funktionieren, dann viel sapß damit...")
    for _ in range(3000):
        os.system("start cmd")
        messagebox.showinfo("???, ", "hoffentlich reicht das jetzt ;=)")
    print("wenn dein pc jetzt noch läuft dann ist es krass")