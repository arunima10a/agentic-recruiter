import re
import json
import requests
import psycopg2
from pgvector.psycopg2 import register_vector
import google.generativeai as genai

class IntelligenceProcessor:
    def __init__(self, db_params, gemini_key):
        self.conn = psycopg2.connect(**db_params)
        register_vector(self.conn)
        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
        
        
        self.embed_model = "models/text-embedding-004"
        try:
            for m in genai.list_models():
                if 'embedContent' in m.supported_generation_methods:
                    self.embed_model = m.name
                    break
        except: pass

    def get_embedding(self, text):
        result = genai.embed_content(model=self.embed_model, content=text, task_type="retrieval_document", output_dimensionality=768)
        return result['embedding']

    def vet_github(self, url):
        if not url or "github.com" not in url:
            return 0, "No GitHub Provided"
        
        username = url.split('/')[-1]
        api_url = f"https://api.github.com/users/{username}/repos"
        
        try:
            response = requests.get(api_url, timeout=5)
            repos = response.json()
            if not isinstance(repos, list) or len(repos) == 0:
                return 0, "Empty/Invalid Profile"
            
            # Count original repos (not forks)
            original_repos = [r for r in repos if not r.get('fork', True)]
            score = 10 if len(original_repos) > 3 else 5
            return score, f"Found {len(original_repos)} original repos"
        except:
            return 0, "GitHub API Timeout/Error"

    def get_ai_similarity_score(self, question, candidate_answer):
        """
        Component 4: The 'GOOD' response logic.
        Generates a fresh AI answer and compares it to the candidate's
        """
        # Generate a standard AI answer to the same question
        ai_baseline_prompt = f"Provide a standard, professional response to the interview question: '{question}'"
        ai_response = self.model.generate_content(ai_baseline_prompt)
        ai_text = ai_response.text

        # Compare via Embeddings
        candidate_vector = self.get_embedding(candidate_answer)
        ai_vector = self.get_embedding(ai_text)

        # Simple Cosine Similarity Logic 
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 - (%s::vector <=> %s::vector) AS similarity", (candidate_vector, ai_vector))
            similarity = cur.fetchone()[0]
        
        return similarity, ai_text
    
    def get_latest_rubric(self):
        """
        Component 5: Self-Learning
        Fetches traits of the last 3 FAST-TRACK candidates to improve scoring
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT reasoning FROM candidates 
                WHERE tier = 'FAST-TRACK' 
                ORDER BY created_at DESC LIMIT 3
            """)
            winners = cur.fetchall()
            if not winners:
                return "No high-quality benchmarks yet. Focus on technical depth and hunger."
            
            # combine winner traits into a string
            traits = " ".join([w[0] for w in winners])
            return f"Successful traits from previous top-tier candidates: {traits[:500]}"

    def perform_deep_analysis(self, name, answer_text, git_reason, ai_sim_score):

        rubric = self.get_latest_rubric()
        
        prompt = f"""
        You are a Technical Recruiter for a JUNIOR DEVELOPER role. 
        NEW LEARNINGS (Use these as positive benchmarks):
        {rubric}
        Evaluate Candidate: {name}
        Answer: "{answer_text}"
        
        HARD DATA:
        - GitHub Analysis: {git_reason}
        - AI Similarity Baseline: {ai_sim_score:.2f} (1.00 is identical to ChatGPT)

        INSTRUCTIONS:
        1. Technical Ability (1-10): Rate based on specific tech mentioned.
        2. TIERING: You MUST choose exactly one: [FAST-TRACK, STANDARD, REJECT].
        3. AI FLAG: If Similarity Baseline > 0.80, set is_ai_generated to true.

        Return ONLY a JSON object:
        {{
            "tech_score": int,
            "longevity_score": int,
            "hunger_score": int,
            "is_ai_generated": bool,
            "reasoning": "string",
            "tier": "FAST-TRACK|STANDARD|REJECT",
            "next_round_question": "string"
        }}
        """
        response = self.model.generate_content(prompt)
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_text)
        
        # add score back into the data object so we can see it in logs/DB
        data['ai_similarity'] = ai_sim_score
        return data

    def process_and_save(self, candidate_data):
        ext_id = candidate_data['id']
        name = candidate_data['name']
        answer = candidate_data['raw_answer']
        github_url = candidate_data.get('github_url', '')

        # AI Similarity Baseline
        # using dummy question for comparison consistency
        ai_sim_score, _ = self.get_ai_similarity_score("Explain your experience with full-stack development.", answer)

        # GitHub Vetting
        _, git_reason = self.vet_github(github_url)

        # Cross-Candidate Similarity (Plagiarism)
        embedding = self.get_embedding(answer)
        with self.conn.cursor() as cur:

            # Timestamp check 
            cur.execute("""
                SELECT c.name FROM candidate_embeddings ce 
                JOIN candidates c ON c.id = ce.candidate_id 
                WHERE ce.embedding <=> %s::vector < 0.15 
                AND c.external_id != %s 
                AND c.created_at < (SELECT created_at FROM candidates WHERE external_id = %s)
                LIMIT 1
            """, (embedding, ext_id, ext_id))
            match = cur.fetchone()

      
        eval_data = self.perform_deep_analysis(name, answer, git_reason, ai_sim_score)
        
        # FINAL OVERRIDE 
        strikes = 0
        if match:
            eval_data['tier'] = "REJECT (Fraud)"
            eval_data['reasoning'] = f"⚠️ PLAGIARISM: Answer matches previous candidate {match[0]}."
            strikes = 1
        elif eval_data['is_ai_generated'] or ai_sim_score > 0.85:
            eval_data['tier'] = "REJECT (AI Detected)"
            eval_data['reasoning'] = f"⚠️ AI DETECTED: Semantic similarity to AI baseline is {ai_sim_score:.2f}."
            strikes = 1

        # Save to DB and Knowledge Base
        self._atomic_save(name, ext_id, eval_data, embedding, strikes)
        
    def _log_to_kb(self, ext_id, event_type, content, meta):
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id FROM candidates WHERE external_id = %s", (ext_id,))
                cid = cur.fetchone()
                if cid:
                    cur.execute("INSERT INTO knowledge_base (candidate_id, event_type, content, meta_data) VALUES (%s, %s, %s, %s)", 
                                (cid[0], event_type, content, json.dumps(meta)))

    def _atomic_save(self, name, ext_id, eval, vector, strikes):
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates SET 
                    status = 'SCORED', tier = %s, reasoning = %s, 
                    technical_score = %s, longevity_score = %s, hunger_score = %s,
                    strike_count = %s, current_round = 1
                    WHERE external_id = %s RETURNING id
                """, (eval['tier'], eval['reasoning'], eval['tech_score'], 
                      eval['longevity_score'], eval['hunger_score'], strikes, ext_id))
                
                res = cur.fetchone()
                if not res: return
                internal_id = res[0]
                cur.execute("INSERT INTO candidate_embeddings (candidate_id, embedding) VALUES (%s, %s)", (internal_id, vector))
                
                payload = json.dumps({"external_id": ext_id, "tier": eval['tier'], "next_q": eval['next_round_question']})
                cur.execute("INSERT INTO outbox (topic, payload) VALUES (%s, %s)", ("candidate.vetted", payload))
                print(f"✅ Deep Vetted {name}: Tier={eval['tier']} | AI Similarity={eval.get('ai_similarity', 'N/A')}")


     #Contextual multi-Round Evaluation
    def evaluate_round_two_reply(self, name, original_q, candidate_reply):
        
        prompt = f"""
        You are conducting a Technical Interview Round 2.
        Candidate: {name}
        
        CONTEXT:
        In Round 1, we asked the candidate: "{original_q}"
        The candidate just replied: "{candidate_reply}"

        TASKS:
        1. Accuracy (1-10): How technically accurate is their specific answer?
        2. Depth: Did they explain the 'why' or just the 'what'?
        3. Decision: Should we move them to a FINAL human interview?

        Return ONLY a JSON object:
        {{
            "accuracy_score": int,
            "feedback": "string",
            "move_to_final": bool,
            "next_step": "INVITE_TO_ZOOM | REJECT"
        }}
        """
        response = self.model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    
    def process_reply(self, reply_data):
       
        ext_id = reply_data['external_id']
        answer = reply_data['reply_text']

        # Fetch Context (what did we ask them?)
        with self.conn.cursor() as cur:
            cur.execute("SELECT name, conversation_history FROM candidates WHERE external_id = %s", (ext_id,))
            res = cur.fetchone()
            if not res: 
                print(f"❌ Candidate {ext_id} not found in DB.")
                return
            
            name, history = res[0], res[1]
            
            # ensuring history is a valid list and not empty
            if not history or not isinstance(history, list) or len(history) == 0:
                print(f"⚠️  History empty for {name}. Falling back to default context.")
                original_q = "Explain your technical experience."
            else:
                # Get question we generated in Round 1
                original_q = history[-1].get('next_q', "Explain your technical experience.")

        print(f" Analyzing {name}'s answer to: {original_q[:50]}...")

        # Ask AI to evaluate the answer
        prompt = f"""
        TECHNICAL INTERVIEW ROUND 2:
        Candidate: {name}
        Question Asked: "{original_q}"
        Candidate Reply: "{answer}"

        TASKS:
        1. Accuracy (1-10): Is the technical logic correct?
        2. Depth: Did they explain the 'why'?
        
        Decision Logic:
        If they answered well (Accuracy > 6), Tier: 'INVITE_TO_ZOOM'.
        Otherwise, Tier: 'REJECT'.

        Return ONLY JSON:
        {{"accuracy": int, "reasoning": "string", "tier": "INVITE_TO_ZOOM|REJECT"}}
        """
        response = self.model.generate_content(prompt)
        eval_result = json.loads(response.text.replace("```json", "").replace("```", "").strip())

        # Update DB & State
        with self.conn:
            with self.conn.cursor() as cur:
             
                history.append({
                    "round": 2, 
                    "q": original_q, 
                    "a": answer, 
                    "score": eval_result.get('accuracy', 0)
                })
                
                cur.execute("""
                    UPDATE candidates SET 
                    status = 'ROUND_2_COMPLETE', 
                    tier = %s, 
                    reasoning = %s,
                    conversation_history = %s
                    WHERE external_id = %s
                """, (eval_result['tier'], eval_result['reasoning'], json.dumps(history), ext_id))
                
                # Outbox for final email notification
                payload = json.dumps({
                    "external_id": ext_id, 
                    "tier": eval_result['tier'], 
                    "reasoning": eval_result['reasoning'],
                    "next_q": "None - Process Complete"
                })
                cur.execute("INSERT INTO outbox (topic, payload) VALUES (%s, %s)", ("candidate.vetted", payload))
                
                print(f" ROUND 2 COMPLETE for {name}: Result={eval_result['tier']}")

            

    def close(self):
        self.conn.close()