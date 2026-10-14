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
	"io/fs"
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

var version = "1.0.9"

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
	case "winscp":
		// WinSCP 会话 URL 只带协议/主机/端口；凭证改用 /username、/password 开关，
		// 免去密码中特殊字符的 URL 编码。日志用 /log（Normal 级别，不记录密码明文）。
		args := []string{r.ExePath, winscpURL(proto, host, port)}
		if user != "" {
			args = append(args, "/username="+user)
		}
		if pass != "" {
			args = append(args, "/password="+pass)
		}
		if r.SessionID != "" {
			args = append(args, "/log="+filepath.ToSlash(winscpLogPath(r.SessionID)), "/loglevel=0")
		}
		return args
	case "chrome":
		// 裸 host 会触发 Chrome 账户选择页，必须带 http(s) scheme
		return []string{r.ExePath, "--new-window", webURL(r)}
	default:
		return []string{r.ExePath}
	}
}

// 客户端不再清洗控制序列：原始伪终端流（含光标移动/擦除/备用屏幕等）原样上传，
// 由服务端 render_terminal 重放成操作者实际看到的文本。若在客户端先删掉 CSI 序列，
// 服务端就无法区分“vim 全屏重绘”和普通输出，反而更容易残留乱码。

func mobaLogPath(sessionID string) string {
	tmp := os.TempDir()
	return filepath.Join(tmp, "moba_"+sessionID+".log")
}

// winscpLogPath 是 WinSCP 传递给 /log 的会话日志文件（每次连接会话号唯一，不会串写）。
func winscpLogPath(sessionID string) string {
	return filepath.Join(os.TempDir(), "winscp_"+sessionID+".log")
}

// seedSessionLog 预创建会话日志文件并写入一行表头。
//
// 这样即使被适配软件本身（或其本地命令）没能产出任何终端输出，审计侧也始终有
// 一份可查看的会话记录——既能说明“助手确实启动了会话”，也能据此判断 tee 是否生效。
func seedSessionLog(path string, r resolveResp) {
	if path == "" {
		return
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return
	}
	defer f.Close()
	fmt.Fprintf(
		f,
		"[lycloud4A] 会话已启动 %s 设备=%s 协议=%s 工具=%s\r\n",
		time.Now().Format("2006-01-02 15:04:05"), r.DeviceName, r.Protocol, r.ToolName,
	)
}

// winscpURL 返回 WinSCP 会话 URL（不含凭证，凭证走 /username、/password 开关）。
// 末尾斜杠表示直接进入远程目录而不是下载某个文件。
func winscpURL(proto, host, port string) string {
	scheme := strings.ToLower(proto)
	switch scheme {
	case "sftp", "scp", "ftp", "ftps", "ftpes":
	default:
		scheme = "sftp"
	}
	url := scheme + "://" + host
	if port != "" {
		url += ":" + port
	}
	return url + "/"
}

func mobaInnerCommand(proto, user, host, port, logFile string) string {
	target := host
	if user != "" {
		target = user + "@" + host
	}

	sshCmd := "ssh " + target
	if port != "" && port != "22" {
		sshCmd = "ssh -p " + port + " " + target
	}

	// sftp/scp 用 MobaXterm 自带的 sftp 客户端开一个真正的 SFTP 会话，
	// 而不是退化成 ssh 终端（端口用 -P，区别于 ssh 的 -p）。
	// scp 本身没有交互会话，同样落到同主机的 sftp 会话做文件传输。
	sftpCmd := "sftp " + target
	if port != "" && port != "22" {
		sftpCmd = "sftp -P " + port + " " + target
	}

	var cmd string
	switch proto {
	case "sftp", "scp":
		cmd = sftpCmd
	case "telnet":
		cmd = "telnet " + host
		if port != "" && port != "23" {
			cmd = "telnet " + host + " " + port
		}
	case "ftp":
		cmd = "ftp " + host
		if port != "" && port != "21" {
			cmd = "ftp " + host + " " + port
		}
	case "mosh":
		if port != "" && port != "22" {
			cmd = "mosh --ssh='ssh -p " + port + "' " + target
		} else {
			cmd = "mosh " + target
		}
	case "rsh":
		cmd = "rsh " + target
	default:
		cmd = sshCmd
	}

	// 所有协议统一经 tee 落盘：此前只有 ssh/telnet 分支带 tee，
	// 导致 SFTP/FTP/Mosh/Rsh 等会话完全没有会话日志。
	if logFile != "" {
		cmd = fmt.Sprintf("((%s) 2>&1 | tee -a '%s')", cmd, filepath.ToSlash(logFile))
	}
	return cmd
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
	body, _ := json.Marshal(map[string]string{"ticket": ticket, "client_version": version})
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

func uploadSessionLog(platform string, r resolveResp, logContent string, snapshot bool) {
	if r.AuditID == 0 || r.Username == "" || r.SessionID == "" {
		return
	}
	base := strings.TrimRight(platform, "/")
	if base == "" {
		base = platformFallback
	}
	mode := "append"
	if snapshot {
		mode = "snapshot"
	}
	body, _ := json.Marshal(map[string]any{
		"audit_id":    r.AuditID,
		"username":    r.Username,
		"session_id":  r.SessionID,
		"log_content": logContent,
		"mode":        mode,
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

// tailUploader 跟踪一个本地日志文件并上传到服务端。
//
// 追加型文件（MobaXterm/SecureCRT 的 tee -a、NetCatty raw 日志）只上传新增的
// **原始**字节，由服务端渲染；快照型文件（NetCatty 默认 txt 日志每次刷新都会
// 用渲染后的整份内容覆盖写）则整份上传，服务端按快照覆盖，避免重复追加。
type tailUploader struct {
	platform string
	info     resolveResp
	path     string
	offset   int64
	snapshot bool
	lastSize int64
	lastMod  time.Time
}

func (t *tailUploader) attach(path string) {
	if path == t.path {
		return
	}
	t.path = path
	t.offset = 0
	t.lastSize = -1
	t.lastMod = time.Time{}
	lower := strings.ToLower(path)
	t.snapshot = strings.HasSuffix(lower, ".txt")
}

func (t *tailUploader) poll() {
	if t.path == "" {
		return
	}
	fi, err := os.Stat(t.path)
	if err != nil || fi.IsDir() {
		t.path = ""
		return
	}

	if t.snapshot {
		// 快照型：内容被整体重写，只要大小/时间有变化就整份重新上传。
		if fi.Size() == t.lastSize && fi.ModTime().Equal(t.lastMod) {
			return
		}
		data, rerr := os.ReadFile(t.path)
		if rerr != nil {
			return
		}
		t.lastSize, t.lastMod = fi.Size(), fi.ModTime()
		if len(data) > 0 {
			uploadSessionLog(t.platform, t.info, string(data), true)
		}
		return
	}

	if fi.Size() < t.offset { // 文件被截断/轮转：从头重读
		t.offset = 0
	}
	if fi.Size() == t.offset {
		return
	}
	data, err := os.ReadFile(t.path)
	if err != nil || int64(len(data)) <= t.offset {
		return
	}
	chunk := string(data[t.offset:])
	t.offset = int64(len(data))
	if chunk != "" {
		uploadSessionLog(t.platform, t.info, chunk, false)
	}
}

// netcattyLogRoots 返回 NetCatty 会话日志的候选根目录。NetCatty 的“会话日志”
// 默认关闭，且目录由用户在 NetCatty 内选择（存在 renderer localStorage），外部
// 无法代开或读取；因此这里只做“开了就能自动生效”的最佳努力探测。开启后日志写入
// 所选目录下的 “{主机}/” 子目录，文件名有两种：
//   {主机}_{YYYY-MM-DDTHH-MM-SS}.txt   手动/连续日志
//   {YYYY-MM-DDTHH-MM-SS}.log          自动保存
// 若目录不在下列候选路径内，可在部署时把实际目录加入这里。
func netcattyLogRoots() []string {
	var roots []string
	add := func(base, app string) {
		if base == "" {
			return
		}
		roots = append(roots,
			filepath.Join(base, app, "logs"),
			filepath.Join(base, app, "session-logs"),
		)
	}
	add(os.Getenv("APPDATA"), "netcatty")
	add(os.Getenv("APPDATA"), "Netcatty")
	add(os.Getenv("LOCALAPPDATA"), "netcatty")
	return roots
}

// netcattyLogName 匹配 NetCatty 会话日志的文件名，用来把它和 Electron 自身的
// 应用日志（如 logs/main.log）区分开。会话日志有两种命名：
//   {主机}_{YYYY-MM-DDTHH-MM-SS}.txt   手动/连续日志
//   {YYYY-MM-DDTHH-MM-SS}.log          自动保存（目录名即主机）
var netcattyLogName = regexp.MustCompile(`(?i)(^|_)\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.(txt|log)$`)

// findNetcattyLog 在候选目录中递归查找 since 之后写入的最新会话日志。
// 只接受扩展名与时间戳命名都符合 NetCatty 会话日志的文件，避免误传应用日志。
func findNetcattyLog(roots []string, host string, since time.Time) string {
	var bestHost, bestAny string
	var hostMod, anyMod time.Time
	hostLower := strings.ToLower(strings.TrimSpace(host))
	for _, root := range roots {
		_ = filepath.WalkDir(root, func(p string, d fs.DirEntry, err error) error {
			if err != nil || d == nil || d.IsDir() {
				return nil
			}
			lower := strings.ToLower(d.Name())
			if !strings.HasSuffix(lower, ".txt") && !strings.HasSuffix(lower, ".log") {
				return nil
			}
			if !netcattyLogName.MatchString(d.Name()) {
				return nil
			}
			fi, ferr := d.Info()
			if ferr != nil || fi.ModTime().Before(since) {
				return nil
			}
			mod := fi.ModTime()
			if mod.After(anyMod) {
				anyMod, bestAny = mod, p
			}
			if hostLower != "" && strings.Contains(strings.ToLower(p), hostLower) && mod.After(hostMod) {
				hostMod, bestHost = mod, p
			}
			return nil
		})
	}
	if bestHost != "" {
		return bestHost
	}
	return bestAny
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
	// MobaXterm 依赖 tee -a 落盘，tee 只追加；先写一行表头，保证任何情况下都有一份
	// 可查看的会话记录（若表头之后为空，即说明该协议本地命令没有可捕获的终端输出）。
	if info.ToolKind == "mobaxterm" && info.SessionID != "" {
		seedSessionLog(mobaLogPath(info.SessionID), info)
	}
	if err := launch(buildCommand(info)); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	go func() {
		startedAt := time.Now().Add(-1 * time.Minute)
		isNetcatty := info.ToolKind == "netcatty"
		roots := netcattyLogRoots()

		tail := tailUploader{platform: body.Platform, info: info}
		if (info.ToolKind == "mobaxterm" || info.ToolKind == "securecrt") && info.SessionID != "" {
			tail.attach(mobaLogPath(info.SessionID))
		}
		if info.ToolKind == "winscp" && info.SessionID != "" {
			tail.attach(winscpLogPath(info.SessionID))
		}
		if isNetcatty {
			// NetCatty 的“会话日志”需在客户端开启并指定目录，日志写在 “{主机}/” 子目录下。
			tail.attach(findNetcattyLog(roots, info.Host, startedAt))
		}

		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()
		timeout := time.After(30 * time.Minute)

		for {
			select {
			case <-timeout:
				return
			case <-ticker.C:
				if isNetcatty {
					// 会话日志文件可能在连接建立后才创建，持续尝试发现最新的文件。
					if p := findNetcattyLog(roots, info.Host, startedAt); p != "" {
						tail.attach(p)
					}
				}
				tail.poll()
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
