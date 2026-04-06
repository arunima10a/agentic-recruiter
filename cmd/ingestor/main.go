package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/arunima10a/agentic-recruiter/internal/domain"
	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
)

func main() {
	// Setup Database Connection
	err := godotenv.Load()
	if err != nil {
		log.Fatal("Error loading .env file")
	}

	dbUser := os.Getenv("DB_USER")
	dbName := os.Getenv("DB_NAME")

	connStr := fmt.Sprintf("user=%s dbname=%s sslmode=disable", dbUser, dbName)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal("DB Connection failed:", err)
	}
	defer db.Close()

	// Load Mock Data
	data, err := os.ReadFile("mock_applications.json")
	if err != nil {
		log.Fatal("Failed to read mock_applications.json:", err)
	}

	var rawCandidates []domain.Candidate
	if err := json.Unmarshal(data, &rawCandidates); err != nil {
		log.Fatal("Failed to parse JSON:", err)
	}

	fmt.Printf("Ingestor: Found %d candidates to process.\n", len(rawCandidates))

	for _, c := range rawCandidates {
		// NORMALIZATION & VALIDATION
		if len(c.Answers) > 0 {
			c.RawAnswer = c.Answers[0].Answer
		}

		// Skip candidates with no content to prevent downstream AI crashes
		if c.RawAnswer == "" {
			fmt.Printf("Skipping %s: No answer content found.\n", c.Name)
			continue
		}

		tx, err := db.Begin()
		if err != nil {
			log.Printf("Could not start transaction for %s: %v", c.Name, err)
			continue
		}

		// duplication (check if already in DB)
		var existingID string
		err = tx.QueryRow("SELECT external_id FROM candidates WHERE external_id = $1 FOR UPDATE", c.ID).Scan(&existingID)

		if err == sql.ErrNoRows {
			// Insert into Candidates Table
			_, err = tx.Exec(`
				INSERT INTO candidates (external_id, name, email, github_url, status, raw_answer) 
				VALUES ($1, $2, $3, $4, $5, $6)`,
				c.ID, c.Name, c.Email, c.GithubURL, "PENDING", c.RawAnswer)

			if err != nil {
				tx.Rollback()
				fmt.Printf("Failed to save %s to candidates: %v\n", c.Name, err)
				continue
			}

			// Insert into Outbox table
			payload, _ := json.Marshal(c)
			_, err = tx.Exec(`
				INSERT INTO outbox (topic, payload) 
				VALUES ($1, $2)`,
				"candidate.ingested", payload)

			if err != nil {
				tx.Rollback()
				fmt.Printf("Failed to save outbox for %s: %v\n", c.Name, err)
				continue
			}

			// COMMIT
			if err := tx.Commit(); err != nil {
				fmt.Printf("Transaction commit failed for %s: %v\n", c.Name, err)
			} else {
				fmt.Printf("%s saved to DB and Outbox (Atomic)\n", c.Name)
			}

		} else {
			// candidate already exists, close the transaction
			tx.Rollback()
			fmt.Printf(" Skipping %s (Already exists)\n", c.Name)
		}
	}
}
