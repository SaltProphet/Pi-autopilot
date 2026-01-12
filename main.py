#!/usr/bin/env python3

import os
import json
from datetime import datetime

from agents.reddit_ingest import ingest_reddit_posts
from agents.problem_agent import extract_problem
from agents.spec_agent import generate_spec
from agents.content_agent import generate_content
from agents.verifier_agent import verify_content
from agents.gumroad_agent import create_listing, upload_to_gumroad
from services.storage import Storage
from services.cost_governor import CostGovernor, CostLimitExceeded
from services.llm_client import LLMClient
from config import settings


def save_artifact(post_id: str, stage: str, data: dict) -> str:
    artifact_dir = os.path.join(settings.artifacts_path, post_id)
    os.makedirs(artifact_dir, exist_ok=True)
    
    filename = f"{stage}_{int(datetime.now().timestamp())}.json"
    filepath = os.path.join(artifact_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath


def save_content_artifact(post_id: str, content: str) -> str:
    artifact_dir = os.path.join(settings.artifacts_path, post_id)
    os.makedirs(artifact_dir, exist_ok=True)
    
    filename = f"content_{int(datetime.now().timestamp())}.md"
    filepath = os.path.join(artifact_dir, filename)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    return filepath


def run_pipeline():
    if settings.kill_switch:
        print("KILL SWITCH ACTIVE - Pipeline execution aborted")
        return
    
    cost_governor = CostGovernor()
    llm_client = LLMClient(cost_governor)
    storage = Storage()
    
    try:
        print("=== REDDIT INGESTION ===")
        ingest_result = ingest_reddit_posts()
        print(f"Saved {ingest_result['total_saved']} new posts")
        
        print("\n=== PROCESSING POSTS ===")
        unprocessed_posts = storage.get_unprocessed_posts()
        print(f"Found {len(unprocessed_posts)} unprocessed posts")
        
        for post in unprocessed_posts:
            post_id = post['id']
            print(f"\n--- Post: {post_id} ---")
            print(f"Title: {post['title'][:60]}...")
            
            try:
                print("Stage: PROBLEM_EXTRACTION")
                problem_data = extract_problem(post, llm_client)
                problem_path = save_artifact(post_id, "problem", problem_data)
                
                if problem_data.get("discard", True):
                    print("DISCARD: Problem not monetizable")
                    storage.log_pipeline_run(post_id, "problem_extraction", "discarded", problem_path)
                    continue
                
                storage.log_pipeline_run(post_id, "problem_extraction", "completed", problem_path)
                print(f"Problem: {problem_data['problem_summary'][:60]}...")
                
                print("Stage: SPEC_GENERATION")
                spec_data = generate_spec(problem_data, llm_client)
                spec_path = save_artifact(post_id, "spec", spec_data)
                
                if not spec_data.get("build", False):
                    print("REJECT: Spec build=false")
                    storage.log_pipeline_run(post_id, "spec_generation", "rejected", spec_path)
                    continue
                
                if spec_data.get("confidence", 0) < 70:
                    print("REJECT: Confidence too low")
                    storage.log_pipeline_run(post_id, "spec_generation", "rejected", spec_path)
                    continue
                
                if len(spec_data.get("deliverables", [])) < 3:
                    print("REJECT: Too few deliverables")
                    storage.log_pipeline_run(post_id, "spec_generation", "rejected", spec_path)
                    continue
                
                storage.log_pipeline_run(post_id, "spec_generation", "completed", spec_path)
                print(f"Spec: {spec_data['working_title']}")
                
                regeneration_count = 0
                content_verified = False
                content = None
                content_path = None
                
                while regeneration_count <= settings.max_regeneration_attempts and not content_verified:
                    print(f"Stage: CONTENT_GENERATION (attempt {regeneration_count + 1})")
                    content = generate_content(spec_data, llm_client)
                    content_path = save_content_artifact(post_id, content)
                    storage.log_pipeline_run(post_id, "content_generation", "completed", content_path)
                    
                    print("Stage: VERIFICATION")
                    verdict = verify_content(content, llm_client)
                    verdict_path = save_artifact(post_id, f"verdict_attempt_{regeneration_count + 1}", verdict)
                    
                    if verdict.get("pass", False):
                        print("PASS: Content verified")
                        storage.log_pipeline_run(post_id, "verification", "passed", verdict_path)
                        content_verified = True
                    else:
                        print(f"FAIL: {', '.join(verdict.get('reasons', []))}")
                        storage.log_pipeline_run(post_id, "verification", "failed", verdict_path)
                        regeneration_count += 1
                
                if not content_verified:
                    print("HARD DISCARD: Max regeneration attempts reached")
                    storage.log_pipeline_run(post_id, "pipeline", "discarded_verification_failed", None, "Max regeneration attempts")
                    continue
                
                print("Stage: GUMROAD_LISTING")
                listing_text = create_listing(spec_data, content, llm_client)
                listing_path = save_content_artifact(post_id, listing_text)
                storage.log_pipeline_run(post_id, "gumroad_listing", "completed", listing_path)
                
                print("Stage: GUMROAD_UPLOAD")
                upload_result = upload_to_gumroad(spec_data, listing_text, content_path)
                upload_path = save_artifact(post_id, "gumroad_upload", upload_result)
                
                if upload_result.get("success"):
                    print(f"SUCCESS: Product uploaded - {upload_result.get('product_url')}")
                    storage.log_pipeline_run(post_id, "gumroad_upload", "completed", upload_path)
                else:
                    print("FAIL: Gumroad upload failed")
                    storage.log_pipeline_run(post_id, "gumroad_upload", "failed", upload_path, "Upload failed")
            
            except CostLimitExceeded as e:
                print(f"COST LIMIT EXCEEDED: {str(e)}")
                storage.log_pipeline_run(post_id, "pipeline", "cost_limit_exceeded", None, str(e))
                break
            
            except Exception as e:
                print(f"ERROR: {str(e)}")
                storage.log_pipeline_run(post_id, "pipeline", "error", None, str(e))
    
    except CostLimitExceeded as e:
        print(f"\nPIPELINE ABORTED: {str(e)}")
    
    finally:
        print("\n=== RUN STATISTICS ===")
        stats = cost_governor.get_run_stats()
        print(f"Tokens sent: {stats['tokens_sent']}")
        print(f"Tokens received: {stats['tokens_received']}")
        print(f"Cost: ${stats['cost_usd']:.4f}")
        print(f"Lifetime cost: ${cost_governor.get_lifetime_cost():.4f}")
        if stats['aborted']:
            print(f"ABORTED: {stats['abort_reason']}")
        
        print("\n=== PIPELINE COMPLETE ===")


if __name__ == "__main__":
    run_pipeline()
