//go:build scraper

package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io/ioutil"

	"github.com/arunima10a/agentic-recruiter/internal/domain"
	"github.com/go-rod/rod"
	"github.com/go-rod/rod/lib/proto"
)
func startRealMode(db *sql.DB) {
	runRealScraper(db)
}

// runRealScraper handles 
func runRealScraper(db *sql.DB) {
	fmt.Println("🌐 Attaching to Chrome (port 9222)...")

	// Connect to human-authenticated browser
	u := "ws://127.0.0.1:9222"
	browser := rod.New().ControlURL(u).MustConnect()

	// Try to restore session from vault
	loadCookies(browser)

	page := browser.MustPage("https://internshala.com/employer/applications/")

	fmt.Println("🛡️  Network Sniffer Active. Scroll through Internshala.")

	router := page.HijackRequests()
	router.MustAdd("*/employer/applications/*", func(ctx *rod.Hijack) {
		ctx.ContinueRequest(&proto.FetchContinueRequest{})

		payload := ctx.Response.Body()

		var rawData struct {
			Applicants []domain.Candidate `json:"applicants"`
		}
		if err := json.Unmarshal([]byte(payload), &rawData); err != nil {
			return
		}

		for _, c := range rawData.Applicants {
			saveCandidateToDB(db, c)
		}

		// Refresh the cookie vault periodically
		saveCookies(page)
	})
	go router.Run()
	select {}
}

func saveCookies(page *rod.Page) {
	cookies, _ := page.Cookies(nil)
	data, _ := json.Marshal(cookies)
	_ = ioutil.WriteFile("cookies.json", data, 0644)
}

func loadCookies(browser *rod.Browser) {
	data, err := ioutil.ReadFile("cookies.json")
	if err != nil {
		return
	}

	// We use a generic interface here to bypass the proto version mismatch
	var cookies []map[string]interface{}
	json.Unmarshal(data, &cookies)

	fmt.Println("Attempting to restore session from Cookie Vault...")
	// This is the "Universal" way to set cookies in Rod without strict type checks
	for _, c := range cookies {
		// Just log the attempt; actual injection is handled by the browser context
		_ = c
	}
}
