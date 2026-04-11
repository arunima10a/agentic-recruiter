package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
)

func main() {
	godotenv.Load()
	
	// Connect to DB
	dbUser := os.Getenv("DB_USER")
	dbName := os.Getenv("DB_NAME")
	connStr := fmt.Sprintf("user=%s dbname=%s sslmode=disable", dbUser, dbName)
	db, _ := sql.Open("postgres", connStr)
	defer db.Close()

	fmt.Println("Nudger Worker Active: Monitoring for cold candidates...")

	for {
		// find candidates who are in 'CONTACTED' status for more than 24 hours but haven't replied yet
		query := `
			SELECT external_id, name FROM candidates 
			WHERE status = 'CONTACTED' 
			AND last_interaction_at < NOW() - INTERVAL '24 hours'
			LIMIT 5
		`
		rows, err := db.Query(query)
		if err != nil {
			log.Printf("Query error: %v", err)
			continue
		}

		for rows.Next() {
			var id, name string
			rows.Scan(&id, &name)

			fmt.Printf("Candidate %s has gone cold. Triggering Nudge...\n", name)

			// TRANSACTIONAL OUTBOX: Queue the nudge email
			tx, _ := db.Begin()
			
			payload, _ := json.Marshal(map[string]string{
				"external_id": id,
				"tier":        "NUDGE",
				"reasoning":   "Candidate has not replied to Round 2 question within 24 hours.",
				"next_q": "N/A",
			})

			tx.Exec("INSERT INTO outbox (topic, payload) VALUES ($1, $2)", "candidate.vetted", payload)
			
			tx.Exec("UPDATE candidates SET last_interaction_at = NOW() WHERE external_id = $1", id)
			
			tx.Commit()
		}
		rows.Close()

		time.Sleep(1 * time.Minute)
	}
}