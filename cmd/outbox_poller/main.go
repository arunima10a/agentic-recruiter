package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
	"github.com/streadway/amqp"
)

func main() {
	// Load .env
	err := godotenv.Load()
	if err != nil {
		log.Fatal("Error loading .env file")
	}

	// DB connection
	dbUser := os.Getenv("DB_USER")
	dbName := os.Getenv("DB_NAME")
	dbHost := os.Getenv("DB_HOST")
	dbPort := os.Getenv("DB_PORT")

	connStr := fmt.Sprintf(
		"user=%s dbname=%s host=%s port=%s sslmode=disable",
		dbUser, dbName, dbHost, dbPort,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal("DB Connection failed:", err)
	}
	defer db.Close()

	conn, _ := amqp.Dial("amqp://guest:guest@localhost:5672/")
	ch, _ := conn.Channel()

	fmt.Println(" Outbox Poller is running...")

	for {
		// Start a Transaction
		tx, err := db.Begin()
		if err != nil {
			time.Sleep(2 * time.Second)
			continue
		}

		// lock the rows so other workers won't touch them
		rows, err := tx.Query(`
			SELECT id, topic, payload FROM outbox 
			ORDER BY created_at 
			LIMIT 10 
			FOR UPDATE SKIP LOCKED`)

		if err != nil {
			tx.Rollback()
			time.Sleep(2 * time.Second)
			continue
		}

		type msg struct {
			id      string
			topic   string
			payload []byte
		}
		var batch []msg

		for rows.Next() {
			var m msg
			rows.Scan(&m.id, &m.topic, &m.payload)
			batch = append(batch, m)
		}
		rows.Close()

		successCount := 0
		for _, m := range batch {
			// Publish to RabbitMQ
			err := ch.Publish("", m.topic, false, false, amqp.Publishing{
				ContentType: "application/json",
				Body:        m.payload,
			})

			if err == nil {
				tx.Exec("DELETE FROM outbox WHERE id = $1", m.id)
				successCount++
			}
		}

		// Commit transaction

		tx.Commit()

		if successCount > 0 {
			fmt.Printf("Reliably dispatched %d events\n", successCount)
		}

		time.Sleep(500 * time.Millisecond)
	}
}
