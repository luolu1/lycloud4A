package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestMobaInnerCommand(t *testing.T) {
	logFile := `C:\Users\a\AppData\Local\Temp\moba_sess.log`
	safe := filepath.ToSlash(logFile)
	tee := func(cmd string) string {
		return "((" + cmd + ") 2>&1 | tee -a '" + safe + "')"
	}
	cases := []struct {
		proto string
		port  string
		want  string
	}{
		{"ssh", "22", tee("ssh root@10.0.0.1")},
		{"ssh", "2222", tee("ssh -p 2222 root@10.0.0.1")},
		{"sftp", "", tee("sftp root@10.0.0.1")},
		{"sftp", "2222", tee("sftp -P 2222 root@10.0.0.1")},
		{"scp", "2222", tee("sftp -P 2222 root@10.0.0.1")},
		{"ftp", "", tee("ftp 10.0.0.1")},
		{"ftp", "2121", tee("ftp 10.0.0.1 2121")},
		{"telnet", "23", tee("telnet 10.0.0.1")},
		{"telnet", "2323", tee("telnet 10.0.0.1 2323")},
		{"mosh", "22", tee("mosh root@10.0.0.1")},
		{"mosh", "2222", tee("mosh --ssh='ssh -p 2222' root@10.0.0.1")},
		{"rsh", "", tee("rsh root@10.0.0.1")},
	}
	for _, c := range cases {
		got := mobaInnerCommand(c.proto, "root", "10.0.0.1", c.port, logFile)
		if got != c.want {
			t.Errorf("proto=%s port=%s\n got=%q\nwant=%q", c.proto, c.port, got, c.want)
		}
	}
	// 无日志文件时不应包裹 tee
	if got := mobaInnerCommand("ftp", "root", "10.0.0.1", "", ""); got != "ftp 10.0.0.1" {
		t.Errorf("no-logFile ftp got %q", got)
	}
}

func TestWinSCP(t *testing.T) {
	if got := winscpURL("sftp", "10.0.0.1", "2222"); got != "sftp://10.0.0.1:2222/" {
		t.Errorf("winscpURL sftp got %q", got)
	}
	if got := winscpURL("ftp", "10.0.0.1", ""); got != "ftp://10.0.0.1/" {
		t.Errorf("winscpURL ftp got %q", got)
	}
	if got := winscpURL("weird", "10.0.0.1", ""); got != "sftp://10.0.0.1/" {
		t.Errorf("winscpURL fallback got %q", got)
	}

	r := resolveResp{
		Host: "10.0.0.1", Protocol: "sftp", LoginUsername: "root", Credential: "p@ss",
		ToolKind: "winscp", ExePath: `C:\Program Files (x86)\WinSCP\WinSCP.exe`,
		SessionID: "sess1",
	}
	port := 2222
	r.Port = &port
	args := buildCommand(r)
	want := []string{
		`C:\Program Files (x86)\WinSCP\WinSCP.exe`,
		"sftp://10.0.0.1:2222/",
		"/username=root",
		"/password=p@ss",
		"/log=" + filepath.ToSlash(winscpLogPath("sess1")),
		"/loglevel=0",
	}
	if len(args) != len(want) {
		t.Fatalf("winscp args = %#v", args)
	}
	for i := range want {
		if args[i] != want[i] {
			t.Errorf("winscp arg[%d] = %q, want %q", i, args[i], want[i])
		}
	}
}

func TestSeedSessionLog(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sess.log")
	r := resolveResp{DeviceName: "test", Protocol: "ftp", ToolName: "MobaXterm"}
	seedSessionLog(path, r)
	seedSessionLog(path, r) // 应追加而非覆盖
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	got := string(data)
	if !strings.Contains(got, "会话已启动") || !strings.Contains(got, "设备=test") || !strings.Contains(got, "协议=ftp") {
		t.Errorf("表头内容缺失: %q", got)
	}
	if n := strings.Count(got, "会话已启动"); n != 2 {
		t.Errorf("应追加两次，实际 %d 次: %q", n, got)
	}
	seedSessionLog("", r) // 空路径不应 panic
}
