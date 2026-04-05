import re
import json
import psycopg2
from pgvector.psycopg2 import register_vector
import google.generativeai as genai

class IntelligenceProcessor:
    def __init__(self, db_params, gemini_key):
        self.db_params = db_params
        self.conn = psycopg2.connect(**db_params)
        register_vector(self.conn)
        
        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Self-healing model discovery
        self.embed_model = "models/text-embedding-004"
        try:
            for m in genai.list_models():
                if 'embedContent' in m.supported_generation_methods:
                    self.embed_model = m.name
                    break
        except: pass

        self.fingerprints = [
            r"in today's rapidly evolving",
            r"comprehensive overview",
            r"it is important to note",
            r"I'd be happy to help"
        ]

    def get_embedding(self, text):
        """Generates a vector and forces it to 768 dimensions."""
        result = genai.embed_content(
            model=self.embed_model, 
            content=text, 
            task_type="retrieval_document",
            output_dimensionality=768 # Forces 768 to match Postgres
        )
        return result['embedding']

    def check_anti_cheat(self, ext_id, answer_text, embedding):
        strikes = 0
        reasons = []
        for pattern in self.fingerprints:
            if re.search(pattern, answer_text.lower()):
                strikes += 1
                reasons.append("AI Fingerprint Detected")
                break

        # Similarity check
        with self.conn.cursor() as cur:
            try:
                query = """
                SELECT c.name FROM candidate_embeddings ce
                JOIN candidates c ON c.id = ce.candidate_id
                WHERE ce.embedding <=> %s::vector < 0.15 
                AND c.external_id != %s LIMIT 1
            """
                cur.execute(query, (embedding, ext_id))
                match = cur.fetchone()
                if match:
                    strikes += 1
                    reasons.append(f"Copied from {match[0]}")
            except Exception as e:
                print(f"Similarity check failed: {e}")
                self.conn.rollback() # RESET THE CONNECTION
        return strikes, reasons

    def score_technical_answer(self, answer_text):
        prompt = f"Analyze this tech answer. Return ONLY JSON: {answer_text}"
        response = self.model.generate_content(prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)

    def process_and_save(self, candidate_data):
        ext_id = candidate_data['id']
        answer = candidate_data['raw_answer']

        try:
            embedding = self.get_embedding(answer)
            strikes, anti_cheat_reasons = self.check_anti_cheat(ext_id, answer, embedding)

            if strikes >= 1:
                tier, tech_score, qual_score = "REJECT (Fraud)", 0, 0
                reasoning = f"⚠️ Fraud: {', '.join(anti_cheat_reasons)}"
            else:
                eval_data = self.score_technical_answer(answer)
                tier, reasoning = eval_data.get('tier', 'STANDARD'), eval_data.get('reasoning', '')
                tech_score, qual_score = eval_data.get('tech_score', 0), eval_data.get('quality_score', 0)

            self._atomic_save(ext_id, tier, reasoning, tech_score, qual_score, embedding, strikes)
        except Exception as e:
            print(f"ERROR IN PIPELINE {e}")
            self.conn.rollback() # Reset connection on failure
            raise e

    def _atomic_save(self, ext_id, tier, reasoning, tech_score, qual_score, embedding, strikes):
        with self.conn: # This starts a transaction
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates SET 
                    status = 'SCORED', tier = %s, reasoning = %s, 
                    technical_score = %s, quality_score = %s, strike_count = %s
                    WHERE external_id = %s RETURNING id
                """, (tier, reasoning, tech_score, qual_score, strikes, ext_id))
                
                res = cur.fetchone()
                if res:
                    internal_id = res[0]
                    cur.execute("INSERT INTO candidate_embeddings (candidate_id, embedding) VALUES (%s, %s)", (internal_id, embedding))
                    event_payload = json.dumps({"external_id": ext_id, "tier": tier, "reasoning": reasoning})
                    cur.execute("INSERT INTO outbox (topic, payload) VALUES (%s, %s)", ("candidate.vetted", event_payload))
                    print(f"Processed {ext_id}: {tier}")

    def close(self):
        self.conn.close()