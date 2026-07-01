Set WshShell = CreateObject("WScript.Shell")
' El 0 significa "ocultar ventana" (hide window)
WshShell.Run "pythonw.exe main.py", 0, False
