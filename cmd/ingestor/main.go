package main

import (
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"

	"github.com/arunima10a/agentic-recruiter/internal/domain"
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
		startRealMode(db)
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
