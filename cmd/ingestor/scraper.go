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

// Save cookies from the real session to a local file
func saveCookies(page *rod.Page) {
	cookies, err := page.Cookies(nil)
	if err != nil {
		fmt.Printf("⚠️  Could not capture cookies: %v\n", err)
		return
	}
	data, _ := json.Marshal(cookies)
	_ = os.WriteFile("cookies.json", data, 0644)
	fmt.Println("Cookies synced to local vault (cookies.json)")
}

// Load cookies into the browser to try and restore a session
func loadCookies(browser *rod.Browser) {
	data, err := os.ReadFile("cookies.json")
	if err != nil {
		return // No vault yet
	}
	var cookies []*proto.NetworkCookie
	json.Unmarshal(data, &cookies)

	for _, c := range cookies {
		_ = browser.SetCookies([]*proto.NetworkCookieParam{{
			Name:     c.Name,
			Value:    c.Value,
			Domain:   c.Domain,
			Path:     c.Path,
			Secure:   c.Secure,
			HTTPOnly: c.HTTPOnly,
		}})
	}
	fmt.Println("Session cookies injected from vault.")
}
