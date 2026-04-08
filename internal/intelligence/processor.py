import re
import json
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

    def perform_deep_analysis(self, name, answer_text):
        prompt = f"""
        You are a Senior Technical Recruiter. Evaluate this candidate for a 5-year career role.
        Candidate: {name} | Answer: "{answer_text}"

        CRITERIA:
        1. Technical Ability (1-10).
        2. Longevity/Hunger (1-10): Builders vs Mass-Appliers.
        3. AI Detection: 
           - Set is_ai_generated to true ONLY if you see high-certainty AI filler.
           - If it is just a short, bad human answer, set is_ai_generated to false and tier to REJECT.
        4. Round 2 Question: A specific deep-dive based on their answer.

        Return ONLY JSON:
        {{"tech_score": int, "longevity_score": int, "hunger_score": int, "is_ai_generated": bool, "reasoning": "string", "tier": "FAST-TRACK|STANDARD|REJECT", "next_round_question": "string"}}
        """
        response = self.model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())

    def process_and_save(self, candidate_data):
        ext_id = candidate_data['id']
        name = candidate_data['name']
        answer = candidate_data['raw_answer']
        strikes = 0

        # 1. THE SIMILARITY CHECK (Now inline, with the Timestamp Fix)
        embedding = self.get_embedding(answer)
        with self.conn.cursor() as cur:
            # We compare the current candidate against OLDER candidates only
            cur.execute("""
                SELECT c.name FROM candidate_embeddings ce 
                JOIN candidates c ON c.id = ce.candidate_id 
                WHERE ce.embedding <=> %s::vector < 0.15 
                AND c.external_id != %s 
                AND c.created_at < (SELECT created_at FROM candidates WHERE external_id = %s)
                LIMIT 1
            """, (embedding, ext_id, ext_id))
            match = cur.fetchone()
        
        # 2. THE AI BRAIN ANALYSIS (Technical + Longevity + AI Detection)
        eval_data = self.perform_deep_analysis(name, answer)
        
        # 3. DECISION LOGIC (Merging the two signals)
        if match:
            # If a match is found in the DB, it's Plagiarism
            strikes += 1
            eval_data['tier'] = "REJECT (Fraud)"
            eval_data['reasoning'] = f"⚠️ Plagiarism detected. Answer matches previous candidate: {match[0]}."
        elif eval_data['is_ai_generated']:
            # If the AI is sure it's ChatGPT, it's AI Detected
            strikes += 1
            eval_data['tier'] = "REJECT (AI Detected)"
        
        # Note: If it's just a bad human answer (like Aarav), 
        # perform_deep_analysis will set tier to REJECT with strikes = 0.

        # 4. ATOMIC SAVE
        self._atomic_save(name, ext_id, eval_data, embedding, strikes)

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
                history = [{"round": 1, "q": "Initial", "a": "", "next_q": eval['next_round_question']}]
                cur.execute("UPDATE candidates SET conversation_history = %s WHERE id = %s", (json.dumps(history), internal_id))

                payload = json.dumps({"external_id": ext_id, "tier": eval['tier'], "next_q": eval['next_round_question'], "reasoning": eval['reasoning']})
                cur.execute("INSERT INTO outbox (topic, payload) VALUES (%s, %s)", ("candidate.vetted", payload))
                print(f"✅ Processed {name}: Tier={eval['tier']} | Strikes={strikes}")

    def close(self):
        self.conn.close()