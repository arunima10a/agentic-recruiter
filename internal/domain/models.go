package domain


import "time"

type Candidate struct {
    ID          string    `json:"id"`
    Name        string    `json:"name"`
    Email       string    `json:"email"`
    GithubURL   string    `json:"github_url"`
    RawAnswer   string    `json:"raw_answer"`
    Status      string    `json:"status"` // PENDING, VETTED, SCORED, CONTACTED
    StrikeCount int       `json:"strike_count"`
    CreatedAt   time.Time `json:"created_at"`
	Answers []struct {
		Answer string `json:"answer"`
	} `json:"answers"`
}


type AnalysisResult struct {
    CandidateID  string  `json:"candidate_id"`
    TechScore    int     `json:"tech_score"`
    QualityScore int     `json:"quality_score"`
    IsAIGenerated bool    `json:"is_ai_generated"`
    Reasoning    string  `json:"reasoning"`
    Embedding    []float32 `json:"-"` 
}