; lycloud4A 连接助手 Windows 安装程序（NSIS）
; 安装 lycloud4A.exe 到 Program Files，注册开机自启并静默后台启动；
; 卸载时先结束后台进程、再把卸载器复制到临时目录重启，从而彻底删除整个安装目录。

Unicode true
SetCompressor /SOLID lzma

!define APP_NAME "lycloud4A 连接助手"
!define APP_EXE  "lycloud4A.exe"
!define COMPANY  "lycloud"
!define VERSION  "1.0.9"
!define RUN_KEY  "Software\Microsoft\Windows\CurrentVersion\Run"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\lycloud4A"

Name "${APP_NAME}"
OutFile "lycloud4A-Setup.exe"
InstallDir "$PROGRAMFILES64\lycloud4A"
RequestExecutionLevel admin
ShowInstDetails show
ShowUnInstDetails show

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  nsExec::Exec 'taskkill /F /IM ${APP_EXE}'
  Pop $0
  Sleep 800

  SetOutPath "$INSTDIR"
  File "lycloud4A.exe"

  WriteRegStr HKCU "${RUN_KEY}" "lycloud4A" '"$INSTDIR\${APP_EXE}"'

  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${COMPANY}"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" '"$INSTDIR\${APP_EXE}"'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\uninstall.exe"

  Exec '"$INSTDIR\${APP_EXE}"'
SectionEnd

Section "Uninstall"
  ; 第一阶段：若卸载器正从安装目录运行，先把自身复制到 $TEMP 并以 _?= 重启，
  ; 让真正执行删除的实例不再占用 $INSTDIR，父实例随后收尾退出。
  StrCmp "$INSTDIR\uninstall.exe" "$EXEPATH" relaunch do_remove

  relaunch:
    CopyFiles /SILENT "$EXEPATH" "$TEMP\lycloud4A-uninstall.exe"
    ExecWait '"$TEMP\lycloud4A-uninstall.exe" _?=$INSTDIR'
    Delete "$INSTDIR\uninstall.exe"
    RMDir "$INSTDIR"
    Delete "$TEMP\lycloud4A-uninstall.exe"
    Goto done

  do_remove:
    ; 第二阶段（临时目录实例）：结束进程、等待句柄释放、强删整个目录与注册表
    nsExec::Exec 'taskkill /F /IM ${APP_EXE}'
    Pop $0
    Sleep 1200

    SetOutPath "$TEMP"
    Delete /REBOOTOK "$INSTDIR\${APP_EXE}"
    RMDir /r /REBOOTOK "$INSTDIR"

    DeleteRegValue HKCU "${RUN_KEY}" "lycloud4A"
    DeleteRegKey HKLM "${UNINST_KEY}"

  done:
SectionEnd
