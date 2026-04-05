package broker

import (
	"encoding/json"
	"github.com/streadway/amqp"
)

type RabbitMQ struct {
	conn    *amqp.Connection
	channel *amqp.Channel
}

func NewRabbitMQ(url string) (*RabbitMQ, error) {
	conn, err := amqp.Dial(url)
	if err != nil { return nil, err }
	ch, err := conn.Channel()
	if err != nil { return nil, err }
	return &RabbitMQ{conn: conn, channel: ch}, nil
}

func (r *RabbitMQ) Publish(queueName string, body interface{}) error {
	data, err := json.Marshal(body)
	if err != nil { return err }

	_, err = r.channel.QueueDeclare(queueName, true, false, false, false, nil)
	if err != nil { return err }

	return r.channel.Publish("", queueName, false, false, amqp.Publishing{
		ContentType: "application/json",
		Body:        data,
	})
}

func (r *RabbitMQ) Close() {
	r.channel.Close()
	r.conn.Close()
}