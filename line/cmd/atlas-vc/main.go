// atlas vc — convert .us declarations to W3C Verifiable Credentials.
//
// Usage:
//
//	atlas vc --us <file.us> [--issuer did:atlas:...] [--out <file.json>]
//	atlas vc verify --vc <file.json>
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"atlas/line/internal/vc"
)

func main() {
	var (
		usPath  = flag.String("us", "", "input .us file")
		vcPath  = flag.String("vc", "", "VC file to verify")
		issuer  = flag.String("issuer", "did:atlas:1512741580b7239b:operator", "issuer DID")
		outPath = flag.String("out", "", "output file (default: stdout)")
		showVer = flag.Bool("version", false, "print version")
	)

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "atlas vc — .us → W3C Verifiable Credential\n\n")
		fmt.Fprintf(os.Stderr, "Usage:\n")
		fmt.Fprintf(os.Stderr, "  atlas vc --us <file.us> [--issuer DID] [--out file.json]\n")
		fmt.Fprintf(os.Stderr, "  atlas vc verify --vc <file.json>\n")
		fmt.Fprintf(os.Stderr, "  atlas vc --version\n\n")
		fmt.Fprintf(os.Stderr, "Flags:\n")
		flag.PrintDefaults()
	}

	flag.Parse()

	if *showVer {
		fmt.Println("0.1.3")
		return
	}

	// Verify mode
	if *vcPath != "" {
		data, err := os.ReadFile(*vcPath)
		if err != nil {
			fatal(err)
		}
		var v vc.VC
		if err := json.Unmarshal(data, &v); err != nil {
			fatal(fmt.Errorf("invalid VC JSON: %w", err))
		}
		errs := vc.Verify(&v)
		if len(errs) > 0 {
			fmt.Fprintf(os.Stderr, "FAIL — %d issue(s):\n", len(errs))
			for _, e := range errs {
				fmt.Fprintf(os.Stderr, "  - %s\n", e)
			}
			os.Exit(1)
		}
		fmt.Printf("PASS — %s is a valid Atlas VC\n", v.CredentialSubject.ID)
		return
	}

	// Convert mode
	if *usPath == "" {
		flag.Usage()
		os.Exit(2)
	}

	v, err := vc.FromFile(*usPath, *issuer)
	if err != nil {
		fatal(err)
	}

	data, err := vc.ToJSON(v)
	if err != nil {
		fatal(err)
	}

	if *outPath != "" {
		if err := os.WriteFile(*outPath, data, 0644); err != nil {
			fatal(err)
		}
		fmt.Fprintf(os.Stderr, "wrote %s\n", *outPath)
	} else {
		fmt.Print(string(data))
	}
}

func fatal(err error) {
	fmt.Fprintf(os.Stderr, "refused: %s\n", err)
	os.Exit(1)
}
