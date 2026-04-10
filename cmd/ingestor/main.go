package main

import (
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"

	"github.com/arunima10a/agentic-recruiter/internal/domain"
	"github.com/go-rod/rod"
	"github.com/go-rod/rod/lib/proto"
	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
)

func main() {
	// Load Configuration
	godotenv.Load()
	mode := flag.String("mode", "mock", "Mode to run: 'mock' or 'real'")
	flag.Parse()

	// Setup Database Connection (shared by both modes)
	dbUser := os.Getenv("DB_USER")
	dbName := os.Getenv("DB_NAME")
	connStr := fmt.Sprintf("user=%s dbname=%s sslmode=disable", dbUser, dbName)
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal("❌ DB Connection failed:", err)
	}
	defer db.Close()

	if *mode == "real" {
		runRealScraper(db)
	} else {
		runMockIngestor(db)
	}
}

// runMockIngestor handles testing using local JSON data
func runMockIngestor(db *sql.DB) {
	fmt.Println("Starting Mock Ingestor...")
	data, err := os.ReadFile("mock_applications.json")
	if err != nil {
		log.Fatal("❌ Failed to read mock_applications.json:", err)
	}

	var rawCandidates []domain.Candidate
	json.Unmarshal(data, &rawCandidates)

	for _, c := range rawCandidates {
		// Normalize data (extract first answer)
		if len(c.Answers) > 0 {
			c.RawAnswer = c.Answers[0].Answer
		}
		saveCandidateToDB(db, c)
	}
}

// runRealScraper handles CDP based session attachment
func runRealScraper(db *sql.DB) {
	fmt.Println("Attaching to Chrome (port 9222)...")

	// Connecting to an existing authenticated browser session
	u := "ws://127.0.0.1:9222"
	browser := rod.New().ControlURL(u).MustConnect()

	loadCookies(browser)

	page := browser.MustPage("https://internshala.com/employer/applications/")

	fmt.Println(" Network Sniffer Active. Scroll through Internshala in your browser.")

	router := page.HijackRequests()
	router.MustAdd("*/employer/applications/*", func(ctx *rod.Hijack) {
		ctx.ContinueRequest(&proto.FetchContinueRequest{})

		payload := ctx.Response.Body()

		// map the real Internshala response to our domain Model
		var rawData struct {
			Applicants []domain.Candidate `json:"applicants"`
		}
		json.Unmarshal([]byte(payload), &rawData)

		for _, c := range rawData.Applicants {
			saveCandidateToDB(db, c)
		}
	})
	go router.Run()
	select {}
}

// saveCandidateToDB handles  Transactional Outbox Pattern
func saveCandidateToDB(db *sql.DB, c domain.Candidate) {
	if c.RawAnswer == "" {
		return
	}

	tx, err := db.Begin()
	if err != nil {
		return
	}

	var existingID string
	err = tx.QueryRow("SELECT external_id FROM candidates WHERE external_id = $1 FOR UPDATE", c.ID).Scan(&existingID)

	if err == sql.ErrNoRows {
		// Save to Candidates
		_, err = tx.Exec(`
			INSERT INTO candidates (external_id, name, email, github_url, status, raw_answer) 
			VALUES ($1, $2, $3, $4, $5, $6)`,
			c.ID, c.Name, c.Email, c.GithubURL, "PENDING", c.RawAnswer)
		if err != nil {
			tx.Rollback()
			return
		}

		// Save to Transactional Outbox
		payload, _ := json.Marshal(c)
		_, err = tx.Exec(`INSERT INTO outbox (topic, payload) VALUES ($1, $2)`, "candidate.ingested", payload)
		if err != nil {
			tx.Rollback()
			return
		}

		tx.Commit()
		fmt.Printf("Processed: %s (Atomic Save Success)\n", c.Name)
	} else {
		tx.Rollback()
		fmt.Printf("Skipping: %s (Already exists)\n", c.Name)
	}
}

// Save cookies to a file after a successful manual login
func saveCookies(page *rod.Page) {
	cookies, _ := page.Cookies(nil)
	data, _ := json.Marshal(cookies)
	_ = ioutil.WriteFile("cookies.json", data, 0644)
	fmt.Println("💾 Cookies saved to vault for next session.")
}

// Load cookies from the vault to bypass login/reCAPTCHA
func loadCookies(browser *rod.Browser) {
	data, err := ioutil.ReadFile("cookies.json")
	if err != nil {
		fmt.Println(" No cookie vault found. Manual login required.")
		return
	}

	var cookies []*proto.NetworkCookie
	json.Unmarshal(data, &cookies)

	// inject cookies into the browser context
	for _, cookie := range cookies {
		browser.SetCookies([]*proto.NetworkCookieParam{{
			Name:     cookie.Name,
			Value:    cookie.Value,
			Domain:   cookie.Domain,
			Path:     cookie.Path,
			Secure:   cookie.Secure,
			HTTPOnly: cookie.HTTPOnly,
		}})
	}
	fmt.Println("Session restored from Cookie Vault.")
}
