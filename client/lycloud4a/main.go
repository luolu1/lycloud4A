// lycloud4A 本地连接助手客户端（Windows 后台常驻，无控制台窗口）。
//
// 安装后随登录自启，监听 127.0.0.1:47621。lycloud4A 平台页面点击“连接”后，
// 浏览器把一次性票据与平台地址 POST 给本客户端；客户端回调平台 /connect/resolve
// 换取设备信息与解密后的凭证，再按适配软件（MobaXterm/NetCatty/Xshell/SecureCRT/Chrome）
// 构建命令并本地启动对应程序，实现一键登录。
//
// 构建（无控制台窗口，后台常驻）：
//
//	GOOS=windows GOARCH=amd64 go build -ldflags "-s -w -H windowsgui" -o lycloud4A.exe .
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const defaultPlatform = "http://127.0.0.1:8000"

var platformFallback = defaultPlatform

var version = "1.0.4"

type resolveResp struct {
	DeviceID       int    `json:"device_id"`
	DeviceName     string `json:"device_name"`
	Host           string `json:"host"`
	Port           *int   `json:"port"`
	Protocol       string `json:"protocol"`
	URL            string `json:"url"`
	LoginUsername  string `json:"login_username"`
	CredentialType string `json:"credential_type"`
	Credential     string `json:"credential"`
	ToolKind       string `json:"tool_kind"`
	ToolName       string `json:"tool_name"`
	ExePath        string `json:"exe_path"`
	Username       string `json:"username"`
	AuditID        int    `json:"audit_id"`
	SessionID      string `json:"session_id"`
	UploadURL      string `json:"upload_url"`
}

func buildCommand(r resolveResp) []string {
	host := r.Host
	port := ""
	if r.Port != nil && *r.Port > 0 {
		port = strconv.Itoa(*r.Port)
	}
	user := r.LoginUsername
	pass := r.Credential
	proto := strings.ToLower(r.Protocol)

	switch r.ToolKind {
	case "mobaxterm":
		logFile := ""
		if r.SessionID != "" {
			logFile = mobaLogPath(r.SessionID)
		}
		// -newtab 接收“标签页内执行的命令”，传 user@host 会被当本地命令 -> command not found
		return []string{r.ExePath, "-newtab", mobaInnerCommand(proto, user, host, port, logFile)}
	case "netcatty":
		return []string{r.ExePath, buildURL(proto, user, pass, host, port)}
	case "xshell":
		return []string{r.ExePath, buildURL(proto, user, pass, host, port)}
	case "securecrt":
		logFile := ""
		if r.SessionID != "" {
			logFile = mobaLogPath(r.SessionID)
		}
		args := []string{r.ExePath}
		if logFile != "" {
			args = append(args, "/LOG", logFile)
		}
		switch proto {
		case "telnet":
			args = append(args, "/TELNET")
		case "serial":
			args = append(args, "/SERIAL")
		default:
			args = append(args, "/SSH2")
		}
		if user != "" {
			args = append(args, "/L", user)
		}
		if pass != "" {
			args = append(args, "/PASSWORD", pass)
		}
		if port != "" {
			args = append(args, "/P", port)
		}
		return append(args, host)
	case "chrome":
		// 裸 host 会触发 Chrome 账户选择页，必须带 http(s) scheme
		return []string{r.ExePath, "--new-window", webURL(r)}
	default:
		return []string{r.ExePath}
	}
}

var ansiRegex = regexp.MustCompile(`\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])`)

func cleanANSI(text string) string {
	return ansiRegex.ReplaceAllString(text, "")
}

func mobaLogPath(sessionID string) string {
	tmp := os.TempDir()
	return filepath.Join(tmp, "moba_"+sessionID+".log")
}

func mobaInnerCommand(proto, user, host, port, logFile string) string {
	target := host
	if user != "" {
		target = user + "@" + host
	}
	if proto == "sftp" || proto == "scp" {
		port = "22"
	}
	sshPort := port
	sshCmd := "ssh " + target
	if sshPort != "" && sshPort != "22" {
		sshCmd = "ssh -p " + sshPort + " " + target
	}
	
	if logFile != "" {
		safeLog := filepath.ToSlash(logFile)
		sshCmd = fmt.Sprintf("((%s) 2>&1 | tee -a '%s')", sshCmd, safeLog)
	}

	switch proto {
	case "sftp", "scp":
		return sshCmd
	case "telnet":
		telnetCmd := "telnet " + host
		if port != "" && port != "23" {
			telnetCmd = "telnet " + host + " " + port
		}
		if logFile != "" {
			safeLog := filepath.ToSlash(logFile)
			telnetCmd = fmt.Sprintf("((%s) 2>&1 | tee -a '%s')", telnetCmd, safeLog)
		}
		return telnetCmd
	case "ftp":
		if port != "" && port != "21" {
			return "ftp " + host + " " + port
		}
		return "ftp " + host
	case "mosh":
		if sshPort != "" && sshPort != "22" {
			return "mosh --ssh='ssh -p " + sshPort + "' " + target
		}
		return "mosh " + target
	case "rsh":
		return "rsh " + target
	default:
		return sshCmd
	}
}

// webURL 返回 Chrome 应打开的完整 http(s) 地址。
func webURL(r resolveResp) string {
	raw := strings.TrimSpace(r.URL)
	if strings.HasPrefix(raw, "http://") || strings.HasPrefix(raw, "https://") {
		return raw
	}
	scheme := "https"
	if strings.ToLower(r.Protocol) == "http" {
		scheme = "http"
	}
	hostport := r.Host
	if r.Port != nil && *r.Port > 0 {
		hostport = r.Host + ":" + strconv.Itoa(*r.Port)
	}
	path := ""
	if raw != "" && strings.Contains(raw, "/") {
		path = "/" + strings.SplitN(raw, "/", 2)[1]
	}
	return scheme + "://" + hostport + path
}

func buildURL(proto, user, pass, host, port string) string {
	scheme := proto
	if scheme == "" {
		scheme = "ssh"
	}
	auth := ""
	if user != "" {
		auth = user
		if pass != "" {
			auth += ":" + pass
		}
		auth += "@"
	}
	hostport := host
	if port != "" {
		hostport += ":" + port
	}
	return scheme + "://" + auth + hostport
}

func resolveTicket(platform, ticket string) (resolveResp, error) {
	var out resolveResp
	base := strings.TrimRight(platform, "/")
	if base == "" {
		base = platformFallback
	}
	body, _ := json.Marshal(map[string]string{"ticket": ticket})
	req, err := http.NewRequest(http.MethodPost, base+"/api/v1/apps/connect/resolve", bytes.NewReader(body))
	if err != nil {
		return out, err
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return out, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return out, fmt.Errorf("平台返回 %d: %s", resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return out, err
	}
	return out, nil
}

func launch(cmd []string) error {
	if len(cmd) == 0 {
		return fmt.Errorf("空的启动命令")
	}
	return exec.Command(cmd[0], cmd[1:]...).Start()
}

func fileExists(path string) bool {
	if path == "" {
		return false
	}
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

// writeCORS 反射任意来源：本助手仅监听 127.0.0.1，且所有操作都需平台签发的一次性票据，
// 因此允许任意前端来源（含通过内网 IP / HTTPS 访问平台的情况）访问本地接口。
func writeCORS(w http.ResponseWriter, r *http.Request) {
	origin := r.Header.Get("Origin")
	if origin == "" {
		origin = "*"
	}
	w.Header().Set("Access-Control-Allow-Origin", origin)
	w.Header().Set("Vary", "Origin")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
}

func writeJSON(w http.ResponseWriter, code int, body map[string]any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(body)
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeCORS(w, r)
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "agent": "lycloud4A", "version": version})
}

func handleDetect(w http.ResponseWriter, r *http.Request) {
	writeCORS(w, r)
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	var body struct {
		ExePath string `json:"exe_path"`
	}
	raw, _ := io.ReadAll(r.Body)
	_ = json.Unmarshal(raw, &body)
	writeJSON(w, http.StatusOK, map[string]any{
		"exe_path":  body.ExePath,
		"installed": fileExists(body.ExePath),
	})
}

func uploadSessionLog(platform string, r resolveResp, logContent string) {
	if r.AuditID == 0 || r.Username == "" || r.SessionID == "" {
		return
	}
	base := strings.TrimRight(platform, "/")
	if base == "" {
		base = platformFallback
	}
	body, _ := json.Marshal(map[string]any{
		"audit_id":    r.AuditID,
		"username":    r.Username,
		"session_id":  r.SessionID,
		"log_content": logContent,
	})
	req, err := http.NewRequest(http.MethodPost, base+"/api/v1/apps/connect/upload-log", bytes.NewReader(body))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err == nil {
		_ = resp.Body.Close()
	}
}

func handleConnect(w http.ResponseWriter, r *http.Request) {
	writeCORS(w, r)
	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	var body struct {
		Ticket   string `json:"ticket"`
		Platform string `json:"platform"`
	}
	raw, _ := io.ReadAll(r.Body)
	if err := json.Unmarshal(raw, &body); err != nil || body.Ticket == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "缺少 ticket"})
		return
	}
	info, err := resolveTicket(body.Platform, body.Ticket)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
		return
	}
	if !fileExists(info.ExePath) {
		writeJSON(w, http.StatusNotFound, map[string]any{
			"error": fmt.Sprintf("未检测到 %s，请确认已安装或在平台更新路径：%s", info.ToolName, info.ExePath),
		})
		return
	}
	if err := launch(buildCommand(info)); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	go func() {
		localLogFile := ""
		if (info.ToolKind == "mobaxterm" || info.ToolKind == "securecrt") && info.SessionID != "" {
			localLogFile = mobaLogPath(info.SessionID)
		}

		appData := os.Getenv("APPDATA")
		isNetcatty := info.ToolKind == "netcatty"
		var netcattyLogDir string
		if isNetcatty && appData != "" {
			netcattyLogDir = filepath.Join(appData, "netcatty", "logs")
		}
		
		var uploadedBytes int64 = 0
		var netcattyActiveFile string
		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()
		timeout := time.After(30 * time.Minute)

		for {
			select {
			case <-timeout:
				return
			case <-ticker.C:
				if localLogFile != "" {
					if fi, err := os.Stat(localLogFile); err == nil && fi.Size() > uploadedBytes {
						data, rerr := os.ReadFile(localLogFile)
						if rerr == nil && len(data) > int(uploadedBytes) {
							newPart := cleanANSI(string(data[uploadedBytes:]))
							if newPart != "" {
								uploadSessionLog(body.Platform, info, newPart)
							}
							uploadedBytes = int64(len(data))
						}
					}
				}

				if isNetcatty && netcattyLogDir != "" {
					if netcattyActiveFile == "" {
						if entries, err := os.ReadDir(netcattyLogDir); err == nil {
							var latestFile string
							var latestTime time.Time
							for _, e := range entries {
								if !e.IsDir() {
									if fi, ferr := e.Info(); ferr == nil && fi.ModTime().After(latestTime) {
										latestTime = fi.ModTime()
										latestFile = filepath.Join(netcattyLogDir, e.Name())
									}
								}
							}
							if latestFile != "" && latestTime.After(time.Now().Add(-1*time.Minute)) {
								netcattyActiveFile = latestFile
							}
						}
					}

					if netcattyActiveFile != "" {
						if fi, err := os.Stat(netcattyActiveFile); err == nil && fi.Size() > uploadedBytes {
							data, rerr := os.ReadFile(netcattyActiveFile)
							if rerr == nil && len(data) > int(uploadedBytes) {
								newPart := cleanANSI(string(data[uploadedBytes:]))
								if newPart != "" {
									uploadSessionLog(body.Platform, info, newPart)
								}
								uploadedBytes = int64(len(data))
							}
						}
					}
				}
			}
		}
	}()
	writeJSON(w, http.StatusOK, map[string]any{
		"launched": true,
		"device":   info.DeviceName,
		"tool":     info.ToolName,
	})
}

func main() {
	var host, platform string
	var port int
	flag.StringVar(&platform, "platform", defaultPlatform, "lycloud4A 平台地址（仅作回退，正常由页面传入）")
	flag.StringVar(&host, "host", "127.0.0.1", "监听地址")
	flag.IntVar(&port, "port", 47621, "监听端口")
	flag.Parse()
	platformFallback = strings.TrimRight(platform, "/")

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/detect", handleDetect)
	mux.HandleFunc("/connect", handleConnect)

	addr := fmt.Sprintf("%s:%d", host, port)
	_ = http.ListenAndServe(addr, mux)
}
