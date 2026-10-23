@echo off
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Controle do PC.lnk'); $s.TargetPath='%~dp0iniciar_oculto.vbs'; $s.WorkingDirectory='%~dp0'; $s.Save()"
echo.
echo Pronto! O servidor vai abrir escondido sempre que o Windows iniciar.
echo Para ligar agora sem reiniciar, de dois cliques em iniciar_oculto.vbs
pause
