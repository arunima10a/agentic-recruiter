package main

import (
	"encoding/json"
	"fmt"
	"log"

	"github.com/streadway/amqp"
)

type VettedEvent struct {
	ExternalID string `json:"external_id"`
	Tier       string `json:"tier"`
	Reasoning  string `json:"reasoning"`
	NextQ      string `json:"next_q"`
}


func main() {
	//Connect to RabbitMQ
	conn, err := amqp.Dial("amqp://guest:guest@localhost:5672/")
	if err != nil { log.Fatal(err) }
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil { log.Fatal(err) }
	defer ch.Close()

	_, err = ch.QueueDeclare(
		"candidate.vetted", // name
		true,               // durable (survives restart)
		false,              // delete when unused
		false,              // exclusive
		false,              // no-wait
		nil,                // arguments
	)
	if err != nil { log.Fatal("Failed to declare queue:", err) }

	// Consume from 'candidate.vetted' (events from Python via Outbox)
	msgs, _ := ch.Consume("candidate.vetted", "", true, false, false, false, nil)

	fmt.Println("Communicator is active. Waiting for vetted candidates...")

	for d := range msgs {
		var event VettedEvent
		json.Unmarshal(d.Body, &event)

		// 3. Multi-Round Contextual Logic (Component 3)
		sendEngagement(event)
	}
}

func sendEngagement(e VettedEvent) {
	fmt.Printf("\n--- ACTION TRIGGERED for %s ---\n", e.ExternalID)

	var message string
	switch e.Tier {
	case "REJECT (Fraud)":
		message = fmt.Sprintf("Hello. Our integrity system flagged your response: %s. We will not be proceeding.", e.Reasoning)
	case "FAST-TRACK", "STANDARD":
		message = fmt.Sprintf(
			"Hello! We reviewed your application and were interested in your background.\n\n" +
			"Follow-up Question: %s\n\n" +
			"Please reply to this email with your answer to move to the next round.", 
			e.NextQ,
		)

	default:
		message = "Thank you for your application."
	}

	// Simulate SMTP/Gmail Send
	fmt.Printf("✉️  OUTBOUND EMAIL TO %s:\n\"%s\"\n", e.ExternalID, message)
	fmt.Println("--------------------------------")
}

