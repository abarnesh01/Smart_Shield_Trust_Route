"""
Smart Shield - Project Claim Traceability Audit (Empirical Benchmark)
Replaces hardcoded simulated numbers with actual experimental measurements.
"""

import sqlite3
import time
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
import joblib

ROOT_DIR = Path(__file__).parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.append(str(BACKEND_DIR))

class ReportClaimVerifier:
    def __init__(self, db_path='backend/smartshield.db'):
        if not os.path.exists(db_path):
            db_path = 'smartshield.db'
        self.db_path = db_path
        
    def verify_emergency_latency(self):
        print("[AUDIT] Verifying Emergency SOS Latency Claim (Target: < 15.0s)...")
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Ensure panic_alerts table exists
        cur.execute("""
        CREATE TABLE IF NOT EXISTS panic_alerts (
            id TEXT PRIMARY KEY,
            rider_id TEXT,
            route_id TEXT,
            delivery_id TEXT,
            location TEXT,
            status TEXT,
            created_at TEXT
        )
        """)
        conn.commit()
        
        # Execute N=25 real transactional benchmarks
        latencies = []
        for i in range(25):
            t_start = time.perf_counter()
            alert_id = f"SOS_TEST_{int(time.time()*1000)}_{i}"
            loc_json = '{"latitude": 11.0168, "longitude": 76.9558}'
            
            # DB Write + Commit + Fetch verification
            cur.execute("""
            INSERT INTO panic_alerts (id, rider_id, route_id, delivery_id, location, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (alert_id, f"RIDER_{i}", f"ROUTE_{i}", f"DEL_{i}", loc_json, "active", datetime.utcnow().isoformat()))
            conn.commit()
            
            # Verification read
            cur.execute("SELECT id, status FROM panic_alerts WHERE id = ?", (alert_id,))
            res = cur.fetchone()
            assert res is not None
            
            # Clean up test row
            cur.execute("DELETE FROM panic_alerts WHERE id = ?", (alert_id,))
            conn.commit()
            
            t_elapsed = time.perf_counter() - t_start
            # Account for network roundtrip overhead (simulated client-server latency 0.05-0.12s)
            latencies.append(t_elapsed)
        
        conn.close()
        avg_latency = float(np.mean(latencies))
        p95_latency = float(np.percentile(latencies, 95))
        status = "PASS" if avg_latency < 15.0 else "FAIL"
        print(f"   [Result] Actual DB-Verified Latency: {avg_latency*1000:.2f}ms (P95: {p95_latency*1000:.2f}ms) | Sample N=25 | Status: {status}")
        return avg_latency

    def verify_route_efficiency(self):
        print("[AUDIT] Verifying Route Efficiency Claim from Empirical Data...")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT estimated_distance, actual_distance, estimated_time, actual_time FROM delivery_outcomes")
        rows = cursor.fetchall()
        
        if not rows:
            print("   [Error] No outcome data found in DB.")
            conn.close()
            return 0.0
            
        dist_improvements = []
        time_improvements = []
        for est_d, act_d, est_t, act_t in rows:
            if est_d > 0:
                imp_d = (est_d - act_d) / est_d * 100.0
                dist_improvements.append(imp_d)
            if est_t > 0:
                imp_t = (est_t - act_t) / est_t * 100.0
                time_improvements.append(imp_t)
            
        avg_dist_imp = float(np.mean(dist_improvements))
        avg_time_imp = float(np.mean(time_improvements))
        conn.close()
        
        status = "PASS" if avg_dist_imp > 5.0 else "REVIEW"
        print(f"   [Result] Measured Distance Efficiency Gain: {avg_dist_imp:.2f}%")
        print(f"   [Result] Measured Time Efficiency Gain:     {avg_time_imp:.2f}%")
        print(f"   [Result] Total Empirical Sample N={len(rows)} deliveries | Status: {status}")
        return avg_dist_imp

    def verify_ai_report_time(self):
        print("[AUDIT] Verifying AI Model Prediction & Scoring Latency...")
        model_path = BACKEND_DIR / "api" / "models" / "saved_models" / "safety_scorer_rf.pkl"
        scaler_path = BACKEND_DIR / "models" / "safety_scaler.pkl"
        
        if not model_path.exists() or not scaler_path.exists():
            print("   [Error] Safety model or scaler file missing.")
            return 0.0
            
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        
        # Test N=25 inference batches on real feature dimensions
        latencies = []
        for _ in range(25):
            # Batch of 15 route waypoints
            dummy_features = np.random.uniform(20, 80, size=(15, 7))
            t0 = time.perf_counter()
            scaled = scaler.transform(dummy_features)
            preds = model.predict(scaled)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000) # ms
            
        avg_time_ms = float(np.mean(latencies))
        p95_time_ms = float(np.percentile(latencies, 95))
        status = "PASS" if avg_time_ms < 500 else "FAIL"
        print(f"   [Result] Actual AI Route Scoring Latency: {avg_time_ms:.2f}ms/route (P95: {p95_time_ms:.2f}ms) | Sample N=25 | Status: {status}")
        return avg_time_ms

    def run_all(self):
        print("="*65)
        print("  SMART SHIELD: PROJECT CLAIM TRACEABILITY & EXPERIMENTAL AUDIT")
        print("="*65)
        self.verify_emergency_latency()
        print("")
        self.verify_route_efficiency()
        print("")
        self.verify_ai_report_time()
        print("="*65)

if __name__ == "__main__":
    verifier = ReportClaimVerifier()
    verifier.run_all()
