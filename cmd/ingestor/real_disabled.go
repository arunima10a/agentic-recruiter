//go:build !scraper

package main

import (
	"fmt"
	"database/sql"
)

func startRealMode(db *sql.DB) {
	fmt.Println("⚠️  REAL mode was not included in this build.")
	fmt.Println("To enable it, run: go run -tags scraper cmd/ingestor/*.go -mode=real")
}