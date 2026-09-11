// Package main provides atlas-tui: the ATLAS CLI with interactive TUI.
// Resource-based command structure, output formats, transforms, shell completion.
// Zero external dependencies — stdlib only.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const (
	reset  = "\033[0m"
	bold   = "\033[1m"
	dim    = "\033[2m"
	red    = "\033[31m"
	green  = "\033[32m"
	yellow = "\033[33m"
	blue   = "\033[34m"
	purple = "\033[35m"
	cyan   = "\033[36m"
	bgBlue = "\033[44m"
	clear  = "\033[2J\033[H"
)

var (
	format    = "auto"
	transform = ""
	rawOutput = false
	debug     = false
	home      = "."
)

func init() {
	// Enable ANSI colors on Windows 10+
	exec.Command("cmd", "/c", "color").Run()
}

func main() {
	args := os.Args[1:]
	home = "."
	var filteredArgs []string

	// Parse global flags
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--format":
			if i+1 < len(args) {
				format = args[i+1]
				i++
			}
		case "--transform":
			if i+1 < len(args) {
				transform = args[i+1]
				i++
			}
		case "-r", "--raw-output":
			rawOutput = true
		case "--debug":
			debug = true
		case "--version":
			printVersion()
			return
		case "--help", "-h":
			if len(args) == 1 || (len(args) == 2 && args[1] == "--help") {
				printUsage()
				return
			}
		default:
			filteredArgs = append(filteredArgs, args[i])
		}
	}

	// Resolve home
	resources := map[string]bool{
		"status": true, "health": true, "tools": true, "chain": true,
		"agents": true, "tenants": true, "rbac": true, "mesh": true,
		"rack": true, "prove": true, "help": true, "completion": true,
	}
	if len(filteredArgs) > 0 && !strings.HasPrefix(filteredArgs[0], "-") && !resources[filteredArgs[0]] {
		if fi, err := os.Stat(filteredArgs[0]); err == nil && fi.IsDir() {
			home = filteredArgs[0]
			filteredArgs = filteredArgs[1:]
		}
	}
	abs, _ := filepath.Abs(home)

	// If no args, start interactive mode
	if len(filteredArgs) == 0 {
		interactiveMode(abs)
		return
	}

	// Resource-based command dispatch
	resource := filteredArgs[0]
	rest := filteredArgs[1:]

	switch resource {
	case "status", "health":
		cmdHealth(abs)
	case "tools":
		if len(rest) == 0 || rest[0] == "list" {
			cmdToolsList(abs, rest[1:])
		} else if rest[0] == "get" && len(rest) > 1 {
			cmdToolsGet(abs, rest[1])
		} else {
			cmdToolsList(abs, rest)
		}
	case "chain":
		if len(rest) == 0 || rest[0] == "list" {
			cmdChainList(abs, rest[1:])
		} else if rest[0] == "verify" {
			cmdChainVerify(abs, rest[1:])
		} else {
			cmdChainList(abs, rest)
		}
	case "agents":
		if len(rest) == 0 || rest[0] == "list" {
			cmdAgentsList(abs, rest[1:])
		} else if rest[0] == "get" && len(rest) > 1 {
			cmdAgentsGet(abs, rest[1])
		} else {
			cmdAgentsList(abs, rest)
		}
	case "tenants":
		cmdTenantsList(abs)
	case "rbac":
		if len(rest) == 0 || rest[0] == "list" {
			cmdRBACList(abs)
		} else if rest[0] == "check" && len(rest) > 2 {
			cmdRBACCheck(abs, rest[1], rest[2])
		} else if rest[0] == "assign" && len(rest) > 2 {
			cmdRBACAssign(abs, rest[1], rest[2])
		} else {
			cmdRBACList(abs)
		}
	case "mesh":
		if len(rest) == 0 || rest[0] == "status" {
			cmdMeshStatus(abs)
		} else if rest[0] == "chain" {
			cmdMeshChain(abs)
		} else {
			cmdMeshStatus(abs)
		}
	case "rack":
		if len(rest) == 0 || rest[0] == "list" {
			cmdRackList(abs)
		} else {
			cmdRackList(abs)
		}
	case "prove":
		cmdProve(abs)
	case "help":
		printUsage()
	case "completion":
		if len(rest) > 0 {
			printCompletion(rest[0])
		} else {
			printCompletion("bash")
		}
	default:
		fmt.Fprintf(os.Stderr, "%sUnknown resource: %s%s\n", red, resource, reset)
		fmt.Fprintf(os.Stderr, "Run %satlas-tui help%s for available commands\n", cyan, reset)
		os.Exit(1)
	}
}

func printVersion() {
	if out, err := run("atlas", "--version"); err == nil {
		fmt.Printf("atlas-tui %s\n", strings.TrimSpace(out))
	} else {
		fmt.Println("atlas-tui 0.1.3")
	}
}

func printUsage() {
	fmt.Printf(`
%s%sATLAS CLI — Resource-based command structure%s

%sUsage:%s
  atlas-tui [home] <resource> <action> [flags] [args]
  atlas-tui [home]                    Interactive mode

%sResources:%s
  status              System health and version
  tools list|get      MCP tool surface
  chain list|verify   Hash chain operations
  agents list|get     Agent declarations
  tenants             List carried tenants
  rbac list|check|assign  Role-based access control
  mesh status|chain   Mesh protocol status
  rack list           Local voice ladder
  prove               Run full prove battery
  help                Show this help
  completion <shell>  Generate shell completion

%sFlags:%s
  --format <fmt>      Output: auto, json, yaml, pretty, raw
  --transform <path>  GJSON path to extract field
  -r, --raw-output    Strip quotes from string results
  --debug             Print full request/response
  --version           Print version
  -h, --help          Show help

%sExamples:%s
  atlas-tui . status
  atlas-tui . tools list --format yaml
  atlas-tui . chain verify --format json
  atlas-tui . agents list --transform name -r
  atlas-tui . rbac check manjuel read_handoffs
  atlas-tui . prove
  atlas-tui completion zsh > ~/.zfunc/_atlas-tui

`, bold, cyan, reset,
		bold, reset,
		bold, reset,
		bold, reset,
		bold, reset)
}

func printCompletion(shell string) {
	switch shell {
	case "bash":
		fmt.Print(`_atlas_tui() {
    local cur prev resources actions
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    resources="status tools chain agents tenants rbac mesh rack prove help completion"
    actions="list get verify check assign status chain"

    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "--format --transform --raw-output --debug --version --help" -- ${cur}) )
    elif [[ ${prev} == "tools" || ${prev} == "chain" || ${prev} == "agents" || ${prev} == "rbac" || ${prev} == "mesh" ]]; then
        COMPREPLY=( $(compgen -W "${actions}" -- ${cur}) )
    elif [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${resources}" -- ${cur}) )
    fi
    return 0
}
complete -F _atlas_tui atlas-tui
`)
	case "zsh":
		fmt.Print(`#compdef atlas-tui

_atlas-tui() {
    _arguments \
        '1:resource:(status tools chain agents tenants rbac mesh rack prove help completion)' \
        '2:action:(list get verify check assign status chain)' \
        '--format[Output format]:(auto json yaml pretty raw)' \
        '--transform[GJSON path]:transform:' \
        '--raw-output[Strip quotes]' \
        '--debug[Print request/response]' \
        '--version[Print version]' \
        '--help[Show help]'
}

_atlas-tui "$@"
`)
	case "fish":
		fmt.Print(`complete -c atlas-tui -f
complete -c atlas-tui -n '__fish_use_subcommand' -a 'status' -d 'System health'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'tools' -d 'MCP tools'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'chain' -d 'Hash chain'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'agents' -d 'Agent declarations'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'tenants' -d 'Carried tenants'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'rbac' -d 'Access control'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'mesh' -d 'Mesh protocol'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'rack' -d 'Voice ladder'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'prove' -d 'Full prove'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'help' -d 'Show help'
complete -c atlas-tui -n '__fish_use_subcommand' -a 'completion' -d 'Shell completion'
complete -c atlas-tui -l format -d 'Output format' -a 'auto json yaml pretty raw'
complete -c atlas-tui -l transform -d 'GJSON path'
complete -c atlas-tui -l raw-output -d 'Strip quotes'
complete -c atlas-tui -l debug -d 'Print request/response'
complete -c atlas-tui -l version -d 'Print version'
complete -c atlas-tui -l help -d 'Show help'
`)
	case "powershell":
		fmt.Print(`Register-ArgumentCompleter -Native -CommandName 'atlas-tui' -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $resources = @('status', 'tools', 'chain', 'agents', 'tenants', 'rbac', 'mesh', 'rack', 'prove', 'help', 'completion')
    $resources | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}
`)
	default:
		fmt.Fprintf(os.Stderr, "Unsupported shell: %s (supported: bash, zsh, fish, powershell)\n", shell)
	}
}

func interactiveMode(home string) {
	fmt.Print(clear)
	drawHeader()

	scanner := bufio.NewReader(os.Stdin)
	for {
		fmt.Printf("\n%s%s%satlas%s:%s> %s", bold, blue, home, cyan, reset, reset)
		input, _ := scanner.ReadString('\n')
		input = strings.TrimSpace(input)
		if input == "" {
			continue
		}
		parts := strings.Fields(input)
		cmd := parts[0]
		args := parts[1:]

		switch cmd {
		case "q", "quit", "exit":
			fmt.Print(clear)
			os.Exit(0)
		case "h", "help":
			printUsage()
		case "s", "status":
			cmdHealth(home)
		case "c", "chain":
			if len(args) > 0 && args[0] == "verify" {
				cmdChainVerify(home, args[1:])
			} else {
				cmdChainList(home, args)
			}
		case "a", "agents":
			cmdAgentsList(home, args)
		case "t", "tools":
			cmdToolsList(home, args)
		case "r", "rbac":
			cmdRBACList(home)
		case "m", "mesh":
			cmdMeshStatus(home)
		case "k", "rack":
			cmdRackList(home)
		case "p", "prove":
			cmdProve(home)
		default:
			fmt.Printf("%sUnknown command: %s%s (type 'h' for help)\n", red, cmd, reset)
		}
	}
}

func drawHeader() {
	fmt.Printf("%s%s╔══════════════════════════════════════════════════════════════╗%s\n", bgBlue, bold, reset)
	fmt.Printf("%s%s║  ATLAS CLI — Resource-based command structure               ║%s\n", bgBlue, bold, reset)
	fmt.Printf("%s%s║  atlas <resource> <action> [flags]                         ║%s\n", bgBlue, bold, reset)
	fmt.Printf("%s%s║  covenant: 1512741580b7239b  ·  operator holds the gate   ║%s\n", bgBlue, bold, reset)
	fmt.Printf("%s%s╚══════════════════════════════════════════════════════════════╝%s\n", bgBlue, bold, reset)
}

// === Resource commands ===

func cmdHealth(home string) {
	data := map[string]any{
		"resource": "status",
		"action":   "health",
	}
	if out, err := run("atlas", "--version"); err == nil {
		data["version"] = strings.TrimSpace(out)
	}
	if h, err := curlJSON(home, "GET", "/health"); err == nil {
		data["server"] = h
	}
	output(data)
}

func cmdToolsList(home string, args []string) {
	if h, err := curlJSON(home, "GET", "/tools"); err == nil {
		if tools, ok := h["tools"].([]any); ok {
			if transform != "" {
				for _, t := range tools {
					if m, ok := t.(map[string]any); ok {
						if val := extractField(m, transform); val != "" {
							fmt.Println(val)
						}
					}
				}
				return
			}
			output(map[string]any{"tools": tools, "count": len(tools)})
		}
	} else {
		fmt.Fprintf(os.Stderr, "%sHTTP server not running. Start with: atlas-mcp --http :8090%s\n", yellow, reset)
	}
}

func cmdToolsGet(home string, name string) {
	if h, err := curlJSON(home, "GET", "/tools"); err == nil {
		if tools, ok := h["tools"].([]any); ok {
			for _, t := range tools {
				if m, ok := t.(map[string]any); ok {
					if m["name"] == name {
						output(m)
						return
					}
				}
			}
			fmt.Fprintf(os.Stderr, "%sTool not found: %s%s\n", red, name, reset)
		}
	}
}

func cmdChainList(home string, args []string) {
	logPath := filepath.Join(home, "SEAT_LOG.md")
	data, err := os.ReadFile(logPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%sNo SEAT_LOG.md found%s\n", red, reset)
		return
	}
	lines := strings.Split(string(data), "\n")
	entries := []map[string]any{}
	for i, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		entries = append(entries, map[string]any{"n": i, "entry": line})
	}
	output(map[string]any{"chain": entries, "count": len(entries)})
}

func cmdChainVerify(home string, args []string) {
	_ = home
	cmdProve(home)
}

func cmdAgentsList(home string, args []string) {
	agentsDir := filepath.Join(home, "agents")
	entries, err := os.ReadDir(agentsDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%sNo agents directory found%s\n", red, reset)
		return
	}
	agents := []any{}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".us") {
			continue
		}
		agents = append(agents, map[string]any{
			"name":   e.Name(),
			"status": "enrolled",
		})
	}
	if transform != "" {
		for _, agent := range agents {
			if m, ok := agent.(map[string]any); ok {
				if val := extractField(m, transform); val != "" {
					if rawOutput {
						fmt.Println(val)
					} else {
						fmt.Printf("%q\n", val)
					}
				}
			}
		}
		return
	}
	output(map[string]any{"agents": agents, "count": len(agents)})
}

func cmdAgentsGet(home string, name string) {
	usPath := filepath.Join(home, "agents", name)
	if !strings.HasSuffix(usPath, ".us") {
		usPath += ".us"
	}
	data, err := os.ReadFile(usPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%sAgent not found: %s%s\n", red, name, reset)
		return
	}
	var parsed map[string]any
	if json.Unmarshal(data, &parsed) == nil {
		output(parsed)
	} else {
		fmt.Println(string(data))
	}
}

func cmdTenantsList(home string) {
	_ = home
	fmt.Println("Tenants are managed by atlas-mcp. Start with: atlas-mcp --http :8090")
}

func cmdRBACList(home string) {
	roles := []any{
		map[string]any{"name": "operator", "description": "the hand; holds the gate", "permissions": "read:allow, edit:allow, bash:deny, net:deny, tools:allow"},
		map[string]any{"name": "steward", "description": "plans, specs, keeps THE_ROAD", "permissions": "read:allow, edit:allow, bash:deny, net:deny, tools:allow"},
		map[string]any{"name": "agent", "description": "a declared seat with limited scope", "permissions": "read:allow, edit:deny, bash:deny, net:deny, tools:allow"},
		map[string]any{"name": "guest", "description": "unauthenticated; deny all", "permissions": "read:deny, edit:deny, bash:deny, net:deny, tools:deny"},
	}
	output(map[string]any{"roles": roles})
}

func cmdRBACCheck(home, actor, tool string) {
	_ = home
	fmt.Printf("RBAC check: actor=%s tool=%s (requires atlas-mcp with RBAC enabled)\n", actor, tool)
}

func cmdRBACAssign(home, actor, role string) {
	_ = home
	fmt.Printf("RBAC assign: actor=%s role=%s (requires atlas-mcp with RBAC enabled)\n", actor, role)
}

func cmdMeshStatus(home string) {
	_ = home
	fmt.Println("Mesh status requires atlas-mcp. Start with: atlas-mcp --http :8090")
}

func cmdMeshChain(home string) {
	_ = home
	fmt.Println("Mesh chain requires atlas-mcp. Start with: atlas-mcp --http :8090")
}

func cmdRackList(home string) {
	_ = home
	fmt.Println("Rack list requires atlas-mcp. Start with: atlas-mcp --http :8090")
}

func cmdProve(home string) {
	fmt.Printf("%sRunning full prove...%s\n", yellow, reset)
	cmds := []struct {
		name string
		args []string
	}{
		{"atlas", []string{"--prove"}},
		{"atlas-mcp", []string{"--prove"}},
		{"atlas-town", []string{"--prove"}},
		{"atlas-door", []string{"--prove"}},
	}
	totalPass, totalFail := 0, 0
	for _, c := range cmds {
		fmt.Printf("\n%s%s%s:%s\n", bold, blue, c.name, reset)
		out, err := exec.Command(c.name, c.args...).CombinedOutput()
		if err != nil {
			fmt.Printf("  %sFAILED: %s%s\n", red, err, reset)
			totalFail++
			continue
		}
		lines := strings.Split(string(out), "\n")
		pass, fail := 0, 0
		for _, l := range lines {
			if strings.Contains(l, "[PASS]") {
				pass++
			} else if strings.Contains(l, "[FAIL]") {
				fail++
				fmt.Printf("  %s%s%s\n", red, l, reset)
			} else if strings.Contains(l, "PROVEN") {
				fmt.Printf("  %s%s%s\n", green, strings.TrimSpace(l), reset)
			}
		}
		totalPass += pass
		totalFail += fail
	}
	fmt.Printf("\n%s%sTOTAL: %d PASS, %d FAIL%s\n", bold, green, totalPass, totalFail, reset)
}

// === Helpers ===

func run(name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func curlJSON(home, method, path string) (map[string]any, error) {
	// N0: stdlib net/http — no external curl process (SPEC_CONTROL_CENTER P0-10).
	// Only loopback is ever dialed; anything else is refused before dial.
	url := "http://127.0.0.1:8090" + path
	client := &http.Client{Timeout: 10 * time.Second}
	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return nil, err
	}
	var data map[string]any
	if err := json.Unmarshal(raw, &data); err != nil {
		return nil, err
	}
	return data, nil
}

func output(data any) {
	switch format {
	case "json":
		b, _ := json.Marshal(data)
		fmt.Println(string(b))
	case "yaml":
		printYAML(data, 0)
	case "raw":
		if s, ok := data.(string); ok {
			fmt.Println(s)
		} else {
			b, _ := json.MarshalIndent(data, "", "  ")
			fmt.Println(string(b))
		}
	case "pretty", "auto":
		b, _ := json.MarshalIndent(data, "", "  ")
		fmt.Println(string(b))
	default:
		b, _ := json.Marshal(data)
		fmt.Println(string(b))
	}
}

func printYAML(data any, indent int) {
	prefix := strings.Repeat("  ", indent)
	switch v := data.(type) {
	case map[string]any:
		for k, val := range v {
			switch val.(type) {
			case map[string]any, []any:
				fmt.Printf("%s%s:\n", prefix, k)
				printYAML(val, indent+1)
			default:
				fmt.Printf("%s%s: %v\n", prefix, k, val)
			}
		}
	case []any:
		for _, item := range v {
			switch item.(type) {
			case map[string]any:
				fmt.Printf("%s-\n", prefix)
				printYAML(item, indent+1)
			default:
				fmt.Printf("%s- %v\n", prefix, item)
			}
		}
	default:
		fmt.Printf("%s%v\n", prefix, data)
	}
}

func extractField(data map[string]any, path string) string {
	// Simple GJSON-like path: "name", "foo.bar", "*.name"
	parts := strings.Split(path, ".")
	current := any(data)
	for i, part := range parts {
		if part == "*" {
			// Array iteration - extract from each item
			if arr, ok := current.([]any); ok {
				var results []string
				remaining := strings.Join(parts[i+1:], ".")
				for _, item := range arr {
					if m, ok := item.(map[string]any); ok {
						if remaining != "" {
							if val := extractField(m, remaining); val != "" {
								results = append(results, val)
							}
						} else {
							results = append(results, fmt.Sprintf("%v", m))
						}
					}
				}
				return strings.Join(results, "\n")
			}
			// If current is a map, find the first array-valued field
			if m, ok := current.(map[string]any); ok {
				for _, v := range m {
					if arr, ok := v.([]any); ok {
						var results []string
						remaining := strings.Join(parts[i+1:], ".")
						for _, item := range arr {
							if im, ok := item.(map[string]any); ok {
								if remaining != "" {
									if val := extractField(im, remaining); val != "" {
										results = append(results, val)
									}
								} else {
									results = append(results, fmt.Sprintf("%v", im))
								}
							}
						}
						return strings.Join(results, "\n")
					}
				}
			}
			return ""
		}
		if m, ok := current.(map[string]any); ok {
			current = m[part]
		} else {
			return ""
		}
	}
	if current == nil {
		return ""
	}
	return fmt.Sprintf("%v", current)
}
