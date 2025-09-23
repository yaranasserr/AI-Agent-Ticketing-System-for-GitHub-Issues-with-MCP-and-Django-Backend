# issues/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import Ticket, Issue, ProcessingLog
from .services.adk_integration import ADKGitHubService
import logging
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_github_url_task(self, ticket_id):
    """
    Background task to process GitHub URL using ADK service with session management
    
    Args:
        ticket_id: ID of the ticket to process
    """
    start_time = time.time()
    adk_service = None
    
    try:
        # Get ticket
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Create ADK service with session tied to this ticket
        session_id = f"ticket_{ticket_id}_{ticket.created_at.strftime('%Y%m%d_%H%M%S')}"
        adk_service = ADKGitHubService(session_id=session_id)
        
        # Log start with session info
        ProcessingLog.objects.create(
            ticket=ticket,
            level='info',
            message=f'Started processing ticket #{ticket_id} for URL: {ticket.github_url} (Session: {session_id})'
        )
        
        # Update status
        ticket.status = 'processing'
        ticket.save()
        
        # Test connection first
        connection_test = adk_service.test_connection()
        if not connection_test['success']:
            raise Exception(f"ADK service connection failed: {connection_test['message']}")
        
        ProcessingLog.objects.create(
            ticket=ticket,
            level='info',
            message=f'ADK service connection established successfully. Session exchanges: {connection_test["session_info"]["total_exchanges"]}'
        )
        
        # Extract issues with session context
        result = adk_service.extract_issues_from_url(ticket.github_url, ticket_id=ticket_id)
        
        if not result['success']:
            raise Exception(result['error'])
        
        issues_data = result['data']
        
        ProcessingLog.objects.create(
            ticket=ticket,
            level='info',
            message=f'Successfully extracted {len(issues_data)} issues from GitHub. Session: {result["session_id"]}'
        )
        
        # If we got a truncated response, try to continue the conversation
        if result.get('response_preview', '').endswith('...'):
            ProcessingLog.objects.create(
                ticket=ticket,
                level='info',
                message='Response was truncated, attempting to get complete data...'
            )
            
            # Ask for complete data
            continue_result = adk_service.continue_conversation(
                "Please provide the complete list of all issues if the previous response was truncated."
            )
            
            if continue_result['success']:
                # Try to parse additional issues from the continued conversation
                additional_issues = adk_service._parse_agent_response(continue_result['response'])
                if additional_issues and len(additional_issues) > len(issues_data):
                    issues_data = additional_issues
                    ProcessingLog.objects.create(
                        ticket=ticket,
                        level='info',
                        message=f'Retrieved complete data: {len(issues_data)} issues total'
                    )
        
        # Save issues to database
        created_issues = []
        skipped_issues = []
        
        for issue_data in issues_data:
            try:
                issue, created = Issue.objects.get_or_create(
                    ticket=ticket,
                    repo=issue_data['repo'],
                    owner=issue_data['owner'],
                    issue_number=issue_data['issue_number'],
                    defaults={
                        'title': issue_data['title'],
                        'body': issue_data['body'],
                        'labels': issue_data['labels'],
                        'issue_type': issue_data['type'],
                        'github_url': issue_data['github_url']
                    }
                )
                
                if created:
                    created_issues.append(issue)
                    logger.info(f"Created issue: {issue}")
                else:
                    skipped_issues.append(issue)
                    logger.info(f"Issue already exists: {issue}")
                    
            except Exception as e:
                ProcessingLog.objects.create(
                    ticket=ticket,
                    level='warning',
                    message=f'Failed to save issue #{issue_data.get("issue_number", "unknown")}: {str(e)}'
                )
                continue
        
        # Log summary of what was processed
        if skipped_issues:
            ProcessingLog.objects.create(
                ticket=ticket,
                level='info',
                message=f'Skipped {len(skipped_issues)} duplicate issues that already existed'
            )
        
        # Update ticket with results
        processing_time = time.time() - start_time
        ticket.total_issues_found = len(created_issues)
        ticket.processing_time_seconds = processing_time
        ticket.status = 'completed'
        ticket.save()
        
        # Final log with session summary
        session_summary = adk_service.get_session_summary()
        ProcessingLog.objects.create(
            ticket=ticket,
            level='info',
            message=f'Processing completed successfully. Created {len(created_issues)} new issues in {processing_time:.2f} seconds. Session had {session_summary["total_exchanges"]} exchanges.'
        )
        
        # Optional: Clear session after successful completion to free memory
        # adk_service.clear_session()
        
        return {
            'success': True,
            'ticket_id': ticket_id,
            'issues_created': len(created_issues),
            'issues_skipped': len(skipped_issues),
            'processing_time': processing_time,
            'session_exchanges': session_summary['total_exchanges']
        }
        
    except Ticket.DoesNotExist:
        error_msg = f'Ticket {ticket_id} not found'
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
        
    except Exception as e:
        error_msg = f'Failed to process ticket {ticket_id}: {str(e)}'
        logger.error(error_msg)
        
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
            ticket.status = 'failed'
            ticket.error_message = str(e)
            processing_time = time.time() - start_time
            ticket.processing_time_seconds = processing_time
            ticket.save()
            
            ProcessingLog.objects.create(
                ticket=ticket,
                level='error',
                message=f'Processing failed after {processing_time:.2f} seconds: {str(e)}'
            )
            
            # Get session info if available
            if adk_service:
                session_info = adk_service.get_session_summary()
                ProcessingLog.objects.create(
                    ticket=ticket,
                    level='info',
                    message=f'Session had {session_info["total_exchanges"]} exchanges before failure'
                )
            
        except Exception as save_error:
            logger.error(f"Failed to save error state for ticket {ticket_id}: {save_error}")
        
        return {'success': False, 'error': error_msg}

@shared_task
def continue_ticket_conversation(ticket_id, message):
    """
    Task to continue a conversation for a specific ticket
    
    Args:
        ticket_id: ID of the ticket
        message: Follow-up message or question
    """
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Recreate the session for this ticket
        session_id = f"ticket_{ticket_id}_{ticket.created_at.strftime('%Y%m%d_%H%M%S')}"
        adk_service = ADKGitHubService(session_id=session_id)
        
        # Continue the conversation
        result = adk_service.continue_conversation(message)
        
        # Log the interaction
        ProcessingLog.objects.create(
            ticket=ticket,
            level='info',
            message=f'Continued conversation: User: "{message}" | Response: "{result.get("response", "No response")[:200]}..."'
        )
        
        return {
            'success': result['success'],
            'response': result.get('response', ''),
            'session_id': result['session_id']
        }
        
    except Ticket.DoesNotExist:
        return {'success': False, 'error': f'Ticket {ticket_id} not found'}
    except Exception as e:
        logger.error(f"Failed to continue conversation for ticket {ticket_id}: {str(e)}")
        return {'success': False, 'error': str(e)}

@shared_task
def cleanup_old_sessions():
    """
    Periodic task to cleanup old ADK sessions from cache
    """
    try:
        from django.core.cache import cache
        from datetime import timedelta
        
        # This is a simplified cleanup - in practice, you'd need to track session keys
        # For now, just log that cleanup should happen
        logger.info("Session cleanup task executed - implement specific cleanup logic based on your cache backend")
        
        return "Session cleanup completed"
        
    except Exception as e:
        logger.error(f"Error during session cleanup: {str(e)}")
        return f"Session cleanup failed: {str(e)}"

@shared_task
def cleanup_old_tickets():
    """
    Periodic task to cleanup old tickets (optional)
    Run this as a periodic task if needed
    """
    from datetime import timedelta
    from django.utils import timezone
    
    # Delete tickets older than 30 days
    cutoff_date = timezone.now() - timedelta(days=30)
    old_tickets = Ticket.objects.filter(created_at__lt=cutoff_date)
    
    deleted_count = old_tickets.count()
    old_tickets.delete()
    
    logger.info(f'Cleaned up {deleted_count} old tickets')
    return f'Cleaned up {deleted_count} old tickets'