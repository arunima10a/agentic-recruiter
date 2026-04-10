package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
)

func main() {

	err := godotenv.Load()
	if err != nil {
		log.Fatal("Error loading .env file")
	}

	// DB connection
	dbHost := os.Getenv("DB_HOST")
	dbUser := os.Getenv("DB_USER")
	dbName := os.Getenv("DB_NAME")
	dbPort := os.Getenv("DB_PORT")

	connStr := fmt.Sprintf(
		"host=%s user=%s dbname=%s port=%s sslmode=disable",
		dbHost, dbUser, dbName, dbPort,
	)
	var db *sql.DB
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal("DB Connection failed:", err)
	}
	defer db.Close()

	// Target Vikram Singh (our Fast-Track candidate)
	candidateID := "app_003"

	// Fetch the question we asked him in Round 1
	var historyJSON []byte
	err = db.QueryRow("SELECT conversation_history FROM candidates WHERE external_id = $1", candidateID).Scan(&historyJSON)
	if err != nil {
		log.Fatal("Could not find candidate. Did you run the Ingestor first?")
	}

	// Simulate Vikram's technical answer
	// Vikram's  answer to the AI-resistant question we generated earlier
	replyText := "To handle the cache invalidation in my Node project, I used a TTL strategy combined with an 'on-update' hook to flush specific Redis keys whenever the underlying SQL data changed."

	fmt.Printf("SIMULATION: Received reply from Vikram Singh: %s\n", replyText)

	// wrap the reply in JSON payload for outbox
	payload, _ := json.Marshal(map[string]string{
		"external_id": candidateID,
		"reply_text":  replyText,
	})

	// Atomic Transaction
	tx, _ := db.Begin()
	tx.Exec("INSERT INTO outbox (topic, payload) VALUES ($1, $2)", "candidate.replied", payload)
	tx.Exec("UPDATE candidates SET status = 'REPLY_RECEIVED' WHERE external_id = $1", candidateID)
	tx.Commit()

	fmt.Println("✅ Simulation Complete: Reply queued for AI Round 2 Evaluation.")

}
