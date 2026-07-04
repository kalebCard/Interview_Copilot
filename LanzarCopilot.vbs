Set WshShell = CreateObject("WScript.Shell")
' Set the working directory to the script's own folder
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' El 0 significa "ocultar ventana" (hide window)
WshShell.Run "pythonw.exe main.py", 0, False
