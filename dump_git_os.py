import os

os.system("git status > git_status_dump.txt 2>&1")
os.system("git log -n 5 >> git_status_dump.txt 2>&1")
os.system("git branch -a >> git_status_dump.txt 2>&1")
