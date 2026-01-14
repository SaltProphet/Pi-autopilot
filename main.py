#!/usr/bin/env python3

import os
import json
from datetime import datetime

from agents.ingest_factory import IngestFactory
from agents.problem_agent import extract_problem
from agents.spec_agent import generate_spec
from agents.content_agent import generate_content
from agents.verifier_agent import verify_content
from agents.gumroad_agent import create_listing, upload_to_gumroad
from services.storage import Storage
from services.cost_governor import CostGovernor, CostLimitExceeded
from services.llm_client import LLMClient
from services.error_handler import ErrorHandler
from services.audit_logger import AuditLogger
from services.backup_manager import BackupManager
from services.sales_feedback import SalesFeedback
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
    
    if settings.dry_run:
        print("=" * 60)
        print("DRY RUN MODE ENABLED - No real Gumroad uploads will be made")
        print("=" * 60)
        print()
    
    cost_governor = CostGovernor()
    llm_client = LLMClient(cost_governor)
    storage = Storage()
    error_handler = ErrorHandler()
    audit_logger = AuditLogger(settings.database_path)
    backup_manager = BackupManager(settings.database_path)
    sales_feedback = SalesFeedback(storage)
    
    # Perform daily backup at pipeline start
    print("=== BACKUP & MAINTENANCE ===")
    backup_path = backup_manager.backup_database()
    print(f"Database backed up to: {backup_path}")
    backup_manager.cleanup_old_backups()
    
    run_id = f"run_{int(datetime.now().timestamp())}"
    
    try:
        # Ingest sales data at pipeline start
        print("=== SALES DATA INGESTION ===")
        try:
            sales_ingest_result = sales_feedback.ingest_sales_data()
            if sales_ingest_result["success"]:
                print(f"Ingested sales data for {sales_ingest_result['products_ingested']} products")
                audit_logger.log(
                    action='sales_data_ingested',
                    post_id=None,
                    run_id=run_id,
                    details={
                        'success': True,
                        'products_ingested': sales_ingest_result.get('products_ingested', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                )
            else:
                print("No sales data available or ingestion failed")
                audit_logger.log(
                    action='sales_data_ingested',
                    post_id=None,
                    run_id=run_id,
                    details={
                        'success': False,
                        'message': sales_ingest_result.get('message', 'No sales data available or ingestion failed'),
                        'timestamp': datetime.now().isoformat()
                    }
                )
        except Exception as e:
            print(f"Sales data ingestion failed: {e}")
            audit_logger.log(
                action='sales_data_ingested',
                post_id=None,
                run_id=run_id,
                details={
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
            )
        
        # Check if publishing should be suppressed
        try:
            suppression_check = sales_feedback.should_suppress_publishing()
            if suppression_check["suppress"]:
                print(f"\n=== PUBLISHING SUPPRESSED ===")
                print(f"Reason: {suppression_check['reason']}")
                audit_logger.log(
                    action='publishing_suppressed',
                    post_id=None,
                    run_id=run_id,
                    details={'suppression_reason': suppression_check['reason']}
                )
                return
        except Exception as e:
            # Fail safely: on error, allow publishing to continue
            print(f"Warning: Suppression check failed: {e}. Allowing publishing to continue.")
            audit_logger.log(
                action='error_occurred',
                post_id=None,
                run_id=run_id,
                details={'stage': 'suppression_check', 'error': str(e), 'failsafe': 'allowing_publishing'},
                error_occurred=True
            )
        
        # Generate sales feedback summary for agent conditioning
        try:
            feedback_summary = sales_feedback.generate_feedback_summary()
            top_categories = sales_feedback.get_top_performing_categories()
            zero_sale_categories = sales_feedback.get_zero_sale_categories()
            
            # Build feedback text with clarity on data availability
            feedback_lines = [
                f"Recent Performance (last {settings.sales_lookback_days} days):",
                f"- Products published: {feedback_summary['products_published']}",
                f"- Products sold: {feedback_summary['products_sold']}",
            ]
            
            # Add zero-sale info with clarity
            if feedback_summary.get('products_without_data', 0) > 0:
                feedback_lines.append(f"- Products without sales data yet: {feedback_summary['products_without_data']}")
            if feedback_summary['zero_sale_products'] > 0:
                feedback_lines.append(f"- Products with tracked zero sales: {feedback_summary['zero_sale_products']}")
            
            feedback_lines.extend([
                f"- Total revenue: ${feedback_summary['total_revenue_cents'] / 100:.2f}",
                f"- Average price: ${feedback_summary['avg_price_cents'] / 100:.2f}",
                f"- Refund rate: {feedback_summary['refund_rate']:.1%}",
                "",
                f"Top-performing categories: {', '.join(top_categories) if top_categories else 'None yet'}",
                f"Zero-sale categories: {', '.join(zero_sale_categories) if zero_sale_categories else 'None'}",
            ])
            
            sales_feedback_text = "\n".join(feedback_lines)
            print(sales_feedback_text)
        except Exception as e:
            # Fail safely: on error, provide empty sales feedback
            print(f"Warning: Feedback summary generation failed: {e}. Continuing without sales conditioning.")
            sales_feedback_text = ""
            audit_logger.log(
                action='error_occurred',
                post_id=None,
                run_id=run_id,
                details={'stage': 'feedback_generation', 'error': str(e), 'failsafe': 'empty_feedback'},
                error_occurred=True
            )
        
        print("=== DATA INGESTION ===")
        
        # Get all enabled ingest agents from factory
        ingest_factory = IngestFactory(settings)
        ingest_agents = ingest_factory.get_enabled_agents()
        
        if not ingest_agents:
            print("ERROR: No data sources enabled or configured properly!")
            print("Check DATA_SOURCES and related credentials in .env file")
            return
        
        print(f"Enabled data sources: {', '.join(agent.source_name for agent in ingest_agents)}")
        
        # Fetch posts from all enabled sources
        all_posts = []
        for agent in ingest_agents:
            try:
                print(f"Fetching from {agent.source_name}...")
                posts = agent.fetch_posts()
                print(f"  → Fetched {len(posts)} posts from {agent.source_name}")
                
                # Save posts to storage
                saved_count = 0
                post_ids = []
                for post in posts:
                    if storage.save_post(post):
                        saved_count += 1
                        post_ids.append(post['id'])
                
                print(f"  → Saved {saved_count} new posts")
                
                # Log ingestion in audit trail
                for post_id in post_ids:
                    audit_logger.log(
                        action='post_ingested',
                        post_id=post_id,
                        run_id=run_id,
                        details={'source': agent.source_name}
                    )
                
            except Exception as e:
                print(f"ERROR: Failed to fetch from {agent.source_name}: {e}")
                error_artifact = error_handler.log_error(
                    post_id=None,
                    stage='data_ingestion',
                    exception=e,
                    context={'source': agent.source_name}
                )
                audit_logger.log(
                    action='error_occurred',
                    post_id=None,
                    run_id=run_id,
                    details={'stage': 'data_ingestion', 'source': agent.source_name, 'error': str(e)},
                    error_occurred=True
                )
                # Continue with other sources
                continue
        
        print("\n=== PROCESSING POSTS ===")
        unprocessed_posts = storage.get_unprocessed_posts()
        print(f"Found {len(unprocessed_posts)} unprocessed posts")
        
        for post in unprocessed_posts:
            post_id = post['id']
            print(f"\n--- Post: {post_id} ---")
            print(f"Title: {post['title'][:60]}...")
            
            try:
                print("Stage: PROBLEM_EXTRACTION")
                problem_data = extract_problem(post, llm_client, sales_feedback_text)
                problem_path = save_artifact(post_id, "problem", problem_data)
                
                if problem_data.get("discard", True):
                    print("DISCARD: Problem not monetizable")
                    storage.log_pipeline_run(post_id, "problem_extraction", "discarded", problem_path)
                    audit_logger.log(
                        action='post_discarded',
                        post_id=post_id,
                        run_id=run_id,
                        details={'stage': 'problem_extraction', 'reason': 'not_monetizable'}
                    )
                    continue
                
                storage.log_pipeline_run(post_id, "problem_extraction", "completed", problem_path)
                audit_logger.log(
                    action='problem_extracted',
                    post_id=post_id,
                    run_id=run_id,
                    details={
                        'summary': problem_data.get('problem_summary', '')[:100],
                        'urgency_score': problem_data.get('urgency_score', 0)
                    }
                )
                print(f"Problem: {problem_data['problem_summary'][:60]}...")
                
                print("Stage: SPEC_GENERATION")
                spec_data = generate_spec(problem_data, llm_client, sales_feedback_text)
                spec_path = save_artifact(post_id, "spec", spec_data)
                
                if not spec_data.get("build", False):
                    print("REJECT: Spec build=false")
                    storage.log_pipeline_run(post_id, "spec_generation", "rejected", spec_path)
                    audit_logger.log(
                        action='spec_generated',
                        post_id=post_id,
                        run_id=run_id,
                        details={'rejected': True, 'reason': 'build_false'}
                    )
                    continue
                
                if spec_data.get("confidence", 0) < 70:
                    print("REJECT: Confidence too low")
                    storage.log_pipeline_run(post_id, "spec_generation", "rejected", spec_path)
                    audit_logger.log(
                        action='spec_generated',
                        post_id=post_id,
                        run_id=run_id,
                        details={'rejected': True, 'reason': 'low_confidence', 'confidence': spec_data.get("confidence", 0)}
                    )
                    continue
                
                if len(spec_data.get("deliverables", [])) < 3:
                    print("REJECT: Too few deliverables")
                    storage.log_pipeline_run(post_id, "spec_generation", "rejected", spec_path)
                    audit_logger.log(
                        action='spec_generated',
                        post_id=post_id,
                        run_id=run_id,
                        details={'rejected': True, 'reason': 'insufficient_deliverables', 'count': len(spec_data.get("deliverables", []))}
                    )
                    continue
                
                storage.log_pipeline_run(post_id, "spec_generation", "completed", spec_path)
                audit_logger.log(
                    action='spec_generated',
                    post_id=post_id,
                    run_id=run_id,
                    details={
                        'title': spec_data.get('working_title', '')[:80],
                        'price': spec_data.get('price_recommendation', 0),
                        'confidence': spec_data.get('confidence', 0)
                    }
                )
                print(f"Spec: {spec_data['working_title']}")
                
                regeneration_count = 0
                content_verified = False
                content = None
                content_path = None
                
                while regeneration_count <= settings.max_regeneration_attempts and not content_verified:
                    print(f"Stage: CONTENT_GENERATION (attempt {regeneration_count + 1})")
                    try:
                        content = generate_content(spec_data, llm_client)
                        content_path = save_content_artifact(post_id, content)
                        storage.log_pipeline_run(post_id, "content_generation", "completed", content_path)
                        
                        print("Stage: VERIFICATION")
                        verdict = verify_content(content, llm_client)
                        verdict_path = save_artifact(post_id, f"verdict_attempt_{regeneration_count + 1}", verdict)
                        
                        if verdict.get("pass", False):
                            print("PASS: Content verified")
                            storage.log_pipeline_run(post_id, "verification", "passed", verdict_path)
                            audit_logger.log(
                                action='content_verified',
                                post_id=post_id,
                                run_id=run_id,
                                details={'attempt': regeneration_count + 1}
                            )
                            content_verified = True
                        else:
                            print(f"FAIL: {', '.join(verdict.get('reasons', []))}")
                            storage.log_pipeline_run(post_id, "verification", "failed", verdict_path)
                            audit_logger.log(
                                action='content_rejected',
                                post_id=post_id,
                                run_id=run_id,
                                details={'attempt': regeneration_count + 1, 'reasons': verdict.get('reasons', [])}
                            )
                            regeneration_count += 1
                    except Exception as e:
                        error_artifact = error_handler.log_error(
                            post_id=post_id,
                            stage='content_generation',
                            exception=e,
                            context={'attempt': regeneration_count + 1}
                        )
                        error_categorization = error_handler.categorize_error(e)
                        audit_logger.log(
                            action='error_occurred',
                            post_id=post_id,
                            run_id=run_id,
                            details={'stage': 'content_generation', 'error_type': type(e).__name__, 'transient': error_categorization['is_transient']},
                            error_occurred=True
                        )
                        if error_categorization['is_transient']:
                            regeneration_count += 1
                            if regeneration_count > settings.max_regeneration_attempts:
                                raise
                        else:
                            raise
                
                if not content_verified:
                    print("HARD DISCARD: Max regeneration attempts reached")
                    storage.log_pipeline_run(post_id, "pipeline", "discarded_verification_failed", None, "Max regeneration attempts")
                    audit_logger.log(
                        action='post_discarded',
                        post_id=post_id,
                        run_id=run_id,
                        details={'stage': 'verification', 'reason': 'max_attempts_exceeded'}
                    )
                    continue
                
                print("Stage: GUMROAD_LISTING")
                listing_text = create_listing(spec_data, content, llm_client)
                listing_path = save_content_artifact(post_id, listing_text)
                storage.log_pipeline_run(post_id, "gumroad_listing", "completed", listing_path)
                audit_logger.log(
                    action='gumroad_listed',
                    post_id=post_id,
                    run_id=run_id,
                    details={'title': spec_data.get('working_title', '')[:80]}
                )
                
                print("Stage: GUMROAD_UPLOAD")
                upload_result = upload_to_gumroad(spec_data, listing_text, content_path)
                upload_path = save_artifact(post_id, "gumroad_upload", upload_result)
                
                if upload_result.get("success"):
                    dry_run_prefix = "[DRY RUN] " if settings.dry_run else ""
                    print(f"SUCCESS: {dry_run_prefix}Product uploaded - {upload_result.get('product_url')}")
                    storage.log_pipeline_run(post_id, "gumroad_upload", "completed", upload_path)
                    
                    upload_details = {
                        'product_url': upload_result.get('product_url'), 
                        'price': spec_data.get('price_recommendation'),
                        'dry_run': settings.dry_run
                    }
                    
                    audit_logger.log(
                        action='gumroad_uploaded',
                        post_id=post_id,
                        run_id=run_id,
                        details=upload_details
                    )
                else:
                    print("FAIL: Gumroad upload failed")
                    storage.log_pipeline_run(post_id, "gumroad_upload", "failed", upload_path, "Upload failed")
                    audit_logger.log(
                        action='error_occurred',
                        post_id=post_id,
                        run_id=run_id,
                        details={'stage': 'gumroad_upload', 'reason': upload_result.get('error', 'unknown')},
                        error_occurred=True
                    )
            
            except CostLimitExceeded as e:
                print(f"COST LIMIT EXCEEDED: {str(e)}")
                storage.log_pipeline_run(post_id, "pipeline", "cost_limit_exceeded", None, str(e))
                audit_logger.log(
                    action='cost_limit_exceeded',
                    post_id=post_id,
                    run_id=run_id,
                    details={'reason': str(e)},
                    cost_limit_exceeded=True
                )
                break
            
            except (KeyboardInterrupt, SystemExit):
                # Allow user interrupts and system exits to propagate
                raise
            
            except Exception as e:
                print(f"ERROR: {str(e)}")
                storage.log_pipeline_run(post_id, "pipeline", "error", None, str(e))
                
                error_artifact = error_handler.log_error(
                    post_id=post_id,
                    stage='pipeline',
                    exception=e,
                    context={'post_title': post.get('title', '')}
                )
                error_categorization = error_handler.categorize_error(e)
                audit_logger.log(
                    action='error_occurred',
                    post_id=post_id,
                    run_id=run_id,
                    details={'stage': 'pipeline', 'error_type': type(e).__name__, 'transient': error_categorization['is_transient']},
                    error_occurred=True
                )
                # Log and continue to next post on non-transient errors
                continue
    
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
